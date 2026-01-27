from typing import List, Dict, Optional

CAP_FULL_THRESHOLD = 0.99995   # 99.995%


def handle_caps_metric(
    *,
    key: str,
    name: str,
    value: float,
    last_value: Optional[float],
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
                    f"🧢 {name.replace('Supply', '').replace('Borrow', '').replace('Cap', '').replace('  Usage', '')} has reached its {'supply' if is_supply else 'borrow'} cap\n"
                    f"Usage: 100.00%"
                ),
            }
        )

    # full -> not full
    elif was_full and not is_full:
        alerts.append(
            {
                "category": "caps",
                "level": "major",
                "metric_key": key,
                "message": (
                    f"🚨 {name.replace('Supply', '').replace('Borrow', '').replace('Cap', '').replace('  Usage', '')} is no longer at its {'supply' if is_supply else 'borrow'} cap\n"
                    f"Usage: {value * 100:.2f}%"
                ),
            }
        )

    return alerts