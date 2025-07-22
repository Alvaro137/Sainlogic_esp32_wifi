# 🌦️ Sainlogic_esp32_wifi

Este proyecto añade conectividad WiFi a la estación meteorológica Sainlogic usando un ESP32, de modo que puedas **capturar** y **visualizar** tus datos de temperatura, humedad, presión, viento y lluvia en tiempo real desde una web estática y responsiva, accesible desde cualquier navegador. 

---
## 📋 Prerrequisitos

- **Hardware**  
  - ESP32 (p. ej. ESP32‑Devkit común)  
  - Estación meteorológica Sainlogic FT0835 sin WiFi como [esta](https://www.amazon.es/Meteorol%C3%B3gica-Inal%C3%A1mbrica-Exteriores-Temperatura-Despertador/dp/B08P5VZKKJ/ref=sr_1_8?crid=3PWAMGKN7AA16&keywords=estacion%2Bmeteorologica%2Bpluviometro&qid=1695751250&refinements=p_36%3A2493684031&rnid=2493681031&s=lawn-garden&sprefix=estacion%2Bmeteorologica%2B%2Clawngarden%2C337&sr=1-8&ufe=app_do%3Aamzn1.fos.5e544547-1f8e-4072-8c08-ed563e39fc7d&th=1) o similar
  - Soldador y cables para interconectar  
- **Conexión física**  
  Soldar el ESP32 al receptor de la estación según la guía de [Robopenguins](https://www.robopenguins.com/weather-station/).
  Para un ejemplo de firmware  adaptado para el ESP8266 (no apto para ESP32) que publica por MQTT a Weather Underground, revisa también [su github](https://github.com/axlan/sainlogic-sdr), que ha inspirado este proyecto.
- **Software**  
  - [PlatformIO](https://platformio.org/) (o ESP‑IDF)  
  - Git  

## 📖 Descripción general

El sistema consta de dos partes:

1. **Firmware para ESP32**  
   - Se conecta a la estación Sainlogic y lee los sensores (temp., humedad, presión, viento, lluvia…).  
   - Decodifica y procesa los datos en el microcontrolador.  
   - El ESP32 se conecta a tu red WiFi y ofrece los datos meteorológicos en tiempo real a través de una API/servidor HTTP ligero. Por defecto envío la información a ThingSpeak vía HTTP, aunque también puedes configurarlo para trabajar con MQTT u otras plataformas de tu elección.
   - Configuración de red en `secrets.h` (no subas tus credenciales al repositorio, para ello confirma que tengas este archivo en el .gitignore).  
   - Código principal en `esp32/src/`.

2. **Interfaz web estática**  
   - Carpeta `docs/` con HTML, CSS y JavaScript para mostrar gráficos interactivos y tablas.  
   - Archivos principales:
     - `index.html` — punto de inicio  
     - `main.js` — conexión con la API del ESP32  
     - `charts.js` — generación de gráficos meteorológicos  
     - `sainlogic.css` — estilos personalizados  
   - La interfaz web es 100 % estática y puede servirse directamente desde el ESP32 (si dispone de suficiente memoria) o desplegarse en cualquier hosting estático —por ejemplo, GitHub Pages, Grafana o incluso integrar directamente con ThingSpeak— para obtener visualizaciones y análisis más avanzados.
  
Un ejemplo de web se muestra [aquí](https://alvaro137.github.io/Sainlogic_esp32_wifi/), con datos en tiempo real del clima en Espadaña, Salamanca, y gráficos interactivos filtrables por fecha realizados únicamente con charts.js para visualización rápida, como este:
<img width="1771" height="369" alt="image" src="https://github.com/user-attachments/assets/e69a65da-aabf-4c33-9742-02d4883170c2" />

---

## ⚙️ Instalación y uso

### 1. Preparar el ESP32

```bash
# Clona el repositorio
git clone https://github.com/Alvaro137/Sainlogic_esp32_wifi.git
cd Sainlogic_esp32_wifi/esp32

# Crea tu archivo de credenciales
cp include/secrets_example.h include/secrets.h
# — Edita secrets.h con tu SSID y contraseña WiFi (WIFI_SSID, WIFI_PASS), y opcionalmente tus credenciales de Thingspeak (TS_CHANNEL_ID y TS_WRITE_APIKEY).

# Compila y flashea con PlatformIO
pio run --target upload
```
### 2. Desplegar la web

```bash
cd ../docs
# - Abre index.html localmente
# - O despliega en GitHub Pages (Settings > Pages > Carpeta /docs)
```

## Ante desconexiones o problemas inesperados
Prueba a resetear el esp32 usando el botón EN.
