from typing import List, Dict, Optional

from db.repo import record_sample, get_last


MINOR_CHANGE = 0.01   # 1%
MAJOR_CHANGE = 0.10   # 10%


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

    # minor alert
    elif abs_delta >= MINOR_CHANGE:
        alerts.append(
            {
                "category": "rates",
                "level": "minor",
                "metric_key": key,
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

    elif abs_delta >= (MINOR_CHANGE / 2) and adapter == "jupiter" and unit == "rate":
        alerts.append(
            {
                "category": "rates",
                "level": "minor",
                "metric_key": key,
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

    return alerts
