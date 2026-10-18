"""
Pruebas unitarias y de integración para la persistencia USB y la importación de datos.
"""

import os
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch

from backend.app.utils import resolve_db_path, get_db_path, init_db, insert_data, get_recent, descale_value
from scripts.import_thingspeak_2024 import validate_and_clean_record
from scripts.migrate_to_usb import migrate_database, get_db_stats, verify_sqlite_integrity


def test_resolve_db_path_with_env(tmp_path):
    custom_db = tmp_path / "custom_meteo" / "datos.db"
    with patch.dict(os.environ, {"METEO_DB_PATH": str(custom_db)}):
        resolved = resolve_db_path()
        assert resolved == custom_db
        assert custom_db.parent.exists()


def test_resolve_db_path_fallback(tmp_path):
    with patch.dict(os.environ, {}, clear=True):
        # Aseguramos que METEO_DB_PATH no está configurado
        os.environ.pop("METEO_DB_PATH", None)
        with patch("pathlib.Path.exists", return_value=False):
            resolved = resolve_db_path()
            assert resolved.name == "datos.db"
            assert "data" in str(resolved)


def test_resolve_db_path_usb_detected(tmp_path):
    mock_usb_file = tmp_path / "mnt" / "usb" / "meteo_data" / "datos.db"
    mock_usb_file.parent.mkdir(parents=True, exist_ok=True)
    mock_usb_file.touch()

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("METEO_DB_PATH", None)
        with patch("backend.app.utils.USB_DEFAULT_DB", mock_usb_file):
            resolved = resolve_db_path()
            assert resolved == mock_usb_file


def test_init_db_and_insert(tmp_path):
    test_db = tmp_path / "test_datos.db"
    with patch("backend.app.utils.get_db_path", return_value=test_db):
        init_db()
        assert test_db.exists()

        conn = sqlite3.connect(str(test_db))
        conn.row_factory = sqlite3.Row

        sample_data = {
            "temperatura": 215,
            "humedad": 55,
            "lluvia": 120,
            "viento_medio": 35,
            "rafaga": 50,
            "direccion": 1800
        }
        insert_data(conn, sample_data, "DEADBEEF", rssi=-65, uptime=3600)

        recent = get_recent(conn, limit=1)
        assert len(recent) == 1
        assert recent[0]["humedad"] == 55
        assert recent[0]["temperatura"] == 21.5
        assert recent[0]["lluvia"] == 12.0
        conn.close()


def test_thingspeak_data_cleaning():
    valid_feed = {
        "created_at": "2024-12-05T23:21:58Z",
        "entry_id": 42,
        "field1": "15.40000",
        "field2": "9.72222",
        "field3": "224.00000",
        "field4": "5.10000",
        "field5": "6.00000",
        "field6": "99.00000"
    }
    cleaned = validate_and_clean_record(valid_feed)
    assert cleaned is not None
    assert cleaned["temperatura"] == 97  # 9.72222 * 10 = 97
    assert cleaned["humedad"] == 99
    assert cleaned["lluvia"] == 154
    assert cleaned["viento_medio"] == 51
    assert cleaned["rafaga"] == 60
    assert cleaned["direccion"] == 2240
    assert cleaned["raw_hex"] == "THINGSPEAK_42"


def test_thingspeak_data_cleaning_incoherent_gust():
    # Ráfaga inferior a viento medio: debe ajustarse al viento medio
    feed = {
        "created_at": "2024-12-05T23:21:58Z",
        "entry_id": 43,
        "field1": "0.0",
        "field2": "15.0",
        "field3": "100.0",
        "field4": "10.0",
        "field5": "5.0",  # Ráfaga menor que viento medio
        "field6": "50.0"
    }
    cleaned = validate_and_clean_record(feed)
    assert cleaned is not None
    assert cleaned["viento_medio"] == 100
    assert cleaned["rafaga"] == 100  # Ajustado a viento_medio


def test_thingspeak_data_cleaning_invalid_temperature():
    # Temperatura absurda (+80 °C o -40 °C)
    invalid_feed = {
        "created_at": "2024-12-05T23:21:58Z",
        "entry_id": 44,
        "field1": "0.0",
        "field2": "85.0",  # Descartar
        "field3": "100.0",
        "field4": "2.0",
        "field5": "3.0",
        "field6": "50.0"
    }
    cleaned = validate_and_clean_record(invalid_feed)
    assert cleaned is None


def test_thingspeak_data_cleaning_invalid_humidity():
    # Humedad absurda (>100% o <=0%)
    invalid_feed = {
        "created_at": "2024-12-05T23:21:58Z",
        "entry_id": 45,
        "field1": "0.0",
        "field2": "20.0",
        "field3": "100.0",
        "field4": "2.0",
        "field5": "3.0",
        "field6": "150.0"  # Descartar
    }
    assert validate_and_clean_record(invalid_feed) is None


def test_database_migration_tool(tmp_path):
    src_db = tmp_path / "source" / "datos.db"
    dest_db = tmp_path / "dest_usb" / "meteo_data" / "datos.db"

    src_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(src_db))
    conn.execute("""
        CREATE TABLE datos (
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
    conn.execute("""
        INSERT INTO datos (timestamp, temperatura, humedad)
        VALUES ('2024-12-06T12:00:00.000000', 150, 60),
               ('2024-12-06T12:01:00.000000', 152, 61);
    """)
    conn.commit()
    conn.close()

    success = migrate_database(src_path=src_db, dest_path=dest_db, force=False, dry_run=False)
    assert success is True
    assert dest_db.exists()
    assert verify_sqlite_integrity(dest_db) is True

    dest_stats = get_db_stats(dest_db)
    assert dest_stats["total_rows"] == 2
