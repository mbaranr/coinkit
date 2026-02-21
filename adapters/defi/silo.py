import requests

SILO_MARKET_URL = "https://app.silo.finance/api/lending-market/avalanche/142"

SCALE = 1e18  # debtBaseApr is scaled by 1e18


def fetch() -> list[dict]:
    """
    Fetch Silo USDC borrow APR.

    Returns a list of metric dicts.
    """
    r = requests.get(SILO_MARKET_URL, timeout=15)
    r.raise_for_status()
    data = r.json()

    silo1 = data["silo1"]  # USDC silo
    raw_apr = int(silo1["debtBaseApr"])
    rate = raw_apr / SCALE  # decimal (e.g. 0.186)

    return [
        {
            "key": "silo:usdc:borrow:rate",
            "name": "Silo savUSD/USDC Borrow APR",
            "value": rate,
            "unit": "rate",
            "adapter": "silo",
        }
    ]
