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
from app.signals import backtester
# Example usage (do not execute at import time):
# def validator(signal):
#     return run_quick_gate(signal)
# publish_signal_if_valid(signal, validator)
# publish_snapshot(snapshot_dict)

log = logging.getLogger("engine")
Broadcaster = Callable[[dict], Awaitable[None]]


class Engine:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.client = MT5Client()
        self.broadcaster = broadcaster
        self.latest: dict = {}
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        # track last published time per symbol to implement TTL
        self._published: dict[str, float] = {}
        # store frozen published signal objects (symbol -> signal dict)
        self._published_signals: dict[str, dict] = {}
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

        # attempt to publish gated signals (quick gate per-candidate)
        published_symbols = []
        now_ts = datetime.now().timestamp()
        for sig in list(signals):
            try:
                sym = sig.get('symbol')
                last = self._published.get(sym)
                if last and (now_ts - last) < settings.signal_ttl_seconds:
                    # skip publishing within TTL
                    continue
                # run quick gate
                gate = backtester.run_quick_gate(sig, self.client)
                sig['backtest'] = gate
                if not gate.get('ok'):
                    continue
                # publish via write_hooks
                ok = publish_signal_if_valid(sig, lambda s: True)
                if ok:
                    # freeze this signal locally so UI/snapshots use the frozen values
                    frozen = dict(sig)
                    frozen['published_at'] = datetime.now().isoformat()
                    frozen['frozen'] = True
                    self._published[sym] = now_ts
                    self._published_signals[sym] = frozen
                    published_symbols.append(sym)
            except Exception:
                log.exception('Failed publishing signal')

        # produce final signals for snapshot: merge live signals but prefer frozen published ones
        final_signals = []
        seen = set()
        # add published frozen signals first (ensures they appear and are stable)
        for sym, frozen in self._published_signals.items():
            # respect TTL
            if (now_ts - self._published.get(sym, 0)) <= settings.signal_ttl_seconds:
                final_signals.append(frozen)
                seen.add(sym)
        # then add live signals for symbols not frozen
        for s in signals:
            sym = s.get('symbol')
            if sym in seen:
                continue
            final_signals.append(s)

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
            "signals": final_signals,
            "published_signals": published_symbols,
            "settings": {
                "initial_balance": settings.initial_balance,
                "daily_dd_limit_pct": settings.daily_dd_limit_pct,
                "total_dd_limit_pct": settings.total_dd_limit_pct,
                "profit_target_pct": settings.profit_target_pct,
                "mock_mode": self.client._mock,
            },
        }
