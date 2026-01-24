import sqlite3
import time
from threading import Lock
from typing import Optional, List, Dict


_DB_FILE = "state.db"
_LOCK = Lock()


def _connect():
    return sqlite3.connect(_DB_FILE)


def init_db():
    with _LOCK, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                key TEXT PRIMARY KEY,
                name TEXT,
                value REAL,
                unit TEXT,
                updated_at INTEGER
            )
            """
        )
        conn.commit()


def record_sample(
    metric_key: str,
    name: str,
    value: float,
    unit: Optional[str] = None,
):
    now = int(time.time())

    with _LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO metrics (key, name, value, unit, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                name = excluded.name,
                unit = excluded.unit,
                updated_at = excluded.updated_at
            """,
            (metric_key, name, value, unit, now),
        )
        conn.commit()


def get_last(metric_key: str) -> Optional[float]:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "SELECT value FROM metrics WHERE key = ?",
            (metric_key,),
        )
        row = cur.fetchone()
        return float(row[0]) if row else None


def list_metrics() -> List[Dict]:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """
            SELECT key, name, unit
            FROM metrics
            ORDER BY key
            """
        )
        rows = cur.fetchall()

    return [
        {
            "key": key,
            "name": name,
            "unit": unit,
        }
        for key, name, unit in rows
    ]