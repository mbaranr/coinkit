import base64
import os

from httputil import get_json, post_json


# Kamino Ethena Market and its reserves.
# The UI label is "Ethena Market"; the pubkey matches the page at
# kamino.com/borrow/reserve/<market>/<reserve>.
MARKET = "BJnbcRHqvppTyGesLzWASGKnmnF1wq9jZu6ExrjT7wvF"

# reserve pubkey -> display token symbol
RESERVES = {
    "Q5av3wh8j9KCqSjs9njUdsPhrMSKBCUyr4VyUndUUFA": "USDG",
    "EDf6dGbVnCCABbNhE3mp5i1jV2JhDAVmTWb1ztij1Yhs": "PYUSD",
}

LIVE_URL = f"https://api.kamino.finance/kamino-market/{MARKET}/reserves/metrics"

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

# Byte offsets into the klend Reserve account data, including the 8-byte Anchor
# discriminator. Derived from the klend IDL (Kamino-Finance/klend-sdk
# src/idl/klend.json) and validated on-chain on 2026-08-06: PYUSD's borrowLimit
# read back its $237M governance cap exactly. Each field is followed by large
# reserved padding, so the offsets hold across program upgrades (new fields land
# in padding).
_MINT_DECIMALS_OFFSET = 272  # liquidity.mintDecimals, u64
_BORROW_LIMIT_OFFSET = 5024  # config.borrowLimit, u64
# utilizationLimitBlockBorrowingAbovePct, u8: a percent, 0 means no limit. The
# UI's "Liq. Available" caps borrows at this percent of deposits.
_UTIL_LIMIT_OFFSET = 5501

_RESERVE_ACCOUNT_LEN = 8624


def _fetch_live_reserves() -> dict:
    reserves = get_json(LIVE_URL, timeout=15)
    return {r.get("reserve"): r for r in reserves}


def _fetch_reserve_accounts() -> dict:
    """
    Reserve config (borrow cap, utilization block, decimals) straight from
    chain. The metrics history endpoint also carries the cap, but it lags
    several hours behind and serves an empty window while it catches up.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getMultipleAccounts",
        "params": [list(RESERVES), {"encoding": "base64"}],
    }
    resp = post_json(SOLANA_RPC_URL, json=payload, timeout=15)
    values = (resp.get("result") or {}).get("value") or []
    if len(values) != len(RESERVES):
        raise RuntimeError(
            f"Kamino expected {len(RESERVES)} reserve accounts, got {len(values)}"
        )

    accounts = {}
    for reserve, value in zip(RESERVES, values):
        symbol = RESERVES[reserve]
        if not value:
            raise RuntimeError(f"Kamino {symbol} reserve account not found on-chain")
        data = base64.b64decode(value["data"][0])
        # Short data would make the fixed offsets below read silent garbage.
        if len(data) < _RESERVE_ACCOUNT_LEN:
            raise RuntimeError(
                f"Kamino {symbol} reserve account is {len(data)}B, "
                f"expected >= {_RESERVE_ACCOUNT_LEN}B"
            )
        accounts[reserve] = data
    return accounts


def _u64(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 8], "little")


def _borrowable(reserve: str, symbol: str, live_by_reserve: dict, account: bytes) -> float:
    decimals = _u64(account, _MINT_DECIMALS_OFFSET)
    cap = _u64(account, _BORROW_LIMIT_OFFSET) / 10 ** decimals

    live = live_by_reserve.get(reserve)
    if live is None:
        raise RuntimeError(f"Kamino {symbol} reserve not found in live metrics")
    total_supply = float(live["totalSupply"])
    total_borrows = float(live["totalBorrow"])
    # totalSupply - totalBorrow underestimates on-chain liquidity by
    # accumulatedProtocolFees (~5 figures on a ~$250M reserve), which
    # is immaterial: the cap is the binding constraint in normal state.
    on_chain = max(0.0, total_supply - total_borrows)

    constraints = [on_chain, cap - total_borrows]
    # Borrowing is blocked above util_pct% of deposits, so the headroom this
    # leaves is its own constraint (binds before the cap on PYUSD).
    util_pct = account[_UTIL_LIMIT_OFFSET]
    if util_pct:
        constraints.append(util_pct / 100.0 * total_supply - total_borrows)

    return max(0.0, min(constraints))


def fetch() -> list[dict]:
    live_by_reserve = _fetch_live_reserves()
    accounts = _fetch_reserve_accounts()

    metrics = []
    for reserve, symbol in RESERVES.items():
        borrowable = _borrowable(reserve, symbol, live_by_reserve, accounts[reserve])
        metrics.append(
            {
                "key": f"kamino:ethena:{symbol.lower()}:borrow:available",
                "name": f"Kamino Ethena {symbol} Borrowable",
                "value": borrowable,
                "unit": "available",
                "adapter": "kamino",
            }
        )
    return metrics
