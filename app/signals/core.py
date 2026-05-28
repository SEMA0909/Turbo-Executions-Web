from __future__ import annotations
import logging
from typing import List, Dict

import pandas as pd

try:
    import MetaTrader5 as mt5  # type: ignore
    HAS_MT5 = True
except Exception:
    mt5 = None  # type: ignore
    HAS_MT5 = False

log = logging.getLogger("signals")


class SignalEngine:
    """Simple signal engine inspired by institutional rules in the provided strategy.

    Scans a list of symbols using MT5 bar data (M5) and returns signals with
    direction, entry, stop, target and confidence.
    """

    def __init__(self, client) -> None:
        self.client = client

    def _get_rates(self, symbol: str, timeframe=mt5.TIMEFRAME_M5, bars: int = 300):
        """Fetch rates and normalize to a list of dicts with keys: time, open, high, low, close, tick_volume
        Handles numpy recarray (with names), lists/tuples and other shapes returned by MT5 or mocks.
        """
        if not HAS_MT5 or mt5 is None:
            return []
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            if rates is None:
                return []
            # If numpy recarray with named fields
            names = getattr(rates, 'dtype', None) and getattr(rates.dtype, 'names', None)
            if names:
                out = []
                for rec in rates:
                    out.append({n: rec[n] for n in names})
                return out
            # If it's already an iterable of dict-like objects
            if isinstance(rates, (list, tuple)) and len(rates) and isinstance(rates[0], dict):
                return list(rates)
            # If it's iterable of tuples/lists assume order: time, open, high, low, close, tick_volume, ...
            out = []
            for row in rates:
                try:
                    # convert to list to allow indexing on tuples/ndarrays
                    r = list(row)
                    rec = {
                        'time': r[0],
                        'open': r[1],
                        'high': r[2],
                        'low': r[3],
                        'close': r[4],
                        'tick_volume': r[5] if len(r) > 5 else 0,
                    }
                    out.append(rec)
                except Exception:
                    # skip malformed rows
                    continue
            return out
        except Exception:
            log.exception("Failed to fetch rates for %s", symbol)
            return []

    def _compute_indicators(self, rates) -> Dict:
        # rates is a sequence of records with fields: time, open, high, low, close, tick_volume
        df = pd.DataFrame(rates)
        if df.empty:
            return {}
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['tick_volume'] = df.get('tick_volume', pd.Series([0]*len(df))).astype(float)

        # EMA short/long
        ema50 = df['close'].ewm(span=50, adjust=False).mean()
        ema200 = df['close'].ewm(span=200, adjust=False).mean()
        # ATR (14)
        high_low = df['high'] - df['low']
        tr = high_low
        atr14 = tr.rolling(14).mean().iloc[-1] if len(tr) >= 14 else tr.mean()
        # RSI (14)
        delta = df['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ma_up = up.rolling(14).mean()
        ma_down = down.rolling(14).mean()
        rs = ma_up / (ma_down.replace(0, 1e-9))
        rsi = (100 - (100 / (1 + rs))).iloc[-1] if not rs.empty else 50
        # volume
        avg_vol = df['tick_volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else df['tick_volume'].mean()
        last_vol = df['tick_volume'].iloc[-1]
        latest = df.iloc[-1]
        return {
            'price': float(latest['close']),
            'ema50': float(ema50.iloc[-1]) if not ema50.empty else None,
            'ema200': float(ema200.iloc[-1]) if not ema200.empty else None,
            'atr14': float(atr14) if pd.notna(atr14) else 0.0,
            'rsi': float(rsi) if pd.notna(rsi) else 50.0,
            'avg_vol': float(avg_vol) if pd.notna(avg_vol) else float(last_vol),
            'last_vol': float(last_vol),
        }

    def scan_symbols(self, symbols: List[str]) -> List[Dict]:
        signals: List[Dict] = []
        if not HAS_MT5:
            return signals
        for sym in symbols:
            try:
                rates = self._get_rates(sym, mt5.TIMEFRAME_M5, 300)
                if len(rates) < 60:
                    continue
                ind = self._compute_indicators(rates)
                if not ind:
                    continue
                price = ind['price']
                ema50 = ind['ema50']
                ema200 = ind['ema200']
                rsi = ind['rsi']
                atr = ind['atr14'] or 0.0
                vol_ok = ind['last_vol'] > max(1.0, ind['avg_vol'] * 0.9)

                direction = None
                confidence = 0.0
                # Trend + momentum filter
                if ema50 and ema200 and price > ema50 and ema50 > ema200 and rsi > 55 and vol_ok:
                    direction = 'BUY'
                    confidence = min(0.95, 0.4 + (rsi - 50) / 100 + (1.0 if ind['last_vol'] > ind['avg_vol'] else 0))
                elif ema50 and ema200 and price < ema50 and ema50 < ema200 and rsi < 45 and vol_ok:
                    direction = 'SELL'
                    confidence = min(0.95, 0.4 + (50 - rsi) / 100 + (1.0 if ind['last_vol'] > ind['avg_vol'] else 0))

                if direction:
                    stop = price - atr * 1.5 if direction == 'BUY' else price + atr * 1.5
                    target = price + atr * 3 if direction == 'BUY' else price - atr * 3
                    signals.append({
                        'symbol': sym,
                        'direction': direction,
                        'entry': price,
                        'stop': round(stop, 5),
                        'target': round(target, 5),
                        'confidence': round(confidence, 3),
                        'rsi': round(rsi, 2),
                        'atr': round(atr, 5),
                    })
            except Exception:
                log.exception('Failed scanning %s', sym)
        return signals
