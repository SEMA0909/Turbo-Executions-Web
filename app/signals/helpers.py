from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List

# Helper functions ported/adapted from strategy_suggestion_engine.py

def calculate_gap_zones(df: pd.DataFrame, lookback: int = 100) -> List[Dict]:
    gaps = []
    if df is None or df.empty:
        return gaps
    length = len(df)
    if length < 3:
        return gaps
    lb = min(lookback, length - 2)
    for i in range(length - lb, length):
        if i < 2:
            continue
        if df['low'].iat[i] > df['high'].iat[i-2]:
            gaps.append({'type': 'bullish', 'low': float(df['high'].iat[i-2]), 'high': float(df['low'].iat[i]), 'start_idx': i-2, 'end_idx': i, 'filled': False})
        elif df['high'].iat[i] < df['low'].iat[i-2]:
            gaps.append({'type': 'bearish', 'low': float(df['high'].iat[i]), 'high': float(df['low'].iat[i-2]), 'start_idx': i-2, 'end_idx': i, 'filled': False})
    # mark filled
    for gap in gaps:
        for j in range(gap['end_idx'] + 1, length):
            if gap['low'] <= df['high'].iat[j] <= gap['high'] or gap['low'] <= df['low'].iat[j] <= gap['high'] or gap['low'] <= df['close'].iat[j] <= gap['high']:
                gap['filled'] = True
                break
    return gaps


def detect_consolidation_zone(df: pd.DataFrame, lookback: int = 30, max_range_pct: float = 0.004) -> Dict:
    if df is None or df.empty:
        return {'is_consolidating': False, 'low': None, 'high': None, 'range_pct': None, 'bars': 0}
    lb = min(lookback, len(df))
    high_window = df['high'].iloc[-lb:]
    low_window = df['low'].iloc[-lb:]
    close_window = df['close'].iloc[-lb:]
    zone_high = float(high_window.max())
    zone_low = float(low_window.min())
    avg_price = float(close_window.mean()) if close_window.mean() else 1.0
    range_pct = (zone_high - zone_low) / avg_price
    return {'is_consolidating': range_pct <= max_range_pct, 'low': zone_low, 'high': zone_high, 'range_pct': range_pct, 'bars': lb}


def detect_reversal_candlestick(df: pd.DataFrame) -> Dict:
    if df is None or len(df) < 3 or 'open' not in df.columns:
        return {'pattern': None, 'confirmed': False}
    o = df['open'].values
    c = df['close'].values
    h = df['high'].values
    l = df['low'].values
    last_open = o[-1]
    last_close = c[-1]
    prev_open = o[-2]
    prev_close = c[-2]
    # Bullish engulfing
    if last_close > last_open and prev_close < prev_open and last_close > prev_open and last_open < prev_close:
        return {'pattern': 'bullish_engulfing', 'confirmed': True}
    # Bearish engulfing
    if last_close < last_open and prev_close > prev_open and last_close < prev_open and last_open > prev_close:
        return {'pattern': 'bearish_engulfing', 'confirmed': True}
    # Hammer / pin bar
    body = abs(last_close - last_open)
    candle_range = h[-1] - l[-1] if h[-1] != l[-1] else 1e-9
    lower_wick = min(last_open, last_close) - l[-1]
    upper_wick = h[-1] - max(last_open, last_close)
    if body <= candle_range * 0.35 and lower_wick >= candle_range * 0.4 and upper_wick <= candle_range * 0.2:
        return {'pattern': 'hammer', 'confirmed': True}
    if body <= candle_range * 0.35 and upper_wick >= candle_range * 0.4 and lower_wick <= candle_range * 0.2:
        return {'pattern': 'shooting_star', 'confirmed': True}
    return {'pattern': None, 'confirmed': False}


