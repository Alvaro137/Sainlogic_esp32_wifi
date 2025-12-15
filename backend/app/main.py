import os
import io
import csv
import pathlib
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from sqlite3 import Connection

# Importamos las funciones y el generador de DB desde utils
from .utils import (
    init_db,
    get_db,
    insert_data,
    get_recent,
    decode_raw_msg,
    get_all_records,
    debugprint,
    get_rain_24h
)

# CONFIGURACIÓN

APP_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_FILES_PATH = FRONTEND_DIR / "static"
LOG_FILE = APP_DIR / "eventos.log"
ENV_PATH = APP_DIR / "secrets.env"

load_dotenv(dotenv_path=ENV_PATH)
API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    print(f"Error: No se encontró API_TOKEN en {ENV_PATH}")
    raise RuntimeError("API_TOKEN no configurado en variables de entorno.")

DEBUGFLAG = False

app = FastAPI(title="App Meteorológica Espadaña")

app.mount("/static", StaticFiles(directory=STATIC_FILES_PATH), name="static")

# Inicialización de tablas al arranque
try:
    init_db()
except Exception as e:
    print(f"Error inicializando la base de datos: {e}")

# SEGURIDAD

async def verify_token(authorization: Optional[str] = Header(None)):
    """
    Dependencia de autenticación basada en token.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    expected = f"Bearer {API_TOKEN}"
    if authorization != expected:
        debugprint(f"Intento de acceso denegado (Token inválido).", debug_flag=DEBUGFLAG)
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    return True

# MIDDLEWARE

@app.middleware("http")
async def log_requests(request: Request, call_next):
    debugprint(f"📡 {request.method}: {request.url}", debug_flag=DEBUGFLAG)
    response = await call_next(request)
    return response

# RUTAS FRONTEND

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    try:
        with open(FRONTEND_DIR / "index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error de frontend</h1>"

@app.get("/analisis", response_class=HTMLResponse)
async def serve_analisis():
    try:
        with open(FRONTEND_DIR / "analisis.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error de frontend</h1>"

# API ENDPOINTS

@app.get("/api/recientes")
async def api_recientes(db: Connection = Depends(get_db)):
    """
    Obtiene el último registro y calcula la lluvia acumulada de las últimas 24h.
    """
    latest_record_list = get_recent(db, limit=1)

    if not latest_record_list:
        raise HTTPException(status_code=404, detail="No hay datos registrados aún.")

    latest_record = latest_record_list[0]

    # Cálculo de lluvia acumulada
    try:
        rain_data = get_rain_24h(db)
        latest_record['rain_accumulated'] = latest_record.get('lluvia')
        latest_record['lluvia'] = rain_data['rain_24h']
        latest_record['rain_24h'] = rain_data['rain_24h']
    except Exception as e:
        debugprint(f"Error calculando lluvia 24h: {e}", debug_flag=DEBUGFLAG)
        latest_record['rain_24h'] = 0.0
        latest_record['rain_accumulated'] = latest_record.get('lluvia', 0.0) # A modo de fallback

    return latest_record


@app.post("/api/raw-data", status_code=200)
async def raw_data(
    request: Request,
    db: Connection = Depends(get_db),
    authorized: bool = Depends(verify_token)
):
    """
    Añade datos binarios recibidos del ESP32.
    Requiere autenticación y mensaje de mínimo 16 bytes.
    """
    # Diagnóstico del ESP32
    rssi = request.headers.get("x-esp-rssi", "0")
    uptime = request.headers.get("x-esp-uptime", "0")

    # Logging de señal débil para mantenimiento
    try:
        rssi_val = int(rssi)
        if rssi_val < -85 and rssi_val != 0:
            debugprint(f"WiFi inestable ({rssi} dBm).", debug_flag=DEBUGFLAG)
    except ValueError: pass

    try:
        raw_bytes = await request.body()

        if len(raw_bytes) < 16:
             debugprint(f"Mensaje descartado: Tamaño insuficiente ({len(raw_bytes)} bytes)", debug_flag=DEBUGFLAG)
             return {"status": "ignored", "reason": "Mensaje demasiado corto"}

        hex_log = raw_bytes[:16].hex().upper()
        debugprint(f"📥 HEX: {hex_log}", debug_flag=DEBUGFLAG)

        data = decode_raw_msg(raw_bytes)

        if data and "temperatura" in data:
            insert_data(db, data, str(hex_log), int(rssi), int(uptime))
            return {"status": "ok"}
        else:
            debugprint("Error decodificando payload (Checksum o estructura inválida).", debug_flag=DEBUGFLAG)
            return {"status": "error", "reason": "Error de decodificación"}

    except Exception as e:
        debugprint(f"Excepción en ingesta de datos: {e}", debug_flag=DEBUGFLAG)
        # Retornamos error con detalle para facilitar depuración en el microcontrolador
        return {"status": "error", "detail": str(e)}


@app.get("/api/descargar-csv")
async def download_csv(db: Connection = Depends(get_db)):
    """
    Exportación completa de datos a CSV.
    """
    data = get_all_records(db)

    if not data:
        raise HTTPException(status_code=404, detail="No data available")

    output = io.StringIO()
    # Usamos las keys del primer registro para generar la cabecera dinámicamente
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)

    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/log-error")
async def log_error(
    request: Request,
    authorized: bool = Depends(verify_token)
):
    """
    Endpoint para registro remoto de errores del cliente (ESP32).
    """
    try:
        body = await request.body()
        mensaje = body.decode("utf-8", errors="ignore") # 'ignore' para evitar crash si el ESP32 envía bytes corruptos en el mensaje de error
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = f"[{timestamp}]: {mensaje}\n"

        with open(LOG_FILE, "a") as f:
            f.write(entry)

        return {"status": "logged"}
    except Exception as e:
        print(f"Error escribiendo en log de eventos: {e}")
        return {"status": "error"}

#TODO: Proteger este endpoint con autenticación
@app.get("/api/ver-logs")
async def ver_logs():
    """
    Visualización rápida de logs del servidor (últimas 50 líneas).
    """
    if not LOG_FILE.exists():
        return Response("Log vacío o inexistente.", media_type="text/plain")

    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        content = "".join(lines[-50:])
        return Response(content, media_type="text/plain")
    except Exception:
        return Response("Error de lectura de archivo de log.", media_type="text/plain")
