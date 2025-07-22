#include <Arduino.h>
#include <ESP32TimerInterrupt.h>
#include <WiFiManager.h>
#include "ThingSpeak.h"
#include <esp_task_wdt.h>  // Watchdog

#include "ring_buffer.h"
#include "ppm_tracker.h"
#include "data_decode.h"
#include "secrets.h"

// Disable default Arduino WDT. Just in case.
extern "C" {
  void disableCore0WDT();
  void disableCore1WDT();
}



// Define DEBUG_SAMPLER to log data packets to serial
// Instead of normal operation

// D1 GPIO5
// Connects to pin that goes low during receive
#define PIN_IN1 5
// D2 GPIO4
// Connects to pin that outputs received data
#define PIN_IN2 4
#define LED 2

// Target time between samples
// Must be long enough that MCU can keep up with
// Expected samples/symbol = is SLEEP_US/46.3uS
#define SAMPLE_PERIOD_US 40
// Parameters for synching data
#define MIN_SAMPLES      4
#define MAX_SAMPLES     16
// Number of samples that are skipped
#define nskip            0

// Configuración de ThingSpeak (from secrets.h)
unsigned long myChannelNumber = THINGSPEAK_CHANNEL;
const char *myWriteAPIKey   = THINGSPEAK_WRITE_API_KEY;

// WiFi reconection interval (ms)
const unsigned long WIFI_RECONNECT_INTERVAL = 60000; // 1 minuto

// Watchdog timeout in seconds
#define WDT_TIMEOUT_S 600 //10 min

// Variables de estado global
WiFiClient client;
ESP32Timer ITimer(0);
BinaryPpmTracker tracker(MIN_SAMPLES, MAX_SAMPLES);
int count_for_nskip = 0;
unsigned long lastWifiAttempt = 0;
bool wifiConnected = false;

// Macros de logging
#define LOG_INFO(fmt, ...)   Serial.printf("[INFO] " fmt "\n", ##__VA_ARGS__)
#define LOG_WARN(fmt, ...)   Serial.printf("[WARN] " fmt "\n", ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...)  Serial.printf("[ERROR] " fmt "\n", ##__VA_ARGS__)

// Conecta o mantiene WiFi
void connectWiFi() {
  WiFiManager wifiManager;
  if (wifiManager.autoConnect(WIFI_SSID, WIFI_PASSWORD)) {
    digitalWrite(LED, LOW);
    wifiConnected = true;
    ThingSpeak.begin(client);
    LOG_INFO("WiFi connected to %s", WIFI_SSID);
  } else {
    digitalWrite(LED, HIGH);
    wifiConnected = false;
    LOG_WARN("WiFi portal active or connection failed");
  }
}

void setup() {
  disableCore0WDT();
  disableCore1WDT();
  // Serial and pin init
  Serial.begin(115200);
  pinMode(PIN_IN1, INPUT);
  pinMode(PIN_IN2, INPUT);
  pinMode(LED, OUTPUT);
  set_sample_pin(PIN_IN2);

  // Watchdog config
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
  esp_task_wdt_add(NULL);
  LOG_INFO("Task watchdog initialized with %d s timeout", WDT_TIMEOUT_S);

  // Initial WiFi connection
  connectWiFi();

  // sampling timer config
  if (!ITimer.attachInterruptInterval(SAMPLE_PERIOD_US, sample_input)) {
    LOG_ERROR("No se pudo configurar ITimer");
    while (true) {
      // Serial.println("Can't set ITimer. Select another freq. or interval");
      delay(1000);
    }
  }
}

#ifdef DEBUG_SAMPLER
/**
 * When debugging, log bit sequence following PIN_IN1 going low
 * DEBUG_SAMPLER causes sampler to capture a full buffers worth
 * after reset_sampler call. Last bit is not valid.
 */
void debug_loop()
{
  static bool sent = true;
  if (sent)
  {
    if (!digitalRead(PIN_IN1))
    {
      reset_sampler();
      sent = false;
    }
    return;
  }
  size_t buffered_len = num_samples();
  if (buffered_len == SAMPLE_LEN - 1)
  {
    sent = true;
    for (int i = 0; i < SAMPLE_LEN / 8; i++)
    {
      Serial.printf("%02X", get_sample_buffer()[i]);
    }
    Serial.print("\n");
    reset_sampler();
  }
}
#endif

// Decode msg and send to ThingSpeak
String decode_and_print(const uint8_t *msg) {
  if (!check_crc(msg)) {
    LOG_WARN("CRC check failed");
    return "CRC error";
  }

  float temperatura      = (get_temperature(msg) - 32.0) * (5.0 / 9.0);
  float direccion_viento = get_direction(msg);
  float viento_medio     = get_avr_wind_speed(msg) * 3.6;
  float rafaga           = get_gust_wind_speed(msg) * 3.6;
  float humedad          = get_humidity(msg);
  float lluvia           = get_rain(msg) * 0.1 - 6.54;

  ThingSpeak.setField(1, lluvia);
  ThingSpeak.setField(2, temperatura);
  ThingSpeak.setField(3, direccion_viento);
  ThingSpeak.setField(4, viento_medio);
  ThingSpeak.setField(5, rafaga);
  ThingSpeak.setField(6, humedad);
  int httpCode = ThingSpeak.writeFields(myChannelNumber, myWriteAPIKey);

  if (httpCode == 200) {
    LOG_INFO("Data sent successfully");
  } else {
    LOG_ERROR("Error sending data: %d", httpCode);
  }

  return (httpCode == 200) ? "OK" : "Error";
}

void loop() {
  // Reset watchdog al inicio de cada iteración
  esp_task_wdt_reset();

  unsigned long now = millis();
  // Reintento de conexión WiFi
  if (!wifiConnected && (now - lastWifiAttempt >= WIFI_RECONNECT_INTERVAL)) {
    lastWifiAttempt = now;
    connectWiFi();
  }

  if (!wifiConnected) {
    delay(100);
    return;
  }

  size_t buffered_len = num_samples();
  if (buffered_len > SAMPLE_LEN / 2) {
    // Serial.printf("Fell Behind\n");
    reset_sampler();
    return;
  }

  for (size_t i = 0; i < buffered_len; i++) {
    // Demodulate PPM signal
    tracker.process_sample(get_next_sample());
    // If full message is received, decode and show
    if (tracker.cur_rx_len() == MSG_LEN) {
      if (count_for_nskip == nskip) {
        decode_and_print(tracker.get_msg());
        count_for_nskip = 0;
      } else {
        count_for_nskip++;
      }
      reset_sampler();
      tracker.reset();
    }
  }

  // Pequeña pausa para evitar sobrecarga
  delayMicroseconds(SAMPLE_PERIOD_US * 10);
}
