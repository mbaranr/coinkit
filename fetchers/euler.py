import requests
from typing import Any


EULER_VAULT_URL = (
    "https://app.euler.finance/api/v1/vault"
    "?chainId=43114"
    "&vaults=0xbaC3983342b805E66F8756E265b3B0DdF4B685Fc,"
    "0x37ca03aD51B8ff79aAD35FadaCBA4CEDF0C3e74e"
    "&type=classic"
)

TARGET_VAULT_SYMBOL = "eUSDC-19"
EULER_APY_SCALE = 1e27  # ray-scaled


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


def fetch_usdc_borrow_rate() -> dict:
    r = requests.get(EULER_VAULT_URL, timeout=20)
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
    rate_pct = (raw / EULER_APY_SCALE) * 100.0

    return {
        "key": "euler:usdc:borrow",
        "name": "Euler USDC Borrow APY",
        "rate": rate_pct / 100.0,  # decimal
    }