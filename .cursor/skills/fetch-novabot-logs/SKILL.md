---
name: fetch-novabot-logs
description: >-
  Fetch all NovaBot logs (local files + live API snapshots into scratch/).
  Use when the user asks to retrieve, dump, analyze, or export bot logs,
  activity logs, scanner state, trades, or debug a running/stopped bot session.
---

# Fetch NovaBot Logs

## Quick start

From repo root, run:

```bash
python .cursor/skills/fetch-novabot-logs/scripts/fetch_logs.py
```

With timestamped archive (keeps history):

```bash
python .cursor/skills/fetch-novabot-logs/scripts/fetch_logs.py --archive
```

## What it collects

### Local files → `scratch/local/`

| File | Content |
|------|---------|
| `novabot.log` (+ `.1`–`.3`) | Technical logs (Python logging) |
| `bot_activity.log` (+ `.1`) | Business events (regime, signals, trades) |
| `ai_payload.jsonl` | AI request/response debug (if present) |

### API snapshots → `scratch/` (bot must be running)

| File | Endpoint |
|------|----------|
| `health.json` | `GET /health` |
| `live_logs.json` | `GET /api/logs?limit=1000` (in-memory deque, max 1000) |
| `live_status.json` | `GET /api/status` |
| `live_scanner.json` | `GET /api/scanner/status` |
| `live_opps.json` | `GET /api/scanner/opportunities` |
| `live_strats.json` | `GET /api/config/strategies-config` |
| `live_trades.json` | `GET /api/history/bot/trades` |
| `live_trade_stats.json` | `GET /api/history/bot/trades/stats` |
| `live_signal_analysis.json` | `GET /api/signal-analysis` |
| `live_sentiment.json` | `GET /api/sentiment-history` |

`manifest.json` lists what succeeded/failed and when.

## Configuration

Reads `.env` at repo root:

- `API_KEY` — sent as `X-API-Key` when `API_KEY_REQUIRED=true`
- `NOVABOT_API_URL` or `API_URL` — override API base (default `http://localhost:3001`)

For Coolify/prod:

```bash
python .cursor/skills/fetch-novabot-logs/scripts/fetch_logs.py \
  --api-url https://your-bot.example.com \
  --api-key "$API_KEY"
```

## Agent workflow

When the user asks to analyze logs:

1. Run the script (add `--archive` if they want to keep a snapshot).
2. Read `scratch/manifest.json` — check errors first.
3. For trading behavior: `scratch/local/bot_activity.log` + `scratch/live_logs.json`.
4. For scanner/symbol choice: `scratch/live_opps.json` + `scratch/live_status.json`.
5. Summarize rejections, trades, errors; cite timestamps from the fetched files.

If API is unreachable, report it and analyze `scratch/local/` only.

**Public repo:** never commit `.env`, `user_settings.json` (use `user_settings.example.json`), or `scratch/`. Production must set `API_KEY_REQUIRED=true`. `sync_config.py` preserves live Discord webhooks — do not copy them into git.

## Companion scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `python .cursor/skills/fetch-novabot-logs/scripts/bot_report.py --fetch` | Fetch API + write `scratch/report.md` |
| `python .cursor/skills/fetch-novabot-logs/scripts/config_diff.py` | Compare local `data/config/` vs live API |
| `python .cursor/skills/fetch-novabot-logs/scripts/sync_config.py --apply` | Push local config to live via API |

Deploy check workflow:

```bash
python .cursor/skills/fetch-novabot-logs/scripts/config_diff.py
python .cursor/skills/fetch-novabot-logs/scripts/sync_config.py --apply   # if diffs
python .cursor/skills/fetch-novabot-logs/scripts/config_diff.py           # verify
```

## Flags

| Flag | Effect |
|------|--------|
| `--local-only` | Skip API (offline / bot stopped) |
| `--api-only` | Skip local file copy |
| `--archive` | Write to `scratch/archives/YYYY-MM-DD_HH-MM-SS/` |
| `-o PATH` | Custom output directory |

## Notes

- `scratch/` is ephemeral debug output — not committed, excluded from Docker.
- In-memory API logs cap at **1000** entries; older history is in `logs/bot_activity.log`.
- Coolify console logs are not captured by this script — use the Coolify UI for container stdout.