def calculate_htf_premium_discount(df: pd.DataFrame, factors=[4,16], ma_period=20, threshold_pips=5, pip_size=0.0001) -> Dict:
    results = {}
    if df is None or df.empty:
        return results
    for factor in factors:
        label = {4:'H1',16:'H4'}.get(factor, f'F{factor}')
        htf_len = (len(df) + factor - 1) // factor
        htf_close = np.zeros(htf_len)
        htf_high = np.zeros(htf_len)
        htf_low = np.zeros(htf_len)
        for i in range(htf_len):
            start = i * factor
            end = min(start + factor, len(df))
            htf_close[i] = df['close'].iat[end-1]
            htf_high[i] = df['high'].iloc[start:end].max()
            htf_low[i] = df['low'].iloc[start:end].min()
        htf_ma = np.convolve(htf_close, np.ones(ma_period)/ma_period, mode='full')[:htf_len]
        if len(htf_ma) < htf_len:
            htf_ma = np.pad(htf_ma, (htf_len - len(htf_ma), 0), constant_values=np.nan)
        mapped_ma = np.zeros(len(df))
        mapped_pd = np.zeros(len(df), dtype=int)
        threshold_value = threshold_pips * pip_size
        for i in range(len(df)):
            bucket = i // factor
            if bucket >= len(htf_ma) or np.isnan(htf_ma[bucket]):
                mapped_ma[i] = np.nan
                mapped_pd[i] = 0
                continue
            mapped_ma[i] = htf_ma[bucket]
            diff = df['close'].iat[i] - htf_ma[bucket]
            if diff > threshold_value:
                mapped_pd[i] = 1
            elif diff < -threshold_value:
                mapped_pd[i] = -1
            else:
                mapped_pd[i] = 0
        results[label] = {'premium_discount': mapped_pd, 'htf_ma': mapped_ma, 'threshold': threshold_value}
    return results


def analyze_signal_freshness(signal: Dict, symbol_data: Dict, timeframe: str) -> Dict:
    # basic freshness analysis: compare signal entry to most recent bar close and time
    res = {'freshness':'UNKNOWN','score':0.0,'description':''}
    try:
        tf = timeframe
        df = symbol_data.get(timeframe) if isinstance(symbol_data, dict) else symbol_data
        if df is None or df.empty:
            return res
        last_close = float(df['close'].iloc[-1])
        entry = float(signal.get('entry', last_close))
        diff = abs(entry - last_close)
        res['freshness'] = 'LIVE' if diff <= (0.5 * float(signal.get('atr',1))) else ('CURRENT' if diff <= (1.5 * float(signal.get('atr',1))) else 'STALE')
        res['score'] = 1.0 if res['freshness']=='LIVE' else (0.6 if res['freshness']=='CURRENT' else 0.2)
        res['description'] = f"Entry vs last: {diff:.5f} | atr {signal.get('atr')}"
    except Exception:
        pass
    return res


def get_intraday_rationale(signal: Dict, data: pd.DataFrame) -> str:
    return f"Intraday rationale: EMA50/EMA200 alignment, RSI={signal.get('rsi')}, confidence={signal.get('confidence')}"

def get_swing_rationale(signal: Dict, data: pd.DataFrame) -> str:
    return f"Swing rationale: HTF trend align, RSI={signal.get('rsi')}, confidence={signal.get('confidence')}"

def get_positional_rationale(signal: Dict, data: pd.DataFrame) -> str:
    return f"Positional rationale: H4 trend + macro alignment, RSI={signal.get('rsi')}, confidence={signal.get('confidence')}"


# Basic order-block detection (approx)
def find_order_blocks(df: pd.DataFrame, lookback=100) -> List[Dict]:
    obs = []
    if df is None or df.empty:
        return obs
    for i in range(2, min(len(df), lookback)):
        # simple detection: large body bar followed by small range candles
        body = abs(df['close'].iat[-i] - df['open'].iat[-i])
        rng = df['high'].iat[-i] - df['low'].iat[-i]
        if body > 0 and body / rng > 0.6 and rng > 0:
            level = float((df['high'].iat[-i] + df['low'].iat[-i]) / 2)
            obs.append({'idx': -i, 'level': level, 'type': 'support' if df['close'].iat[-i] > df['open'].iat[-i] else 'resistance'})
    return obs


def detect_fvg(df: pd.DataFrame, lookback=20) -> List[Dict]:
    fvgs = []
    if df is None or df.empty:
        return fvgs
    for i in range(2, min(len(df), lookback)):
        # naive FVG: when middle bar has body not overlapping neighbors
        if df['low'].iat[-i] > df['high'].iat[-i-2]:
            fvgs.append({'type':'bullish','low':float(df['high'].iat[-i-2]),'high':float(df['low'].iat[-i])})
        elif df['high'].iat[-i] < df['low'].iat[-i-2]:
            fvgs.append({'type':'bearish','low':float(df['high'].iat[-i]),'high':float(df['low'].iat[-i-2])})
    return fvgs
