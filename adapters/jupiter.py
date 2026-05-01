from httputil import get_json


BASE_URL = "https://api.solana.fluid.io/v1/borrowing/vaults"

VAULTS: dict[int, str] = {
    7: "USDC",
    30: "USDT",
    31: "USDG",
    60: "JupUSD",
    33: "USDS",
}

RATE_SCALE = 10_000


def _fetch_vault(vault_id: int) -> dict:
    return get_json(f"{BASE_URL}/{vault_id}", timeout=15)


def _extract_borrow_rate_decimal(vault_payload: dict) -> float:
    # Prefer borrowRateLiquidity when present; fall back to borrowRate.
    raw = vault_payload.get("borrowRateLiquidity", vault_payload.get("borrowRate"))
    if raw is None:
        raise KeyError("Missing borrowRate / borrowRateLiquidity in vault payload")

    return int(raw) / RATE_SCALE


def fetch() -> list[dict]:
    """
    Fetch Jupiter syrupUSD/* borrow APRs for the configured vault ids.

    Returns a list of metric dicts.
    """
    metrics: list[dict] = []

    for vault_id, token_symbol in VAULTS.items():
        payload = _fetch_vault(vault_id)
        rate = _extract_borrow_rate_decimal(payload)

        token_key = token_symbol.lower()

        metrics.append(
            {
                "key": f"jupiter:syrupusdc:{token_key}:borrow:rate",
                "name": f"Jupiter syrupUSDC/{token_symbol} Borrow APR",
                "value": rate,
                "unit": "rate",
                "adapter": "jupiter",
            }
        )

    return metrics