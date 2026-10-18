#!/usr/bin/env python3
"""
Script de migración segura de datos SQLite hacia pendrive USB para la estación meteorológica.

Uso habitual en Orange Pi:
    python3 scripts/migrate_to_usb.py
    o especificando rutas:
    python3 scripts/migrate_to_usb.py --src /home/varo/meteo_lite/backend/data/datos.db --dest /mnt/usb/meteo_data/datos.db
"""

import sys
import os
import argparse
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# Rutas estándar del sistema en Orange Pi y fallback de desarrollo
DEFAULT_ORANGE_PI_SRC = Path("/home/varo/meteo_lite/backend/data/datos.db")
DEFAULT_USB_DEST = Path("/mnt/usb/meteo_data/datos.db")
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_LOCAL_SRC = PROJECT_ROOT / "backend" / "data" / "datos.db"


def find_default_source() -> Path:
    """Detecta la mejor ruta de origen disponible."""
    if DEFAULT_ORANGE_PI_SRC.exists():
        return DEFAULT_ORANGE_PI_SRC
    if DEFAULT_LOCAL_SRC.exists():
        return DEFAULT_LOCAL_SRC
    return DEFAULT_LOCAL_SRC


def get_db_stats(db_path: Path) -> dict:
    """Obtiene estadísticas básicas de la tabla datos en una base de datos SQLite."""
    if not db_path.exists():
        return {"exists": False}

    stats = {
        "exists": True,
        "size_bytes": db_path.stat().st_size,
        "size_mb": round(db_path.stat().st_size / (1024 * 1024), 2),
        "total_rows": 0,
        "first_timestamp": None,
        "last_timestamp": None,
        "tables": []
    }

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        stats["tables"] = tables

        if "datos" in tables:
            cur.execute("SELECT COUNT(*) FROM datos;")
            stats["total_rows"] = cur.fetchone()[0]

            cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM datos;")
            row = cur.fetchone()
            if row:
                stats["first_timestamp"] = row[0]
                stats["last_timestamp"] = row[1]
        conn.close()
    except Exception as e:
        stats["error"] = str(e)

    return stats


def verify_sqlite_integrity(db_path: Path) -> bool:
    """Ejecuta PRAGMA integrity_check sobre la base de datos."""
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchall()
        conn.close()
        return len(res) == 1 and res[0][0] == "ok"
    except Exception as e:
        print(f"[ERROR] Fallo al verificar integridad de {db_path}: {e}")
        return False


def migrate_database(src_path: Path, dest_path: Path, force: bool = False, dry_run: bool = False) -> bool:
    """
    Realiza la migración de origen a destino usando SQLite online backup y checkpoint de WAL.
    """
    print("=" * 65)
    print("  MIGRACIÓN DE BASE DE DATOS METEOROLÓGICA A PENDRIVE USB")
    print("=" * 65)
    print(f"Origen:  {src_path}")
    print(f"Destino: {dest_path}")
    print(f"Modo:    {'SIMULACIÓN (--dry-run)' if dry_run else 'EJECUCIÓN REAL'}")
    print("-" * 65)

    if not src_path.exists():
        print(f"[ERROR] El archivo de origen no existe: {src_path}")
        return False

    src_stats = get_db_stats(src_path)
    if "error" in src_stats:
        print(f"[ERROR] El origen no es una base de datos SQLite válida: {src_stats['error']}")
        return False

    print(f"Estadísticas de origen ({src_path.name}):")
    print(f"  * Tamaño: {src_stats['size_mb']} MB ({src_stats['size_bytes']} bytes)")
    print(f"  * Registros en 'datos': {src_stats['total_rows']}")
    print(f"  * Primer timestamp:     {src_stats['first_timestamp']}")
    print(f"  * Último timestamp:     {src_stats['last_timestamp']}")
    print("-" * 65)

    # Validar destino
    dest_dir = dest_path.parent
    if dest_path.exists():
        if not force:
            print(f"[AVISO] El archivo destino ya existe: {dest_path}")
            dest_stats = get_db_stats(dest_path)
            print(f"  * Tamaño actual: {dest_stats.get('size_mb', 0)} MB")
            print(f"  * Registros actuales: {dest_stats.get('total_rows', 0)}")
            print("Para sobrescribir este archivo, vuelva a ejecutar con la bandera --force")
            return False
        else:
            print(f"[AVISO] Bandera --force activada. El destino existente será sobrescrito.")

    if dry_run:
        print("[DRY-RUN] Comprobación de destino:")
        print(f"  * Directorio destino: {dest_dir}")
        print(f"  * Existe directorio:  {dest_dir.exists()}")
        print("[DRY-RUN] Simulación completada con éxito. No se realizaron cambios.")
        return True

    # Asegurar directorio de destino
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[ERROR] No se pudo crear el directorio destino {dest_dir}: {e}")
        print("Asegúrate de que el pendrive está montado y el usuario tiene permisos.")
        return False

    # Copia segura con SQLite Backup API
    print("Iniciando copia y consolidación de páginas SQLite...")
    try:
        # 1. Consolidar WAL en el origen si existe
        src_conn = sqlite3.connect(str(src_path))
        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

        # 2. Conectar a destino
        dest_conn = sqlite3.connect(str(dest_path))

        # 3. SQLite backup online
        src_conn.backup(dest_conn, pages=250)

        # 4. Configurar WAL en destino
        dest_conn.execute("PRAGMA journal_mode=WAL;")
        dest_conn.execute("PRAGMA synchronous=NORMAL;")
        dest_conn.commit()

        src_conn.close()
        dest_conn.close()
        print("[OK] Copia SQLite consolidada con éxito.")
    except Exception as e:
        print(f"[ERROR] Error durante el proceso de backup SQLite: {e}")
        return False

    # Verificar integridad en destino
    print("Verificando integridad en la base de datos destino...")
    if not verify_sqlite_integrity(dest_path):
        print("[ERROR] La verificación de integridad en el destino falló. El archivo podría estar dañado.")
        return False
    print("[OK] Integridad de SQLite verificada correctamente (PRAGMA integrity_check = ok).")

    # Comparar estadísticas
    dest_stats = get_db_stats(dest_path)
    print("-" * 65)
    print(f"Estadísticas de destino ({dest_path.name}):")
    print(f"  * Tamaño: {dest_stats['size_mb']} MB ({dest_stats['size_bytes']} bytes)")
    print(f"  * Registros en 'datos': {dest_stats['total_rows']}")
    print(f"  * Primer timestamp:     {dest_stats['first_timestamp']}")
    print(f"  * Último timestamp:     {dest_stats['last_timestamp']}")
    print("-" * 65)

    if src_stats['total_rows'] == dest_stats['total_rows']:
        print("[OK] ¡MIGRACIÓN COMPLETADA CON ÉXITO!")
        print(f"Total de {dest_stats['total_rows']} lecturas migradas al pendrive USB sin pérdida.")
        return True
    else:
        print(f"[ADVERTENCIA] Discrepancia en número de filas: origen={src_stats['total_rows']}, destino={dest_stats['total_rows']}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Migra la base de datos SQLite de la estación meteorológica al pendrive USB."
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=find_default_source(),
        help=f"Ruta a la base de datos origen (por defecto: {find_default_source()})"
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_USB_DEST,
        help=f"Ruta a la base de datos destino en USB (por defecto: {DEFAULT_USB_DEST})"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribe el archivo de destino si ya existe"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la migración sin escribir en disco"
    )

    args = parser.parse_args()

    success = migrate_database(
        src_path=args.src,
        dest_path=args.dest,
        force=args.force,
        dry_run=args.dry_run
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
