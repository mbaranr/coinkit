import base64
import os
from datetime import datetime, timedelta, timezone

from httputil import get_json, post_json


# Kamino Ethena Market and its reserves.
# The UI label is "Ethena Market"; the pubkey matches the page at
# kamino.com/borrow/reserve/<market>/<reserve>.
MARKET = "BJnbcRHqvppTyGesLzWASGKnmnF1wq9jZu6ExrjT7wvF"

# reserve pubkey -> display token symbol
RESERVES = {
    "Q5av3wh8j9KCqSjs9njUdsPhrMSKBCUyr4VyUndUUFA": "USDG",
    "EDf6dGbVnCCABbNhE3mp5i1jV2JhDAVmTWb1ztij1Yhs": "PYUSD",
}

LIVE_URL = f"https://api.kamino.finance/kamino-market/{MARKET}/reserves/metrics"

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

# Byte offset of ReserveConfig.utilizationLimitBlockBorrowingAbovePct (u8, a
# percent; 0 means no limit) into the klend Reserve account data, including the
# 8-byte Anchor discriminator. Derived from the klend IDL
# (Kamino-Finance/klend-sdk src/idl/klend.json: ReserveConfig sits at +4848,
# the field at +645 within it) and validated on-chain on 2026-06-03: the
# borrowLimit at the adjacent computed offset read back the governance cap
# exactly. The field is followed by large reserved padding, so existing offsets
# hold across program upgrades (new fields land in padding).
_UTIL_LIMIT_OFFSET = 5501


def _history_url(reserve: str) -> str:
    return (
        f"https://api.kamino.finance/kamino-market/{MARKET}"
        f"/reserves/{reserve}/metrics/history"
    )


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _fetch_history_metrics(reserve: str, symbol: str) -> dict:
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
    payload = get_json(_history_url(reserve), params=params, timeout=15)
    history = payload.get("history") or []
    if not history:
        raise RuntimeError(f"Kamino {symbol} history empty")
    return history[-1]["metrics"]


def _fetch_live_reserves() -> dict:
    reserves = get_json(LIVE_URL, timeout=15)
    return {r.get("reserve"): r for r in reserves}


def _fetch_util_limit_pct(reserve: str, symbol: str) -> int:
    """
    Read utilizationLimitBlockBorrowingAbovePct from the on-chain reserve.
    The UI's "Liq. Available" caps borrows at this percent of deposits, and the
    metrics API does not expose it. 0 means no limit.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [
            reserve,
            {"encoding": "base64", "dataSlice": {"offset": _UTIL_LIMIT_OFFSET, "length": 1}},
        ],
    }
    resp = post_json(SOLANA_RPC_URL, json=payload, timeout=15)
    value = (resp.get("result") or {}).get("value")
    if not value:
        raise RuntimeError(f"Kamino {symbol} reserve account not found on-chain")
    return base64.b64decode(value["data"][0])[0]


def _borrowable(reserve: str, symbol: str, live_by_reserve: dict) -> float:
    hist = _fetch_history_metrics(reserve, symbol)
    decimals = int(hist["decimals"])
    cap = int(hist["reserveBorrowLimit"]) / 10 ** decimals

    live = live_by_reserve.get(reserve)
    if live is None:
        raise RuntimeError(f"Kamino {symbol} reserve not found in live metrics")
    total_supply = float(live["totalSupply"])
    total_borrows = float(live["totalBorrow"])
    # totalSupply - totalBorrow underestimates on-chain liquidity by
    # accumulatedProtocolFees (~5 figures on a ~$250M reserve), which
    # is immaterial: the cap is the binding constraint in normal state.
    on_chain = max(0.0, total_supply - total_borrows)

    constraints = [on_chain, cap - total_borrows]
    # Borrowing is blocked above util_pct% of deposits, so the headroom this
    # leaves is its own constraint (binds before the cap on PYUSD).
    util_pct = _fetch_util_limit_pct(reserve, symbol)
    if util_pct:
        constraints.append(util_pct / 100.0 * total_supply - total_borrows)

    return max(0.0, min(constraints))


def fetch() -> list[dict]:
    live_by_reserve = _fetch_live_reserves()

    metrics = []
    for reserve, symbol in RESERVES.items():
        borrowable = _borrowable(reserve, symbol, live_by_reserve)
        metrics.append(
            {
                "key": f"kamino:ethena:{symbol.lower()}:borrow:available",
                "name": f"Kamino Ethena {symbol} Borrowable",
                "value": borrowable,
                "unit": "available",
                "adapter": "kamino",
            }
        )
    return metrics
