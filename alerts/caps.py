from typing import List, Dict, Optional


CAP_FULL_THRESHOLD = 0.99995   # 99.995%


def handle_caps_metric(
    *,
    key: str,
    name: str,
    value: float,
    last_value: Optional[float],
    adapter: Optional[str] = None,
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
