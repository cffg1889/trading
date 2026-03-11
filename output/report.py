"""
Terminal report using the 'rich' library.

Displays a ranked table of signals with:
  - Ticker, Pattern, Direction
  - Entry / Stop / Target / R:R
  - Confidence score
  - Backtest win rate & sample count
  - Options trade recommendation
"""

from __future__ import annotations
from datetime import datetime

from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.text    import Text
from rich import box

from patterns.base         import Signal
from backtest.engine        import BacktestResult
from recommender.options    import OptionsRecommendation

console = Console()


def _direction_style(direction: str) -> str:
    return "bold green" if direction == "long" else "bold red"


def _confidence_style(score: float) -> str:
    if score >= 75:
        return "bold green"
    if score >= 55:
        return "yellow"
    return "dim"


def print_report(results: list[dict], timeframe: str = "daily") -> None:
    """
    Print a full signal report to the terminal.

    Each item in results is a dict with keys:
        signal    : Signal
        bt_result : BacktestResult | None
        opt_rec   : OptionsRecommendation | None
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    console.print()
    console.print(Panel(
        f"[bold cyan]Trading Signal Scanner[/bold cyan]  ·  "
        f"[white]{now}[/white]  ·  "
        f"[yellow]{timeframe.upper()}[/yellow]  ·  "
        f"[white]{len(results)} signals[/white]",
        expand=False,
    ))
    console.print()

    if not results:
        console.print("[dim]No signals detected.[/dim]")
        return

    # ── Main signals table ────────────────────────────────────────────────────
    tbl = Table(
        show_header=True,
        header_style="bold white on dark_blue",
        box=box.SIMPLE_HEAD,
        expand=True,
    )

    tbl.add_column("#",         style="dim",     width=3,  justify="right")
    tbl.add_column("Ticker",    style="bold",    width=10)
    tbl.add_column("Pattern",                    width=35)
    tbl.add_column("Dir",                        width=6)
    tbl.add_column("Entry",     justify="right", width=10)
    tbl.add_column("Stop",      justify="right", width=10)
    tbl.add_column("Target",    justify="right", width=10)
    tbl.add_column("R:R",       justify="right", width=5)
    tbl.add_column("Conf",      justify="right", width=6)
    tbl.add_column("Win%",      justify="right", width=6)
    tbl.add_column("N",         justify="right", width=5)
    tbl.add_column("Options Trade",              width=45)

    for rank, item in enumerate(results, 1):
        sig:     Signal                  = item["signal"]
        bt:      BacktestResult | None   = item.get("bt_result")
        opt:     OptionsRecommendation | None = item.get("opt_rec")

        dir_text = Text(sig.direction.upper(), style=_direction_style(sig.direction))
        conf_str = Text(f"{sig.confidence:.0f}", style=_confidence_style(sig.confidence))

        win_str = (
            Text(f"{bt.win_rate*100:.0f}%", style="green" if bt.win_rate >= 0.5 else "red")
            if bt and bt.n_trades > 0 else Text("—", style="dim")
        )
        n_str = str(bt.n_trades) if bt and bt.n_trades > 0 else "—"

        if opt:
            short_str = f"/{opt.short_strike:.0f}" if opt.short_strike else ""
            opt_str = (
                f"{opt.structure}  K={opt.long_strike:.2f}{short_str}  "
                f"{opt.dte}d  ~{opt.estimated_premium:.2f}"
            )
        else:
            opt_str = "—"

        tbl.add_row(
            str(rank),
            sig.ticker,
            sig.pattern,
            dir_text,
            f"{sig.entry:.4f}",
            f"{sig.stop:.4f}",
            f"{sig.target:.4f}",
            f"{sig.risk_reward:.1f}",
            conf_str,
            win_str,
            n_str,
            opt_str,
        )

    console.print(tbl)

    # ── Detail cards for top 3 ────────────────────────────────────────────────
    console.print()
    console.rule("[bold cyan]Top Signal Details[/bold cyan]")

    for item in results[:3]:
        sig = item["signal"]
        bt  = item.get("bt_result")
        opt = item.get("opt_rec")

        lines = [
            f"[bold]{sig.ticker}[/bold] — [cyan]{sig.pattern}[/cyan]",
            f"Direction  : {sig.direction.upper()}",
            f"Detected   : {sig.detected_at}",
            f"Entry      : {sig.entry:.4f}",
            f"Stop       : {sig.stop:.4f}  (−{abs(sig.entry - sig.stop):.4f})",
            f"Target     : {sig.target:.4f}  (+{abs(sig.target - sig.entry):.4f})",
            f"R:R        : {sig.risk_reward:.2f}",
            f"Confidence : {sig.confidence:.0f}/100",
        ]
        if sig.notes:
            lines.append(f"Notes      : {sig.notes}")

        if bt and bt.n_trades > 0:
            lines += [
                "",
                f"[bold]Backtest ({bt.n_trades} trades)[/bold]",
                f"  Win rate      : {bt.win_rate*100:.1f}%",
                f"  Avg R:R       : {bt.avg_rr:.2f}",
                f"  Profit factor : {bt.profit_factor:.2f}",
                f"  Max drawdown  : {bt.max_drawdown:.2f}R",
                f"  Sharpe        : {bt.sharpe:.2f}",
                f"  Avg hold      : {bt.avg_bars_held:.1f} bars",
            ]

        if opt:
            lines += [
                "",
                f"[bold]Options Idea[/bold]",
                f"  Structure : {opt.structure}",
                f"  Strike    : {opt.long_strike:.2f}"
                + (f" / {opt.short_strike:.2f}" if opt.short_strike else ""),
                f"  Expiry    : ~{opt.dte} days",
                f"  Premium   : ~{opt.estimated_premium:.4f}",
                f"  Max loss  : {opt.max_loss:.4f}",
                f"  Max gain  : {opt.max_gain:.4f}" if opt.max_gain < 999999 else "  Max gain  : unlimited",
                f"  IV used   : {opt.iv_used*100:.0f}%",
            ]

        console.print(Panel("\n".join(lines), expand=False))

    console.print()
