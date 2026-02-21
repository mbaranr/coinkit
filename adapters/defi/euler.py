import requests
from typing import Any, Dict, List, Optional

EULER_VAULT_ENDPOINT = "https://app.euler.finance/api/v1/vault"
EULER_APY_SCALE = 1e27  # ray-scaled

# Chains
AVALANCHE_CHAIN_ID = 43114
ETHEREUM_CHAIN_ID = 1

# Markets (for consistent metric keys)
MARKET_9SUMMITS = "9summits"
MARKET_TURTLE = "turtle"
MARKET_SENTORA = "sentora"

# Avalanche markets (vault addresses from positions URLs)
NINESUMMITS_SAVUSD_VAULT_ID = "0xbaC3983342b805E66F8756E265b3B0DdF4B685Fc"
NINESUMMITS_USDC_VAULT_ID = "0x37ca03aD51B8ff79aAD35FadaCBA4CEDF0C3e74e"

TURTLE_SAVUSD_VAULT_ID = "0x5Db7b0dbcDa67E4Ff1B4D9b17a1cf2e6416BCC81"
TURTLE_USDC_VAULT_ID = "0xA9B21f76a3CD97F3e886Bf299abc5F7cCca58d5f"

# Ethereum / Sentora yield vault addresses
ETHEREUM_VAULT_IDS = [
    "0xba98fC35C9dfd69178AD5dcE9FA29c64554783b5",  # PYUSD
    "0xaF5372792a29dC6b296d6FFD4AA3386aff8f9BB2",  # RLUSD
]

SENTORA_VAULTS = {
    "ePYUSD-6": {
        "asset": "pyusd",
        "name": "Euler Sentora PYUSD Supply Cap Utilization",
    },
    "eRLUSD-7": {
        "asset": "rlusd",
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
    """
    Index by vaultSymbol. Only safe when symbols are unique in the requested set.
    """
    params = {"chainId": chain_id, "vaults": ",".join(vault_ids)}
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


def _fetch_vaults_by_address(
    *, chain_id: int, vault_ids: List[str], vault_type: Optional[str] = None
) -> Dict[str, Dict]:
    """
    Index by vault address. Recommended for cluster markets to avoid symbol collisions.
    """
    params = {"chainId": chain_id, "vaults": ",".join(vault_ids)}
    if vault_type:
        params["type"] = vault_type

    r = requests.get(EULER_VAULT_ENDPOINT, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    vaults: Dict[str, Dict] = {}
    for v in data.values():
        if isinstance(v, dict):
            addr = v.get("vault") or v.get("vaultAddress") or v.get("address")
            if addr:
                vaults[str(addr).lower()] = v
    return vaults


def _require_vault(vaults: Dict[str, Dict], symbol: str) -> Dict:
    try:
        return vaults[symbol]
    except KeyError as exc:
        raise RuntimeError(f"Euler vault '{symbol}' not found") from exc


def _require_vault_addr(vaults: Dict[str, Dict], addr: str) -> Dict:
    try:
        return vaults[addr.lower()]
    except KeyError as exc:
        raise RuntimeError(f"Euler vault address '{addr}' not found") from exc


def _borrow_apy(vault: Dict) -> float:
    irm = vault.get("irmInfo", {}) or {}
    info = irm.get("interestRateInfo") or []
    if not info:
        raise RuntimeError("Euler response missing interestRateInfo")
    row = info[0]
    raw = _to_int(row.get("borrowAPY"))
    return raw / EULER_APY_SCALE


def _supply_cap_ratio(vault: Dict) -> float:
    total_assets = _to_int(vault["totalAssets"])
    supply_cap = _to_int(vault["supplyCap"])
    if supply_cap <= 0:
        return 0.0
    return min(total_assets / supply_cap, 1.0)


def fetch() -> List[Dict]:
    """
    Fetch Euler metrics:
    - USDC borrow APY (Avalanche, 9Summits market)
    - USDC borrow APY (Avalanche, Turtle market)
    - PYUSD supply cap usage (Ethereum, Sentora)
    - RLUSD supply cap usage (Ethereum, Sentora)
    """
    metrics: List[Dict] = []

    # Avalanche: 9Summits (positions URL gives vault addresses)
    # Borrow APY is taken from the borrowed asset vault (USDC)
    ninesummits_vaults = _fetch_vaults_by_address(
        chain_id=AVALANCHE_CHAIN_ID,
        vault_ids=[NINESUMMITS_SAVUSD_VAULT_ID, NINESUMMITS_USDC_VAULT_ID],
        vault_type="classic",  # keep if Euler API requires it for this market
    )
    ninesummits_usdc = _require_vault_addr(ninesummits_vaults, NINESUMMITS_USDC_VAULT_ID)

    metrics.append(
        {
            "key": f"euler:{MARKET_9SUMMITS}:usdc:borrow:rate",
            "name": "Euler 9Summits savUSD/USDC Borrow APY",
            "value": _borrow_apy(ninesummits_usdc),
            "unit": "rate",
            "adapter": "euler",
        }
    )

    # Avalanche: Turtle (borrowed asset vault is USDC)
    turtle_vaults = _fetch_vaults_by_address(
        chain_id=AVALANCHE_CHAIN_ID,
        vault_ids=[TURTLE_SAVUSD_VAULT_ID, TURTLE_USDC_VAULT_ID],
        # no type param; add one only if the API requires it for cluster markets
    )
    turtle_usdc = _require_vault_addr(turtle_vaults, TURTLE_USDC_VAULT_ID)

    metrics.append(
        {
            "key": f"euler:{MARKET_TURTLE}:usdc:borrow:rate",
            "name": "Euler Turtle savUSD/USDC Borrow APY",
            "value": _borrow_apy(turtle_usdc),
            "unit": "rate",
            "adapter": "euler",
        }
    )

    # Ethereum: Sentora supply cap usage
    eth_vaults = _fetch_vaults(chain_id=ETHEREUM_CHAIN_ID, vault_ids=ETHEREUM_VAULT_IDS)

    for vault_symbol, meta in SENTORA_VAULTS.items():
        vault = _require_vault(eth_vaults, vault_symbol)
        metrics.append(
            {
                "key": f"euler:{MARKET_SENTORA}:{meta['asset']}:supply:cap_util",
                "name": meta["name"],
                "value": _supply_cap_ratio(vault),  # ratio: 0.0–1.0
                "unit": "ratio",
                "adapter": "euler",
            }
        )

    return metrics