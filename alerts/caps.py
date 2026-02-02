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
                    f":pouting_cat: {name.replace('Supply', '').replace('Borrow', '').replace('Cap', '').replace('   Utilization', '')} {'supply' if is_supply else 'borrow'} cap reached.\n"
                    f"Usage: 100.00%"
                ),
            }
        )

    # full -> not full
    elif was_full and not is_full:
        alerts.append(
            {
                "category": "caps",
                "level": "minor",
                "metric_key": key,
                "message": (
                    f":scream_cat: {name.replace('Supply', '').replace('Borrow', '').replace('Cap', '').replace('   Utilization', '')} {'supply' if is_supply else 'borrow'} cap freed.\n"
                    f"Usage: {value * 100:.2f}%"
                ),
            }
        )

    return alerts
