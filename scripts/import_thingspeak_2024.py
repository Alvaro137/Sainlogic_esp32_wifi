#!/usr/bin/env python3
"""
Script para descargar, limpiar e importar el histórico de ThingSpeak (Canal 2770121)
a la base de datos persistente SQLite de la estación meteorológica Sainlogic.

Canal ThingSpeak: 2770121 (Estacion_meteorologica_jose, Espadaña)
Campos:
  - field1: lluvia (acumulado en mm)
  - field2: temperatura (°C)
  - field3: direccion_viento (grados 0-360)
  - field4: viento_medio (m/s)
  - field5: rafaga (m/s)
  - field6: humedad (%)

Uso:
  # Importar histórico de 2024 a la base de datos activa:
  python3 scripts/import_thingspeak_2024.py

  # Importar todo el histórico completo (desde inicio en 2024 hasta la actualidad):
  python3 scripts/import_thingspeak_2024.py --all

  # Simular sin escribir en la base de datos:
  python3 scripts/import_thingspeak_2024.py --dry-run
"""

import sys
import os
import time
import argparse
import sqlite3
import urllib.request
import urllib.error
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set

# Ajuste de path para importar módulos de backend si están disponibles
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from backend.app.utils import get_db_path, init_db, SCALE_FACTOR
except ImportError:
    # Fallback si se ejecuta de forma aislada
    SCALE_FACTOR = 10.0

    def get_db_path() -> Path:
        env_path = os.getenv("METEO_DB_PATH")
        if env_path:
            return Path(env_path).resolve()
        usb_db = Path("/mnt/usb/meteo_data/datos.db")
        if usb_db.exists():
            return usb_db
        return PROJECT_ROOT / "backend" / "data" / "datos.db"

    def init_db() -> None:
        p = get_db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p))
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


DEFAULT_CHANNEL_ID = 2770121
DEFAULT_START_2024 = "2024-12-01T00:00:00Z"
DEFAULT_END_2024 = "2024-12-31T23:59:59Z"


def fetch_thingspeak_window(channel_id: int, start_iso: str, end_iso: str, max_retries: int = 5) -> List[Dict[str, Any]]:
    """
    Descarga una ventana temporal de feeds desde ThingSpeak.
    Maneja reintentos con backoff exponencial.
    Si la ventana alcanza el límite de 8000 registros, la subdivide recursivamente a la mitad.
    """
    url = (
        f"https://api.thingspeak.com/channels/{channel_id}/feeds.json"
        f"?start={urllib.parse.quote(start_iso)}&end={urllib.parse.quote(end_iso)}"
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "MeteoEspadana-Importer/1.0", "Accept": "application/json"}
    )

    data = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8")
                data = json.loads(content)
                break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = (attempt + 1) * 3
                print(f"[ThingSpeak] Rate limit (429). Esperando {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[ThingSpeak] Error HTTP {e.code} en {url}. Reintentando ({attempt+1}/{max_retries})...")
                time.sleep(2)
        except Exception as e:
            print(f"[ThingSpeak] Error de red ({e}). Reintentando ({attempt+1}/{max_retries})...")
            time.sleep(2)

    if data is None or "feeds" not in data:
        print(f"[ERROR] No se pudo obtener datos para intervalo {start_iso} - {end_iso}")
        return []

    feeds = data["feeds"]

    # Si ThingSpeak devuelve exactamente 8000 registros, es probable que haya truncado datos
    if len(feeds) >= 8000:
        dt_start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        dt_end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        duration = (dt_end - dt_start).total_seconds()

        # Si el intervalo es de más de 10 minutos, podemos subdividirlo
        if duration > 600:
            midpoint = dt_start + timedelta(seconds=duration / 2)
            mid_iso = midpoint.strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"[INFO] Ventana saturada ({len(feeds)} registros). Subdividiendo en dos bloques...")
            left = fetch_thingspeak_window(channel_id, start_iso, mid_iso, max_retries)
            right = fetch_thingspeak_window(channel_id, mid_iso, end_iso, max_retries)
            return left + right

    return feeds


