import requests
from typing import Any, List, Dict


AAVE_GRAPHQL_URL = "https://api.v3.aave.com/graphql"

# Aave V3 Ethereum
CHAIN_ID = 1
POOL_ADDRESS = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"

# underlying tokens (Ethereum)
TOKENS = {
    "RLUSD": "0x8292bb45bf1ee4d140127049757c2e0ff06317ed",
    "PYUSD": "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8",
}


QUERY_TEMPLATE = """
query ReserveCaps {
  reserve(
    request: {
      chainId: %d
      market: "%s"
      underlyingToken: "%s"
    }
  ) {
    supplyInfo {
      total {
        value
      }
      supplyCap {
        amount {
          value
        }
      }
      supplyCapReached
    }
    borrowInfo {
      total {
        amount {
          value
        }
      }
      borrowCap {
        amount {
          value
        }
      }
      borrowCapReached
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


def _fetch_cap_ratios(symbol: str, address: str) -> Dict[str, float]:
    query = QUERY_TEMPLATE % (CHAIN_ID, POOL_ADDRESS, address)

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
        raise RuntimeError(f"Aave response missing reserve for {symbol}")

    supply = reserve["supplyInfo"]
    borrow = reserve["borrowInfo"]

    # supply values
    supply_used = _to_float(supply["total"]["value"])
    supply_cap = _to_float(supply["supplyCap"]["amount"]["value"])

    # borrow values
    borrow_used = _to_float(borrow["total"]["amount"]["value"])
    borrow_cap = _to_float(borrow["borrowCap"]["amount"]["value"])

    supply_ratio = (
        1.0
        if supply["supplyCapReached"]
        else (supply_used / supply_cap if supply_cap > 0 else 0.0)
    )

    borrow_ratio = (
        1.0
        if borrow["borrowCapReached"]
        else (borrow_used / borrow_cap if borrow_cap > 0 else 0.0)
    )

    return {
        "supply_ratio": supply_ratio,
        "borrow_ratio": borrow_ratio,
    }


def fetch() -> List[Dict]:
    """
    Fetch Aave supply-cap and borrow-cap usage ratios
    for RLUSD and PYUSD.

    Ratios:
      1.0 == 100%
    """
    metrics: List[Dict] = []

    for symbol, address in TOKENS.items():
        ratios = _fetch_cap_ratios(symbol, address)

        metrics.extend(
            [
                {
                    "key": f"aave:{symbol.lower()}:supply:cap_util",
                    "name": f"Aave {symbol} Supply Cap Utilization",
                    "value": ratios["supply_ratio"],
                    "unit": "ratio",
                },
                {
                    "key": f"aave:{symbol.lower()}:borrow:cap_util",
                    "name": f"Aave {symbol} Borrow Cap Utilization",
                    "value": ratios["borrow_ratio"],
                    "unit": "ratio",
                },
            ]
        )

    return metrics