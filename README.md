# 🌦️ Sainlogic_esp32_wifi - Estación Meteorológica con Conectividad WiFi

Este proyecto permite añadir conectividad WiFi a la estación meteorológica Sainlogic FT0835 (o similar) utilizando un ESP32. Esto posibilita la **captura**, **decodificado**, **almacenamiento** y **visualización** de datos de temperatura, humedad, viento y lluvia en tiempo real a través de una [aplicación web](https://varo137.ddns.net/).

---
## 📋 Prerrequisitos

- **Hardware**
    - ESP32 (p. ej. ESP32‑Devkit común)
    - Estación meteorológica Sainlogic FT0835 sin WiFi.
    - **Advertencia:** Se requiere soldador, cables y conocimientos básicos de electrónica para interconectar los dispositivos.
    - Conviene añadir condensadores entre alimentación y tierra para evitar resets por picos de voltaje, ya que enviar datos por HTTP supone un pico de demanda por parte del ESP32.

- **Conexión física**
  Soldar el ESP32 al receptor de la estación según la guía de [Robopenguins](https://www.robopenguins.com/weather-station/).

- **Software**
    - [PlatformIO](https://platformio.org/) (o ESP‑IDF)
    - Git
    - Python 3.x (para el servidor API)
    - Un servidor Linux para hostear la app web.

## 📖 Descripción general y Arquitectura

El sistema se divide en tres componentes principales:

1. **Firmware para ESP32 (Backend Lógica)**
  - Muestrea el receptor Sainlogic, obtiene los binarios crudos.
  - Envía estos binarios vía HTTP POST a la API de destino.
  - *Opcional:* Se puede configurar para usar MQTT o publicar en servicios como Thingspeak.

2. **API (Backend Recepción, decodificación y Almacenamiento)**
  - Aplicación basada en **Python y FastAPI** que recibe los datos binarios del ESP32, valida el token de acceso, los decodifica y los almacena en una **base de datos SQLite** (ligera, ideal para SBCs como la Orange Pi).
  - El protocolo de de los datos se explica [aquí](https://github.com/merbanan/rtl_433/blob/master/src/devices/cotech_36_7959.c). Este modelo de estación no dispone de sensor de UV ni intensidad luminosa, por lo que siempre manda FF FB FB. Además, algunos datos como la presión o temperatura interior se toman con sensores ubicados en la pantalla de visualización de la estación, no en el módulo externo.

3. **Frontend (Visualización)**
  - **Vanilla JS**. Sirve los datos procesados desde la API, maneja la actualización en tiempo real y permite la exportación histórica.

Un ejemplo de web se muestra [aquí](https://varo137.ddns.net/), con datos en tiempo real.
*(Nota: El ESP32 puede sufrir desconexiones temporales por tener un WiFi inestable).*

---

## ⚙️ Instalación y Despliegue

### 1. Preparar el ESP32 (Captura de Datos)

```bash
# Clona el repositorio
git clone [https://github.com/Alvaro137/Sainlogic_esp32_wifi.git](https://github.com/Alvaro137/Sainlogic_esp32_wifi.git)
cd Sainlogic_esp32_wifi/backend/esp32

# Crea tu archivo de credenciales
cp src/secrets_example.h src/secrets.h
# --- Edita secrets.h con tu SSID, contraseña WiFi, URL de la API (ej: [https://tudominio.com/api/raw-data](https://tudominio.com/api/raw-data)) y access token.

# Compila y flashea con PlatformIO
pio run --target upload
```

### 2. Configurar la API (Recepción y Almacenamiento)

La API está desarrollada en **Python/FastAPI** y utiliza **SQLite** como base de datos. SQLite es ideal para este despliegue por ser ligero (un solo archivo), no requerir un proceso de servidor separado y minimizar el desgaste de escritura en la SD de la Orange Pi.

Es recomendable aislar las dependencias en un entorno virtual:

```bash
# Navega a la carpeta de la API
cd Sainlogic_esp32_wifi/backend/app

# Crea e inicializa el entorno virtual (sainlogic_venv)
python3 -m venv sainlogic_venv
source sainlogic_venv/bin/activate

# Instala las dependencias (FastAPI, Uvicorn, etc.)
pip install -r requirements.txt

# Crea tu archivo de credenciales a partir de la plantilla
cp example.env secrets.env
nano secrets.env
```
*Importante*: Recuerda añadir el mismo access token en secrets.env del servidor y en secrets.h del firmware del ESP32, y no subir estos archivos.

### 3. Despliegue en Producción con systemd
Para asegurar que la API funcione 24/7 y arranque automáticamente con el sistema, utilizamos un servicio de systemd.

### 4. Configuración del Servidor Web (Caddy)
Utilizamos Caddy como Proxy Inverso. Caddy gestiona automáticamente los certificados SSL (HTTPS) y redirige el tráfico seguro de internet hacia nuestra API interna.
