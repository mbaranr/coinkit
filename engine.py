import importlib
import os
import pkgutil
from datetime import datetime, timezone
from types import ModuleType
from typing import Dict, List, Optional

import adapters as _adapters_pkg
from db import (
    get_last,
    ico_alert_state,
    mark_ico_released,
    mark_ico_scheduled,
    record_sample,
)


# Thresholds

CAP_FULL_THRESHOLD = 0.99995   # 99.995%

# Rate change thresholds. Edit these when the trader requests a tweak.
RATE_MAJOR = 0.10   # 10%, applies to all adapters
RATE_MINOR_DEFAULT = 0.01   # 1%
RATE_MINOR = {
    "aave":     0.001,   # 0.1%
    "compound": 0.001,   # 0.1%
    "jupiter":  0.005,   # 0.5%
}


# Adapter discovery

def _disabled_set() -> set:
    raw = os.getenv("DISABLED_ADAPTERS", "")
    return {n.strip() for n in raw.split(",") if n.strip()}


def _discover_adapters() -> Dict[str, ModuleType]:
    """
    Auto-discover every module under adapters/. Each MUST expose
    `fetch() -> list[dict]`. Optional: a `PAIRED_CAPS` list of pair configs.

    Adapters listed in the DISABLED_ADAPTERS env (comma-separated) are skipped.
    """
    disabled = _disabled_set()
    out: Dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(_adapters_pkg.__path__):
        if info.name in disabled:
            print(f"[engine] adapter {info.name!r} disabled via DISABLED_ADAPTERS")
            continue
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


# Caps

def handle_caps_metric(
    *,
    key: str,
    name: str,
    value: float,
    last_value: Optional[float],
    adapter: Optional[str] = None,
    paired_keys: Optional[set] = None,
) -> List[Dict]:
    """
    State-based alerting for cap metrics.

    - no alert on first observation
    - minor update when cap is reached
    - major alert when cap is freed
    """
    alerts: List[Dict] = []

    if last_value is None:
        return alerts

    was_full = last_value >= CAP_FULL_THRESHOLD
    is_full = value >= CAP_FULL_THRESHOLD

    is_supply = "Supply" in name

    # not full -> full
    if not was_full and is_full:
        alerts.append(
            {
                "category": "caps",
                "level": "minor",
                "metric_key": key,
                "message": (
                    f":pouting_cat: {name.replace('Supply', '').replace('Borrow', '').replace('Cap', '').replace('   Utilization', '')} {'supply' if is_supply else 'borrow'} cap reached.\n"
                    f"Utilization: 100.00%"
                ),
                "adapter": adapter,
            }
        )

    # full -> not full
    elif was_full and not is_full:

        if key in paired_keys:
            return alerts

        alerts.append(
            {
                "category": "caps",
                "level": "minor",
                "metric_key": key,
                "message": (
                    f":kissing_cat: {name.replace('Supply', '').replace('Borrow', '').replace('Cap', '').replace('   Utilization', '')} {'supply' if is_supply else 'borrow'} cap freed.\n"
                    f"Utilization: {value * 100:.2f}%"
                ),
                "adapter": adapter,
            }
        )

    return alerts


def handle_paired_caps(
    *,
    pair_name: str,
    supply_key: str,
    supply_value: float,
    supply_last: Optional[float],
    borrow_value: float,
    borrow_last: Optional[float],
    adapter: Optional[str] = None,
) -> List[Dict]:
    """
    Fires a major alert when both supply and borrow caps for a pair are freed
    simultaneously (i.e. at least one was full before, and now both are free).
    """
    alerts: List[Dict] = []

    if supply_last is None or borrow_last is None:
        return alerts

    was_either_full = (supply_last >= CAP_FULL_THRESHOLD) or (borrow_last >= CAP_FULL_THRESHOLD)
    both_now_free = (supply_value < CAP_FULL_THRESHOLD) and (borrow_value < CAP_FULL_THRESHOLD)

    if was_either_full and both_now_free:
        alerts.append(
            {
                "category": "caps",
                "level": "major",
                "metric_key": supply_key,
                "message": (
                    f":scream_cat: {pair_name} both supply and borrow caps are free!\n"
                    f"Supply: {supply_value * 100:.2f}% | Borrow: {borrow_value * 100:.2f}%"
                ),
                "adapter": adapter,
            }
        )

    return alerts


