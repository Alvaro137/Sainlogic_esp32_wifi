#include <Arduino.h>
#include <ESP32TimerInterrupt.h>
#include <WiFiManager.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <esp_task_wdt.h>

#include "ring_buffer.h"
#include "ppm_tracker.h"
#include "data_decode.h"
#include "secrets.h" 

#define PIN_IN1 5
#define PIN_IN2 4
#define LED 2

#define SAMPLE_PERIOD_US 40
#define MIN_SAMPLES 4
#define MAX_SAMPLES 16
#define NSKIP 2 
#define WIFI_RECONNECT_INTERVAL 60000 
#define WDT_TIMEOUT 120 
#define MAX_HTTP_ERRORS 5

// --- TIEMPOS ---
#define RADIO_TIMEOUT 600000        // 10 min -> Reinicio
#define RADIO_WARNING_TIME 300000   // 5 min -> Enviar Alerta Web
#define FORCED_REBOOT_MS 86400000   // 24 h -> Mantenimiento

ESP32Timer ITimer(0);
BinaryPpmTracker tracker(MIN_SAMPLES, MAX_SAMPLES);

int count_for_nskip = 0;
unsigned long lastWifiAttempt = 0;
bool wifiConnected = false;

// Variables Diagnóstico
int buffer_overflow_count = 0; 
unsigned long boot_time = 0;
int consecutive_http_errors = 0;
unsigned long last_radio_activity = 0; 
bool warning_sent = false; // Para no spammear la alerta

#define LOG_ERROR(fmt, ...)   Serial.printf("[ERROR] " fmt "\n", ##__VA_ARGS__)

void connectWiFi() {
    WiFiManager wifiManager;
    wifiManager.setConnectTimeout(60);
    if (wifiManager.autoConnect(WIFI_SSID, WIFI_PASSWORD)) {
        wifiConnected = true;
    } else {
        wifiConnected = false;
        LOG_ERROR("Fallo WiFi. Reiniciando...");
        delay(2000);
        ESP.restart();
    }
}

// --- FUNCIÓN NUEVA: ENVIAR ALERTA ---
void sendAlert(String mensaje) {
    if (!wifiConnected) return;
    
    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;
    
    // Apuntamos al endpoint nuevo /api/log-error
    if (http.begin(client, String(SERVER_URL) + "/api/log-error")) {
        http.addHeader("Content-Type", "text/plain");
        http.addHeader("Authorization", String("Bearer ") + String(API_TOKEN_ESP));
        
        // Enviamos el mensaje de texto
        int code = http.POST(mensaje);
        Serial.printf("Alerta enviada: %s (Code: %d)\n", mensaje.c_str(), code);
        http.end();
    }
}

String sendRawData(const uint8_t *msg, size_t len) {
    if (!wifiConnected) return "WiFi not connected";

    WiFiClientSecure client;
    client.setInsecure(); 
    HTTPClient http;
    
    if (!http.begin(client, String(SERVER_URL) + "/api/raw-data")) {
        consecutive_http_errors++;
        return "Connect failed";
    }

    http.addHeader("Content-Type", "application/octet-stream");
    http.addHeader("Authorization", String("Bearer ") + String(API_TOKEN_ESP));

    String rssiVal = String(WiFi.RSSI());
    String uptimeVal = String((millis() - boot_time) / 1000);
    String errorVal = String(buffer_overflow_count);
    String heapVal = String(ESP.getFreeHeap());

    http.addHeader("X-ESP-RSSI", rssiVal);
    http.addHeader("X-ESP-Uptime", uptimeVal);
    http.addHeader("X-ESP-Errors", errorVal);
    http.addHeader("X-ESP-Heap", heapVal);

    int httpCode = http.POST((uint8_t*)msg, len);
    http.end();
    
    if (httpCode == 200) {
        buffer_overflow_count = 0;
        consecutive_http_errors = 0;
        return "OK";
    } else {
        consecutive_http_errors++;
        if (consecutive_http_errors >= MAX_HTTP_ERRORS) {
            LOG_ERROR("Demasiados fallos HTTP (%d). REINICIANDO...", consecutive_http_errors);
            delay(1000);
            ESP.restart();
        }
        return "Error";
    }
}

void setup() {
    Serial.begin(115200);
    boot_time = millis(); 
    last_radio_activity = millis(); 
    
    pinMode(PIN_IN1, INPUT);
    pinMode(PIN_IN2, INPUT);
    pinMode(LED, OUTPUT);
    set_sample_pin(PIN_IN2);

    esp_task_wdt_init(WDT_TIMEOUT, true);
    esp_task_wdt_add(NULL);

    connectWiFi();

    if (!ITimer.attachInterruptInterval(SAMPLE_PERIOD_US, sample_input)) {
        LOG_ERROR("Error Timer");
        while (true) delay(1000); 
    }
}

void loop() {
    unsigned long now = millis();
    esp_task_wdt_reset();

    // --- PROTECCIÓN 1: REINICIO 24H ---
    if (now - boot_time > FORCED_REBOOT_MS) {
        ESP.restart();
    }

    // --- PROTECCIÓN 2: RADIO ---
    unsigned long silence_duration = now - last_radio_activity;

    // A) Aviso a los 5 minutos (Si hay WiFi, te chivas)
    if (silence_duration > RADIO_WARNING_TIME && !warning_sent) {
        sendAlert("RADIO_SILENCE_5_MIN_WARNING");
        warning_sent = true; // Marcamos para no enviarlo en bucle
    }

    // B) Muerte a los 10 minutos (Reinicio)
    if (silence_duration > RADIO_TIMEOUT) {
        LOG_ERROR("10 min sin radio. Reiniciando...");
        delay(1000);
        ESP.restart();
    }

    if (!wifiConnected && (now - lastWifiAttempt >= WIFI_RECONNECT_INTERVAL)) {
        lastWifiAttempt = now;
        connectWiFi();
    }

    if (!wifiConnected) { delay(100); return; }

    size_t buffered_len = num_samples();

    if (buffered_len > SAMPLE_LEN / 2) {
        buffer_overflow_count++; 
        reset_sampler();
        return;
    }

    for (size_t i = 0; i < buffered_len; i++) {
        tracker.process_sample(get_next_sample());

        if (tracker.cur_rx_len() == MSG_LEN) {
            
            // ¡SEÑAL VIVA!
            last_radio_activity = now; 
            warning_sent = false; // Reseteamos la alerta para la próxima vez

            if (count_for_nskip == NSKIP) {
                sendRawData(tracker.get_msg(), MSG_LEN);
                count_for_nskip = 0;
            } else {
                count_for_nskip++;
            }
            reset_sampler();
            tracker.reset();
        }
    }
    delayMicroseconds(SAMPLE_PERIOD_US * 10);
}