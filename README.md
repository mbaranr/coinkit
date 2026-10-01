# coinkit

A minimal Discord bot for monitoring DeFi signals.

## What it does

CoinKit polls a handful of DeFi protocols every 5 minutes and posts alerts to per-protocol Discord channels:

- **Cap utilization**: alerts when supply or borrow caps are reached or freed.
- **Rate moves**: alerts when interest rates drift past per-adapter thresholds.
- **Borrowable liquidity**: tiered alerts when the amount available to borrow crosses 1k / 100k / 10M.
- **ICO schedules**: alerts on newly scheduled launches and on launch day.

Active adapters: Aave (V3 Ethereum and Monad WETH), Dolomite (ETH), Jupiter (Ethena USDG borrowable), and Kamino. Paused but kept in code: Compound, Euler, Silo, and MetaDAO (upstream unreachable). Paused adapters don't need a channel id and their keys are hidden from `$toys`.

## Quick start

```bash
uv sync
# create a .env file with the variables listed below
uv run python bot.py
```

## Environment

| Variable | Required | Purpose |
| --- | --- | --- |
| `DISCORD_TOKEN` | yes | Discord bot token |
| `ENGINE_ERROR_DM_USER_ID` | yes | User id to DM on engine errors |
| `METADAO_CHANNEL_ID` | yes | Channel for MetaDAO alerts |
| `DOLOMITE_CHANNEL_ID` | yes | Channel for Dolomite alerts |
| `AAVE_CHANNEL_ID` | yes | Channel for Aave alerts |
| `JUPITER_CHANNEL_ID` | yes | Channel for Jupiter alerts |
| `KAMINO_CHANNEL_ID` | yes | Channel for Kamino alerts |
| `GITHUB_TOKEN` | optional | Enables the `$issue` command |
| `GITHUB_REPO` | optional | Target repo for `$issue`, e.g. `owner/name` |
| `SOLANA_RPC_URL` | optional | Preferred Solana RPC for Kamino on-chain reads. Public nodes are tried as fallback either way. |

## Discord commands

| Command | Description |
| --- | --- |
| `$help` | List commands |
| `$info` | Thresholds, behavior, repo link |
| `$toys` | List known metric keys |
| `$sub <key>` | Subscribe (get tagged on alerts for that key) |
| `$unsub <key>` | Unsubscribe |
| `$mytoys` | Show your subscriptions |
| `$issue <text>` | Open a GitHub issue from chat |
| `$ping` | pong |

## Alert thresholds

- **Caps**: state-based. Threshold is 99.995% utilization. Adapters can declare paired supply/borrow caps (`PAIRED_CAPS`) that fire a major alert when both are freed at once.
- **Rates**: delta-based against a sticky anchor. Major at 10%. Minor thresholds: 0.1% for Aave and Dolomite ETH, 1% for the rest.
- **Available**: tier-based. Fires on upward crossings at 1k / 100k / 10M of the borrow token. The 10M tier is major.
- **ICOs**: alert on first sighting and on launch day (UTC).

## Layout

```
bot.py               Discord entrypoint, commands, alert dispatch loop
engine.py            Adapter discovery, cap/rate/ICO alert logic, run_once orchestrator
adapters/*.py        One module per data source
db.py                sqlite-backed state (state.db)
httputil.py          Shared HTTP helpers (get_json, post_json, to_float)
scripts/*.py         Maintenance CLIs (e.g. purge_metrics.py)
tests.py             Unit + live-network tests
```

## Tests

```bash
uv run python -m unittest tests
```

Adapter tests hit live APIs and require internet. Purge-metrics tests are hermetic.
