import importlib
import pkgutil
from types import ModuleType
from typing import Dict, List

import adapters as _adapters_pkg
from db import get_last, record_sample
from alerts import (
    handle_caps_metric,
    handle_ico_schedule,
    handle_paired_caps,
    handle_rate_metric,
)


def _discover_adapters() -> Dict[str, ModuleType]:
    """
    Auto-discover every module under adapters/. Each MUST expose
    `fetch() -> list[dict]`. Optional: a `PAIRED_CAPS` list of pair configs.
    """
    out: Dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(_adapters_pkg.__path__):
        mod = importlib.import_module(f"adapters.{info.name}")
        if not callable(getattr(mod, "fetch", None)):
            raise RuntimeError(f"Adapter {info.name!r} missing required fetch() callable")
        out[info.name] = mod
    return out


ADAPTERS: Dict[str, ModuleType] = _discover_adapters()

PAIRED_CAPS: List[Dict] = [
    pair
    for mod in ADAPTERS.values()
    for pair in getattr(mod, "PAIRED_CAPS", [])
]


def run_once() -> List[Dict]:
    """
    Run all fetchers once, store samples, evaluate alerts.

    Alerting models:
    - Rates: delta-based, sticky anchor
    - Caps: state-based (full vs not full)
    - ICOs: scheduled + launch-day alerts
    """
    alerts: List[Dict] = []
    cap_snapshots: Dict[str, tuple] = {}
    paired_keys = {
        key
        for pair in PAIRED_CAPS
        for key in (pair["supply_key"], pair["borrow_key"])
    }

    for adapter_name, mod in ADAPTERS.items():
        try:
            metrics = mod.fetch()
        except Exception as e:
            msg = f"Error fetching data from {adapter_name}: {e}"
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
                        paired_keys=paired_keys,
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

    for pair in PAIRED_CAPS:
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
