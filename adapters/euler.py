import requests
from typing import Dict, List

from Crypto.Hash import keccak


# ── RPC + VaultLens ──────────────────────────────────────────────────────────
# Euler's REST API is behind Cloudflare. All data is now fetched on-chain via
# their RPC proxy and the VaultLens contract (getVaultInfoFull).

EULER_RPC_URL = "https://app.euler.finance/api/rpc/{chain_id}"
EULER_APY_SCALE = 1e27  # ray

# VaultLens addresses per chain (from euler-xyz/euler-interfaces)
VAULT_LENS = {
    1:     "0xA18D79deB85C414989D7297F23e5391703Ea66aB",
    43114: "0x7a2A57a0ed6807c7dbF846cc74aa04eE9DFa7F57",
}

# ── VaultInfoFull struct layout (fixed-position word indices) ────────────────
# Returned inside an outer ABI tuple, so word 0 = outer offset (32).
# Words below are 1-indexed from the struct start.
_W_TOTAL_BORROWED = 16
_W_TOTAL_ASSETS   = 17
_W_SUPPLY_CAP     = 26
_W_BORROW_CAP     = 27
# irmInfo is a dynamic struct; its offset lives at word 40.
_W_IRM_OFFSET     = 40

# ── Chains ───────────────────────────────────────────────────────────────────
AVALANCHE_CHAIN_ID = 43114
ETHEREUM_CHAIN_ID  = 1

# ── Markets ──────────────────────────────────────────────────────────────────
MARKET_9SUMMITS = "9summits"
MARKET_TURTLE   = "turtle"
MARKET_SENTORA  = "sentora"

# Avalanche vaults
NINESUMMITS_SAVUSD_VAULT_ID = "0xbaC3983342b805E66F8756E265b3B0DdF4B685Fc"
NINESUMMITS_USDC_VAULT_ID   = "0x37ca03aD51B8ff79aAD35FadaCBA4CEDF0C3e74e"

TURTLE_SAVUSD_VAULT_ID = "0x5Db7b0dbcDa67E4Ff1B4D9b17a1cf2e6416BCC81"
TURTLE_USDC_VAULT_ID   = "0xA9B21f76a3CD97F3e886Bf299abc5F7cCca58d5f"

# Ethereum / Sentora vaults
VAULT_SYRUPUSDC_PYUSD = "0xE1d2a34e34039711a655aC06Bc1dba6F7ab786B3"
VAULT_SYRUPUSDC_RLUSD = "0x4BC68f0CC010A0BedA0E3f63CfBEcDee5Ad55A18"
VAULT_RLUSD           = "0xaF5372792a29dC6b296d6FFD4AA3386aff8f9BB2"
VAULT_PYUSD           = "0xba98fC35C9dfd69178AD5dcE9FA29c64554783b5"
VAULT_USDC_RLUSD      = "0x9bD52F2805c6aF014132874124686e7b248c2Cbb"
VAULT_USDC_PYUSD      = "0xAB2726DAf820Aa9270D14Db9B18c8d187cbF2f30"


