"""
Utilidades de persistencia, decodificación y cálculo de métricas para la estación meteorológica.
"""

import sqlite3
from sqlite3 import Connection
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from pydantic import ValidationError
from .models import WeatherReading

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "datos.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Factores de escala para almacenamiento eficiente en enteros de 1 decimal
SCALE_FACTOR = 10.0
SCALED_FIELDS = ['temperatura', 'lluvia', 'viento_medio', 'rafaga', 'direccion']


def debugprint(msg: str, debug_flag: bool = False) -> None:
    if debug_flag:
        print(msg)


def scale_value(value: Optional[float]) -> int:
    """Convierte un valor float en entero escalado."""
    if value is None:
        return 0
    return int(round(value * SCALE_FACTOR))


def descale_value(value: Optional[int]) -> float:
    """Convierte un entero escalado de la base de datos a su float real."""
    if value is None:
        return 0.0
    return value / SCALE_FACTOR


def process_db_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Mapea una fila de SQLite a un diccionario con valores en unidades reales."""
    record = dict(row)
    for field in SCALED_FIELDS:
        if field in record and record[field] is not None:
            record[field] = descale_value(record[field])
    return record


def get_db():
    """
    Dependency injection para FastAPI.
    Abre conexión con optimizaciones WAL y la cierra al finalizar la solicitud.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # WAL para escrituras concurrentes
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS datos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            temperatura INTEGER,
            humedad INTEGER,
            lluvia INTEGER,
            viento_medio INTEGER,
            rafaga INTEGER,
            direccion INTEGER,
            rssi INTEGER,
            uptime INTEGER,
            raw_hex TEXT
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_datos_timestamp ON datos(timestamp);")
    conn.commit()
    conn.close()


def insert_data(db: Connection, data: Dict[str, Any], hex_string: str, rssi: int, uptime: int) -> None:
    cur = db.cursor()
    try:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        cur.execute("""
            INSERT INTO datos (
                timestamp, temperatura, humedad, lluvia,
                viento_medio, rafaga, direccion, rssi, uptime, raw_hex
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_iso,
            data.get("temperatura"),
            data.get("humedad"),
            data.get("lluvia"),
            data.get("viento_medio"),
            data.get("rafaga"),
            data.get("direccion"),
            rssi,
            uptime,
            hex_string
        ))
        db.commit()
    except Exception as e:
        print(f"Error crítico en insert_data: {e}")


def get_rain_24h(db: Connection) -> Dict[str, float]:
    """
    Calcula la lluvia acumulada en las últimas 24 horas considerando
    posibles reinicios del contador del pluviómetro.
    """
    cursor = db.cursor()
    # Usamos el índice idx_datos_timestamp
    time_limit = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S.%f")

    cursor.execute("""
        SELECT lluvia FROM datos WHERE timestamp >= ? ORDER BY timestamp ASC
    """, (time_limit,))

    rows = cursor.fetchall()

    if not rows:
        return {"rain_24h": 0.0, "rain_accumulated": 0.0}

    rain_values_mm = [v[0] / SCALE_FACTOR for v in rows if v[0] is not None]

    if not rain_values_mm:
        return {"rain_24h": 0.0, "rain_accumulated": 0.0}

    rain_24h = 0.0
    rain_accumulated = rain_values_mm[-1]

    if len(rain_values_mm) > 1:
        for i in range(1, len(rain_values_mm)):
            current = rain_values_mm[i]
            previous = rain_values_mm[i - 1]

            if current >= previous:
                rain_24h += (current - previous)
            else:
                # Detección de reset de contador (ej. 409.5 -> 0.0)
                rain_24h += (previous - current)

    return {
        "rain_24h": round(rain_24h, 1),
        "rain_accumulated": round(rain_accumulated, 1)
    }


def get_recent(db: Connection, limit: int = 1) -> List[Dict[str, Any]]:
    """Obtiene los últimos registros registrados ordenados por ID descendente."""
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    try:
        cur.execute("SELECT * FROM datos ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [process_db_row(row) for row in rows]
    except Exception as e:
        print(f"Error en get_recent: {e}")
        return []


def get_all_records(db: Connection) -> List[Dict[str, Any]]:
    """Obtiene todos los registros cronológicos para exportación CSV."""
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    try:
        cur.execute("SELECT * FROM datos ORDER BY id ASC")
        rows = cur.fetchall()
        return [process_db_row(row) for row in rows]
    except Exception as e:
        print(f"Error en get_all_records: {e}")
        return []


def decode_raw_msg(msg: bytes) -> Dict[str, Any]:
    """
    Decodifica y valida el payload binario recibido del ESP32.
    Retorna diccionario escalado para almacenamiento o {} si falla.
    """
    try:
        reading = WeatherReading.from_raw_bytes(msg)
        return reading.to_db_dict()
    except (ValueError, ValidationError) as e:
        print(f"Payload descartado por validación: {e}")
        return {}
