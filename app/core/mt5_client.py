"""MetaTrader 5 client with auto-reconnect + mock-mode fallback."""
from __future__ import annotations
import logging
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any

from app.config import settings

log = logging.getLogger("mt5")

try:
    import MetaTrader5 as mt5  # type: ignore
    HAS_MT5 = True
except Exception:
    mt5 = None  # type: ignore
    HAS_MT5 = False


@dataclass
class AccountInfo:
    login: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    currency: str
    profit: float
    leverage: int


@dataclass
class Position:
    ticket: int
    symbol: str
    type: str           # buy / sell
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    swap: float
    time: str


@dataclass
class Deal:
    ticket: int
    order: int
    symbol: str
    type: str
    volume: float
    price: float
    profit: float
    commission: float
    swap: float
    time: str
    entry: str          # in / out


class MT5Client:
    def __init__(self) -> None:
        self.connected = False
        self._last_attempt = 0.0
        self._mock = settings.mock_mode or not HAS_MT5
        if self._mock:
            log.warning("Running in MOCK MODE (no real MT5 connection).")
            self._mock_state = _MockMarket()

    # ----- lifecycle -----
    def connect(self) -> bool:
        if self._mock:
            self.connected = True
            return True
        if mt5 is None:
            return False
        kwargs: dict[str, Any] = {}
        if settings.mt5_path:
            kwargs["path"] = settings.mt5_path
        if not mt5.initialize(**kwargs):
            log.error("MT5 initialize() failed: %s", mt5.last_error())
            return False
        if settings.mt5_login and settings.mt5_password and settings.mt5_server:
            ok = mt5.login(
                login=settings.mt5_login,
                password=settings.mt5_password,
                server=settings.mt5_server,
            )
            if not ok:
                log.error("MT5 login failed: %s", mt5.last_error())
                mt5.shutdown()
                return False
        self.connected = True
        log.info("MT5 connected.")
        return True

    def ensure_connected(self) -> bool:
        if self.connected:
            if self._mock:
                return True
            # cheap heartbeat
            info = mt5.account_info() if mt5 else None
            if info is not None:
                return True
            log.warning("MT5 heartbeat lost, reconnecting…")
            self.connected = False
        # backoff
        if time.time() - self._last_attempt < 3:
            return False
        self._last_attempt = time.time()
        return self.connect()

    def shutdown(self) -> None:
        if not self._mock and mt5 is not None and self.connected:
            mt5.shutdown()
        self.connected = False

    # ----- data -----
    def account_info(self) -> AccountInfo | None:
        if self._mock:
            return self._mock_state.account()
        info = mt5.account_info()
        if info is None:
            return None
        return AccountInfo(
            login=info.login,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            margin_free=info.margin_free,
            margin_level=info.margin_level,
            currency=info.currency,
            profit=info.profit,
            leverage=info.leverage,
        )

    def positions(self) -> list[Position]:
        if self._mock:
            return self._mock_state.positions()
        rows = mt5.positions_get() or []
        out: list[Position] = []
        for p in rows:
            out.append(Position(
                ticket=p.ticket,
                symbol=p.symbol,
                type="buy" if p.type == 0 else "sell",
                volume=p.volume,
                price_open=p.price_open,
                price_current=p.price_current,
                sl=p.sl, tp=p.tp,
                profit=p.profit, swap=p.swap,
                time=datetime.fromtimestamp(p.time).isoformat(),
            ))
        return out

    def deals(self, days: int = 30) -> list[Deal]:
        if self._mock:
            return self._mock_state.deals()
        to = datetime.now()
        frm = to - timedelta(days=days)
        rows = mt5.history_deals_get(frm, to) or []
        out: list[Deal] = []
        for d in rows:
            out.append(Deal(
                ticket=d.ticket, order=d.order, symbol=d.symbol,
                type="buy" if d.type == 0 else "sell",
                volume=d.volume, price=d.price,
                profit=d.profit, commission=d.commission, swap=d.swap,
                time=datetime.fromtimestamp(d.time).isoformat(),
                entry="in" if d.entry == 0 else "out",
            ))
        return out


# ---------- mock generator ----------
class _MockMarket:
    """Generates plausible account + trade data for offline development."""

    def __init__(self) -> None:
        self.balance = settings.initial_balance
        self.equity = self.balance
        self._t0 = time.time()
        self._positions: list[Position] = []
        self._deals: list[Deal] = []
        self._next_ticket = 100000
        self._symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100"]
        # seed some history
        for i in range(40):
            self._close_random_deal(offset_min=-(40 - i) * 30)

    def _close_random_deal(self, offset_min: int = 0) -> None:
        sym = random.choice(self._symbols)
        vol = round(random.choice([0.05, 0.1, 0.1, 0.2, 0.5]), 2)
        win = random.random() < 0.55
        pnl = round(random.uniform(40, 220) * (1 if win else -1) * (vol / 0.1), 2)
        self.balance += pnl
        t = (datetime.now() + timedelta(minutes=offset_min)).isoformat()
        self._next_ticket += 1
        self._deals.append(Deal(
            ticket=self._next_ticket, order=self._next_ticket, symbol=sym,
            type=random.choice(["buy", "sell"]), volume=vol,
            price=random.uniform(1, 2000), profit=pnl,
            commission=-0.5 * vol, swap=0, time=t, entry="out",
        ))

    def account(self) -> AccountInfo:
        # gentle equity drift
        drift = random.uniform(-25, 30)
        self.equity = max(self.balance + drift + sum(p.profit for p in self._positions), 1)
        # occasionally open/close a position
        if random.random() < 0.05 and len(self._positions) < 3:
            self._open_random_position()
        elif self._positions and random.random() < 0.07:
            p = self._positions.pop(random.randrange(len(self._positions)))
            self.balance += p.profit
            self._next_ticket += 1
            self._deals.append(Deal(
                ticket=self._next_ticket, order=p.ticket, symbol=p.symbol,
                type=p.type, volume=p.volume, price=p.price_current,
                profit=p.profit, commission=-0.5 * p.volume, swap=p.swap,
                time=datetime.now().isoformat(), entry="out",
            ))
        # mutate floating P&L
        for p in self._positions:
            p.profit = round(p.profit + random.uniform(-5, 5), 2)
        used = sum(p.volume * 1000 for p in self._positions)
        return AccountInfo(
            login=99999999, balance=round(self.balance, 2),
            equity=round(self.equity, 2), margin=used,
            margin_free=max(self.equity - used, 0),
            margin_level=(self.equity / used * 100) if used else 0,
            currency="USD", profit=round(self.equity - self.balance, 2),
            leverage=100,
        )

    def _open_random_position(self) -> None:
        self._next_ticket += 1
        sym = random.choice(self._symbols)
        self._positions.append(Position(
            ticket=self._next_ticket, symbol=sym,
            type=random.choice(["buy", "sell"]),
            volume=round(random.choice([0.05, 0.1, 0.2]), 2),
            price_open=random.uniform(1, 2000),
            price_current=random.uniform(1, 2000),
            sl=0, tp=0, profit=0, swap=0,
            time=datetime.now().isoformat(),
        ))

    def positions(self) -> list[Position]:
        return list(self._positions)

    def deals(self) -> list[Deal]:
        return list(self._deals)


def to_dict(obj) -> dict:
    return asdict(obj) if hasattr(obj, "__dataclass_fields__") else dict(obj)
