from datetime import datetime, timedelta, timezone

from httputil import get_json


# Kamino Ethena Market and its USDG reserve.
# The UI label is "Ethena Market"; the pubkey matches the page at
# kamino.com/borrow/reserve/<market>/<reserve>.
MARKET = "BJnbcRHqvppTyGesLzWASGKnmnF1wq9jZu6ExrjT7wvF"
USDG_RESERVE = "Q5av3wh8j9KCqSjs9njUdsPhrMSKBCUyr4VyUndUUFA"

HISTORY_URL = (
    f"https://api.kamino.finance/kamino-market/{MARKET}"
    f"/reserves/{USDG_RESERVE}/metrics/history"
)
LIVE_URL = f"https://api.kamino.finance/kamino-market/{MARKET}/reserves/metrics"


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _fetch_history_metrics() -> dict:
    """
    History endpoint is the only source for reserveBorrowLimit (cap).
    Cap changes only via governance, so an hourly sample is plenty.
    """
    now = datetime.now(timezone.utc)
    params = {
        "frequency": "hour",
        "start": _iso(now - timedelta(hours=3)),
        "end": _iso(now),
    }
    payload = get_json(HISTORY_URL, params=params, timeout=15)
    history = payload.get("history") or []
    if not history:
        raise RuntimeError("Kamino USDG history empty")
    return history[-1]["metrics"]


def _fetch_live_reserve() -> dict:
    reserves = get_json(LIVE_URL, timeout=15)
    for r in reserves:
        if r.get("reserve") == USDG_RESERVE:
            return r
    raise RuntimeError("Kamino USDG reserve not found in live metrics")


def fetch() -> list[dict]:
    hist = _fetch_history_metrics()
    decimals = int(hist["decimals"])
    cap = int(hist["reserveBorrowLimit"]) / 10 ** decimals

    live = _fetch_live_reserve()
    total_borrows = float(live["totalBorrow"])
    # totalSupply - totalBorrow underestimates on-chain liquidity by
    # accumulatedProtocolFees (~5 figures on a ~$250M reserve), which
    # is immaterial: the cap is the binding constraint in normal state.
    on_chain = max(0.0, float(live["totalSupply"]) - total_borrows)

    borrowable = max(0.0, min(on_chain, cap - total_borrows))

    return [
        {
            "key": "kamino:ethena:usdg:borrow:available",
            "name": "Kamino Ethena USDG Borrowable",
            "value": borrowable,
            "unit": "available",
            "adapter": "kamino",
        }
    ]
