"""Rich-based terminal monitor. Reads from local API.

Run after `python -m app.main` is up:

    python -m app.tui
"""
from __future__ import annotations
import time
import os
import httpx
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.config import settings

BASE = f"http://{settings.host}:{settings.port}"
console = Console()


def _color(status: str) -> str:
    return {"safe": "green", "info": "cyan", "warning": "yellow",
            "breach": "red", "danger": "red", "green": "green",
            "yellow": "yellow", "red": "red"}.get(status, "white")


def render(snap: dict) -> Layout:
    layout = Layout()
    layout.split_column(Layout(name="top", size=8), Layout(name="mid"), Layout(name="bot", size=12))

    acc = snap.get("account", {})
    dd = snap.get("drawdowns", {})
    perf = snap.get("performance", {})
    cons = snap.get("consistency", {})
    rules = snap.get("rules", {})

    summary = Table.grid(expand=True)
    summary.add_column(); summary.add_column(); summary.add_column(); summary.add_column()
    summary.add_row(
        f"[bold]Balance[/]\n${acc.get('balance', 0):,.2f}",
        f"[bold]Equity[/]\n${acc.get('equity', 0):,.2f}",
        f"[bold]Floating P&L[/]\n${acc.get('profit', 0):,.2f}",
        f"[bold]Margin Lvl[/]\n{acc.get('margin_level', 0):.0f}%",
    )
    layout["top"].update(Panel(summary, title=f"Account #{acc.get('login','-')} — {'MOCK' if snap.get('settings',{}).get('mock_mode') else 'LIVE'}"))

    metrics_tbl = Table(title="Performance & Risk", expand=True)
    metrics_tbl.add_column("Metric"); metrics_tbl.add_column("Value", justify="right")
    metrics_tbl.add_row("Trades", str(perf.get("trades", 0)))
    metrics_tbl.add_row("Win rate", f"{perf.get('win_rate',0):.1f}%")
    metrics_tbl.add_row("Profit factor", f"{perf.get('profit_factor',0)}")
    metrics_tbl.add_row("Expectancy", f"${perf.get('expectancy',0):.2f}")
    metrics_tbl.add_row("Net profit", f"${perf.get('net_profit',0):,.2f}")
    metrics_tbl.add_row("Daily loss", f"${dd.get('daily_loss_abs',0):,.2f} ({dd.get('daily_loss_pct',0):.2f}%)")
    metrics_tbl.add_row("Max drawdown", f"${dd.get('max_drawdown_abs',0):,.2f} ({dd.get('max_drawdown_pct',0):.2f}%)")
    g = _color(cons.get("grade", "green"))
    metrics_tbl.add_row("Consistency", Text(f"{cons.get('score',0)} ({cons.get('grade','-')})", style=g))

    layout["mid"].update(Panel(metrics_tbl, title="Metrics"))

    rules_tbl = Table(title=f"Prop Firm Rules — overall: [{_color(rules.get('overall','safe'))}]{rules.get('overall','-').upper()}[/]", expand=True)
    rules_tbl.add_column("Rule"); rules_tbl.add_column("Status"); rules_tbl.add_column("Detail"); rules_tbl.add_column("Used", justify="right")
    for r in rules.get("rules", []):
        rules_tbl.add_row(r["name"], Text(r["status"].upper(), style=_color(r["status"])),
                          r["detail"], f"{r['used_pct']}%" if r.get("used_pct") is not None else "-")
    layout["bot"].update(Panel(rules_tbl, title="Compliance"))
    return layout


def main() -> None:
    update_count = 0
    while True:
        try:
            r = httpx.get(f"{BASE}/api/snapshot", timeout=3)
            data = r.json()
            if r.status_code == 200 and data:
                os.system("cls" if os.name == "nt" else "clear")
                console.print(render(data))
                update_count += 1
                console.print(f"\n[dim]Update #{update_count} at {time.strftime('%H:%M:%S')}[/]")
            else:
                console.print(Panel(f"[yellow]Waiting for data… Status {r.status_code}[/]"))
        except Exception as e:
            console.print(Panel(f"[red]Error connecting to {BASE}[/]\n{e}"))
        time.sleep(settings.poll_interval)


if __name__ == "__main__":
    main()
