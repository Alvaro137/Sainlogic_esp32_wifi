#include <Arduino.h>
#include <ESP32TimerInterrupt.h>
#include <WiFiManager.h> // Incluye WiFiManager
#include "ThingSpeak.h"

#include "ring_buffer.h"
#include "ppm_tracker.h"
#include "data_decode.h"
#include "secrets.h"

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
#define MIN_SAMPLES 4
#define MAX_SAMPLES 16

// Number of samples that are skipped
#define nskip 0

int count_for_nskip = 0;

// Configuración de ThingSpeak
unsigned long myChannelNumber = 1;
const char *myWriteAPIKey = "90J22DQBTZEO9P65";

WiFiClient client;

// Timer variables
unsigned long lastTime = 0;
unsigned long timerDelay = 10000;

// Variables de los sensores
float temperatura, lluvia, humedad, rafaga, viento_medio, direccion_viento;
// Init ESP32 timer
ESP32Timer ITimer(0);

BinaryPpmTracker tracker(MIN_SAMPLES, MAX_SAMPLES);

// setup WiFi based on ssid and password
void setup_wifi()
{
  // Configurar WiFiManager
  WiFiManager wifiManager;

  // Inicia el portal de configuración si no puede conectarse a WiFi
  if (!wifiManager.autoConnect("ESP32_AP", "12345678")) // Nombre y contraseña del AP
  {
    // Serial.println("No se pudo conectar a WiFi. Reiniciando...");
    digitalWrite(LED, HIGH);
    delay(1000);
    digitalWrite(LED, LOW);
    delay(1000);
    digitalWrite(LED, HIGH);
    delay(1000);
    digitalWrite(LED, LOW);
    delay(1000);
    digitalWrite(LED, HIGH);
    delay(1000);
    digitalWrite(LED, LOW);
    delay(1000);
    digitalWrite(LED, HIGH);
    delay(1000);
    digitalWrite(LED, LOW);
    setup_wifi();
  }

  // Serial.println("Conexión WiFi establecida.");
  // Serial.print("IP local: ");
  // Serial.println(WiFi.localIP());

  // Inicializar ThingSpeak
  ThingSpeak.begin(client);
}

// Setup pins, serial, timer ISR, Wifi
void setup()
{
  pinMode(PIN_IN1, INPUT);
  pinMode(PIN_IN2, INPUT);
  pinMode(LED, OUTPUT);
  set_sample_pin(PIN_IN2);
  // Serial.begin(115200);

  setup_wifi();

  if (ITimer.attachInterruptInterval(SAMPLE_PERIOD_US, sample_input))
    // Serial.println("Starting ITimer OK, millis() = " + String(millis()));
    delay(1);
  else
    // Serial.println("Can't set ITimer. Select another freq. or interval");
    delay(1);
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

String decode_and_print(const uint8_t *msg)
{
  if (check_crc(tracker.get_msg()))
  {
    temperatura = ((get_temperature(msg) - 32.0) * (5.0 / 9.0));
    direccion_viento = get_direction(msg);
    viento_medio = get_avr_wind_speed(msg) * (36.0 / 10.0);
    rafaga = get_gust_wind_speed(msg) * (36.0 / 10.0);
    humedad = get_humidity(msg);
    lluvia = get_rain(msg) * (1.0 / 10.0) - 6.54;
    // Mostrar los datos por serial en formato JSON
    String json_data = "{";
    /*
    json_data += String("\"wind_dir_deg\": ") + String(direccion_viento) + ", ";
    json_data += String("\"avr_wind_m/s\": ") + String(viento_medio) + ", ";
    json_data += String("\"gust_wind_m/s\": ") + String(rafaga) + ", ";
    json_data += String("\"rain_mm\": ") + String(lluvia);
    json_data += "}";
    */
    ThingSpeak.setField(1, lluvia);
    ThingSpeak.setField(2, temperatura);
    ThingSpeak.setField(3, direccion_viento);
    ThingSpeak.setField(4, viento_medio);
    ThingSpeak.setField(5, rafaga);
    ThingSpeak.setField(6, humedad);
    // Escribir en ThingSpeak
    int httpCode = ThingSpeak.writeFields(myChannelNumber, myWriteAPIKey);
    /*
      if (httpCode == 200)
      {
        Serial.println("Datos enviados a ThingSpeak con éxito");
      }
      else
      {
        Serial.print("Error al enviar datos: ");
        Serial.println(httpCode);
      }
      */
    return (json_data);
  }
  else
  {
    // Serial.print("CRC check failed\n");
    return ("CRC check failed\n");
  }
}

void loop()
{
#ifdef DEBUG_SAMPLER
  debug_loop();
#else
  if (WiFi.status() != WL_CONNECTED)
  {
    setup_wifi();
  }

  size_t buffered_len = num_samples();
  if (buffered_len > SAMPLE_LEN / 2)
  {
    // Serial.printf("Fell Behind\n");
    reset_sampler();
    return;
  }
  for (size_t i = 0; i < buffered_len; i++)
  {
    // Demodulate PPM signal
    tracker.process_sample(get_next_sample());

    // If full message is received, decodificar y mostrar
    if (tracker.cur_rx_len() == MSG_LEN)
    {
      for (int i = 0; i < MSG_BYTES; i++)
      {
        // Serial.printf("%02X", tracker.get_msg()[i]);
      }
      // Serial.print("\n");
      if (count_for_nskip == nskip)
      {
        // Mostrar los datos decodificados y enviarlos a Thingspeak
        String json_data = decode_and_print(tracker.get_msg());
        // Serial.println(json_data);
        count_for_nskip = 0;
      }
      else
      {
        count_for_nskip++;
      }
      reset_sampler();
      tracker.reset();
      // Serial.print("count_for_nskip: ");
      // Serial.print(count_for_nskip);
    }
  }
  delayMicroseconds(SAMPLE_PERIOD_US * 10);
#endif
}
