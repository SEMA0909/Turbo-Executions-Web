"""Risk + performance metrics. Pure functions over dicts/lists."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from statistics import mean, pstdev
from typing import Iterable


def _closed_deals(deals: list[dict]) -> list[dict]:
    return [d for d in deals if d.get("entry") == "out"]


def daily_pnl(deals: list[dict]) -> dict[str, float]:
    """Net P&L (profit + commission + swap) keyed by YYYY-MM-DD."""
    out: dict[str, float] = defaultdict(float)
    for d in _closed_deals(deals):
        day = d["time"][:10]
        out[day] += d.get("profit", 0) + d.get("commission", 0) + d.get("swap", 0)
    return dict(out)


def equity_curve(initial_balance: float, deals: list[dict]) -> list[dict]:
    closed = sorted(_closed_deals(deals), key=lambda d: d["time"])
    eq = initial_balance
    out = [{"t": closed[0]["time"] if closed else datetime.now().isoformat(), "equity": eq}]
    for d in closed:
        eq += d.get("profit", 0) + d.get("commission", 0) + d.get("swap", 0)
        out.append({"t": d["time"], "equity": round(eq, 2)})
    return out


def drawdowns(initial_balance: float, equity_now: float, deals: list[dict]) -> dict:
    curve = equity_curve(initial_balance, deals)
    peak = initial_balance
    max_dd_abs = 0.0
    for pt in curve:
        peak = max(peak, pt["equity"])
        max_dd_abs = max(max_dd_abs, peak - pt["equity"])
    # today
    today = datetime.now().strftime("%Y-%m-%d")
    start_today = initial_balance
    for pt in curve:
        if pt["t"][:10] >= today:
            break
        start_today = pt["equity"]
    daily_loss = max(start_today - equity_now, 0)
    total_loss = max(initial_balance - equity_now, 0)
    return {
        "max_drawdown_abs": round(max_dd_abs, 2),
        "max_drawdown_pct": round(max_dd_abs / initial_balance * 100, 2),
        "daily_loss_abs": round(daily_loss, 2),
        "daily_loss_pct": round(daily_loss / initial_balance * 100, 2),
        "total_loss_abs": round(total_loss, 2),
        "total_loss_pct": round(total_loss / initial_balance * 100, 2),
        "day_start_equity": round(start_today, 2),
    }


def performance(deals: list[dict]) -> dict:
    closed = _closed_deals(deals)
    if not closed:
        return {
            "trades": 0, "win_rate": 0, "profit_factor": 0, "expectancy": 0,
            "avg_win": 0, "avg_loss": 0, "avg_rr": 0, "gross_profit": 0,
            "gross_loss": 0, "net_profit": 0,
        }
    pnls = [d["profit"] + d.get("commission", 0) + d.get("swap", 0) for d in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gp = sum(wins); gl = abs(sum(losses))
    avg_win = mean(wins) if wins else 0
    avg_loss = mean(losses) if losses else 0
    # Calculate profit_factor: avoid infinity, use 0 if no losses
    profit_factor = 0
    if gl > 0:
        profit_factor = round(gp / gl, 2)
    elif gp > 0:
        profit_factor = 999.99  # All wins, no losses
    return {
        "trades": len(closed),
        "win_rate": round(len(wins) / len(closed) * 100, 2),
        "profit_factor": profit_factor,
        "expectancy": round(mean(pnls), 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "avg_rr": round(abs(avg_win / avg_loss), 2) if avg_loss else 0,
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "net_profit": round(sum(pnls), 2),
    }


def equity_slope(curve: list[dict]) -> float:
    """Simple least-squares slope over equity points (per trade index)."""
    n = len(curve)
    if n < 2:
        return 0.0
    xs = list(range(n))
    ys = [p["equity"] for p in curve]
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return round(num / den, 4) if den else 0.0


def symbol_exposure(positions: list[dict]) -> list[dict]:
    agg: dict[str, dict] = defaultdict(lambda: {"volume": 0.0, "net_lots": 0.0, "floating": 0.0, "count": 0})
    for p in positions:
        sign = 1 if p["type"] == "buy" else -1
        a = agg[p["symbol"]]
        a["volume"] += p["volume"]
        a["net_lots"] += sign * p["volume"]
        a["floating"] += p["profit"]
        a["count"] += 1
    return [{"symbol": s, **v} for s, v in agg.items()]


def risk_per_trade(positions: list[dict], equity: float) -> list[dict]:
    out = []
    for p in positions:
        risk = 0.0
        if p["sl"]:
            risk = abs(p["price_open"] - p["sl"]) * p["volume"] * 100  # rough notional
        out.append({
            "ticket": p["ticket"], "symbol": p["symbol"],
            "risk_abs": round(risk, 2),
            "risk_pct": round(risk / equity * 100, 2) if equity else 0,
        })
    return out
