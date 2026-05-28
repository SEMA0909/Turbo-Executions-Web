from __future__ import annotations
import logging
from typing import List, Dict

import pandas as pd
import numpy as np
from app.signals.helpers import (calculate_gap_zones, detect_consolidation_zone, detect_reversal_candlestick, calculate_htf_premium_discount, analyze_signal_freshness, get_intraday_rationale, get_swing_rationale, get_positional_rationale, find_order_blocks, detect_fvg)

try:
    import MetaTrader5 as mt5  # type: ignore
    HAS_MT5 = True
except Exception:
    mt5 = None  # type: ignore
    HAS_MT5 = False

log = logging.getLogger("signals.paste")


class SignalEngine:
    """Ported institutional-grade signal engine (fast, pragmatic port).

    Produces signals for strategies: INTRADAY (M15), SWING (H1), POSITIONAL (H4),
    ORDER_BLOCK and LIQUIDITY_SWEEP (approximated).
    """

    def __init__(self, client=None) -> None:
        self.client = client
        self.signal_cache: Dict = {}

    def _get_rates(self, symbol: str, timeframe, bars: int = 300):
        if not HAS_MT5 or mt5 is None:
            return []
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            if rates is None:
                return []
            names = getattr(rates, 'dtype', None) and getattr(rates.dtype, 'names', None)
            if names:
                out = []
                for rec in rates:
                    out.append({n: rec[n] for n in names})
                return out
            if isinstance(rates, (list, tuple)) and len(rates) and isinstance(rates[0], dict):
                return list(rates)
            out = []
            for row in rates:
                try:
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
                    continue
            return out
        except Exception:
            log.exception("Failed to fetch rates for %s", symbol)
            return []

    def _build_df(self, rates) -> pd.DataFrame:
        df = pd.DataFrame(rates)
        if df.empty:
            return df
        # normalize names
        for c in ['open', 'high', 'low', 'close']:
            if c not in df.columns and c.capitalize() in df.columns:
                df[c] = df[c.capitalize()]
        if 'tick_volume' not in df.columns and 'volume' in df.columns:
            df['tick_volume'] = df['volume']
        df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].copy()
        df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['open'] = df['open'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df

    def _indicators(self, df: pd.DataFrame) -> Dict:
        if df.empty:
            return {}
        price = float(df['close'].iloc[-1])
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1] if len(df) >= 50 else df['close'].rolling(8).mean().iloc[-1]
        ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1] if len(df) >= 200 else df['close'].rolling(50).mean().iloc[-1]
        # ATR14
        high_low = df['high'] - df['low']
        tr = high_low
        atr14 = tr.rolling(14).mean().iloc[-1] if len(tr) >= 14 else tr.mean()
        # RSI
        delta = df['close'].diff()
        up = delta.clip(lower=0).rolling(14).mean()
        down = -delta.clip(upper=0).rolling(14).mean()
        rs = up / down.replace(0, 1e-9)
        rsi = (100 - (100 / (1 + rs))).iloc[-1] if not rs.empty else 50
        last_vol = float(df['volume'].iloc[-1])
        avg_vol = float(df['volume'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else last_vol
        return {
            'price': price,
            'ema50': float(ema50) if pd.notna(ema50) else None,
            'ema200': float(ema200) if pd.notna(ema200) else None,
            'atr14': float(atr14) if pd.notna(atr14) else 0.0,
            'rsi': float(rsi) if pd.notna(rsi) else 50.0,
            'avg_vol': avg_vol,
            'last_vol': last_vol,
        }

    def _make_signal(self, symbol, strategy, direction, price, atr, rsi, confidence_base):
        if direction not in ('BUY', 'SELL'):
            return None
        stop = price - atr * 1.5 if direction == 'BUY' else price + atr * 1.5
        target = price + atr * 3 if direction == 'BUY' else price - atr * 3
        conf = max(0.0, min(0.99, confidence_base))
        return {
            'symbol': symbol,
            'strategy': strategy,
            'direction': direction,
            'entry': round(price, 5),
            'stop': round(stop, 5),
            'target': round(target, 5),
            'confidence': round(conf, 3),
            'rsi': round(rsi, 2),
            'atr': round(atr, 5),
        }

    def _intraday(self, symbol, df_m15: pd.DataFrame):
        ind = self._indicators(df_m15)
        if not ind:
            return None
        price = ind['price']
        atr = ind['atr14']
        rsi = ind['rsi']
        vol_ok = ind['last_vol'] > max(1.0, ind['avg_vol'] * 0.9)
        direction = None
        conf = 0.0
        if ind['ema50'] and ind['ema200'] and price > ind['ema50'] and ind['ema50'] > ind['ema200'] and rsi > 55 and vol_ok:
            direction = 'BUY'
            conf = 0.5 + (rsi - 50) / 100
        elif ind['ema50'] and ind['ema200'] and price < ind['ema50'] and ind['ema50'] < ind['ema200'] and rsi < 45 and vol_ok:
            direction = 'SELL'
            conf = 0.5 + (50 - rsi) / 100
        if direction and conf >= 0.25:
            sig = self._make_signal(symbol, 'INTRADAY', direction, price, atr, rsi, conf)
            # structural confirmation
            try:
                df = df_m15
                gaps = calculate_gap_zones(df)
                htf = {}
                if not df.empty:
                    htf = calculate_htf_premium_discount(df, factors=[4,16], ma_period=20, threshold_pips=5, pip_size=0.0001)
                # apply adjustments
                freshness = analyze_signal_freshness(sig, {'M15': df}, 'M15')
                sig['freshness'] = freshness['freshness']
                sig['freshness_score'] = freshness['score']
                sig['rationale'] = get_intraday_rationale(sig, df)
                # small bonus from structural confirmations
                if detect_consolidation_zone(df)['is_consolidating']:
                    sig['confidence'] = min(0.99, sig['confidence'] + 0.05)
                cand = detect_reversal_candlestick(df)
                if cand['confirmed']:
                    sig['confidence'] = min(0.99, sig['confidence'] + 0.07)
                return sig
            except Exception:
                return sig
        return None

    def _swing(self, symbol, df_h1: pd.DataFrame):
        ind = self._indicators(df_h1)
        if not ind:
            return None
        price = ind['price']
        atr = ind['atr14']
        rsi = ind['rsi']
        direction = None
        conf = 0.0
        # Trend-following: ema50 vs ema200
        if ind['ema50'] and ind['ema200'] and ind['ema50'] > ind['ema200'] and rsi > 52:
            direction = 'BUY'; conf = 0.55 + (rsi - 50) / 200
        elif ind['ema50'] and ind['ema200'] and ind['ema50'] < ind['ema200'] and rsi < 48:
            direction = 'SELL'; conf = 0.55 + (50 - rsi) / 200
        if direction and conf >= 0.4:
            sig = self._make_signal(symbol, 'SWING', direction, price, atr, rsi, conf)
            try:
                df = df_h1
                gaps = calculate_gap_zones(df)
                htf = calculate_htf_premium_discount(df, factors=[4,16], ma_period=20, threshold_pips=5, pip_size=0.0001)
                sig['rationale'] = get_swing_rationale(sig, df)
                freshness = analyze_signal_freshness(sig, {'H1': df}, 'H1')
                sig['freshness'] = freshness['freshness']
                sig['freshness_score'] = freshness['score']
                # order-block proximity bonus
                obs = find_order_blocks(df)
                if obs:
                    sig['confidence'] = min(0.99, sig['confidence'] + 0.04)
                return sig
            except Exception:
                return sig
        return None

    def _positional(self, symbol, df_h4: pd.DataFrame):
        ind = self._indicators(df_h4)
        if not ind:
            return None
        price = ind['price']
        atr = ind['atr14']
        rsi = ind['rsi']
        direction = None
        conf = 0.0
        # MACD/HTF proxy: use ema50/ema200
        if ind['ema50'] and ind['ema200'] and ind['ema50'] > ind['ema200'] and rsi > 50:
            direction = 'BUY'; conf = 0.6 + (rsi - 50) / 200
        elif ind['ema50'] and ind['ema200'] and ind['ema50'] < ind['ema200'] and rsi < 50:
            direction = 'SELL'; conf = 0.6 + (50 - rsi) / 200
        if direction and conf >= 0.45:
            sig = self._make_signal(symbol, 'POSITIONAL', direction, price, atr, rsi, conf)
            try:
                df = df_h4
                sig['rationale'] = get_positional_rationale(sig, df)
                freshness = analyze_signal_freshness(sig, {'H4': df}, 'H4')
                sig['freshness'] = freshness['freshness']
                sig['freshness_score'] = freshness['score']
                # HTF alignment bonus
                htf = calculate_htf_premium_discount(df, factors=[4,16,96], ma_period=20, threshold_pips=5, pip_size=0.0001)
                # if HTF shows premium/discount aligning with direction, bump
                pf = None
                if 'H4' in htf and len(htf['H4']['premium_discount']):
                    pd_flag = int(htf['H4']['premium_discount'][-1])
                    if (pd_flag == -1 and direction == 'BUY') or (pd_flag == 1 and direction == 'SELL'):
                        sig['confidence'] = min(0.99, sig['confidence'] + 0.06)
                return sig
            except Exception:
                return sig
        return None

    def scan_symbols(self, symbols: List[str]) -> List[Dict]:
        signals: List[Dict] = []
        if not HAS_MT5:
            return signals
        for sym in symbols:
            try:
                # fetch multi timeframe data
                rates_m15 = self._get_rates(sym, mt5.TIMEFRAME_M15, 500)
                rates_h1 = self._get_rates(sym, mt5.TIMEFRAME_H1, 400)
                rates_h4 = self._get_rates(sym, mt5.TIMEFRAME_H4, 300)

                df_m15 = self._build_df(rates_m15)
                df_h1 = self._build_df(rates_h1)
                df_h4 = self._build_df(rates_h4)

                s1 = self._intraday(sym, df_m15) if not df_m15.empty else None
                s2 = self._swing(sym, df_h1) if not df_h1.empty else None
                s3 = self._positional(sym, df_h4) if not df_h4.empty else None

                # collect per-strategy signals and append
                per_strat = [s for s in (s1, s2, s3) if s]
                for s in per_strat:
                    signals.append(s)

                # CONSENSUS logic: prefer signals agreed across strategies and apply simple caching to reduce flips
                if per_strat:
                    buy_count = sum(1 for s in per_strat if s.get('direction') == 'BUY')
                    sell_count = sum(1 for s in per_strat if s.get('direction') == 'SELL')
                    avg_conf = float(sum(s.get('confidence', 0) for s in per_strat) / len(per_strat))
                    final_direction = None
                    consensus = max(buy_count, sell_count)
                    if buy_count > sell_count:
                        final_direction = 'BUY'
                    elif sell_count > buy_count:
                        final_direction = 'SELL'

                    # choose best strategy (highest confidence) as prototype for entry/stop/target
                    best = max(per_strat, key=lambda x: x.get('confidence', 0))

                    overall_confidence = round((consensus / len(per_strat)) * avg_conf, 3) if consensus > 0 else 0.0

                    # caching: if previous signal for this symbol exists, require meaningful improvement to flip
                    cache = self.signal_cache.get(sym)
                    allow_emit = True
                    if cache:
                        cached_dir = cache.get('direction')
                        cached_conf = cache.get('confidence', 0)
                        # if direction changed but confidence not significantly higher, keep cached
                        if final_direction and cached_dir and final_direction != cached_dir and overall_confidence <= cached_conf + 0.05:
                            allow_emit = False
                    if final_direction and allow_emit and overall_confidence >= 0.25:
                        consensus_signal = {
                            'symbol': sym,
                            'strategy': 'CONSENSUS',
                            'direction': final_direction,
                            'entry': best.get('entry'),
                            'stop': best.get('stop'),
                            'target': best.get('target'),
                            'confidence': overall_confidence,
                            'components': per_strat,
                        }
                        signals.append(consensus_signal)
                        # update cache
                        self.signal_cache[sym] = {
                            'direction': final_direction,
                            'confidence': overall_confidence,
                            'timestamp': pd.Timestamp.now().isoformat()
                        }

            except Exception:
                log.exception('Failed scanning %s', sym)
        return signals
