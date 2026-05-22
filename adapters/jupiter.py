from httputil import get_json


BASE_URL = "https://lite-api.jup.ag/lend/v1/borrow/vaults"
ETHENA_URL = "https://lite-api.jup.ag/lend/v1/borrow/vaults?market=ethena"

VAULTS: dict[int, str] = {
    7: "USDC",
    30: "USDT",
    31: "USDG",
    60: "JupUSD",
    33: "USDS",
}

RATE_SCALE = 10_000


def _fetch_vaults() -> list[dict]:
    return get_json(BASE_URL, timeout=15)


def _fetch_vault(vault_id: int) -> dict | None:
    return next((v for v in _fetch_vaults() if v.get("id") == vault_id), None)


def _fetch_ethena_vaults() -> list[dict]:
    return get_json(ETHENA_URL, timeout=15)


def _extract_borrow_rate_decimal(vault_payload: dict) -> float:
    # Prefer borrowRateLiquidity when present; fall back to borrowRate.
    raw = vault_payload.get("borrowRateLiquidity", vault_payload.get("borrowRate"))
    if raw is None:
        raise KeyError("Missing borrowRate / borrowRateLiquidity in vault payload")

    return int(raw) / RATE_SCALE


def _extract_borrowable(vault_payload: dict) -> float:
    raw = vault_payload.get("borrowable")
    decimals = vault_payload.get("borrowToken", {}).get("decimals")
    if raw is None or decimals is None:
        raise KeyError("Missing borrowable / borrowToken.decimals in vault payload")

    return int(raw) / 10 ** int(decimals)


def fetch() -> list[dict]:
    """
    Fetch Jupiter syrupUSD/* borrow APRs for the configured vault ids, and
    USDG borrowable amounts from the USDe Loop vault on the ethena endpoint.

    Returns a list of metric dicts.
    """
    metrics: list[dict] = []

    vaults_by_id = {v.get("id"): v for v in _fetch_vaults()}

    for vault_id, token_symbol in VAULTS.items():
        payload = vaults_by_id.get(vault_id)
        if payload is None:
            raise KeyError(f"Jupiter vault id {vault_id} not found in vault list")

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

    for vault in _fetch_ethena_vaults():
        borrow_symbol = vault.get("borrowToken", {}).get("symbol")
        supply_symbol = vault.get("supplyToken", {}).get("symbol")
        if borrow_symbol != "USDG" or supply_symbol != "USDe":
            continue

        metrics.append(
            {
                "key": "jupiter:ethena:usde:usdg:borrow:available",
                "name": "Jupiter Ethena USDe/USDG Borrowable",
                "value": _extract_borrowable(vault),
                "unit": "available",
                "adapter": "jupiter",
            }
        )

    return metrics