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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id TEXT NOT NULL,
                metric_key TEXT NOT NULL,
                PRIMARY KEY (user_id, metric_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ico_alerts (
                block_id TEXT PRIMARY KEY,
                scheduled_notified_at INTEGER,
                release_notified_at INTEGER
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


def metric_exists(metric_key: str) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "SELECT 1 FROM metrics WHERE key = ?",
            (metric_key,),
        )
        return cur.fetchone() is not None


def add_subscription(user_id: int, metric_key: str) -> bool:
    """
    Returns True if a new subscription was created.
    """
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO subscriptions (user_id, metric_key)
            VALUES (?, ?)
            """,
            (str(user_id), metric_key),
        )
        conn.commit()
        return cur.rowcount > 0


def list_subscriptions(user_id: int) -> List[str]:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """
            SELECT metric_key
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY metric_key
            """,
            (str(user_id),),
        )
        rows = cur.fetchall()
    return [row[0] for row in rows]


def remove_subscription(user_id: int, metric_key: str) -> bool:
    """
    Returns True if a subscription was removed.
    """
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """
            DELETE FROM subscriptions
            WHERE user_id = ? AND metric_key = ?
            """,
            (str(user_id), metric_key),
        )
        conn.commit()
        return cur.rowcount > 0


def subscriptions_for_metric(metric_key: str) -> List[int]:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """
            SELECT user_id
            FROM subscriptions
            WHERE metric_key = ?
            """,
            (metric_key,),
        )
        rows = cur.fetchall()

    return [int(user_id) for (user_id,) in rows]


# ICO alert helpers

def ico_alert_state(block_id: str) -> Dict[str, Optional[int]]:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """
            SELECT scheduled_notified_at, release_notified_at
            FROM ico_alerts
            WHERE block_id = ?
            """,
            (block_id,),
        )
        row = cur.fetchone()

    if not row:
        return {"scheduled": None, "released": None}

    return {"scheduled": row[0], "released": row[1]}


def mark_ico_scheduled(block_id: str, ts: Optional[int] = None):
    ts = ts or int(time.time())
    with _LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO ico_alerts (block_id, scheduled_notified_at)
            VALUES (?, ?)
            ON CONFLICT(block_id) DO UPDATE SET
                scheduled_notified_at = excluded.scheduled_notified_at
            """,
            (block_id, ts),
        )
        conn.commit()


def mark_ico_released(block_id: str, ts: Optional[int] = None):
    ts = ts or int(time.time())
    with _LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO ico_alerts (block_id, release_notified_at)
            VALUES (?, ?)
            ON CONFLICT(block_id) DO UPDATE SET
                release_notified_at = excluded.release_notified_at
            """,
            (block_id, ts),
        )
        conn.commit()
