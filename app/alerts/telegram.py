"""Telegram alert sender (no-op if not configured)."""
from __future__ import annotations
import logging
import httpx
from app.config import settings

log = logging.getLogger("alerts.telegram")


async def send(message: str) -> bool:
    if not settings.telegram_token or not settings.telegram_chat_id:
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(url, json={
                "chat_id": settings.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
            })
        if r.status_code != 200:
            log.warning("Telegram failed: %s %s", r.status_code, r.text)
            return False
        return True
    except Exception as e:
        log.warning("Telegram error: %s", e)
        return False
