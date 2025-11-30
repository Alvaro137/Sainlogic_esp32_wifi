#include <Arduino.h>
#include <ESP32TimerInterrupt.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <esp_task_wdt.h>

#include "ring_buffer.h"
#include "ppm_tracker.h"
#include "data_decode.h"
#include "secrets.h" 

// --- CONFIGURACIÓN ---
#define PIN_IN1 5
#define PIN_IN2 4
#define LED 2

// Configuración de Muestreo (40us para precisión en 433MHz)
#define SAMPLE_PERIOD_US 40
#define MIN_SAMPLES 4
#define MAX_SAMPLES 16

// --- TIEMPOS DE PROTECCIÓN ---
#define WDT_TIMEOUT 120             // 2 min: Watchdog de Hardware (Bloqueo CPU)
#define UPLOAD_TIMEOUT 900000       // 15 min: Watchdog "End-to-End" (Si no sube datos -> Reinicio)
#define RADIO_WARNING_TIME 300000   // 5 min: Solo para enviar Log de aviso ("Radio Silence")
#define WIFI_CHECK_INTERVAL 300000   // 5 min: Intervalo para chequear y reconectar WiFi
#define WIFI_TIMEOUT 4000         // 4 seg: Timeout de conexión WiFi

#define NSKIP 5                     // Enviar 1 de cada NSKIP paquetes

// Objetos
ESP32Timer ITimer(0);
BinaryPpmTracker tracker(MIN_SAMPLES, MAX_SAMPLES);

// Variables
unsigned long last_radio_activity = 0; 
unsigned long boot_time = 0;       
unsigned long last_wifi_check = 0;  
unsigned long last_successful_upload = 0; // La variable más importante
bool warning_sent = false;          

#define LOG_ERROR(fmt, ...) Serial.printf("[ERROR] " fmt "\n", ##__VA_ARGS__)

// ================================================================
// GESTIÓN WIFI (Asíncrona)
// ================================================================
void setupWiFi() {
    WiFi.disconnect(true); 
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.println("WiFi: Conexión iniciada en segundo plano.");
}

void checkWiFi() {
    if (WiFi.status() != WL_CONNECTED) {
        if (millis() - last_wifi_check > WIFI_CHECK_INTERVAL) {
            last_wifi_check = millis();
            Serial.printf("WiFi caído (status %d). Reintentando...\n", WiFi.status());
            WiFi.disconnect();
            WiFi.reconnect();
        }
    }
}

// ================================================================
// ENVÍO DE LOGS (Diagnóstico)
// ================================================================
void sendErrorLog(String mensaje) {
    if (WiFi.status() != WL_CONNECTED) return;

    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;

    if (http.begin(client, String(SERVER_URL) + "/api/log-error")) {
        http.addHeader("Content-Type", "text/plain");
        http.addHeader("Authorization", String("Bearer ") + String(API_TOKEN_ESP));
        http.POST(mensaje);
        http.end();
    }
}

// ================================================================
// ENVÍO DE DATOS
// ================================================================
void sendRawData(const uint8_t *msg, size_t len) {
    if (WiFi.status() != WL_CONNECTED) return;

    WiFiClientSecure client;
    client.setInsecure();
    client.setTimeout(WIFI_TIMEOUT); 
    
    HTTPClient http;
    http.setConnectTimeout(WIFI_TIMEOUT);

    if (!http.begin(client, String(SERVER_URL) + "/api/raw-data")) {
        return;
    }

    http.addHeader("Content-Type", "application/octet-stream");
    http.addHeader("Authorization", String("Bearer ") + String(API_TOKEN_ESP));

    // Telemetría para el backend
    http.addHeader("X-ESP-RSSI", String(WiFi.RSSI()));
    http.addHeader("X-ESP-Uptime", String((millis() - boot_time) / 1000));
    http.addHeader("X-ESP-Heap", String(ESP.getFreeHeap()));

    int httpCode = http.POST((uint8_t*)msg, len);
    http.end();

    if (httpCode == 200) {
        last_successful_upload = millis(); 
        // Serial.println("Envío OK");
    } else {
        Serial.printf("Error HTTP: %d\n", httpCode);
    }
}

// ================================================================
// SETUP
// ================================================================
void setup() {
    Serial.begin(115200);
    boot_time = millis();
    last_radio_activity = millis();
    
    // Al arrancar, damos por hecho que acabamos de "tener éxito" para dar margen de 15 min
    last_successful_upload = millis(); 

    pinMode(PIN_IN1, INPUT);
    pinMode(PIN_IN2, INPUT);
    pinMode(LED, OUTPUT);
    set_sample_pin(PIN_IN2);

    // Watchdog Hardware (Protege contra bloqueos de CPU)
    esp_task_wdt_init(WDT_TIMEOUT, true);
    esp_task_wdt_add(NULL);

    setupWiFi();

    if (!ITimer.attachInterruptInterval(SAMPLE_PERIOD_US, sample_input)) {
        LOG_ERROR("Error Timer");
        while (true) delay(1000); 
    }
}

// ================================================================
// LOOP
// ================================================================
int count_for_nskip = 0;

void loop() {
    unsigned long now = millis();
    
    // 1. Watchdog Hardware (Acariciar al perro)
    esp_task_wdt_reset();

    // 2. Mantenimiento WiFi
    checkWiFi();

    // 3. WATCHDOG "END-TO-END" (La protección maestra)
    // Si en 15 minutos no hemos recibido un "200 OK" del servidor, reiniciamos.
    // Esto cubre: Fallo Radio, Fallo WiFi, Fallo Router, Fallo SSL, Fallo Servidor.
    if (now - last_successful_upload > UPLOAD_TIMEOUT) {
        LOG_ERROR("15 minutos sin éxito. Reiniciando sistema completo...");
        delay(500);
        ESP.restart();
    }

    // 4. Aviso Diagnóstico (Opcional, no reinicia)
    // Si hay WiFi pero no hay radio, avisa al log para que sepas qué pasa.
    if (now - last_radio_activity > RADIO_WARNING_TIME && !warning_sent) {
        sendErrorLog("ALERTA: 5 minutos sin señal de radio");
        warning_sent = true;
    }

    // 5. Procesamiento Radio
    size_t buffered_len = num_samples();

    if (buffered_len > 128 * 8) { 
        reset_sampler();
        return;
    }

    for (size_t i = 0; i < buffered_len; i++) {
        tracker.process_sample(get_next_sample());

        if (tracker.cur_rx_len() == MSG_BYTES * 8) { // 128 bits
            last_radio_activity = now; 
            warning_sent = false;

            digitalWrite(LED, HIGH);

            if (count_for_nskip == NSKIP) {
                sendRawData(tracker.get_msg(), MSG_BYTES); 
                count_for_nskip = 0;
            } else {
                count_for_nskip++;
            }
            
            digitalWrite(LED, LOW);
            
            reset_sampler();
            tracker.reset();
        }
    }
    
    delayMicroseconds(50); 
}