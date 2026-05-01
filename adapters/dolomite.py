from typing import Dict, List

from httputil import get_json, to_float


DOLOMITE_INTEREST_RATES_URL = (
    "https://api.dolomite.io/tokens/80094/interest-rates?exclude-odolo=false"
)

TARGETS = {
    "USDC": {
        "key": "dolomite:usdc:borrow:rate",
        "name": "Dolomite USDC Borrow APR",
    },
    # "BYUSD": {
    #     "key": "dolomite:byusd:borrow:rate",
    #     "name": "Dolomite BYUSD Borrow APR",
    # },
    # "rUSD": {
    #     "key": "dolomite:rusd:borrow:rate",
    #     "name": "Dolomite rUSD Borrow APR",
    # },
    "USDT": {
        "key": "dolomite:usdt:borrow:rate",
        "name": "Dolomite USDT Borrow APR",
    },
}


def fetch() -> List[Dict]:
    """
    Fetch Dolomite borrow APRs (Berachain):
    - USDC borrow rate
    - BYUSD borrow rate
    - rUSD borrow rate
    - USDT borrow rate

    Returns a list of metric dicts.
    """
    data = get_json(DOLOMITE_INTEREST_RATES_URL)

    rates = data.get("interestRates")
    if not isinstance(rates, list) or not rates:
        raise RuntimeError("Dolomite response missing interestRates")

    found: Dict[str, float] = {}

    for row in rates:
        token = (row or {}).get("token") or {}
        symbol = token.get("tokenSymbol")
        if symbol in TARGETS:
            borrow = row.get("borrowInterestRate")
            if borrow is None:
                raise RuntimeError(f"Dolomite response missing borrowInterestRate for {symbol}")
            found[symbol] = to_float(borrow)

    missing = [sym for sym in TARGETS.keys() if sym not in found]
    if missing:
        raise RuntimeError(f"Dolomite markets not found in response: {', '.join(missing)}")

    metrics: List[Dict] = []
    for sym, meta in TARGETS.items():
        metrics.append(
            {
                "key": meta["key"],
                "name": meta["name"],
                "value": found[sym],  # decimal (e.g. 0.0667)
                "unit": "rate",
                "adapter": "dolomite",
            }
        )

    return metrics
