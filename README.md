# Stonks

A minimal Python bot that monitors **USDC** borrow rates on [Silo Finance](https://app.silo.finance/markets/avalanche/savusd-usdc-142?action=borrow
) and [Euler Finance](https://app.euler.finance/positions/0xbaC3983342b805E66F8756E265b3B0DdF4B685Fc/0x37ca03aD51B8ff79aAD35FadaCBA4CEDF0C3e74e?network=avalanche), and sends Discord alerts when rates move significantly (≥ 1 percentage point).

## What it does

The bot is designed to:

- track USDC borrow APR / APY
- persist state between runs
- send Discord webhook alerts when the borrow rate moves by **±1.00%** from the current baseline
- run periodically via GitHub Actions
