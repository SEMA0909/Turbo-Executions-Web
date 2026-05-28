"""Environment configuration loader."""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # MT5
    mt5_login: int = _int("MT5_LOGIN", 0)
    mt5_password: str = os.getenv("MT5_PASSWORD", "")
    mt5_server: str = os.getenv("MT5_SERVER", "")
    mt5_path: str = os.getenv("MT5_PATH", "")
    poll_interval: float = _float("POLL_INTERVAL_SECONDS", 2.0)
    mock_mode: bool = _bool("MOCK_MODE", False)

    # Prop-firm rules
    initial_balance: float = _float("INITIAL_BALANCE", 100_000)
    daily_dd_limit_pct: float = _float("DAILY_DD_LIMIT_PCT", 5)
    total_dd_limit_pct: float = _float("TOTAL_DD_LIMIT_PCT", 10)
    profit_target_pct: float = _float("PROFIT_TARGET_PCT", 8)
    min_trading_days: int = _int("MIN_TRADING_DAYS", 5)
    max_consistency_day_pct: float = _float("MAX_CONSISTENCY_DAY_PCT", 40)

    # Alerts
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    alert_dd_usage_pct: float = _float("ALERT_DD_USAGE_PCT", 70)
    alert_consistency_below: float = _float("ALERT_CONSISTENCY_BELOW", 50)

    # Server
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = _int("PORT", 8000)

    # Access code for dashboard (simple shared secret). Set ACCESS_CODE in .env
    access_code: str = os.getenv("ACCESS_CODE", "")


settings = Settings()
