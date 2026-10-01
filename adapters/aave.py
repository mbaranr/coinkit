from typing import Dict, List

from httputil import post_json, to_float


AAVE_V3_GRAPHQL_URL = "https://api.v3.aave.com/graphql"
AAVE_V4_GRAPHQL_URL = "https://api.aave.com/graphql"

ETHEREUM_CHAIN_ID = 1
ETHEREUM_V3_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"

WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

# Aave V4 Core hub on Ethereum (the "weETH pool")
V4_CORE_HUB_ADDRESS = "0xCca852Bc40e560adC3b1Cc58CA5b55638ce826c9"

MONAD_CHAIN_ID = 143
MONAD_V3_POOL = "0x69a5F9AD4f96ebf0a0C792dD42a01cC5C0102fef"
MONAD_WETH_ADDRESS = "0xEE8c0E9f1BFFb4Eb878d8f15f368A02a35481242"

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


def _fetch_v3_borrow_apy(chain_id: int, pool: str, token: str) -> float:
    query = QUERY_V3_BORROW_APY % (chain_id, pool, token)
    payload = post_json(AAVE_V3_GRAPHQL_URL, json={"query": query})

    reserve = payload.get("data", {}).get("reserve")
    if not reserve:
        raise RuntimeError(f"Aave V3 response missing WETH reserve on chain {chain_id}")

    return to_float(reserve["borrowInfo"]["apy"]["value"])


def _fetch_v4_borrow_apy() -> float:
    query = QUERY_V4_HUB_ASSETS % (V4_CORE_HUB_ADDRESS, ETHEREUM_CHAIN_ID)
    payload = post_json(AAVE_V4_GRAPHQL_URL, json={"query": query})

    hub_assets = payload.get("data", {}).get("hubAssets")
    if not hub_assets:
        raise RuntimeError("Aave V4 response missing hubAssets for Core hub")

    weth = WETH_ADDRESS.lower()
    for asset in hub_assets:
        if asset["underlying"]["address"].lower() == weth:
            return to_float(asset["summary"]["borrowApy"]["value"])

    raise RuntimeError("Aave V4 Core hub does not contain WETH")


SOURCES: List[Dict] = [
    {
        "key": "aave:v3:eth:borrow:rate",
        "name": "Aave V3 ETH Borrow APY",
        "fetch": lambda: _fetch_v3_borrow_apy(ETHEREUM_CHAIN_ID, ETHEREUM_V3_POOL, WETH_ADDRESS),
    },
    {
        "key": "aave:v3:monad:eth:borrow:rate",
        "name": "Aave V3 Monad WETH Borrow APY",
        "fetch": lambda: _fetch_v3_borrow_apy(MONAD_CHAIN_ID, MONAD_V3_POOL, MONAD_WETH_ADDRESS),
    },
    {
        "key": "aave:v4:eth:borrow:rate",
        "name": "Aave V4 ETH Borrow APY (Core)",
        "fetch": _fetch_v4_borrow_apy,
    },
]

PAUSED_KEYS = {"aave:v4:eth:borrow:rate"}


def fetch() -> List[Dict]:
    """
    Fetch Aave ETH borrow rates for every source not in PAUSED_KEYS:
    - V3 Ethereum mainnet
    - V3 Monad
    - V4 Core hub (weETH pool)
    """
    return [
        {
            "key": s["key"],
            "name": s["name"],
            "value": s["fetch"](),
            "unit": "rate",
            "adapter": "aave",
        }
        for s in SOURCES
        if s["key"] not in PAUSED_KEYS
    ]
