"""Engine: poll MT5 -> compute -> persist -> broadcast."""
from __future__ import annotations
import asyncio
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Callable, Awaitable

from app.config import settings
from app.core.mt5_client import MT5Client
from app.core import metrics, consistency, rules
from app.storage import db
from app.alerts.dispatcher import evaluate as evaluate_alerts
from app.signals.paste_engine import SignalEngine

from supabase_integration.backend.write_hooks import publish_signal_if_valid, publish_snapshot
 # validator should be a function that uses your backtester quick gate
 def validator(signal): return run_quick_gate(signal)  # implement/run your gate
 
 # when you have a signal dict:
 publish_signal_if_valid(signal, validator)
 
 # periodically (e.g., each snapshot interval) publish snapshot
 publish_snapshot(snapshot_dict)

log = logging.getLogger("engine")
Broadcaster = Callable[[dict], Awaitable[None]]


class Engine:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.client = MT5Client()
        self.broadcaster = broadcaster
        self.latest: dict = {}
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        # signal engine
        try:
            self.signal_engine = SignalEngine(self.client)
        except Exception:
            self.signal_engine = None

    async def start(self) -> None:
        db.init()
        self.client.connect()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
        self.client.shutdown()

    async def _loop(self) -> None:
        first_tick = True
        while not self._stop.is_set():
            try:
                if not self.client.ensure_connected():
                    if first_tick:
                        log.warning("Engine: MT5 not connected on startup, retrying…")
                        first_tick = False
                    await self._sleep(2)
                    continue
                snap = self._snapshot()
                if snap:
                    self.latest = snap
                    if first_tick:
                        log.info(f"Engine: First snapshot acquired ({len(snap.get('deals', []))} deals)")
                        first_tick = False
                    db.save_snapshot(snap["account"])
                    db.upsert_deals(snap["deals"][-50:])
                    today = datetime.now().strftime("%Y-%m-%d")
                    db.upsert_daily(today,
                                    snap["daily_pnl"].get(today, 0),
                                    snap["performance"]["trades"],
                                    snap["performance"]["win_rate"],
                                    snap["consistency"]["score"])
                    await self.broadcaster(snap)
                    await evaluate_alerts(snap)
                else:
                    if first_tick:
                        log.warning("Engine: MT5 account_info() returned None, retrying…")
            except Exception:
                log.exception("Engine tick failed")
            await self._sleep(settings.poll_interval)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    def _snapshot(self) -> dict | None:
        acc = self.client.account_info()
        if acc is None:
            return None
        account = asdict(acc)
        positions = [asdict(p) for p in self.client.positions()]
        deals = [asdict(d) for d in self.client.deals(days=60)]

        perf = metrics.performance(deals)
        dd = metrics.drawdowns(settings.initial_balance, account["equity"], deals)
        curve = metrics.equity_curve(settings.initial_balance, deals)
        cons = consistency.compute(deals)
        daily = metrics.daily_pnl(deals)
        rule_eval = rules.evaluate(account, dd, perf, daily)

        signals = []
        try:
            # choose symbols to scan: open positions + top common FX
            syms = list({p['symbol'] for p in positions})
            if not syms:
                syms = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
            if self.signal_engine:
                signals = self.signal_engine.scan_symbols(syms)
        except Exception:
            log.exception("Signal engine failed")

        return {
            "ts": datetime.now().isoformat(),
            "account": account,
            "positions": positions,
            "deals": deals,
            "performance": perf,
            "drawdowns": dd,
            "equity_curve": curve[-200:],
            "equity_slope": metrics.equity_slope(curve),
            "consistency": cons,
            "daily_pnl": daily,
            "exposure": metrics.symbol_exposure(positions),
            "risk_per_trade": metrics.risk_per_trade(positions, account["equity"]),
            "rules": rule_eval,
            "signals": signals,
            "settings": {
                "initial_balance": settings.initial_balance,
                "daily_dd_limit_pct": settings.daily_dd_limit_pct,
                "total_dd_limit_pct": settings.total_dd_limit_pct,
                "profit_target_pct": settings.profit_target_pct,
                "mock_mode": self.client._mock,
            },
        }
