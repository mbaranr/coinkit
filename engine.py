from typing import List, Dict, Optional

from db.repo import init_db, record_sample, get_last

from adapters.defi.silo import fetch as fetch_silo
from adapters.defi.euler import fetch as fetch_euler, SENTORA_CAP_PAIRS
from adapters.defi.aave import fetch as fetch_aave
from adapters.defi.dolomite import fetch as fetch_dolomite
from adapters.gov.metadao import fetch as fetch_metadao
from adapters.defi.jupiter import fetch as fetch_jupiter

from alerts.caps import handle_caps_metric, handle_paired_caps
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

    alerts: List[Dict] = []
    cap_snapshots: Dict[str, tuple] = {}  # key -> (value, last_value) for paired checks

    fetchers = [
        fetch_silo,
        fetch_euler,
        fetch_aave,
        fetch_dolomite,
        fetch_metadao,
        fetch_jupiter,
    ]

    for fetcher in fetchers:
        try:
            metrics = fetcher()
        except Exception as e:
            msg = f"Error fetching data from {fetcher.__module__.split('.')[-1]}: {e}"
            print(msg)
            alerts.append(
                {
                    "category": "engine",
                    "level": "major",
                    "value": msg,
                },
            )
            continue

        for metric in metrics:
            key = metric["key"]
            name = metric["name"]
            value = metric["value"]
            unit = metric.get("unit")
            adapter = metric.get("adapter")

            last_value = get_last(key)

            if unit == "json" and key == "metadao:icos:scheduled":
                # record a lightweight count so the toy list includes this key
                record_sample(
                    metric_key=key,
                    name=name,
                    value=float(len(value or [])),
                    unit=unit,
                )
                alerts.extend(
                    handle_ico_schedule(value or [], key, adapter)
                )
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
                cap_snapshots[key] = (value_f, last_value)
                alerts.extend(
                    handle_caps_metric(
                        key=key,
                        name=name,
                        value=value_f,
                        last_value=last_value,
                        adapter=adapter,
                    ),
                )
            else:
                alerts.extend(
                    handle_rate_metric(
                        key=key,
                        name=name,
                        value=value_f,
                        unit=unit,
                        adapter=adapter,
                    ),
                )

    for pair in SENTORA_CAP_PAIRS:
        sk, bk = pair["supply_key"], pair["borrow_key"]
        if sk in cap_snapshots and bk in cap_snapshots:
            s_val, s_last = cap_snapshots[sk]
            b_val, b_last = cap_snapshots[bk]
            alerts.extend(
                handle_paired_caps(
                    pair_name=pair["pair_name"],
                    supply_key=sk,
                    supply_value=s_val,
                    supply_last=s_last,
                    borrow_value=b_val,
                    borrow_last=b_last,
                    adapter=pair["adapter"],
                )
            )

    return alerts
