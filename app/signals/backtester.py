"""Quick historical gate/backtester for candidate signals.

This module implements a fast forward-scan to estimate win-rate and profit-factor
for the signal's entry/stop/target geometry on recent historical bars. It's
intended as a quick pre-publish gate (fast) not a full production backtest.
"""
from __future__ import annotations
import logging
from typing import Dict, Any

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except Exception:
    mt5 = None
    HAS_MT5 = False

from app.config import settings

log = logging.getLogger("signals.backtester")


def _fetch_rates(symbol: str, timeframe, bars: int = 500):
    if not HAS_MT5 or mt5 is None:
        return []
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None:
            return []
        # convert to simple list of dicts
        names = getattr(rates, 'dtype', None) and getattr(rates.dtype, 'names', None)
        out = []
        if names:
            for rec in rates:
                out.append({n: rec[n] for n in names})
            return out
        for row in rates:
            try:
                r = list(row)
                out.append({'time': r[0], 'open': r[1], 'high': r[2], 'low': r[3], 'close': r[4]})
            except Exception:
                continue
        return out
    except Exception:
        log.exception('fetch_rates failed')
        return []


def _simulate(series, direction: str, entry: float, stop: float, target: float, lookahead: int = 48):
    """Return wins, losses, rr_sum over series by scanning forward windows."""
    wins = 0
    losses = 0
    rr_total = 0.0
    n = len(series)
    if n < 5:
        return {'wins': 0, 'losses': 0, 'rr_total': 0.0, 'n': 0}
    stop_dist = abs(entry - stop)
    target_dist = abs(target - entry)
    for i in range(n - lookahead):
        window = series[i+1:i+1+lookahead]
        hit_win = False
        hit_loss = False
        for bar in window:
            high = bar.get('high') or bar.get('h') or 0
            low = bar.get('low') or bar.get('l') or 0
            if direction == 'BUY':
                if high >= entry + target_dist:
                    hit_win = True; break
                if low <= entry - stop_dist:
                    hit_loss = True; break
            else:
                if low <= entry - target_dist:
                    hit_win = True; break
                if high >= entry + stop_dist:
                    hit_loss = True; break
        if hit_win:
            wins += 1
            rr_total += (target_dist / (stop_dist if stop_dist else 1e-9))
        elif hit_loss:
            losses += 1
    return {'wins': wins, 'losses': losses, 'rr_total': rr_total, 'n': (wins + losses)}


def run_quick_gate(signal: Dict[str, Any], client) -> Dict[str, Any]:
    """Run a quick gate. Returns dict with keys: ok(bool), winrate, pf, details
    - If no real rates available (mock mode) returns ok=True with mocked stats.
    """
    try:
        strat = signal.get('strategy', 'INTRADAY')
        if strat == 'INTRADAY':
            tf = mt5.TIMEFRAME_M15 if HAS_MT5 else None
            lookahead = 48
        elif strat == 'SWING':
            tf = mt5.TIMEFRAME_H1 if HAS_MT5 else None
            lookahead = 48
        else:
            tf = mt5.TIMEFRAME_H4 if HAS_MT5 else None
            lookahead = 36
        bars = settings.backtest_lookback_bars
        series = _fetch_rates(signal['symbol'], tf, bars) if tf else []
        if not series and getattr(client, '_mock', False):
            # Mock mode - accept but mark as mocked
            return {'ok': True, 'mock': True, 'winrate': None, 'pf': None, 'details': 'mock-mode accepted'}
        if not series:
            return {'ok': False, 'mock': False, 'winrate': 0.0, 'pf': 0.0, 'details': 'no historical rates'}
        sim = _simulate(series, signal['direction'], float(signal['entry']), float(signal['stop']), float(signal['target']), lookahead=lookahead)
        n = sim.get('n', 0)
        wins = sim.get('wins', 0)
        losses = sim.get('losses', 0)
        rr_total = sim.get('rr_total', 0.0)
        winrate = (wins / n) if n else 0.0
        avg_rr = (rr_total / wins) if wins else 0.0
        gross_win = wins * (float(signal['target']) - float(signal['entry']))
        gross_loss = losses * (float(signal['entry']) - float(signal['stop']))
        pf = (abs(gross_win) / abs(gross_loss)) if gross_loss else (avg_rr if avg_rr else 0.0)
        ok = (winrate >= settings.backtest_min_winrate and pf >= settings.backtest_min_pf)
        return {'ok': bool(ok), 'winrate': round(winrate, 3), 'pf': round(pf, 3), 'wins': wins, 'losses': losses, 'n': n, 'avg_rr': round(avg_rr,3)}
    except Exception:
        log.exception('run_quick_gate failed')
        return {'ok': False, 'winrate': 0.0, 'pf': 0.0, 'details': 'error'}
