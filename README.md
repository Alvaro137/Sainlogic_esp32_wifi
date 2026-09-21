# Sainlogic ESP32 WiFi Bridge

Puente WiFi y servidor de telemetría para estaciones meteorológicas Sainlogic (FT0835 y compatibles). Captura paquetes de radiofrecuencia (433.92 MHz) desde el módulo receptor interno de la consola, decodifica las lecturas en un ESP32 y las publica vía HTTP a una API REST basada en FastAPI con persistencia en SQLite y visualización web en tiempo real.

---

## Arquitectura

```
[ Sensor exterior (433.92 MHz) ]
             │
             ▼
[ Consola Sainlogic / Receptor RF ] ──(GPIO)──► [ ESP32 DevKit ]
                                                       │
                                                (HTTP POST / JSON)
                                                       │
                                                       ▼
                                         [ FastAPI + SQLite (WAL) ]
                                                       │
                                            ┌──────────┴──────────┐
                                            ▼                     ▼
                                    [ Dashboard Web ]     [ Exportación CSV ]
```

El sistema consta de tres componentes desacoplados:

1. **Firmware ESP32 (`firmware/`):** Lee el flujo binario del demodulador RF de la estación, extrae y valida el paquete (preámbulo, tipo de mensaje, carga útil y checksum) y envía la trama codificada mediante HTTP POST con autenticación por token Bearer.
2. **API Backend (`backend/app/`):** Servicio FastAPI asíncrono que ingesta las lecturas, las almacena en SQLite con journal en modo WAL e índice temporal, y expone endpoints de consulta reciente y descarga de históricos.
3. **Frontend (`frontend/`):** Interfaz web ligera en Vanilla JS y CSS sin dependencias de compilación, adaptada para navegadores de escritorio y móviles.

---

## Hardware y Conexión

### Material necesario
- Placa de desarrollo **ESP32** (NodeMCU, ESP32-WROOM-32 o equivalente).
- Estación meteorológica **Sainlogic FT0835** (modelo estándar sin módulo WiFi integrado).
- Soldador, estaño y cable fino para puenteado (30 AWG recomendado).
- Condensador electrolítico (100 µF a 470 µF) entre 3.3V y GND en el ESP32 para mitigar caídas de tensión durante las ráfagas de transmisión WiFi.

### Conexión eléctrica
1. Abrir la consola receptora de la estación retirando los tornillos traseros.
2. Localizar el módulo receptor RF superheterodino de 433 MHz soldado a la placa base.
3. Soldar tres cables:
   - **VCC (3.3V):** Alimentación común.
   - **GND:** Masa común entre la consola y el ESP32.
   - **DATA:** Salida digital del receptor RF conectada a un pin GPIO del ESP32 configurado como entrada de interrupción (por defecto GPIO 13).
4. Más detalles sobre el análisis del receptor en la documentación de [Robopenguins](https://www.robopenguins.com/weather-station/).

---

## Protocolo de Radiofrecuencia

La estación exterior transmite ráfagas ASK/OOK moduladas en 433.92 MHz con un intervalo aproximado de 16 segundos. La estructura de la trama sigue el estándar compatible con Cotech 36-7959 / Fine Offset WH24:

- **Preámbulo y Sync:** Secuencia de sincronización de bits.
- **Identificador de estación:** ID aleatorio que cambia tras el reemplazo de baterías.
- **Temperatura:** Entero de 12 bits codificado en décimas de grado Celsius con offset.
- **Humedad relativa:** Porcentaje (1 byte, rango 1-99%).
- **Velocidad media y racha de viento:** Enteros en décimas de m/s.
- **Dirección del viento:** Codificación angular en pasos de 22.5 grados (16 rumbos).
- **Contador acumulado de lluvia:** Contador continuo de impulsos del balancín (0.3 mm por vaciado).
- **Checksum / CRC:** Comprobación de redundancia cíclica de 8 bits para descartar tramas corruptas por colisiones de radio.

---

## Configuración y Despliegue

### 1. Firmware (ESP32)

Compilación y carga mediante [PlatformIO](https://platformio.org/):

```bash
cd firmware

# Copiar plantilla de configuración
cp src/secrets_example.h src/secrets.h
```

Editar `src/secrets.h` con las credenciales de red y la dirección del servidor:

```c
#define WIFI_SSID "TuRedWiFi"
#define WIFI_PASSWORD "TuPassword"
#define API_URL "http://192.168.1.254:8000/api/raw-data"
#define API_TOKEN "tu_token_secreto"
```

Flashear el dispositivo:
```bash
pio run --target upload
```

---

### 2. Backend (FastAPI)

El backend requiere Python 3.10+ y SQLite 3.

```bash
cd backend/app

# Entorno virtual
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuración de variables de entorno
cp example.env secrets.env
```

Editar `secrets.env`:
```ini
API_TOKEN=tu_token_secreto
```

Iniciar el servidor en desarrollo:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### 3. Ejecución con Docker

El proyecto incluye soporte para contenedor distroless de mínimo tamaño y superficie de ataque:

```bash
docker compose up -d --build
```

El servicio expondrá el puerto 8000 y persistirá los datos en el volumen montado para `datos.db`.

---

### 4. Producción con systemd y Caddy

Para despliegues persistentes en placas monoplaca (Orange Pi, Raspberry Pi) o servidores Linux:

#### Servicio systemd (`/etc/systemd/system/meteo.service`)
```ini
[Unit]
Description=Servicio API Estación Meteorológica Sainlogic
After=network.target

[Service]
User=varo
WorkingDirectory=/home/varo/meteo_lite/backend/app
ExecStart=/home/varo/meteo_lite/backend/app/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### Proxy inverso con Caddy (`/etc/caddy/Caddyfile`)
```caddy
clima.tudominio.com {
    encode gzip
    reverse_proxy 127.0.0.1:8000

    header {
        Strict-Transport-Security "max-age=31536000;"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
    }
}
```

---

## Endpoints de la API

| Método | Ruta | Autenticación | Descripción |
|---|---|---|---|
| `GET` | `/` | Pública | Dashboard principal interactivo |
| `GET` | `/analisis` | Pública | Vista de análisis y exportación |
| `GET` | `/api/recientes` | Pública | Últimas lecturas (`?limit=1` por defecto) |
| `GET` | `/api/descargar-csv` | Pública | Descarga por streaming de todo el histórico en CSV |
| `POST` | `/api/raw-data` | Bearer Token | Ingesta de tramas crudas del ESP32 |
| `POST` | `/api/log-error` | Bearer Token | Registro de diagnósticos de conexión del microcontrolador |

---

## Licencia

Código abierto bajo licencia [MIT](LICENSE).
