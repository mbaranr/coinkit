import requests


SILO_URL = "https://app.silo.finance/api/lending-market/avalanche/142/rates"


def fetch_usdc_borrow_rate():
    data = requests.get(SILO_URL, timeout=10).json()

    silo = data["silo1"]          # USDC market
    points = silo["data"]["24h"]

    latest = points[-1]
    borrow_apr_raw = int(latest["borrowApr"])
    borrow_apr = borrow_apr_raw / 1e18

    return {
        "key": "silo:142:usdc:borrow",
        "name": "Silo USDC Borrow APR",
        "rate": borrow_apr,
    }