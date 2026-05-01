import requests
from typing import Any, Dict, List


AAVE_V3_GRAPHQL_URL = "https://api.v3.aave.com/graphql"
AAVE_V4_GRAPHQL_URL = "https://api.aave.com/graphql"

ETHEREUM_CHAIN_ID = 1
ETHEREUM_V3_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"

WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

# Aave V4 Core hub on Ethereum (the "weETH pool")
V4_CORE_HUB_ADDRESS = "0xCca852Bc40e560adC3b1Cc58CA5b55638ce826c9"

QUERY_V3_BORROW_APY = """
query BorrowRate {
  reserve(
    request: {
      chainId: %d
      market: "%s"
      underlyingToken: "%s"
    }
  ) {
    borrowInfo {
      apy { value }
    }
  }
}
"""

QUERY_V4_HUB_ASSETS = """
query HubAssets {
  hubAssets(
    request: {
      query: {
        hubInput: { address: "%s", chainId: %d }
      }
      orderBy: { borrowApy: DESC }
    }
  ) {
    underlying { address }
    summary {
      borrowApy { value }
    }
  }
}
"""


def _to_float(x: Any) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        return float(x)
    raise TypeError(f"Cannot convert to float: {x}")


def _fetch_v3_borrow_apy() -> float:
    query = QUERY_V3_BORROW_APY % (ETHEREUM_CHAIN_ID, ETHEREUM_V3_POOL, WETH_ADDRESS)

    r = requests.post(
        AAVE_V3_GRAPHQL_URL,
        json={"query": query},
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    payload = r.json()

    reserve = payload.get("data", {}).get("reserve")
    if not reserve:
        raise RuntimeError("Aave V3 response missing reserve for WETH")

    return _to_float(reserve["borrowInfo"]["apy"]["value"])


def _fetch_v4_borrow_apy() -> float:
    query = QUERY_V4_HUB_ASSETS % (V4_CORE_HUB_ADDRESS, ETHEREUM_CHAIN_ID)

    r = requests.post(
        AAVE_V4_GRAPHQL_URL,
        json={"query": query},
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    payload = r.json()

    hub_assets = payload.get("data", {}).get("hubAssets")
    if not hub_assets:
        raise RuntimeError("Aave V4 response missing hubAssets for Core hub")

    weth = WETH_ADDRESS.lower()
    for asset in hub_assets:
        if asset["underlying"]["address"].lower() == weth:
            return _to_float(asset["summary"]["borrowApy"]["value"])

    raise RuntimeError("Aave V4 Core hub does not contain WETH")


def fetch() -> List[Dict]:
    """
    Fetch Aave ETH borrow rates:
    - V3 Ethereum mainnet
    - V4 Core hub (weETH pool)
    """
    v3_rate = _fetch_v3_borrow_apy()
    v4_rate = _fetch_v4_borrow_apy()

    return [
        {
            "key": "aave:v3:eth:borrow:rate",
            "name": "Aave V3 ETH Borrow APY",
            "value": v3_rate,
            "unit": "rate",
            "adapter": "aave",
        },
        {
            "key": "aave:v4:eth:borrow:rate",
            "name": "Aave V4 ETH Borrow APY (Core)",
            "value": v4_rate,
            "unit": "rate",
            "adapter": "aave",
        },
    ]
