"""Alert rule evaluation + dedupe."""
from __future__ import annotations
import time
from app.config import settings
from app.alerts.telegram import send as tg_send
from app.storage.db import save_alert

_last_sent: dict[str, float] = {}
_COOLDOWN = 300  # seconds


def _cooldown_ok(kind: str) -> bool:
    now = time.time()
    if now - _last_sent.get(kind, 0) < _COOLDOWN:
        return False
    _last_sent[kind] = now
    return True


async def evaluate(snapshot: dict) -> list[dict]:
    fired: list[dict] = []
    dd = snapshot["drawdowns"]
    cons = snapshot["consistency"]
    acc = snapshot["account"]
    rules = snapshot["rules"]

    daily_used_pct = next((r["used_pct"] for r in rules["rules"]
                           if r["name"] == "Daily drawdown" and r["used_pct"] is not None), 0)
    if daily_used_pct >= settings.alert_dd_usage_pct and _cooldown_ok("daily_dd"):
        msg = f"⚠️ <b>Daily DD warning</b>\nUsed {daily_used_pct:.1f}% of daily limit (${dd['daily_loss_abs']:.2f})"
        fired.append({"kind": "daily_dd", "level": "warning", "message": msg})

    if cons["score"] < settings.alert_consistency_below and _cooldown_ok("consistency"):
        msg = f"⚠️ <b>Consistency low</b>\nScore: {cons['score']} ({cons['grade']})"
        fired.append({"kind": "consistency", "level": "warning", "message": msg})

    ml = acc.get("margin_level", 0)
    if 0 < ml < 200 and _cooldown_ok("margin"):
        msg = f"🚨 <b>Margin level danger</b>\nCurrent: {ml:.0f}%"
        fired.append({"kind": "margin", "level": "danger", "message": msg})

    for a in fired:
        save_alert(a["level"], a["kind"], a["message"])
        await tg_send(a["message"])
    return fired
