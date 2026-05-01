import os
import sqlite3
import tempfile
import unittest

from engine import ADAPTERS
from purge_metrics import purge_keys


REQUIRED_METRIC_KEYS = {"key", "name", "value", "unit", "adapter"}
ALLOWED_UNITS = {"rate", "ratio", "json"}


class TestAdapters(unittest.TestCase):
    """
    Shape-only contract tests. Hits live APIs (requires internet).
    Adding or removing a metric inside an adapter does not break these.
    """
    pass


def _make_adapter_test(adapter_name, mod):
    def test(self):
        metrics = mod.fetch()
        self.assertIsInstance(metrics, list)
        self.assertGreater(len(metrics), 0, f"{adapter_name} returned no metrics")

        for m in metrics:
            self.assertIsInstance(m, dict)
            self.assertGreaterEqual(set(m), REQUIRED_METRIC_KEYS)
            self.assertIn(m["unit"], ALLOWED_UNITS)
            self.assertEqual(m["adapter"], adapter_name)

            if m["unit"] == "json":
                self.assertIsInstance(m["value"], list)
            else:
                self.assertIsInstance(m["value"], (int, float))
    return test


for _name, _mod in ADAPTERS.items():
    setattr(TestAdapters, f"test_fetch_{_name}", _make_adapter_test(_name, _mod))


def _make_db(path: str):
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE metrics (
                key TEXT PRIMARY KEY,
                name TEXT,
                value REAL,
                unit TEXT,
                updated_at INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE subscriptions (
                user_id TEXT NOT NULL,
                metric_key TEXT NOT NULL,
                PRIMARY KEY (user_id, metric_key)
            )
        """)
        conn.commit()


def _insert_metric(conn, key, name="test", value=0.5, unit="ratio"):
    conn.execute(
        "INSERT INTO metrics (key, name, value, unit, updated_at) VALUES (?, ?, ?, ?, 0)",
        (key, name, value, unit),
    )


def _insert_subscription(conn, user_id, metric_key):
    conn.execute(
        "INSERT INTO subscriptions (user_id, metric_key) VALUES (?, ?)",
        (str(user_id), metric_key),
    )


def _keys_in_db(conn, table, column) -> set:
    cur = conn.execute(f"SELECT {column} FROM {table}")
    return {row[0] for row in cur.fetchall()}


class TestPurgeMetrics(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        _make_db(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_purge_removes_metric_row(self):
        with sqlite3.connect(self.db_path) as conn:
            _insert_metric(conn, "euler:sentora:syrupusdc:pyusd:supply:cap_util")
            conn.commit()

        purge_keys(self.db_path, ["euler:sentora:syrupusdc:pyusd:supply:cap_util"])

        with sqlite3.connect(self.db_path) as conn:
            keys = _keys_in_db(conn, "metrics", "key")
        self.assertNotIn("euler:sentora:syrupusdc:pyusd:supply:cap_util", keys)

    def test_purge_removes_anchor(self):
        key = "euler:9summits:usdc:borrow:rate"
        with sqlite3.connect(self.db_path) as conn:
            _insert_metric(conn, key, unit="rate")
            _insert_metric(conn, f"{key}:anchor", unit="rate")
            conn.commit()

        purge_keys(self.db_path, [key])

        with sqlite3.connect(self.db_path) as conn:
            keys = _keys_in_db(conn, "metrics", "key")
        self.assertNotIn(key, keys)
        self.assertNotIn(f"{key}:anchor", keys)

    def test_purge_removes_subscriptions(self):
        key = "euler:sentora:syrupusdc:rlusd:borrow:cap_util"
        with sqlite3.connect(self.db_path) as conn:
            _insert_metric(conn, key)
            _insert_subscription(conn, 111, key)
            _insert_subscription(conn, 222, key)
            conn.commit()

        purge_keys(self.db_path, [key])

        with sqlite3.connect(self.db_path) as conn:
            subs = _keys_in_db(conn, "subscriptions", "metric_key")
        self.assertNotIn(key, subs)

    def test_purge_leaves_other_keys_intact(self):
        key_to_delete = "euler:sentora:syrupusdc:pyusd:supply:cap_util"
        key_to_keep = "aave:ethereum:rlusd:supply:cap_util"
        with sqlite3.connect(self.db_path) as conn:
            _insert_metric(conn, key_to_delete)
            _insert_metric(conn, key_to_keep)
            _insert_subscription(conn, 1, key_to_keep)
            conn.commit()

        purge_keys(self.db_path, [key_to_delete])

        with sqlite3.connect(self.db_path) as conn:
            metric_keys = _keys_in_db(conn, "metrics", "key")
            sub_keys = _keys_in_db(conn, "subscriptions", "metric_key")
        self.assertIn(key_to_keep, metric_keys)
        self.assertIn(key_to_keep, sub_keys)

    def test_purge_multiple_keys(self):
        keys = [
            "euler:sentora:syrupusdc:pyusd:supply:cap_util",
            "euler:sentora:syrupusdc:rlusd:supply:cap_util",
        ]
        with sqlite3.connect(self.db_path) as conn:
            for k in keys:
                _insert_metric(conn, k)
            conn.commit()

        purge_keys(self.db_path, keys)

        with sqlite3.connect(self.db_path) as conn:
            remaining = _keys_in_db(conn, "metrics", "key")
        for k in keys:
            self.assertNotIn(k, remaining)

    def test_purge_nonexistent_key_is_safe(self):
        purge_keys(self.db_path, ["does:not:exist"])  # should not raise

    def test_returns_correct_counts(self):
        key = "euler:9summits:usdc:borrow:rate"
        with sqlite3.connect(self.db_path) as conn:
            _insert_metric(conn, key, unit="rate")
            _insert_metric(conn, f"{key}:anchor", unit="rate")
            _insert_subscription(conn, 1, key)
            conn.commit()

        results = purge_keys(self.db_path, [key])
        self.assertEqual(results[key]["metrics"], 2)       # key + anchor
        self.assertEqual(results[key]["subscriptions"], 1)


if __name__ == "__main__":
    unittest.main()
