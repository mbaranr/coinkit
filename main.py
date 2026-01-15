import os
from data.state import init_db, get_last_value, save_value
from fetchers.silo import fetch_usdc_borrow_rate as fetch_silo_usdc
from fetchers.euler import fetch_usdc_borrow_rate as fetch_euler_usdc
from notifier.discord import notify

# absolute threshold: 1 percentage point (14% -> 15%)
THRESHOLD = 0.01


def main():
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]

    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")

    init_db()

    sources = [
        fetch_silo_usdc(),
        fetch_euler_usdc(),
    ]

    for item in sources:
        base_key = item["key"]
        name = item["name"]
        value = item["rate"]

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

        # notify on change > 1 percentage point
        delta_last = value - last

        if abs(delta_last) > THRESHOLD:
            direction = "⬆️" if delta_last > 0 else "⬇️"
            notify(
                webhook_url,
                f"{direction} {name} changed (>1.00%)\n"
                f"Previous: {last:.2%}\n"
                f"Current: {value:.2%}"
            )

        # threshold check (absolute percentage points)
        if baseline is not None:
            delta = value - baseline

            if abs(delta) >= THRESHOLD:
                direction = "⬆️" if delta > 0 else "⬇️"
                notify(
                    webhook_url,
                    f"🚨 {direction} {name} moved ≥ 1.00%\n"
                    f"Baseline: {baseline:.2%}\n"
                    f"Current: {value:.2%}"
                )
                # reset baseline after threshold hit
                save_value(baseline_key, value)

        # always update last value
        save_value(last_key, value)


if __name__ == "__main__":
    main()