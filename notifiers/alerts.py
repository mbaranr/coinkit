from typing import List, Dict

from storage.sqlite import (
    init_db,
    record_sample,
    get_last,
)

from fetchers.silo import fetch as fetch_silo
from fetchers.euler import fetch as fetch_euler
from fetchers.aave import fetch as fetch_aave


MINOR_CHANGE = 0.01   # 1%
MAJOR_CHANGE = 0.10   # 10%


def _baseline_key(metric_key: str) -> str:
    return f"{metric_key}:baseline"


def run_once() -> List[Dict]:
    """
    Run all fetchers once, store samples, evaluate alerts.

    Two alerting models:
    - Rates: delta-based, sticky baseline
    - Caps: state-based (full vs not full)
    """
    init_db()

    alerts: List[Dict] = []

    fetchers = [
        fetch_silo,
        fetch_euler,
        fetch_aave,
    ]

    for fetcher in fetchers:
        metrics = fetcher()

        for metric in metrics:
            key = metric["key"]
            name = metric["name"]
            value = float(metric["value"])
            unit = metric.get("unit")

            last_value = get_last(key)

            # always record the current value
            record_sample(
                metric_key=key,
                name=name,
                value=value,
                unit=unit,
            )

            # caps logic
            if unit == "ratio":
                # first observation: no alert
                if last_value is None:
                    continue

                was_full = last_value >= 1.0
                is_full = value >= 1.0

                # transition: not full -> full
                if not was_full and is_full:
                    alerts.append(
                        {
                            "category": "caps",
                            "level": "minor",
                            "metric_key": key,
                            "message": (
                                f"🧢 {name} has reached its cap\n"
                                f"Usage: 100%"
                            ),
                        }
                    )

                # transition: full -> not full
                elif was_full and not is_full:
                    alerts.append(
                        {
                            "category": "caps",
                            "level": "major",
                            "metric_key": key,
                            "message": (
                                f"🚨 {name} is no longer at its cap\n"
                                f"Usage: {value:.2%}"
                            ),
                        }
                    )

                continue  # caps do not use baseline logic

            # rates logic (delta-based)

            baseline_key = _baseline_key(key)
            baseline = get_last(baseline_key)

            # first observation: set baseline
            if baseline is None:
                record_sample(
                    metric_key=baseline_key,
                    name=f"{name} (baseline)",
                    value=value,
                    unit=unit,
                )
                alerts.append(
                    {
                        "category": "rates",
                        "level": "minor",
                        "metric_key": key,
                        "message": f"{name} initial value: {value:.2%}",
                    }
                )
                continue

            delta = value - baseline
            abs_delta = abs(delta)

            # major alert
            if abs_delta >= MAJOR_CHANGE:
                direction = "⬆️" if delta > 0 else "⬇️"

                alerts.append(
                    {
                        "category": "rates",
                        "level": "major",
                        "metric_key": key,
                        "message": (
                            f"🚨🚨 {direction} {name} moved ≥ 10%\n"
                            f"Baseline: {baseline:.2%}\n"
                            f"Current: {value:.2%}"
                        ),
                    }
                )

                record_sample(
                    metric_key=baseline_key,
                    name=f"{name} (baseline)",
                    value=value,
                    unit=unit,
                )

            # minor alert
            elif abs_delta >= MINOR_CHANGE:
                direction = "⬆️" if delta > 0 else "⬇️"

                alerts.append(
                    {
                        "category": "rates",
                        "level": "minor",
                        "metric_key": key,
                        "message": (
                            f"🚨 {direction} {name} moved ≥ 1%\n"
                            f"Baseline: {baseline:.2%}\n"
                            f"Current: {value:.2%}"
                        ),
                    }
                )

                record_sample(
                    metric_key=baseline_key,
                    name=f"{name} (baseline)",
                    value=value,
                    unit=unit,
                )

    return alerts