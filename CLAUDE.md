# CoinKit

Minimal Discord bot for DeFi alerts (caps, rates, ICOs). See `README.md` for user-facing setup and the Discord command list.

## Layout

```
bot.py               Discord entrypoint, commands, alert loop
engine.py            Orchestrates fetchers, records samples, dispatches alerts
adapters/*.py        One module per data source
alerts.py            Cap / rate / ICO alert logic and thresholds
db.py                sqlite state (state.db); also exposes purge_keys()
httputil.py          Shared HTTP helpers (get_json, post_json, to_float)
scripts/*.py         Maintenance CLIs (purge_metrics.py removes keys from state.db)
tests.py             Unit tests + live-network adapter tests
```

## Tooling

`uv` for everything. **YOU MUST use `uv run`** for any Python invocation. 

- `uv sync`, `uv add <pkg>`, `uv remove <pkg>`
- `uv run python bot.py`
- `uv run python -m unittest tests`

## Adapter contract

Adapters are auto-discovered: every module under `adapters/` is loaded by `engine._discover_adapters` at import time. Adding a new adapter means dropping `adapters/<name>.py` and setting `<NAME>_CHANNEL_ID` in `.env`. No engine, bot, or test edits required.

To temporarily mute a misbehaving adapter without touching code, set `DISABLED_ADAPTERS=foo,bar` in `.env`.

Each `adapters/<name>.py` MUST expose `fetch() -> list[dict]`. Metric dicts have `key`, `name`, `value`, `unit`, `adapter` (where `adapter` matches the module filename). Use `httputil.get_json` / `httputil.post_json` / `httputil.to_float` instead of rolling raw `requests` calls.

Optional: an adapter can expose `PAIRED_CAPS = [...]` to declare paired supply/borrow caps that should fire a major alert when freed simultaneously. The engine aggregates `PAIRED_CAPS` across all adapters.

`engine.run_once` routes by `unit`:
- `"ratio"` to cap alerts
- `"json"` to ICO alerts
- everything else (numeric) to rate alerts

## Where volatile config lives

Thresholds, intervals, and pairings change often. Read the source rather than assuming:

- Rate thresholds (per-adapter and default): `RATE_MINOR`, `RATE_MINOR_DEFAULT`, `RATE_MAJOR` at the top of `alerts.py`.
- Cap-full threshold and paired-cap logic: `CAP_FULL_THRESHOLD` and `handle_paired_caps` in `alerts.py`.
- Polling interval: `ALERT_INTERVAL_SECONDS` in `bot.py`.
- Paired-cap configs: `PAIRED_CAPS` inside the adapter that owns them (e.g. `adapters/euler.py`).
- DB schema: `init_db` in `db.py`.

## Tests

`tests.py` has two suites: `TestAdapters` (live network, fails offline) and `TestPurgeMetrics` (hermetic). Both run with `uv run python -m unittest tests`.

## Style

- **NEVER commit** `.env` or `state.db`.
- No comments restating what the code does; only why, when non-obvious.
- No em dashes in prose. Use commas, colons, parens, or periods.
