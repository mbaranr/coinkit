import requests
from typing import Any, List, Dict


EULER_CLASSIC_VAULT_URL = (
    "https://app.euler.finance/api/v1/vault"
    "?chainId=43114"
    "&vaults=0xbaC3983342b805E66F8756E265b3B0DdF4B685Fc,"
    "0x37ca03aD51B8ff79aAD35FadaCBA4CEDF0C3e74e"
    "&type=classic"
)

TARGET_VAULT_SYMBOL = "eUSDC-19"
EULER_APY_SCALE = 1e27  # ray-scaled


EULER_ETHEREUM_VAULT_URL = (
    "https://app.euler.finance/api/v1/vault"
    "?chainId=1"
    "&vaults="
    "0xba98fC35C9dfd69178AD5dcE9FA29c64554783b5,"  # PYUSD
    "0xaF5372792a29dC6b296d6FFD4AA3386aff8f9BB2"   # RLUSD
)

YIELD_VAULTS = {
    "ePYUSD-6": {
        "key": "euler:sentora_pyusd:supply:cap",
        "name": "Euler Sentora PYUSD Supply Cap Usage",
    },
    "eRLUSD-7": {
        "key": "euler:sentora_rlusd:supply:cap",
        "name": "Euler Sentora RLUSD Supply Cap Usage",
    },
}


def _to_int(x: Any) -> int:
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        s = x.strip()
        if s.startswith("__bigint__"):
            s = s.replace("__bigint__", "")
        if s.startswith("0x"):
            return int(s, 16)
        return int(s)
    raise TypeError(f"Cannot convert to int: {x}")


def fetch() -> List[Dict]:
    """
    Fetch Euler metrics:
    - USDC borrow APY (Avalanche, classic)
    - PYUSD supply cap usage (Ethereum, yield)
    - RLUSD supply cap usage (Ethereum, yield)
    """
    metrics: List[Dict] = []

    # borrow apy

    r = requests.get(EULER_CLASSIC_VAULT_URL, timeout=20)
    r.raise_for_status()
    data = r.json()

    target = None
    for v in data.values():
        if isinstance(v, dict) and v.get("vaultSymbol") == TARGET_VAULT_SYMBOL:
            target = v
            break

    if not target:
        raise RuntimeError(f"Euler vault '{TARGET_VAULT_SYMBOL}' not found")

    irm = target.get("irmInfo", {})
    info = irm.get("interestRateInfo") or []
    if not info:
        raise RuntimeError("Euler response missing interestRateInfo")

    row = info[0]
    raw = _to_int(row.get("borrowAPY"))
    rate = raw / EULER_APY_SCALE

    metrics.append(
        {
            "key": "euler:usdc:borrow:rate",
            "name": "Euler USDC Borrow APY",
            "value": rate,
            "unit": "rate",
        }
    )

    # supply cap usage
    
    r = requests.get(EULER_ETHEREUM_VAULT_URL, timeout=20)
    r.raise_for_status()
    data = r.json()

    for vault_symbol, meta in YIELD_VAULTS.items():
        vault = None

        for v in data.values():
            if isinstance(v, dict) and v.get("vaultSymbol") == vault_symbol:
                vault = v
                break

        if not vault:
            raise RuntimeError(f"Euler yield vault '{vault_symbol}' not found")

        total_assets = _to_int(vault["totalAssets"])
        supply_cap = _to_int(vault["supplyCap"])
        decimals = _to_int(vault["assetDecimals"])

        ratio = min(total_assets / supply_cap, 1.0) if supply_cap > 0 else 0.0

        metrics.append(
            {
                "key": meta["key"],
                "name": meta["name"],
                "value": ratio,   # ratio: 0.0–1.0
                "unit": "ratio",
            }
        )

    return metrics