import requests
from typing import Any, Dict, List


SUMMARY_URL = "https://v3-api.compound.finance/market/{network}/{comet}/summary"
REWARDS_URL = "https://v3-api.compound.finance/market/all-networks/all-contracts/rewards/dapp-data"

MARKETS = [
    {
        "network": "mainnet",
        "chain_id": 1,
        "comet": "0xA17581A9E3356d9A858b789D68B4d866e593aE94",
        "key": "compound:v3:eth:borrow:rate",
        "name": "Compound V3 ETH Borrow APR",
    },
    {
        "network": "base-mainnet",
        "chain_id": 8453,
        "comet": "0x46e6b214b524310239732D51387075E0e70970bf",
        "key": "compound:v3:base:eth:borrow:rate",
        "name": "Compound V3 Base ETH Borrow APR",
    },
]


def _to_float(x: Any) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        return float(x)
    raise TypeError(f"Cannot convert to float: {x}")


def _fetch_borrow_apr(network: str, comet: str) -> float:
    url = SUMMARY_URL.format(network=network, comet=comet)
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()

    if not isinstance(data, dict) or "borrow_apr" not in data:
        raise RuntimeError(f"Compound summary response missing borrow_apr for {network}/{comet}")

    return _to_float(data["borrow_apr"])


def _fetch_rewards_map() -> Dict[str, float]:
    """
    Returns a map of "chain_id:comet_lower" -> borrow_rewards_apr for WETH markets.
    """
    r = requests.get(REWARDS_URL, timeout=20)
    r.raise_for_status()
    data = r.json()

    rewards: Dict[str, float] = {}
    for entry in data:
        base = entry.get("base_asset", {})
        if base.get("symbol") != "WETH":
            continue
        chain_id = entry.get("chain_id")
        comet_addr = entry.get("comet", {}).get("address", "").lower()
        apr = entry.get("borrow_rewards_apr", "0")
        rewards[f"{chain_id}:{comet_addr}"] = _to_float(apr)

    return rewards


def fetch() -> List[Dict]:
    """
    Fetch Compound V3 ETH borrow rates (net of COMP rewards):
    - Ethereum mainnet
    - Base
    """
    rewards = _fetch_rewards_map()
    metrics: List[Dict] = []

    for market in MARKETS:
        borrow_apr = _fetch_borrow_apr(market["network"], market["comet"])

        reward_key = f"{market['chain_id']}:{market['comet'].lower()}"
        reward_apr = rewards.get(reward_key, 0.0)

        net_rate = borrow_apr - reward_apr

        metrics.append(
            {
                "key": market["key"],
                "name": market["name"],
                "value": net_rate,
                "unit": "rate",
                "adapter": "compound",
            }
        )

    return metrics
