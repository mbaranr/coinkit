from typing import List, Dict, Optional

CAP_FULL_THRESHOLD = 0.99985   # 99.985%


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

    # not full -> full
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

    # full -> not full
    elif was_full and not is_full:
        alerts.append(
            {
                "category": "caps",
                "level": "major",
                "metric_key": key,
                "message": (
                    f"🚨 {name} is no longer at its cap\n"
                    f"Usage: {value * 100:.4f}%"
                ),
            }
        )

    return alerts