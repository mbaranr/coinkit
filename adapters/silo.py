from httputil import post_json

SILO_MARKET_URL = "https://app.silo.finance/api/lending-market"
SILO_MARKET_ID = "avalanche-0x33fAdB3dB0A1687Cdd4a55AB0afa94c8102856A1"
SCALE = 1e18  # borrowBaseApr is scaled by 1e18


def fetch() -> list[dict]:
    """
    Fetch Silo USDC borrow APR.

    Returns a list of metric dicts.
    """
    data = post_json(
        SILO_MARKET_URL,
        json={"marketId": SILO_MARKET_ID, "account": "0x0000000000000000000000000000000000000000"},
        timeout=15,
    )

    silo1 = data["silo1"]  # USDC silo
    raw_apr = int(silo1["borrowBaseApr"])
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
