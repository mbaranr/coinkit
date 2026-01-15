import requests

EULER_URL = (
    "https://app.euler.finance/api/v1/vault"
    "?chainId=43114"
    "&vaults=0x37ca03aD51B8ff79aAD35FadaCBA4CEDF0C3e74e"
    "&type=classic"
)


def fetch_usdc_borrow_rate():
    data = requests.get(EULER_URL, timeout=10).json()

    vault = data["0x37ca03aD51B8ff79aAD35FadaCBA4CEDF0C3e74e"]

    ir_info = vault["irmInfo"]["interestRateInfo"]
    if not ir_info:
        raise RuntimeError("Euler interestRateInfo empty")

    borrow_raw = ir_info[0]["borrowAPY"]
    borrow_apy = int(borrow_raw.replace("__bigint__", "")) / 1e27

    return {
        "key": "euler:usdc:borrow",
        "name": "Euler USDC Borrow APY",
        "rate": borrow_apy,
    }