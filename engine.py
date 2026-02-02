from typing import List, Dict

from db.repo import init_db, record_sample, get_last

from adapters.defi.silo import fetch as fetch_silo
from adapters.defi.euler import fetch as fetch_euler
from adapters.defi.aave import fetch as fetch_aave

from alerts.caps import handle_caps_metric
from alerts.rates import handle_rate_metric


def run_once() -> List[Dict]:
    """
    Run all fetchers once, store samples, evaluate alerts.

    Alerting models:
    - Rates: delta-based, sticky anchor
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

            # always record current value
            record_sample(
                metric_key=key,
                name=name,
                value=value,
                unit=unit,
            )

            if unit == "ratio":
                alerts.extend(
                    handle_caps_metric(
                        key=key,
                        name=name,
                        value=value,
                        last_value=last_value,
                    )
                )
            else:
                alerts.extend(
                    handle_rate_metric(
                        key=key,
                        name=name,
                        value=value,
                        unit=unit,
                    )
                )

    return alerts
