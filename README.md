# MT5 Execution Intelligence & Prop Firm Risk Monitor

Local, real-time analytics for a MetaTrader 5 account. Runs entirely on your machine — no cloud, no hosting.

## What you get

- **Live MT5 connector** (`MetaTrader5` Python API) with auto-reconnect
- **Metrics engine**: drawdown, win rate, profit factor, expectancy, RR, equity slope
- **Proprietary Consistency Score (0–100)** with rule-breach probability
- **Prop firm rule tracker**: daily DD, total DD, profit cap, min trading days, overexposure
- **FastAPI + WebSocket** server streaming snapshots every 1–5s
- **Web dashboard** at `http://localhost:8000` (Tailwind + Chart.js, zero build step)
- **Terminal monitor** (`python -m app.tui`) using Rich
- **SQLite** persistence (trades, equity snapshots, daily summaries, alert log)
- **Telegram alerts** (optional)

## Requirements

- **Windows** (MetaTrader5 Python package is Windows-only)
- **MT5 desktop terminal installed and logged into your account**
- **Python 3.10+**

> Mac/Linux: you can still run the app in `MOCK_MODE=1` (synthetic data) for UI/dev work.

## Setup (VS Code terminal)

```bash
# 1. Create venv
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux (mock mode only)

# 2. Install
pip install -r requirements.txt

# 3. Configure
copy .env.example .env          # Windows
# cp .env.example .env          # Mac/Linux
# edit .env with your MT5 login + prop firm rules

# 4. Run the server (MT5 connector + API + dashboard)
python -m app.main

# 5. Open the dashboard
# http://localhost:8000
```

Optional terminal-only view (in a second tab):

```bash
python -m app.tui
```

## Configuration (`.env`)

```
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=YourBroker-Demo
MT5_PATH=                       # optional: full path to terminal64.exe

POLL_INTERVAL_SECONDS=2
MOCK_MODE=0                     # set to 1 to run without MT5

# Prop firm rules
INITIAL_BALANCE=100000
DAILY_DD_LIMIT_PCT=5
TOTAL_DD_LIMIT_PCT=10
PROFIT_TARGET_PCT=8
MIN_TRADING_DAYS=5
MAX_CONSISTENCY_DAY_PCT=40      # single day cannot exceed 40% of total profit

# Alerts (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ALERT_DD_USAGE_PCT=70           # alert when 70% of daily DD limit consumed
ALERT_CONSISTENCY_BELOW=50
```

## Project layout

```
app/
  main.py              # entry: starts MT5 poller + FastAPI server
  config.py            # env loader
  tui.py               # Rich terminal monitor
  core/
    mt5_client.py      # MT5 connection + auto-reconnect
    metrics.py         # risk / performance metrics
    consistency.py     # proprietary score
    rules.py           # prop-firm compliance evaluator
    engine.py          # orchestrates polling -> compute -> store -> broadcast
  api/
    server.py          # FastAPI app + WebSocket
    schemas.py
  storage/
    db.py              # SQLite (sqlite3, no ORM)
  alerts/
    dispatcher.py
    telegram.py
  web/
    static/index.html  # dashboard (Tailwind + Chart.js via CDN)
scripts/
  run.bat              # Windows launcher
  run.sh               # *nix launcher (mock mode)
```

## How the Consistency Score works

Penalizes:
- **Lot variance** — std/mean of trade volumes
- **One-trade dominance** — share of total profit from best winning day/trade
- **Sizing spikes** — trades > 2σ from mean lot size
- **Asymmetric emotion** — avg win vs avg loss imbalance beyond healthy RR
- **Daily P&L concentration** — any single day's P&L exceeding `MAX_CONSISTENCY_DAY_PCT` of net profit

Output: `score` (0–100), `grade` (green/yellow/red), `breach_probability` (0–1), plus a breakdown of each penalty so you can see *why*.

## Notes

- The MT5 Python API requires the desktop terminal to be running and logged in on the same machine.
- Symbol exposure aggregates by base/quote currency to surface correlated risk (e.g., long EURUSD + short USDCHF).
- All snapshots are written to `data/mt5_intel.db` for audit trail.
- WebSocket endpoint: `ws://localhost:8000/ws`. REST snapshot: `GET /api/snapshot`.

## Troubleshooting

- `initialize() failed`: terminal not running or wrong path — set `MT5_PATH` to your `terminal64.exe`.
- `login() failed`: check `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` (server name must match exactly).
- Dashboard empty: open the browser console; check `ws://localhost:8000/ws` connects.
