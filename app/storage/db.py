"""SQLite persistence (audit trail)."""
from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "mt5_intel.db")


def _conn() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS equity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            balance REAL, equity REAL, margin REAL, margin_level REAL, profit REAL
        );
        CREATE TABLE IF NOT EXISTS deals (
            ticket INTEGER PRIMARY KEY,
            symbol TEXT, type TEXT, volume REAL,
            price REAL, profit REAL, commission REAL, swap REAL,
            entry TEXT, time TEXT
        );
        CREATE TABLE IF NOT EXISTS daily_summaries (
            day TEXT PRIMARY KEY,
            net_pnl REAL, trades INTEGER, win_rate REAL, consistency_score REAL
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, level TEXT, kind TEXT, message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_equity_ts ON equity_snapshots(ts);
        """)


def save_snapshot(account: dict) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO equity_snapshots(ts,balance,equity,margin,margin_level,profit) VALUES(?,?,?,?,?,?)",
            (datetime.now().isoformat(), account["balance"], account["equity"],
             account["margin"], account["margin_level"], account["profit"]),
        )


def upsert_deals(deals: list[dict]) -> None:
    if not deals:
        return
    with _conn() as c:
        c.executemany(
            """INSERT OR REPLACE INTO deals
               (ticket,symbol,type,volume,price,profit,commission,swap,entry,time)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [(d["ticket"], d["symbol"], d["type"], d["volume"], d["price"],
              d["profit"], d["commission"], d["swap"], d["entry"], d["time"]) for d in deals],
        )


def save_alert(level: str, kind: str, message: str) -> None:
    with _conn() as c:
        c.execute("INSERT INTO alerts(ts,level,kind,message) VALUES(?,?,?,?)",
                  (datetime.now().isoformat(), level, kind, message))


def upsert_daily(day: str, net: float, trades: int, win_rate: float, consistency: float) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO daily_summaries(day,net_pnl,trades,win_rate,consistency_score) VALUES(?,?,?,?,?)",
            (day, net, trades, win_rate, consistency),
        )