SENTORA_CAP_PAIRS = [
    {
        "asset": "syrupusdc:rlusd",
        "pair_name": "Euler Sentora syrupUSDC/RLUSD",
        "collateral_vault_id": VAULT_SYRUPUSDC_RLUSD,
        "debt_vault_id": VAULT_RLUSD,
        "supply_key": f"euler:{MARKET_SENTORA}:syrupusdc:rlusd:supply:cap_util",
        "borrow_key": f"euler:{MARKET_SENTORA}:syrupusdc:rlusd:borrow:cap_util",
        "name_supply": "Euler Sentora syrupUSDC/RLUSD Supply Cap Utilization",
        "name_borrow": "Euler Sentora syrupUSDC/RLUSD Borrow Cap Utilization",
        "adapter": "euler",
    },
    {
        "asset": "rlusd:usdc",
        "pair_name": "Euler Sentora RLUSD/USDC",
        "collateral_vault_id": VAULT_RLUSD,
        "debt_vault_id": VAULT_USDC_RLUSD,
        "supply_key": f"euler:{MARKET_SENTORA}:rlusd:usdc:supply:cap_util",
        "borrow_key": f"euler:{MARKET_SENTORA}:rlusd:usdc:borrow:cap_util",
        "name_supply": "Euler Sentora RLUSD/USDC Supply Cap Utilization",
        "name_borrow": "Euler Sentora RLUSD/USDC Borrow Cap Utilization",
        "adapter": "euler",
    },
    {
        "asset": "syrupusdc:pyusd",
        "pair_name": "Euler Sentora syrupUSDC/PYUSD",
        "collateral_vault_id": VAULT_SYRUPUSDC_PYUSD,
        "debt_vault_id": VAULT_PYUSD,
        "supply_key": f"euler:{MARKET_SENTORA}:syrupusdc:pyusd:supply:cap_util",
        "borrow_key": f"euler:{MARKET_SENTORA}:syrupusdc:pyusd:borrow:cap_util",
        "name_supply": "Euler Sentora syrupUSDC/PYUSD Supply Cap Utilization",
        "name_borrow": "Euler Sentora syrupUSDC/PYUSD Borrow Cap Utilization",
        "adapter": "euler",
    },
    {
        "asset": "pyusd:usdc",
        "pair_name": "Euler Sentora PYUSD/USDC",
        "collateral_vault_id": VAULT_PYUSD,
        "debt_vault_id": VAULT_USDC_PYUSD,
        "supply_key": f"euler:{MARKET_SENTORA}:pyusd:usdc:supply:cap_util",
        "borrow_key": f"euler:{MARKET_SENTORA}:pyusd:usdc:borrow:cap_util",
        "name_supply": "Euler Sentora PYUSD/USDC Supply Cap Utilization",
        "name_borrow": "Euler Sentora PYUSD/USDC Borrow Cap Utilization",
        "adapter": "euler",
    },
    {
        "asset": "usdc:pyusd",
        "pair_name": "Euler Sentora USDC/PYUSD",
        "collateral_vault_id": VAULT_USDC_PYUSD,
        "debt_vault_id": VAULT_PYUSD,
        "supply_key": f"euler:{MARKET_SENTORA}:usdc:pyusd:supply:cap_util",
        "borrow_key": f"euler:{MARKET_SENTORA}:usdc:pyusd:borrow:cap_util",
        "name_supply": "Euler Sentora USDC/PYUSD Supply Cap Utilization",
        "name_borrow": "Euler Sentora USDC/PYUSD Borrow Cap Utilization",
        "adapter": "euler",
    },
    {
        "asset": "usdc:rlusd",
        "pair_name": "Euler Sentora USDC/RLUSD",
        "collateral_vault_id": VAULT_USDC_RLUSD,
        "debt_vault_id": VAULT_RLUSD,
        "supply_key": f"euler:{MARKET_SENTORA}:usdc:rlusd:supply:cap_util",
        "borrow_key": f"euler:{MARKET_SENTORA}:usdc:rlusd:borrow:cap_util",
        "name_supply": "Euler Sentora USDC/RLUSD Supply Cap Utilization",
        "name_borrow": "Euler Sentora USDC/RLUSD Borrow Cap Utilization",
        "adapter": "euler",
    },
]


# ── ABI helpers ──────────────────────────────────────────────────────────────

def _keccak256(data: bytes) -> bytes:
    k = keccak.new(digest_bits=256)
    k.update(data)
    return k.digest()


_GET_VAULT_INFO_FULL_SELECTOR = _keccak256(b"getVaultInfoFull(address)")[:4].hex()


def _encode_call(vault_address: str) -> str:
    addr = vault_address.lower().replace("0x", "").zfill(64)
    return "0x" + _GET_VAULT_INFO_FULL_SELECTOR + addr


def _decode_words(hex_result: str) -> List[int]:
    raw = hex_result[2:]  # strip 0x
    return [int(raw[i : i + 64], 16) for i in range(0, len(raw), 64)]


# ── RPC batch caller ────────────────────────────────────────────────────────

def _rpc_batch(chain_id: int, vault_addresses: List[str]) -> Dict[str, List[int]]:
    """
    Batch eth_call for getVaultInfoFull on each vault.
    Returns {lowercase_vault_address: decoded_words}.
    """
    lens = VAULT_LENS.get(chain_id)
    if not lens:
        raise RuntimeError(f"No VaultLens address for chain {chain_id}")

    batch = []
    for i, vault in enumerate(vault_addresses):
        batch.append({
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": lens, "data": _encode_call(vault)}, "latest"],
            "id": i + 1,
        })

    url = EULER_RPC_URL.format(chain_id=chain_id)
    r = requests.post(url, json=batch, timeout=30)
    r.raise_for_status()
    responses = r.json()

    results: Dict[str, List[int]] = {}
    for resp in responses:
        idx = resp["id"] - 1
        if "error" in resp:
            raise RuntimeError(
                f"RPC error for vault {vault_addresses[idx]}: {resp['error']}"
            )
        result = resp.get("result", "0x")
        if result == "0x" or len(result) < 66:
            raise RuntimeError(
                f"Empty response for vault {vault_addresses[idx]} on chain {chain_id}"
            )
        results[vault_addresses[idx].lower()] = _decode_words(result)

    return results


