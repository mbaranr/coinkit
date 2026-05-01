import argparse
import os
import sys

# Allow running this script directly from repo root: `uv run python scripts/purge_metrics.py ...`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import purge_keys


DB_FILE = "state.db"


def main():
    parser = argparse.ArgumentParser(
        description="Purge metric keys from state.db.",
        epilog=(
            "Each key (and its :anchor sibling for rate metrics) is removed from\n"
            "the metrics table. All user subscriptions to that key are also deleted.\n"
            "\n"
            "Examples:\n"
            "  uv run python scripts/purge_metrics.py euler:sentora:syrupusdc:pyusd:supply:cap_util\n"
            "  uv run python scripts/purge_metrics.py key1 key2 key3\n"
            "  uv run python scripts/purge_metrics.py euler:9summits:usdc:borrow:rate --db /path/to/state.db\n"
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
