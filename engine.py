from typing import List, Dict

from db.repo import init_db, record_sample, get_last

from adapters.defi.silo import fetch as fetch_silo
from adapters.defi.euler import fetch as fetch_euler
from adapters.defi.aave import fetch as fetch_aave
from adapters.defi.dolomite import fetch as fetch_dolomite
from adapters.gov.metadao import fetch as fetch_metadao

from alerts.caps import handle_caps_metric
from alerts.rates import handle_rate_metric
from alerts.icos import handle_ico_schedule


def run_once() -> List[Dict]:
    """
    Run all fetchers once, store samples, evaluate alerts.

    Alerting models:
    - Rates: delta-based, sticky anchor
    - Caps: state-based (full vs not full)
    - ICOs: scheduled + launch-day alerts
    """
    init_db()

    alerts: List[Dict] = []

    fetchers = [
        fetch_silo,
        fetch_euler,
        fetch_aave,
        fetch_dolomite,
        fetch_metadao,
    ]

    for fetcher in fetchers:
        metrics = fetcher()

        for metric in metrics:
            key = metric["key"]
            name = metric["name"]
            value = metric["value"]
            unit = metric.get("unit")

            last_value = get_last(key)

            if unit == "json" and key == "metadao:icos:scheduled":
                # Record a lightweight count so the toy list includes this key
                record_sample(
                    metric_key=key,
                    name=name,
                    value=float(len(value or [])),
                    unit=unit,
                )
                alerts.extend(handle_ico_schedule(value or []))
                continue

            # numeric metrics only beyond this point
            value_f = float(value)

            # always record current value
            record_sample(
                metric_key=key,
                name=name,
                value=value_f,
                unit=unit,
            )

            if unit == "ratio":
                alerts.extend(
                    handle_caps_metric(
                        key=key,
                        name=name,
                        value=value_f,
                        last_value=last_value,
                    )
                )
            else:
                alerts.extend(
                    handle_rate_metric(
                        key=key,
                        name=name,
                        value=value_f,
                        unit=unit,
                    )
                )

    return alerts
