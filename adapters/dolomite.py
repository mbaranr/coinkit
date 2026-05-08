from collections import defaultdict
from typing import Dict, List

from httputil import get_json, to_float


DOLOMITE_INTEREST_RATES_URL = (
    "https://api.dolomite.io/tokens/{chain_id}/interest-rates?exclude-odolo=false"
)

TARGETS: List[Dict] = [
    {"chain_id": 80094, "symbol": "USDC", "key": "dolomite:usdc:borrow:rate", "name": "Dolomite USDC Borrow APR"},
    {"chain_id": 80094, "symbol": "USDT", "key": "dolomite:usdt:borrow:rate", "name": "Dolomite USDT Borrow APR"},
    {"chain_id": 1,     "symbol": "WETH", "key": "dolomite:eth:borrow:rate",  "name": "Dolomite ETH Borrow APR"},
]


def _fetch_chain_rates(chain_id: int) -> Dict[str, float]:
    """Return {symbol: borrow_rate} for the given chain."""
    data = get_json(DOLOMITE_INTEREST_RATES_URL.format(chain_id=chain_id))

    rates = data.get("interestRates")
    if not isinstance(rates, list) or not rates:
        raise RuntimeError(f"Dolomite chain {chain_id} response missing interestRates")

    out: Dict[str, float] = {}
    for row in rates:
        token = (row or {}).get("token") or {}
        symbol = token.get("tokenSymbol")
        borrow = row.get("borrowInterestRate") if symbol else None
        if symbol and borrow is not None:
            out[symbol] = to_float(borrow)
    return out


def fetch() -> List[Dict]:
    """
    Fetch Dolomite borrow APRs across configured chains:
    - Berachain (80094): USDC, USDT
    - Ethereum  (1):     ETH (WETH)
    """
    by_chain: Dict[int, List[Dict]] = defaultdict(list)
    for t in TARGETS:
        by_chain[t["chain_id"]].append(t)

    metrics: List[Dict] = []
    for chain_id, targets in by_chain.items():
        rates = _fetch_chain_rates(chain_id)
        missing = [t["symbol"] for t in targets if t["symbol"] not in rates]
        if missing:
            raise RuntimeError(
                f"Dolomite chain {chain_id} markets not found in response: {', '.join(missing)}"
            )
        for t in targets:
            metrics.append(
                {
                    "key": t["key"],
                    "name": t["name"],
                    "value": rates[t["symbol"]],
                    "unit": "rate",
                    "adapter": "dolomite",
                }
            )

    return metrics
