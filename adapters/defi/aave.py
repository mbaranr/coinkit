import requests
from typing import Any, List, Dict, TypedDict


AAVE_GRAPHQL_URL = "https://api.v3.aave.com/graphql"


QUERY_SUPPLY_BORROW = """
query ReserveCaps {
  reserve(
    request: {
      chainId: %d
      market: "%s"
      underlyingToken: "%s"
    }
  ) {
    supplyInfo {
      total { value }
      supplyCap { amount { value } }
      supplyCapReached
    }
    borrowInfo {
      total { amount { value } }
      borrowCap { amount { value } }
      borrowCapReached
    }
  }
}
"""

QUERY_SUPPLY_ONLY = """
query ReserveCaps {
  reserve(
    request: {
      chainId: %d
      market: "%s"
      underlyingToken: "%s"
    }
  ) {
    supplyInfo {
      total { value }
      supplyCap { amount { value } }
      supplyCapReached
    }
  }
}
"""


class Asset(TypedDict):
    chain_id: int
    market: str
    symbol: str
    address: str
    include_borrow: bool


ETHEREUM_CHAIN_ID = 1
ETHEREUM_POOL_ADDRESS = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"

MANTLE_CHAIN_ID = 5000
MANTLE_POOL_ADDRESS = "0x458F293454fE0d67EC0655f3672301301DD51422"


ASSETS: List[Asset] = [
    # Ethereum (supply + borrow)
    {
        "chain_id": ETHEREUM_CHAIN_ID,
        "market": ETHEREUM_POOL_ADDRESS,
        "symbol": "RLUSD",
        "address": "0x8292bb45bf1ee4d140127049757c2e0ff06317ed",
        "include_borrow": True,
    },
    {
        "chain_id": ETHEREUM_CHAIN_ID,
        "market": ETHEREUM_POOL_ADDRESS,
        "symbol": "PYUSD",
        "address": "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8",
        "include_borrow": True,
    },
    # Mantle (supply only)
    {
        "chain_id": MANTLE_CHAIN_ID,
        "market": MANTLE_POOL_ADDRESS,
        "symbol": "syrupUSDT",
        "address": "0x051665f2455116e929b9972c36d23070f5054ce0",
        "include_borrow": False,
    },
    {
        "chain_id": MANTLE_CHAIN_ID,
        "market": MANTLE_POOL_ADDRESS,
        "symbol": "USDC",
        "address": "0x09bc4e0d864854c6afb6eb9a9cdf58ac190d0df9",
        "include_borrow": False,
    },
    {
        "chain_id": MANTLE_CHAIN_ID,
        "market": MANTLE_POOL_ADDRESS,
        "symbol": "wrsETH",
        "address": "0x93e855643e940d025be2e529272e4dbd15a2cf74",
        "include_borrow": False,
    },
]


def _to_float(x: Any) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        return float(x)
    raise TypeError(f"Cannot convert to float: {x}")


def _fetch(chain_id: int, market: str, address: str, include_borrow: bool):
    query_template = QUERY_SUPPLY_BORROW if include_borrow else QUERY_SUPPLY_ONLY
    query = query_template % (chain_id, market, address)

    r = requests.post(
        AAVE_GRAPHQL_URL,
        json={"query": query},
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    payload = r.json()

    reserve = payload.get("data", {}).get("reserve")
    if not reserve:
        raise RuntimeError(
            f"Aave response missing reserve (chainId={chain_id}, market={market}, token={address})"
        )

    supply = reserve["supplyInfo"]
    supply_used = _to_float(supply["total"]["value"])
    supply_cap = _to_float(supply["supplyCap"]["amount"]["value"])

    supply_ratio = (
        1.0
        if supply["supplyCapReached"]
        else (supply_used / supply_cap if supply_cap > 0 else 0.0)
    )

    borrow_ratio = None

    if include_borrow:
        borrow = reserve["borrowInfo"]
        borrow_used = _to_float(borrow["total"]["amount"]["value"])
        borrow_cap = _to_float(borrow["borrowCap"]["amount"]["value"])

        borrow_ratio = (
            1.0
            if borrow["borrowCapReached"]
            else (borrow_used / borrow_cap if borrow_cap > 0 else 0.0)
        )

    return supply_ratio, borrow_ratio


def fetch() -> List[Dict]:
    """
    - Ethereum assets: supply + borrow cap utilization
    - Mantle assets: supply cap utilization only
    """
    metrics: List[Dict] = []

    for asset in ASSETS:
        supply_ratio, borrow_ratio = _fetch(
            chain_id=asset["chain_id"],
            market=asset["market"],
            address=asset["address"],
            include_borrow=asset["include_borrow"],
        )

        sym = asset["symbol"].lower()

        # supply metric (all assets)
        metrics.append(
            {
                "key": f"aave:{sym}:supply:cap_util",
                "name": f"Aave {asset['symbol']} Supply Cap Utilization",
                "value": supply_ratio,
                "unit": "ratio",
            }
        )

        # borrow metric (Ethereum only)
        if asset["include_borrow"] and borrow_ratio is not None:
            metrics.append(
                {
                    "key": f"aave:{sym}:borrow:cap_util",
                    "name": f"Aave {asset['symbol']} Borrow Cap Utilization",
                    "value": borrow_ratio,
                    "unit": "ratio",
                }
            )

    return metrics