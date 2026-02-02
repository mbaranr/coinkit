import requests
from typing import Any, Dict, List, Optional


EULER_VAULT_ENDPOINT = "https://app.euler.finance/api/v1/vault"

# Avalanche / classic
CLASSIC_CHAIN_ID = 43114
CLASSIC_VAULT_IDS = [
    "0xbaC3983342b805E66F8756E265b3B0DdF4B685Fc",
    "0x37ca03aD51B8ff79aAD35FadaCBA4CEDF0C3e74e",
]
TARGET_VAULT_SYMBOL = "eUSDC-19"
EULER_APY_SCALE = 1e27  # ray-scaled

# Ethereum / yield
ETHEREUM_CHAIN_ID = 1
ETHEREUM_VAULT_IDS = [
    "0xba98fC35C9dfd69178AD5dcE9FA29c64554783b5",  # PYUSD
    "0xaF5372792a29dC6b296d6FFD4AA3386aff8f9BB2",  # RLUSD
]

YIELD_VAULTS = {
    "ePYUSD-6": {
        "key": "euler:sentora_pyusd:supply:cap_util",
        "name": "Euler Sentora PYUSD Supply Cap Utilization",
    },
    "eRLUSD-7": {
        "key": "euler:sentora_rlusd:supply:cap_util",
        "name": "Euler Sentora RLUSD Supply Cap Utilization",
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


def _fetch_vaults(
    *, chain_id: int, vault_ids: List[str], vault_type: Optional[str] = None
) -> Dict[str, Dict]:
    params = {
        "chainId": chain_id,
        "vaults": ",".join(vault_ids),
    }
    if vault_type:
        params["type"] = vault_type

    r = requests.get(EULER_VAULT_ENDPOINT, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    vaults: Dict[str, Dict] = {}
    for v in data.values():
        if isinstance(v, dict) and v.get("vaultSymbol"):
            vaults[v["vaultSymbol"]] = v

    return vaults


def _require_vault(vaults: Dict[str, Dict], symbol: str) -> Dict:
    try:
        return vaults[symbol]
    except KeyError as exc:
        raise RuntimeError(f"Euler vault '{symbol}' not found") from exc


def _supply_cap_ratio(vault: Dict) -> float:
    total_assets = _to_int(vault["totalAssets"])
    supply_cap = _to_int(vault["supplyCap"])

    if supply_cap <= 0:
        return 0.0
    return min(total_assets / supply_cap, 1.0)


def fetch() -> List[Dict]:
    """
    Fetch Euler metrics:
    - USDC borrow APY (Avalanche, classic)
    - PYUSD supply cap usage (Ethereum, yield)
    - RLUSD supply cap usage (Ethereum, yield)
    """
    metrics: List[Dict] = []

    # classic borrow apy (Avalanche)
    classic_vaults = _fetch_vaults(
        chain_id=CLASSIC_CHAIN_ID,
        vault_ids=CLASSIC_VAULT_IDS,
        vault_type="classic",
    )
    target = _require_vault(classic_vaults, TARGET_VAULT_SYMBOL)

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
    eth_vaults = _fetch_vaults(
        chain_id=ETHEREUM_CHAIN_ID,
        vault_ids=ETHEREUM_VAULT_IDS,
    )

    for vault_symbol, meta in YIELD_VAULTS.items():
        vault = _require_vault(eth_vaults, vault_symbol)
        ratio = _supply_cap_ratio(vault)

        metrics.append(
            {
                "key": meta["key"],
                "name": meta["name"],
                "value": ratio,   # ratio: 0.0–1.0
                "unit": "ratio",
            }
        )

    return metrics
