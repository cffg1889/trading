"""
Backtesting engine — vectorized, look-ahead-bias free.

For each pattern detector, replay it on historical data:
  1. Slide a window across the full history
  2. At each bar, detect signals using only past data
  3. Simulate the trade (entry at next open, stop/target via ATR)
  4. Compute aggregate statistics

Usage:
    from backtest.engine import run_backtest
    stats = run_backtest(detector, ticker, df)
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
import logging

from patterns.base import PatternDetector, Signal
from config import STOP_ATR_MULT, TARGET_ATR_MULT, RISK_REWARD_MIN

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    ticker:      str
    pattern:     str
    n_trades:    int
    win_rate:    float   # 0–1
    avg_rr:      float   # average realised R:R on winners
    profit_factor: float # gross profit / gross loss
    max_drawdown: float  # max peak-to-trough in cumulative P&L (in R units)
    sharpe:      float   # annualised Sharpe on daily R units
    avg_bars_held: float
    trades:      list[dict]  # raw trade log

    @property
    def summary(self) -> str:
        return (
            f"  Win rate: {self.win_rate*100:.1f}%  |  "
            f"Avg R:R: {self.avg_rr:.2f}  |  "
            f"Profit factor: {self.profit_factor:.2f}  |  "
            f"Max DD: {self.max_drawdown:.2f}R  |  "
            f"Sharpe: {self.sharpe:.2f}  |  "
            f"N={self.n_trades}"
        )


def run_backtest(
    detector: PatternDetector,
    ticker:   str,
    df:       pd.DataFrame,
    timeframe: str = "daily",
    min_bars_before_detect: int = 60,
    max_bars_in_trade: int = 30,
) -> BacktestResult | None:
    """
    Walk-forward backtest for a single detector on a single instrument.

    Entry  : next bar's Open after signal
    Stop   : fixed from signal (entry - STOP_ATR_MULT * ATR)
    Target : fixed from signal (entry + TARGET_ATR_MULT * ATR)
    Exit   : whichever of stop/target hits first, or max_bars_in_trade
    """
    if len(df) < min_bars_before_detect + 10:
        return None

    trades: list[dict] = []

    # Walk forward: detect at bar i, trade from bar i+1
    for i in range(min_bars_before_detect, len(df) - 1):
        slice_df = df.iloc[:i + 1].copy()

        try:
            signals = detector.detect(ticker, slice_df, timeframe)
        except Exception as e:
            logger.debug(f"[backtest] {ticker} {detector.name} bar {i}: {e}")
            continue

        for sig in signals:
            if sig.risk_reward < RISK_REWARD_MIN:
                continue

            # Entry at next open
            entry_bar  = i + 1
            if entry_bar >= len(df):
                continue

            entry_price = float(df["Open"].iloc[entry_bar])
            stop        = sig.stop
            target      = sig.target
            direction   = sig.direction  # "long" | "short"

            result      = None
            bars_held   = 0
            exit_price  = None

            for j in range(entry_bar, min(entry_bar + max_bars_in_trade, len(df))):
                bar_high = float(df["High"].iloc[j])
                bar_low  = float(df["Low"].iloc[j])
                bars_held = j - entry_bar + 1

                if direction == "long":
                    if bar_low <= stop:
                        result     = "loss"
                        exit_price = stop
                        break
                    if bar_high >= target:
                        result     = "win"
                        exit_price = target
                        break
                else:  # short
                    if bar_high >= stop:
                        result     = "loss"
                        exit_price = stop
                        break
                    if bar_low <= target:
                        result     = "win"
                        exit_price = target
                        break
            else:
                # Timeout — exit at close
                result     = "timeout"
                exit_price = float(df["Close"].iloc[min(entry_bar + max_bars_in_trade - 1, len(df) - 1)])

            # Compute R unit P&L
            risk = abs(entry_price - stop)
            if risk == 0:
                continue

            if direction == "long":
                pnl_r = (exit_price - entry_price) / risk
            else:
                pnl_r = (entry_price - exit_price) / risk

            trades.append({
                "entry_bar":   entry_bar,
                "entry_price": entry_price,
                "exit_price":  exit_price,
                "direction":   direction,
                "result":      result,
                "pnl_r":       pnl_r,
                "bars_held":   bars_held,
                "confidence":  sig.confidence,
            })

    if not trades:
        return BacktestResult(
            ticker=ticker, pattern=detector.name, n_trades=0,
            win_rate=0.0, avg_rr=0.0, profit_factor=0.0,
            max_drawdown=0.0, sharpe=0.0, avg_bars_held=0.0, trades=[],
        )

    pnl_series = pd.Series([t["pnl_r"] for t in trades])
    wins       = pnl_series[pnl_series > 0]
    losses     = pnl_series[pnl_series <= 0]

    win_rate   = len(wins) / len(trades)
    avg_rr     = float(wins.mean()) if len(wins) > 0 else 0.0
    gross_win  = float(wins.sum())  if len(wins) > 0 else 0.0
    gross_loss = float(losses.abs().sum()) if len(losses) > 0 else 1e-9
    pf         = gross_win / gross_loss

    # Max drawdown in R units
    cumulative = pnl_series.cumsum()
    rolling_max = cumulative.cummax()
    drawdown    = rolling_max - cumulative
    max_dd      = float(drawdown.max())

    # Sharpe (daily R units, annualised)
    if pnl_series.std() > 0:
        sharpe = float(pnl_series.mean() / pnl_series.std() * np.sqrt(252))
    else:
        sharpe = 0.0

    avg_bars = float(np.mean([t["bars_held"] for t in trades]))

    return BacktestResult(
        ticker       = ticker,
        pattern      = detector.name,
        n_trades     = len(trades),
        win_rate     = round(win_rate, 4),
        avg_rr       = round(avg_rr, 2),
        profit_factor= round(pf, 2),
        max_drawdown  = round(max_dd, 2),
        sharpe       = round(sharpe, 2),
        avg_bars_held= round(avg_bars, 1),
        trades       = trades,
    )
