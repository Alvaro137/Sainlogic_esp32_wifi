import sqlite3
from sqlite3 import Connection
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "datos.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Configuración de escalado para evitar Float en SQLite
SCALE_FACTOR = 10.0
SCALED_FIELDS = ["temperatura", "lluvia", "viento_medio", "rafaga", "direccion"]


def debugprint(msg: str, debug_flag: bool = False) -> None:
    if debug_flag:
        print(msg)


def scale_value(value: float) -> int:
    """Float -> Int escalado para almacenamiento eficiente."""
    if value is None:
        return 0
    return int(round(value * SCALE_FACTOR))


def descale_value(value: int) -> float:
    """Int escalado -> Float real para la API."""
    if value is None:
        return 0.0
    return value / SCALE_FACTOR


def process_db_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Mapea la fila de DB a diccionario aplicando desescalado."""
    record = dict(row)
    for field in SCALED_FIELDS:
        if field in record:
            record[field] = descale_value(record[field])
    return record


def get_db():
    """
    Dependency Injection para FastAPI.
    Gestiona la conexión (Open -> Yield -> Close).
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Optimización: WAL mode para mejor concurrencia en lecturas/escrituras
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Creación de db y tabla si no existe (se ejecuta al principio)."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    cur = conn.cursor()

    # Uso INTEGER escalados para optimizar almacenamiento pero conservar 1 decimal de precisión
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS datos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            temperatura INTEGER, humedad INTEGER, lluvia INTEGER,
            viento_medio INTEGER, rafaga INTEGER, direccion INTEGER,
            rssi INTEGER, uptime INTEGER,
            raw_hex TEXT
        );
    """
    )
    conn.commit()
    conn.close()


# OPERACIONES DE DATOS


def insert_data(
    db: Connection, data: Dict[str, Any], hex_string: str, rssi: int, uptime: int
) -> None:
    """Inserta los datos en la db. Requiere conexión inyectada."""
    print(f"Insertando datos: {data['temperatura']/10.0}°C, Uptime: {uptime}s")

    cur = db.cursor()
    try:
        cur.execute(
            """
            INSERT INTO datos (timestamp, temperatura, humedad, lluvia,
                viento_medio, rafaga, direccion, rssi, uptime, raw_hex
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.utcnow().isoformat(),
                data.get("temperatura"),
                data.get("humedad"),
                data.get("lluvia"),
                data.get("viento_medio"),
                data.get("rafaga"),
                data.get("direccion"),
                rssi,
                uptime,
                hex_string,
            ),
        )
        db.commit()
    except Exception as e:
        print(f"Error crítico DB en insert: {e}")


def get_rain_24h(db: Connection) -> Dict[str, float]:
    """
    Calcula lluvia acumulada en 24h.
    Maneja el caso de reinicio de contador del sensor.
    """
    cursor = db.cursor()
    time_limit = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    cursor.execute(
        """
        SELECT lluvia FROM datos WHERE timestamp >= ? ORDER BY timestamp ASC
    """,
        (time_limit,),
    )

    rows = cursor.fetchall()

    if not rows:
        return {"rain_24h": 0.0, "rain_accumulated": 0.0}

    # Detectar reinicios
    rain_values_mm = [v[0] / SCALE_FACTOR for v in rows]
    rain_24h = 0.0
    rain_accumulated = rain_values_mm[-1]

    if len(rain_values_mm) > 1:
        for i in range(1, len(rain_values_mm)):
            current = rain_values_mm[i]
            previous = rain_values_mm[i - 1]

            if current >= previous:
                rain_24h += current - previous
            else:
                # Detección de reset (ej. 409.5 -> 0.0).
                # Sumamos el offset para asegurarnos de que la lluvia acumulada nunca decrece.
                reset_amount = previous - current
                rain_24h += reset_amount

    return {
        "rain_24h": round(rain_24h, 1),
        "rain_accumulated": round(rain_accumulated, 1),
    }


def get_recent(db: Connection, limit: int = 1) -> List[Dict[str, Any]]:
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    try:
        cur.execute("SELECT * FROM datos ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [process_db_row(row) for row in rows]
    except Exception as e:
        print(f"Error lectura DB: {e}")
        return []


def get_all_records(db: Connection) -> List[Dict[str, Any]]:
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    try:
        cur.execute("SELECT * FROM datos ORDER BY timestamp ASC")
        rows = cur.fetchall()
        return [process_db_row(row) for row in rows]
    except Exception as e:
        print(f"Error lectura DB: {e}")
        return []


# DECODIFICACIÓN DEL MENSAJE (ver Readme.md)


def decode_raw_msg(msg: bytes) -> Dict[str, Any]:
    """Decodificación del mensaje binario propietario del sensor."""
    if len(msg) < 16:
        return {}
    data = msg[2:]

    # Bitmasking para extraer flags de viento
    flags_wind = data[1] & 0x0F
    wind_dir_msb = 1 if (flags_wind & 0x04) else 0
    wind_gust_msb = 1 if (flags_wind & 0x02) else 0
    wind_avg_msb = 1 if (flags_wind & 0x01) else 0

    # Reconstrucción de valores (LSB + MSB)
    viento_med = (data[2] | (wind_avg_msb << 8)) * 0.1
    rafaga = (data[3] | (wind_gust_msb << 8)) * 0.1
    direccion = float(data[4] | (wind_dir_msb << 8))

    raw_rain = ((data[5] & 0x0F) << 8) | data[6]
    lluvia = raw_rain * 0.1 + 642.2  # Offset calibración

    raw_temp = ((data[7] & 0x0F) << 8) | data[8]
    temp_c = (((raw_temp - 400) / 10.0) - 32) * (5.0 / 9.0)  # Conversión F a C

    hum = int(data[9])

    return {
        "temperatura": scale_value(temp_c),
        "humedad": hum,
        "viento_medio": scale_value(viento_med),
        "rafaga": scale_value(rafaga),
        "lluvia": scale_value(lluvia),
        "direccion": scale_value(direccion),
    }