# Rates

def _anchor_key(metric_key: str) -> str:
    return f"{metric_key}:anchor"


def handle_rate_metric(
    *,
    key: str,
    name: str,
    value: float,
    unit: Optional[str],
    adapter: Optional[str] = None,
) -> List[Dict]:
    """
    Delta-based alerting for rate metrics with a sticky anchor.
    """
    alerts: List[Dict] = []

    anchor_key = _anchor_key(key)
    anchor = get_last(anchor_key)

    # first observation -> set anchor
    if anchor is None:
        record_sample(
            metric_key=anchor_key,
            name=f"{name} (anchor)",
            value=value,
            unit=unit,
        )
        alerts.append(
            {
                "category": "rates",
                "level": "minor",
                "metric_key": key,
                "adapter": adapter,
                "message": f":smirk_cat: {name} anchor set: {value:.2%}",
            }
        )
        return alerts

    delta = value - anchor
    abs_delta = abs(delta)
    direction = "⬆️" if delta > 0 else "⬇️"

    minor_threshold = RATE_MINOR.get(adapter, RATE_MINOR_DEFAULT)

    if abs_delta >= RATE_MAJOR:
        level, threshold, icon = "major", RATE_MAJOR, ":scream_cat:"
    elif abs_delta >= minor_threshold:
        level, threshold, icon = "minor", minor_threshold, ":smirk_cat:"
    else:
        return alerts

    alerts.append(
        {
            "category": "rates",
            "level": level,
            "metric_key": key,
            "adapter": adapter,
            "message": (
                f"{icon} {direction} {name} moved ≥ {threshold * 100:g}%\n"
                f"Anchor: {anchor:.2%}\n"
                f"Current: {value:.2%}"
            ),
        }
    )

    record_sample(
        metric_key=anchor_key,
        name=f"{name} (anchor)",
        value=value,
        unit=unit,
    )

    return alerts


# ICOs

def _utc_today() -> datetime.date:
    return datetime.now(timezone.utc).date()


def _parse_iso_date(iso_str: str) -> Optional[datetime.date]:
    """
    Parse ISO-ish strings (handles trailing 'Z') into a UTC date.
    Returns None on failure.
    """
    try:
        clean = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean).astimezone(timezone.utc).date()
    except Exception:
        return None


def _pretty_date(iso_str: Optional[str]) -> Optional[str]:
    if not iso_str:
        return None
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean).astimezone(timezone.utc)
        return dt.strftime("%b %d, %Y (%H:%M UTC)")
    except Exception:
        return iso_str


def handle_ico_schedule(entries: List[Dict], key: str, adapter: str) -> List[Dict]:
    """
    entries: list of ICO dicts.
    Emits:
      - major alert when a new scheduled ICO is first seen
      - major alert on the day of launch (UTC) if not already sent
    """
    alerts: List[Dict] = []
    today = _utc_today()

    for ico in entries:
        block_id = ico.get("block_id") or ico.get("project")
        if not block_id:
            continue

        project = ico.get("project", "Unknown project")
        start_iso = ico.get("start_date")
        start_date = _parse_iso_date(start_iso) if start_iso else None
        start_pretty = _pretty_date(start_iso) if start_iso else None
        fundraising_goals = ico.get("fundraising_goals")
        twitter = ico.get("twitter_link")

        state = ico_alert_state(block_id)

        # New scheduled ICO
        if state["scheduled"] is None:
            msg = (
                f":heart_eyes_cat: {project} ICO scheduled for "
                + (f"{start_pretty}" if start_pretty else "")
                + (f"\n{fundraising_goals}" if fundraising_goals else "")
                + (f"\nLink: {twitter}" if twitter else "")
            )
            alerts.append(
                {
                    "category": "icos",
                    "level": "major",
                    "metric_key": key,
                    "message": msg,
                    "adapter": adapter,
                }
            )
            mark_ico_scheduled(block_id)

        # Launch day alert
        if start_date and start_date == today and state["released"] is None:
            msg = (
                f":smile_cat: {project} ICO launches today!"
            )
            alerts.append(
                {
                    "category": "icos",
                    "level": "major",
                    "metric_key": key,
                    "message": msg,
                    "adapter": adapter,
                }
            )
            mark_ico_released(block_id)

    return alerts


# Orchestration

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

            if unit == "json":
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
