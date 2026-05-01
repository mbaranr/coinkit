# CoinKit

Minimal Discord bot for DeFi alerts (caps, rates, ICOs). See `README.md` for user-facing setup and the Discord command list.

## Layout

```
bot.py               Discord entrypoint, commands, alert loop
engine.py            Orchestrates fetchers, records samples, dispatches alerts
adapters/*.py        One module per data source
alerts.py            Cap / rate / ICO alert logic and thresholds
db.py                sqlite state (state.db)
purge_metrics.py     CLI: remove metric keys from state.db
tests.py             Unit tests + live-network adapter tests
```

**DO NOT** reintroduce subpackages (no `alerts/`, `db/`, `scripts/`, `adapters/defi/`, etc.). The flat structure is deliberate.

## Tooling

`uv` for everything. **YOU MUST use `uv run`** for any Python invocation. There is no `requirements.txt`; `uv.lock` is committed.

- `uv sync`, `uv add <pkg>`, `uv remove <pkg>`
- `uv run python bot.py`
- `uv run python -m unittest tests`

## Adapter contract

Each `adapters/<name>.py` MUST expose `fetch() -> list[dict]`. Metric dicts have `key`, `name`, `value`, `unit`, `adapter`.

`engine.run_once` routes by `unit`:
- `"ratio"` to cap alerts
- numeric (e.g. `"rate"`) to rate alerts
- `"json"` to ICO alerts

## Where volatile config lives

Thresholds, intervals, channel mappings, and the adapter set change often. Read the source rather than assuming:

- Alert thresholds and per-adapter rate rules: top of `alerts.py` and inside `handle_rate_metric`.
- Cap-full threshold and paired-cap logic: `CAP_FULL_THRESHOLD` and `handle_paired_caps` in `alerts.py`.
- Polling interval: `ALERT_INTERVAL_SECONDS` in `bot.py`.
- Adapter list and required `*_CHANNEL_ID` env vars: `ADAPTER_CHANNEL_ENV` in `bot.py`.
- Sentora cap pairs: `SENTORA_CAP_PAIRS` in `adapters/euler.py`.
- DB schema: `init_db` in `db.py`.

## Tests

`tests.py` has two suites: `TestAdapters` (live network, fails offline) and `TestPurgeMetrics` (hermetic). Both run with `uv run python -m unittest tests`.

## Style

- **NEVER commit** `.env` or `state.db`.
- No comments restating what the code does; only why, when non-obvious.
- No em dashes in prose. Use commas, colons, parens, or periods.
