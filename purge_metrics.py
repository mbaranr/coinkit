import argparse
import sqlite3
import os
import sys

DB_FILE = os.path.join(os.path.dirname(__file__), "state.db")


def purge_keys(db_path: str, keys: list[str]) -> dict[str, dict[str, int]]:
    """
    Delete each key (and its :anchor) from metrics and subscriptions.
    Returns a summary: {key: {metrics: N, subscriptions: N}}.
    """
    results = {}
    with sqlite3.connect(db_path) as conn:
        for key in keys:
            targets = [key, f"{key}:anchor"]
            metrics_deleted = 0
            subs_deleted = 0
            for target in targets:
                cur = conn.execute("DELETE FROM metrics WHERE key = ?", (target,))
                metrics_deleted += cur.rowcount
                cur = conn.execute(
                    "DELETE FROM subscriptions WHERE metric_key = ?", (target,)
                )
                subs_deleted += cur.rowcount
            conn.commit()
            results[key] = {"metrics": metrics_deleted, "subscriptions": subs_deleted}
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Purge metric keys from state.db.",
        epilog=(
            "Each key (and its :anchor sibling for rate metrics) is removed from\n"
            "the metrics table. All user subscriptions to that key are also deleted.\n"
            "\n"
            "Examples:\n"
            "  python scripts/purge_metrics.py euler:sentora:syrupusdc:pyusd:supply:cap_util\n"
            "  python scripts/purge_metrics.py key1 key2 key3\n"
            "  python scripts/purge_metrics.py euler:9summits:usdc:borrow:rate --db /path/to/state.db\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keys", nargs="+", help="Metric keys to delete")
    parser.add_argument("--db", default=DB_FILE, help="Path to state.db")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    results = purge_keys(args.db, args.keys)
    for key, counts in results.items():
        anchor_note = " (+ :anchor)" if counts["metrics"] > 1 else ""
        print(
            f"{key}{anchor_note}: "
            f"{counts['metrics']} metric row(s), "
            f"{counts['subscriptions']} subscription(s) removed"
        )


if __name__ == "__main__":
    main()
