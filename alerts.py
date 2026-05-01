from datetime import datetime, timezone
from typing import Dict, List, Optional

from db import (
    get_last,
    ico_alert_state,
    mark_ico_released,
    mark_ico_scheduled,
    record_sample,
)


CAP_FULL_THRESHOLD = 0.99995   # 99.995%
MINOR_CHANGE = 0.01   # 1%
MAJOR_CHANGE = 0.10   # 10%


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

    # major alert
    if abs_delta >= MAJOR_CHANGE:
        alerts.append(
            {
                "category": "rates",
                "level": "major",
                "metric_key": key,
                "adapter": adapter,
                "message": (
                    f":scream_cat: {direction} {name} moved ≥ 10%\n"
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

    # minor alert for Aave/Compound rates at 0.1% threshold
    elif abs_delta >= (MINOR_CHANGE / 10) and adapter in ("aave", "compound") and unit == "rate":
        alerts.append(
            {
                "category": "rates",
                "level": "minor",
                "metric_key": key,
                "adapter": adapter,
                "message": (
                    f":smirk_cat: {direction} {name} moved ≥ 0.1%\n"
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

    # minor alert for Jupiter rates at 0.5% threshold
    elif abs_delta >= (MINOR_CHANGE / 2) and adapter == "jupiter" and unit == "rate":
        alerts.append(
            {
                "category": "rates",
                "level": "minor",
                "metric_key": key,
                "adapter": adapter,
                "message": (
                    f":smirk_cat: {direction} {name} moved ≥ 0.5%\n"
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

    # minor alert
    elif abs_delta >= MINOR_CHANGE:
        alerts.append(
            {
                "category": "rates",
                "level": "minor",
                "metric_key": key,
                "adapter": adapter,
                "message": (
                    f":smirk_cat: {direction} {name} moved ≥ 1%\n"
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
        tldr = ico.get("tldr")
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
