"""Prop firm compliance evaluator."""
from __future__ import annotations
from datetime import datetime
from app.config import settings


def evaluate(account: dict, dd: dict, perf: dict, daily_pnl: dict[str, float]) -> dict:
    s = settings
    daily_limit = s.initial_balance * s.daily_dd_limit_pct / 100
    total_limit = s.initial_balance * s.total_dd_limit_pct / 100
    target = s.initial_balance * s.profit_target_pct / 100

    daily_used = dd["daily_loss_abs"]
    total_used = dd["total_loss_abs"]

    trading_days = sum(1 for v in daily_pnl.values() if abs(v) > 0.01)
    progress = perf["net_profit"] / target * 100 if target else 0

    rules = []

    def add(name, status, detail, used_pct=None):
        rules.append({"name": name, "status": status, "detail": detail, "used_pct": used_pct})

    # Daily DD
    used_pct = daily_used / daily_limit * 100 if daily_limit else 0
    add("Daily drawdown",
        "breach" if used_pct >= 100 else "warning" if used_pct >= s.alert_dd_usage_pct else "safe",
        f"${daily_used:,.2f} of ${daily_limit:,.2f}", round(used_pct, 1))

    # Total DD
    used_pct_t = total_used / total_limit * 100 if total_limit else 0
    add("Total drawdown",
        "breach" if used_pct_t >= 100 else "warning" if used_pct_t >= s.alert_dd_usage_pct else "safe",
        f"${total_used:,.2f} of ${total_limit:,.2f}", round(used_pct_t, 1))

    # Profit target
    add("Profit target",
        "safe" if progress >= 100 else "warning" if progress >= 50 else "info",
        f"${perf['net_profit']:,.2f} of ${target:,.2f}", round(min(progress, 100), 1))

    # Min trading days
    add("Min trading days",
        "safe" if trading_days >= s.min_trading_days else "info",
        f"{trading_days} of {s.min_trading_days}",
        round(min(trading_days / s.min_trading_days * 100, 100), 1) if s.min_trading_days else None)

    # Margin level
    ml = account.get("margin_level", 0)
    add("Margin level",
        "breach" if 0 < ml < 100 else "warning" if 0 < ml < 250 else "safe",
        f"{ml:.0f}%" if ml else "n/a")

    worst = max((r["status"] for r in rules), key=lambda x: ["safe", "info", "warning", "breach"].index(x))
    return {"overall": worst, "rules": rules, "trading_days": trading_days, "target_pct": round(progress, 2)}
