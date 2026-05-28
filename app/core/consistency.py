"""Proprietary Consistency Score (0-100).

Penalises:
- lot variance (irregular sizing)
- one-day P&L dominance
- sizing spikes (> 2σ trades)
- asymmetric emotion (avg win vs avg loss imbalance)
- single-trade dominance of net profit
"""
from __future__ import annotations
from collections import defaultdict
from statistics import mean, pstdev

from app.config import settings


def _closed(deals: list[dict]) -> list[dict]:
    return [d for d in deals if d.get("entry") == "out"]


def compute(deals: list[dict]) -> dict:
    closed = _closed(deals)
    if len(closed) < 3:
        return {
            "score": 100, "grade": "green", "breach_probability": 0.0,
            "breakdown": {}, "reason": "Not enough data",
        }

    pnls = [d["profit"] + d.get("commission", 0) + d.get("swap", 0) for d in closed]
    vols = [d["volume"] for d in closed]
    net = sum(pnls)

    penalties: dict[str, float] = {}

    # 1) Lot variance — coefficient of variation
    mv = mean(vols) or 1e-9
    cv = pstdev(vols) / mv
    penalties["lot_variance"] = min(cv * 25, 25)            # cap 25

    # 2) Sizing spikes (> 2σ)
    sd = pstdev(vols)
    if sd > 0:
        spikes = sum(1 for v in vols if abs(v - mv) > 2 * sd)
        penalties["sizing_spikes"] = min(spikes / len(vols) * 100, 15)
    else:
        penalties["sizing_spikes"] = 0

    # 3) One-trade dominance
    if net > 0:
        biggest_win = max((p for p in pnls if p > 0), default=0)
        penalties["single_trade_dominance"] = min(biggest_win / net * 30, 20)
    else:
        penalties["single_trade_dominance"] = 0

    # 4) Daily concentration vs prop-firm rule
    by_day: dict[str, float] = defaultdict(float)
    for d, p in zip(closed, pnls):
        by_day[d["time"][:10]] += p
    if net > 0:
        worst_day_share = max(by_day.values()) / net * 100
        limit = settings.max_consistency_day_pct
        over = max(worst_day_share - limit, 0)
        penalties["daily_concentration"] = min(over * 0.6, 25)
    else:
        penalties["daily_concentration"] = 0

    # 5) Asymmetric emotion (avg win vs avg loss)
    wins = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]
    if wins and losses:
        ratio = mean(wins) / mean(losses)
        # healthy band 0.8 – 2.5
        if ratio < 0.8:
            penalties["asymmetry"] = min((0.8 - ratio) * 20, 15)
        elif ratio > 2.5:
            penalties["asymmetry"] = min((ratio - 2.5) * 8, 15)
        else:
            penalties["asymmetry"] = 0
    else:
        penalties["asymmetry"] = 10  # all wins or all losses

    total_penalty = sum(penalties.values())
    score = max(0, round(100 - total_penalty, 1))

    if score >= 75:
        grade = "green"
    elif score >= 50:
        grade = "yellow"
    else:
        grade = "red"

    # rough breach probability — sigmoid on penalty load
    import math
    breach_prob = round(1 / (1 + math.exp((75 - score) / 10)), 3)

    return {
        "score": score,
        "grade": grade,
        "breach_probability": breach_prob,
        "breakdown": {k: round(v, 2) for k, v in penalties.items()},
    }