# ── Field extractors ─────────────────────────────────────────────────────────

def _borrow_apy(words: List[int]) -> float:
    """
    Navigate VaultInfoFull → irmInfo → interestRateInfo[0].borrowAPY.

    irmInfo is a dynamic struct whose byte-offset is at word 40.
    Inside irmInfo (VaultInterestRateModelInfo):
      +0 queryFailure, +1 queryFailureReason(offset), +2 vault, +3 irm,
      +4 interestRateInfo[](offset), +5 interestRateModelInfo(offset)
    interestRateInfo is an array of InterestRateInfo structs:
      cash, borrows, borrowSPY, borrowAPY, supplyAPY
    """
    irm_byte_offset = words[_W_IRM_OFFSET]
    irm_start = 1 + irm_byte_offset // 32

    iri_byte_offset = words[irm_start + 4]
    iri_start = irm_start + iri_byte_offset // 32

    arr_len = words[iri_start]
    if arr_len == 0:
        raise RuntimeError("interestRateInfo array is empty")

    # borrowAPY is the 4th field (index 3) in InterestRateInfo
    borrow_apy_raw = words[iri_start + 1 + 3]
    return borrow_apy_raw / EULER_APY_SCALE


def _supply_cap_ratio(words: List[int]) -> float:
    total_assets = words[_W_TOTAL_ASSETS]
    supply_cap = words[_W_SUPPLY_CAP]
    if supply_cap <= 0:
        return 0.0
    return min(total_assets / supply_cap, 1.0)


def _borrow_cap_ratio(words: List[int]) -> float:
    total_borrowed = words[_W_TOTAL_BORROWED]
    borrow_cap = words[_W_BORROW_CAP]
    if borrow_cap <= 0:
        return 0.0
    return min(total_borrowed / borrow_cap, 1.0)


# ── Public fetch ─────────────────────────────────────────────────────────────

def fetch() -> List[Dict]:
    """
    Fetch Euler metrics via on-chain RPC:
    - USDC borrow APY (Avalanche, 9Summits market)
    - USDC borrow APY (Avalanche, Turtle market)
    - Sentora paired cap utilization (Ethereum)
    """
    metrics: List[Dict] = []

    # ── Avalanche: borrow APY for 9Summits + Turtle USDC vaults ──────────
    avax_vaults = _rpc_batch(
        AVALANCHE_CHAIN_ID,
        [NINESUMMITS_USDC_VAULT_ID, TURTLE_USDC_VAULT_ID],
    )

    ninesummits_words = avax_vaults[NINESUMMITS_USDC_VAULT_ID.lower()]
    metrics.append({
        "key": f"euler:{MARKET_9SUMMITS}:usdc:borrow:rate",
        "name": "Euler 9Summits savUSD/USDC Borrow APY",
        "value": _borrow_apy(ninesummits_words),
        "unit": "rate",
        "adapter": "euler",
    })

    turtle_words = avax_vaults[TURTLE_USDC_VAULT_ID.lower()]
    metrics.append({
        "key": f"euler:{MARKET_TURTLE}:usdc:borrow:rate",
        "name": "Euler Turtle savUSD/USDC Borrow APY",
        "value": _borrow_apy(turtle_words),
        "unit": "rate",
        "adapter": "euler",
    })

    # ── Ethereum: Sentora paired cap metrics ─────────────────────────────
    unique_vault_ids = list({
        vid
        for pair in SENTORA_CAP_PAIRS
        for vid in (pair["collateral_vault_id"], pair["debt_vault_id"])
    })
    eth_vaults = _rpc_batch(ETHEREUM_CHAIN_ID, unique_vault_ids)

    for pair in SENTORA_CAP_PAIRS:
        coll_words = eth_vaults[pair["collateral_vault_id"].lower()]
        debt_words = eth_vaults[pair["debt_vault_id"].lower()]

        metrics.append({
            "key": pair["supply_key"],
            "name": pair["name_supply"],
            "value": _supply_cap_ratio(coll_words),
            "unit": "ratio",
            "adapter": "euler",
        })
        metrics.append({
            "key": pair["borrow_key"],
            "name": pair["name_borrow"],
            "value": _borrow_cap_ratio(debt_words),
            "unit": "ratio",
            "adapter": "euler",
        })

    return metrics