def validate_and_clean_record(feed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Valida, limpia y escala un registro recibido de ThingSpeak.
    Devuelve diccionario listo para insertar en SQLite o None si es inválido.
    """
    # 1. Parsear timestamp
    raw_ts = feed.get("created_at")
    if not raw_ts:
        return None

    try:
        # Formatos comunes de ThingSpeak: '2024-12-05T23:21:58Z' o '2024-12-05 23:21:58 UTC'
        if "UTC" in raw_ts:
            dt = datetime.strptime(raw_ts.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        
        # Formato ISO homogéneo con la aplicación: YYYY-MM-DDTHH:MM:SS.000000
        iso_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S.000000")
    except Exception:
        return None

    # 2. Temperatura (field2) en °C
    # Rango físico razonable: -20.0 °C a 55.0 °C
    try:
        temp_val = float(feed.get("field2"))
        if not (-20.0 <= temp_val <= 55.0):
            return None
    except (ValueError, TypeError):
        return None

    # 3. Humedad (field6) en %
    # Rango físico: 1% a 100%
    try:
        hum_val = float(feed.get("field6"))
        if not (1.0 <= hum_val <= 100.0):
            return None
        hum_int = int(round(hum_val))
    except (ValueError, TypeError):
        return None

    # 4. Viento medio (field4) en m/s
    try:
        viento_val = float(feed.get("field4") or 0.0)
        if not (0.0 <= viento_val <= 150.0):
            return None
    except (ValueError, TypeError):
        viento_val = 0.0

    # 5. Ráfaga (field5) en m/s
    try:
        rafaga_val = float(feed.get("field5") or 0.0)
        if not (0.0 <= rafaga_val <= 200.0):
            return None
        # Coherencia física: la ráfaga no puede ser inferior al viento medio
        if rafaga_val < viento_val:
            rafaga_val = viento_val
    except (ValueError, TypeError):
        rafaga_val = viento_val

    # 6. Dirección del viento (field3) en grados (0-360)
    try:
        dir_val = float(feed.get("field3") or 0.0)
        if not (0.0 <= dir_val <= 360.0):
            dir_val = 0.0
    except (ValueError, TypeError):
        dir_val = 0.0

    # 7. Lluvia (field1) en mm (acumulado)
    # Monotonía o reseteos de balancín: no negativos y < 2000 mm
    try:
        rain_val = float(feed.get("field1") or 0.0)
        if rain_val < 0.0 or rain_val > 2000.0:
            return None
    except (ValueError, TypeError):
        rain_val = 0.0

    entry_id = feed.get("entry_id", 0)

    # Escalado para SQLite (idéntico al backend)
    return {
        "timestamp": iso_timestamp,
        "temperatura": int(round(temp_val * SCALE_FACTOR)),
        "humedad": hum_int,
        "lluvia": int(round(rain_val * SCALE_FACTOR)),
        "viento_medio": int(round(viento_val * SCALE_FACTOR)),
        "rafaga": int(round(rafaga_val * SCALE_FACTOR)),
        "direccion": int(round(dir_val * SCALE_FACTOR)),
        "rssi": 0,
        "uptime": 0,
        "raw_hex": f"THINGSPEAK_{entry_id}"
    }


def get_existing_timestamps(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> Set[str]:
    """Obtiene el conjunto de timestamps ya existentes en el rango de búsqueda."""
    cur = conn.cursor()
    # Permitir buscar timestamps con o sin microsegundos
    cur.execute(
        "SELECT timestamp FROM datos WHERE timestamp >= ? AND timestamp <= ?",
        (start_iso[:19], end_iso[:19] + "Z")
    )
    return {row[0] for row in cur.fetchall()}


def import_thingspeak(
    channel_id: int,
    db_path: Path,
    start_time: datetime,
    end_time: datetime,
    step_hours: int = 12,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Descarga en bloques de `step_hours` horas, deduplica, valida e inserta registros.
    """
    print("=" * 65)
    print("  IMPORTACIÓN DE HISTÓRICO THINGSPEAK A BASE DE DATOS")
    print("=" * 65)
    print(f"Canal ThingSpeak: {channel_id}")
    print(f"Base de datos:    {db_path}")
    print(f"Intervalo inicio: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Intervalo fin:    {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Paso de consulta: {step_hours} horas por petición")
    print(f"Modo:             {'SIMULACIÓN (--dry-run)' if dry_run else 'ESCRITURA REAL'}")
    print("-" * 65)

    if not dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db()
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    else:
        conn = None

    stats = {
        "total_fetched": 0,
        "duplicates_skipped": 0,
        "invalid_discarded": 0,
        "inserted": 0,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }

    current_start = start_time
    delta = timedelta(hours=step_hours)

    insert_query = """
        INSERT INTO datos (
            timestamp, temperatura, humedad, lluvia,
            viento_medio, rafaga, direccion, rssi, uptime, raw_hex
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    while current_start < end_time:
        current_end = min(current_start + delta, end_time)
        s_iso = current_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        e_iso = current_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        print(f"[*] Consultando bloque: {s_iso} -> {e_iso} ...", end=" ", flush=True)

        feeds = fetch_thingspeak_window(channel_id, s_iso, e_iso)
        stats["total_fetched"] += len(feeds)

        if not feeds:
            print("0 registros.")
            current_start = current_end
            time.sleep(0.5)  # Respetar rate limits de ThingSpeak
            continue

        # Cargar timestamps existentes para deduplicación eficiente
        existing_ts = set()
        if conn is not None:
            existing_ts = get_existing_timestamps(conn, s_iso, e_iso)

        batch_to_insert = []
        for feed in feeds:
            cleaned = validate_and_clean_record(feed)
            if cleaned is None:
                stats["invalid_discarded"] += 1
                continue

            ts = cleaned["timestamp"]
            # Deduplicación: comprobar si ya existe con microsegundos o sin ellos
            if ts in existing_ts or ts[:19] in existing_ts or (ts[:19] + "Z") in existing_ts:
                stats["duplicates_skipped"] += 1
                continue

            batch_to_insert.append((
                cleaned["timestamp"],
                cleaned["temperatura"],
                cleaned["humedad"],
                cleaned["lluvia"],
                cleaned["viento_medio"],
                cleaned["rafaga"],
                cleaned["direccion"],
                cleaned["rssi"],
                cleaned["uptime"],
                cleaned["raw_hex"]
            ))
            existing_ts.add(ts)

        if batch_to_insert and not dry_run and conn is not None:
            cur = conn.cursor()
            cur.executemany(insert_query, batch_to_insert)
            conn.commit()
            stats["inserted"] += len(batch_to_insert)
        elif dry_run:
            stats["inserted"] += len(batch_to_insert)

        print(f"{len(feeds)} recibidos ({len(batch_to_insert)} nuevos, {len(feeds)-len(batch_to_insert)} omitidos).")
        current_start = current_end
        time.sleep(0.5)

    if conn is not None:
        conn.close()

    print("-" * 65)
    print("[OK] RESUMEN DE IMPORTACION THINGSPEAK:")
    print(f"  * Total feeds descargados:    {stats['total_fetched']}")
    print(f"  * Duplicados ya existentes:   {stats['duplicates_skipped']}")
    print(f"  * Descartados por validacion: {stats['invalid_discarded']}")
    print(f"  * Nuevos insertados en SQLite:{stats['inserted']}")
    print("=" * 65)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Descarga e importa datos históricos de ThingSpeak al SQLite de la estación meteorológica."
    )
    parser.add_argument(
        "--channel-id",
        type=int,
        default=DEFAULT_CHANNEL_ID,
        help=f"ID del canal público de ThingSpeak (por defecto: {DEFAULT_CHANNEL_ID})"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=get_db_path(),
        help=f"Ruta a la base de datos destino (por defecto detecta pendrive o fallback: {get_db_path()})"
    )
    parser.add_argument(
        "--start",
        type=str,
        default=DEFAULT_START_2024,
        help=f"Fecha y hora de inicio UTC ISO-8601 (por defecto: {DEFAULT_START_2024})"
    )
    parser.add_argument(
        "--end",
        type=str,
        default=DEFAULT_END_2024,
        help=f"Fecha y hora de fin UTC ISO-8601 (por defecto: {DEFAULT_END_2024})"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Descarga todo el histórico disponible (desde 2024-12-05 hasta la fecha actual)"
    )
    parser.add_argument(
        "--step-hours",
        type=int,
        default=12,
        help="Tamaño del bloque temporal por llamada a ThingSpeak en horas (por defecto: 12)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Descarga y valida sin escribir en la base de datos"
    )

    args = parser.parse_args()

    if args.all:
        start_dt = datetime(2024, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime.now(timezone.utc)
    else:
        start_dt = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(args.end.replace("Z", "+00:00"))

    import_thingspeak(
        channel_id=args.channel_id,
        db_path=args.db_path,
        start_time=start_dt,
        end_time=end_dt,
        step_hours=args.step_hours,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
