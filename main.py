import os
from datetime import datetime

from data.state import init_db, get_last_value, save_value
from fetchers.silo import fetch_usdc_borrow_rate as fetch_silo_usdc
from fetchers.euler import fetch_usdc_borrow_rate as fetch_euler_usdc
from notifier.discord import notify

# thresholds (rates are decimals, e.g. 0.089 = 8.9%)
SMALL_CHANGE = 0.0001   # 0.01%
BIG_CHANGE = 0.01       # 1.00%


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")

    init_db()

    sources = [
        fetch_silo_usdc(),
        fetch_euler_usdc(),
    ]

    print("=" * 50)
    print(f"Run @ {datetime.utcnow().isoformat()} UTC")
    print("-" * 50)

    for item in sources:
        base_key = item["key"]
        name = item["name"]
        value = item["rate"]

        print(f"{name}: {value:.4%}")

        last_key = f"{base_key}:last"
        baseline_key = f"{base_key}:baseline"

        last = get_last_value(last_key)
        baseline = get_last_value(baseline_key)

        # first observation
        if last is None:
            notify(
                webhook_url,
                f"{name} initial value: {value:.2%}"
            )
            save_value(last_key, value)
            save_value(baseline_key, value)
            continue

        baseline_triggered = False

        # 🚨 baseline alert (±1.00%)
        if baseline is not None:
            delta_baseline = value - baseline
            if abs(delta_baseline) >= BIG_CHANGE:
                direction = "⬆️" if delta_baseline > 0 else "⬇️"
                notify(
                    webhook_url,
                    f"🚨 {direction} {name} moved ≥ 1.00%\n"
                    f"Baseline: {baseline:.2%}\n"
                    f"Current: {value:.2%}"
                )
                save_value(baseline_key, value)
                baseline_triggered = True

        # 🔔 normal change alert (±0.01%), only if baseline didn't fire
        if not baseline_triggered:
            delta_last = value - last
            if abs(delta_last) >= SMALL_CHANGE:
                direction = "⬆️" if delta_last > 0 else "⬇️"
                notify(
                    webhook_url,
                    f"{direction} {name} changed\n"
                    f"Previous: {last:.2%}\n"
                    f"Current: {value:.2%}"
                )

        # always update last value
        save_value(last_key, value)

    print("=" * 50)


if __name__ == "__main__":
    main()