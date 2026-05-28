"""Smoke tests for pure modules."""
from app.core import metrics, consistency

DEALS = [
    {"ticket": 1, "symbol": "EURUSD", "type": "buy",  "volume": 0.1, "price": 1.1, "profit": 100, "commission": -0.5, "swap": 0, "entry": "out", "time": "2025-05-27T10:00:00"},
    {"ticket": 2, "symbol": "EURUSD", "type": "sell", "volume": 0.1, "price": 1.1, "profit": -50, "commission": -0.5, "swap": 0, "entry": "out", "time": "2025-05-27T11:00:00"},
    {"ticket": 3, "symbol": "XAUUSD", "type": "buy",  "volume": 0.2, "price": 2000,"profit": 200, "commission": -1.0, "swap": 0, "entry": "out", "time": "2025-05-28T09:00:00"},
    {"ticket": 4, "symbol": "XAUUSD", "type": "buy",  "volume": 0.1, "price": 2000,"profit": -30, "commission": -0.5, "swap": 0, "entry": "out", "time": "2025-05-28T10:00:00"},
]

def test_performance():
    p = metrics.performance(DEALS)
    assert p["trades"] == 4
    assert p["win_rate"] == 50.0

def test_consistency():
    c = consistency.compute(DEALS)
    assert 0 <= c["score"] <= 100
    assert c["grade"] in {"green", "yellow", "red"}

def test_drawdowns():
    d = metrics.drawdowns(100000, 100200, DEALS)
    assert d["max_drawdown_abs"] >= 0

if __name__ == "__main__":
    test_performance(); test_consistency(); test_drawdowns()
    print("ok")
