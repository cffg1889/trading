"""
Unit tests for the backtesting engine.
"""

import numpy as np
import pandas as pd
import pytest

from backtest.engine import run_backtest, BacktestResult
from patterns.volume_breakout import VolumeBreakoutDetector
from patterns.base import Signal, PatternDetector


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_trending_ohlcv(n: int = 200, trend: float = 0.5) -> pd.DataFrame:
    """Uptrending OHLCV with all indicators."""
    from data.fetcher import add_indicators
    idx = pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC")
    close = 100.0 + trend * np.arange(n) + np.random.default_rng(0).normal(0, 1, n)
    high  = close + 1.0
    low   = close - 1.0
    open_ = close - 0.2
    vol   = np.full(n, 500_000.0)
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )
    return add_indicators(df)


class _AlwaysSignalDetector(PatternDetector):
    """Detector that always emits a long signal (for deterministic backtest tests)."""
    name = "always_signal"

    def detect(self, ticker, df, timeframe="daily"):
        if len(df) < 2:
            return []
        close = float(df["Close"].iloc[-1])
        atr   = float(df["atr"].iloc[-1]) if "atr" in df.columns else 1.0
        return [Signal(
            ticker=ticker, pattern=self.name, direction="long",
            timeframe=timeframe, detected_at=df.index[-1],
            entry=close, stop=close - 1.5 * atr, target=close + 3.0 * atr,
            confidence=70.0,
        )]


class _NeverSignalDetector(PatternDetector):
    """Detector that never emits a signal."""
    name = "never_signal"

    def detect(self, ticker, df, timeframe="daily"):
        return []


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRunBacktest:
    def test_returns_none_with_insufficient_data(self):
        df = _make_trending_ohlcv(30)
        det = _AlwaysSignalDetector()
        result = run_backtest(det, "TEST", df, min_bars_before_detect=60)
        assert result is None

    def test_returns_zero_trades_when_no_signals(self):
        df = _make_trending_ohlcv(200)
        det = _NeverSignalDetector()
        result = run_backtest(det, "TEST", df)
        assert result is not None
        assert result.n_trades == 0
        assert result.win_rate == 0.0

    def test_returns_backtest_result(self):
        df = _make_trending_ohlcv(200)
        det = _AlwaysSignalDetector()
        result = run_backtest(det, "TEST", df)
        assert isinstance(result, BacktestResult)
        assert result.n_trades >= 0

    def test_win_rate_between_0_and_1(self):
        df = _make_trending_ohlcv(200)
        det = _AlwaysSignalDetector()
        result = run_backtest(det, "TEST", df)
        assert 0.0 <= result.win_rate <= 1.0

    def test_no_overlapping_trades_with_deduplication(self):
        """With deduplication, trades should not overlap in time."""
        df = _make_trending_ohlcv(300)
        det = _AlwaysSignalDetector()
        result = run_backtest(det, "TEST", df)
        if result.n_trades <= 1:
            return  # nothing to verify
        # Verify no two trades start on the same bar
        entry_bars = [t["entry_bar"] for t in result.trades]
        assert len(entry_bars) == len(set(entry_bars)), "Duplicate entry bars found"

    def test_stride_reduces_trade_count(self):
        """Higher stride → fewer detection opportunities → equal or fewer trades."""
        df = _make_trending_ohlcv(400)
        det1 = _AlwaysSignalDetector()
        det2 = _AlwaysSignalDetector()
        r1 = run_backtest(det1, "TEST", df, stride=1)
        r2 = run_backtest(det2, "TEST", df, stride=3)
        assert r2.n_trades <= r1.n_trades

    def test_pnl_r_sign_matches_result(self):
        """Win trades should have positive P&L, loss trades negative."""
        df = _make_trending_ohlcv(300)
        det = _AlwaysSignalDetector()
        result = run_backtest(det, "TEST", df)
        for trade in result.trades:
            if trade["result"] == "win":
                assert trade["pnl_r"] > 0, f"Win trade has pnl_r={trade['pnl_r']}"
            elif trade["result"] == "loss":
                assert trade["pnl_r"] < 0, f"Loss trade has pnl_r={trade['pnl_r']}"

    def test_profit_factor_positive(self):
        df = _make_trending_ohlcv(300)
        det = _AlwaysSignalDetector()
        result = run_backtest(det, "TEST", df)
        assert result.profit_factor >= 0.0

    def test_summary_string(self):
        df = _make_trending_ohlcv(200)
        det = _AlwaysSignalDetector()
        result = run_backtest(det, "TEST", df)
        assert "Win rate" in result.summary
        assert "Sharpe" in result.summary


# ── BacktestResult ────────────────────────────────────────────────────────────

class TestBacktestResult:
    def test_summary_format(self):
        r = BacktestResult(
            ticker="AAPL", pattern="test",
            n_trades=10, win_rate=0.6, avg_rr=2.5,
            profit_factor=3.0, max_drawdown=2.0, sharpe=1.5,
            avg_bars_held=8.0, trades=[],
        )
        s = r.summary
        assert "60.0%" in s
        assert "2.50" in s
        assert "N=10" in s
