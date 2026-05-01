# coinkit

A minimal Discord bot for monitoring DeFi signals.

CoinKit polls a handful of DeFi protocols every 5 minutes and posts alerts to per-protocol Discord channels:

- **Cap utilization**: alerts when supply or borrow caps are reached or freed.
- **Rate moves**: alerts when interest rates drift past per-adapter thresholds.
- **ICO schedules**: alerts on newly scheduled launches and on launch day.

Adapters cover Aave, Compound, Dolomite, Euler, Jupiter, MetaDAO, and Silo.

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
| `EULER_CHANNEL_ID` | yes | Channel for Euler alerts |
| `SILO_CHANNEL_ID` | yes | Channel for Silo alerts |
| `METADAO_CHANNEL_ID` | yes | Channel for MetaDAO alerts |
| `DOLOMITE_CHANNEL_ID` | yes | Channel for Dolomite alerts |
| `AAVE_CHANNEL_ID` | yes | Channel for Aave alerts |
| `COMPOUND_CHANNEL_ID` | yes | Channel for Compound alerts |
| `JUPITER_CHANNEL_ID` | yes | Channel for Jupiter alerts |
| `GITHUB_TOKEN` | optional | Enables the `$issue` command |
| `GITHUB_REPO` | optional | Target repo for `$issue`, e.g. `owner/name` |

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

- **Caps**: state-based. Threshold is 99.995% utilization. Paired Sentora caps fire a major alert when both supply and borrow caps are freed at once.
- **Rates**: delta-based against a sticky anchor. Major at 10%. Minor thresholds: 0.1% for Aave and Compound, 0.5% for Jupiter, 1% for the rest.
- **ICOs**: alert on first sighting and on launch day (UTC).

## Layout

```
bot.py               Discord entrypoint, commands, alert dispatch loop
engine.py            Polls adapters, records samples, evaluates alerts
adapters/*.py        One module per data source
alerts.py            Cap / rate / ICO alert logic
db.py                sqlite-backed state (state.db)
purge_metrics.py     Maintenance: remove metric keys
tests.py             Unit + live-network tests
```

## Tests

```bash
uv run python -m unittest tests
```

Adapter tests hit live APIs and require internet. Purge-metrics tests are hermetic.
