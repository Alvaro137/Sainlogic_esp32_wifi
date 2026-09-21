"""
Servidor FastAPI para la estación meteorológica Sainlogic Espadaña.
Ingesta binaria de datos de ESP32, visualización en tiempo real y descarga streaming de históricos.
"""

import os
import io
import csv
import sqlite3
import pathlib
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager
from sqlite3 import Connection

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .utils import (
    init_db,
    get_db,
    insert_data,
    get_recent,
    decode_raw_msg,
    debugprint,
    get_rain_24h,
    descale_value,
    DB_PATH
)

# Configuración de rutas
APP_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_FILES_PATH = FRONTEND_DIR / "static"
LOG_FILE = APP_DIR / "eventos.log"
ENV_PATH = APP_DIR / "secrets.env"

# Cargar variables de entorno
load_dotenv(dotenv_path=ENV_PATH)
API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    print(f"Advertencia: No se encontró API_TOKEN en {ENV_PATH}")

DEBUGFLAG = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: inicializa la base de datos al arrancar."""
    try:
        init_db()
    except Exception as e:
        print(f"Error inicializando la base de datos: {e}")
    yield


app = FastAPI(
    title="Estación Meteorológica Espadaña",
    description="API de telemetría y dashboard para estación meteorológica Sainlogic",
    version="2.1.0",
    lifespan=lifespan
)

# Servir estáticos
app.mount("/static", StaticFiles(directory=STATIC_FILES_PATH), name="static")


# SEGURIDAD Y AUTENTICACIÓN

async def verify_token(authorization: Optional[str] = Header(None)) -> bool:
    """Valida la cabecera Authorization Bearer para endpoints de ingesta."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    expected = f"Bearer {API_TOKEN}"
    if authorization != expected:
        debugprint("Intento de acceso denegado (Token inválido).", debug_flag=DEBUGFLAG)
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    return True


# MIDDLEWARE

@app.middleware("http")
async def log_requests(request: Request, call_next):
    debugprint(f"📡 {request.method}: {request.url}", debug_flag=DEBUGFLAG)
    response = await call_next(request)
    return response


# RUTAS DE INTERFAZ HTML

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Sirve el dashboard interactivo principal."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Error: index.html no encontrado</h1>", status_code=500)
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/analisis", response_class=HTMLResponse)
async def serve_analisis():
    """Sirve la página de análisis y descarga de históricos."""
    analisis_path = FRONTEND_DIR / "analisis.html"
    if not analisis_path.exists():
        return HTMLResponse("<h1>Error: analisis.html no encontrado</h1>", status_code=500)
    with open(analisis_path, "r", encoding="utf-8") as f:
        return f.read()


# ENDPOINTS DE API

@app.get("/api/recientes")
async def api_recientes(db: Connection = Depends(get_db)):
    """
    Obtiene la última lectura de los sensores y la lluvia acumulada de las últimas 24h.
    """
    latest_record_list = get_recent(db, limit=1)

    if not latest_record_list:
        raise HTTPException(status_code=404, detail="No hay datos registrados aún.")

    latest_record = latest_record_list[0]

    try:
        rain_data = get_rain_24h(db)
        latest_record['rain_accumulated'] = latest_record.get('lluvia')
        latest_record['lluvia'] = rain_data['rain_24h']
        latest_record['rain_24h'] = rain_data['rain_24h']
    except Exception as e:
        debugprint(f"Error calculando lluvia 24h: {e}", debug_flag=DEBUGFLAG)
        latest_record['rain_24h'] = 0.0
        latest_record['rain_accumulated'] = latest_record.get('lluvia', 0.0)

    return latest_record


@app.post("/api/raw-data", status_code=200)
async def raw_data(
    request: Request,
    db: Connection = Depends(get_db),
    authorized: bool = Depends(verify_token)
):
    """
    Ingesta de telemetría binaria desde el microcontrolador ESP32.
    """
    rssi = request.headers.get("x-esp-rssi", "0")
    uptime = request.headers.get("x-esp-uptime", "0")

    try:
        rssi_val = int(rssi)
        if rssi_val < -85 and rssi_val != 0:
            debugprint(f"WiFi inestable ({rssi} dBm).", debug_flag=DEBUGFLAG)
    except ValueError:
        rssi_val = 0

    try:
        uptime_val = int(uptime)
    except ValueError:
        uptime_val = 0

    try:
        raw_bytes = await request.body()

        if len(raw_bytes) < 16:
            debugprint(f"Mensaje descartado: tamaño insuficiente ({len(raw_bytes)} bytes)", debug_flag=DEBUGFLAG)
            return {"status": "ignored", "reason": "Mensaje demasiado corto"}

        hex_log = raw_bytes[:16].hex().upper()
        debugprint(f"📥 HEX: {hex_log}", debug_flag=DEBUGFLAG)

        data = decode_raw_msg(raw_bytes)

        if data and "temperatura" in data:
            insert_data(db, data, str(hex_log), rssi_val, uptime_val)
            return {"status": "ok"}
        else:
            debugprint("Error decodificando payload (Checksum o estructura inválida).", debug_flag=DEBUGFLAG)
            return {"status": "error", "reason": "Error de decodificación"}

    except Exception as e:
        debugprint(f"Excepción en ingesta de datos: {e}", debug_flag=DEBUGFLAG)
        return {"status": "error", "detail": str(e)}


@app.get("/api/descargar-csv")
async def download_csv():
    """
    Exportación del histórico de telemetría a CSV mediante streaming por bloques.
    Itera sobre el cursor SQLite usando fetchmany para evitar cargar todo el dataset en memoria.
    """
    def iter_csv():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, timestamp, temperatura, humedad, lluvia,
                   viento_medio, rafaga, direccion, rssi, uptime, raw_hex
            FROM datos
            ORDER BY id ASC
        """)

        # 1. Cabecera CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'id', 'timestamp', 'temperatura', 'humedad', 'lluvia',
            'viento_medio', 'rafaga', 'direccion', 'rssi', 'uptime', 'raw_hex'
        ])
        yield output.getvalue()

        # 2. Transmisión por bloques de 2000 filas
        try:
            while True:
                rows = cur.fetchmany(2000)
                if not rows:
                    break
                output = io.StringIO()
                writer = csv.writer(output)
                for r in rows:
                    writer.writerow([
                        r['id'],
                        r['timestamp'],
                        descale_value(r['temperatura']),
                        r['humedad'],
                        descale_value(r['lluvia']),
                        descale_value(r['viento_medio']),
                        descale_value(r['rafaga']),
                        descale_value(r['direccion']),
                        r['rssi'],
                        r['uptime'],
                        r['raw_hex']
                    ])
                yield output.getvalue()
        finally:
            conn.close()

    now_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
    filename = f"export_{now_str}.csv"

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/log-error")
async def log_error(
    request: Request,
    authorized: bool = Depends(verify_token)
):
    """
    Registro de incidencias y diagnósticos remotos del ESP32.
    """
    try:
        body = await request.body()
        mensaje = body.decode("utf-8", errors="ignore")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp} UTC]: {mensaje}\n"

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

        return {"status": "logged"}
    except Exception as e:
        print(f"Error registrando en log de eventos: {e}")
        return {"status": "error"}


@app.get("/api/ver-logs")
async def ver_logs():
    """
    Visualización de las últimas 50 líneas del log de eventos.
    """
    if not LOG_FILE.exists():
        return Response("Log vacío o inexistente.", media_type="text/plain")

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        content = "".join(lines[-50:])
        return Response(content, media_type="text/plain")
    except Exception:
        return Response("Error de lectura de archivo de log.", media_type="text/plain")
