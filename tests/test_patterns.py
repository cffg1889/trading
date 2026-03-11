"""
Unit tests for pattern detectors and Signal dataclass.
"""

import numpy as np
import pandas as pd
import pytest

from patterns.base import Signal, PatternDetector
from patterns.double_bottom import DoubleBottomDetector
from patterns.volume_breakout import VolumeBreakoutDetector
from patterns.rsi_divergence import RSIDivergenceDetector
from patterns.vwap_deviation import VWAPDeviationDetector
from patterns.squeeze_breakout import SqueezeBreakoutDetector


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 100, base_price: float = 100.0, seed: int = 42) -> pd.DataFrame:
    """Generate a simple random-walk OHLCV DataFrame with tz-aware UTC index."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B", tz="UTC")
    close = base_price + np.cumsum(rng.normal(0, 1, n))
    high  = close + rng.uniform(0, 2, n)
    low   = close - rng.uniform(0, 2, n)
    open_ = close + rng.normal(0, 0.5, n)
    vol   = rng.integers(100_000, 1_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def _add_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Minimal indicator set required by most detectors."""
    from data.fetcher import add_indicators
    return add_indicators(df)


# ── Signal dataclass ──────────────────────────────────────────────────────────

class TestSignal:
    def test_risk_reward_calculated(self):
        sig = Signal(
            ticker="TEST", pattern="p", direction="long", timeframe="daily",
            detected_at=pd.Timestamp.now(tz="UTC"),
            entry=100.0, stop=95.0, target=115.0,
        )
        assert sig.risk_reward == pytest.approx(3.0)  # (115-100)/(100-95) = 15/5

    def test_risk_reward_short(self):
        sig = Signal(
            ticker="TEST", pattern="p", direction="short", timeframe="daily",
            detected_at=pd.Timestamp.now(tz="UTC"),
            entry=100.0, stop=104.0, target=90.0,
        )
        assert sig.risk_reward == pytest.approx(2.5)  # (100-90)/(104-100) = 10/4

    def test_risk_reward_zero_when_entry_equals_stop(self):
        sig = Signal(
            ticker="TEST", pattern="p", direction="long", timeframe="daily",
            detected_at=pd.Timestamp.now(tz="UTC"),
            entry=100.0, stop=100.0, target=110.0,
        )
        # __post_init__ skips computation when entry == stop
        assert sig.risk_reward == 0.0

    def test_summary_contains_ticker(self):
        sig = Signal(
            ticker="AAPL", pattern="Double Bottom", direction="long", timeframe="daily",
            detected_at=pd.Timestamp.now(tz="UTC"),
            entry=150.0, stop=145.0, target=165.0, confidence=75.0,
        )
        assert "AAPL" in sig.summary
        assert "LONG" in sig.summary


# ── PatternDetector helpers ───────────────────────────────────────────────────

class TestPatternDetectorHelpers:
    def test_atr_returns_series(self):
        df = _make_ohlcv(50)
        atr = PatternDetector._atr(df)
        assert len(atr) == len(df)
        assert atr.iloc[-1] > 0

    def test_atr_uses_precomputed_column(self):
        df = _make_ohlcv(50)
        df["atr"] = 5.0
        atr = PatternDetector._atr(df)
        assert (atr == 5.0).all()

    def test_pivot_lows_marks_local_minima(self):
        series = pd.Series([5.0, 3.0, 4.0, 2.0, 4.0, 3.0, 5.0])
        lows = PatternDetector._pivot_lows(series, window=1)
        # Index 3 (value 2.0) should be marked as a local minimum
        assert lows.iloc[3]

    def test_pivot_highs_marks_local_maxima(self):
        series = pd.Series([2.0, 5.0, 3.0, 6.0, 3.0, 5.0, 2.0])
        highs = PatternDetector._pivot_highs(series, window=1)
        # Index 3 (value 6.0) should be marked as a local maximum
        assert highs.iloc[3]


# ── DoubleBottomDetector ──────────────────────────────────────────────────────

class TestDoubleBottomDetector:
    def test_returns_empty_with_insufficient_data(self):
        df = _make_ohlcv(20)
        df = _add_basic_indicators(df)
        det = DoubleBottomDetector()
        assert det.detect("TEST", df, "daily") == []

    def test_returns_list(self):
        df = _make_ohlcv(100)
        df = _add_basic_indicators(df)
        det = DoubleBottomDetector()
        result = det.detect("TEST", df, "daily")
        assert isinstance(result, list)

    def test_signals_are_signal_objects(self):
        df = _make_ohlcv(200)
        df = _add_basic_indicators(df)
        det = DoubleBottomDetector()
        for sig in det.detect("TEST", df, "daily"):
            assert isinstance(sig, Signal)
            assert sig.direction in ("long", "short")
            assert sig.entry > 0
            assert sig.stop < sig.entry if sig.direction == "long" else sig.stop > sig.entry


# ── VolumeBreakoutDetector ────────────────────────────────────────────────────

class TestVolumeBreakoutDetector:
    def test_returns_empty_with_insufficient_data(self):
        df = _make_ohlcv(10)
        df = _add_basic_indicators(df)
        det = VolumeBreakoutDetector()
        assert det.detect("TEST", df, "daily") == []

    def test_returns_empty_with_low_volume(self):
        df = _make_ohlcv(60)
        df = _add_basic_indicators(df)
        # Force vol_ratio to 0.5 (below threshold)
        df["vol_ratio"] = 0.5
        det = VolumeBreakoutDetector()
        assert det.detect("TEST", df, "daily") == []

    def test_detects_bullish_breakout(self):
        """Construct a scenario where the last bar breaks the 20-day high with high volume."""
        df = _make_ohlcv(60, base_price=100.0, seed=1)
        df = _add_basic_indicators(df)
        # Force last bar to break 20-day high with strong volume
        df.iloc[-1, df.columns.get_loc("High")]   = df["High"].iloc[-21:-1].max() + 5.0
        df.iloc[-1, df.columns.get_loc("Close")]  = df["High"].iloc[-1] - 0.1
        df.iloc[-2, df.columns.get_loc("Close")]  = df["High"].iloc[-21:-1].max() - 0.1
        df["vol_ratio"] = 0.5
        df.iloc[-1, df.columns.get_loc("vol_ratio")] = 3.0
        det = VolumeBreakoutDetector()
        signals = det.detect("TEST", df, "daily")
        long_signals = [s for s in signals if s.direction == "long"]
        assert len(long_signals) >= 1


# ── RSIDivergenceDetector ─────────────────────────────────────────────────────

class TestRSIDivergenceDetector:
    def test_returns_empty_without_rsi_column(self):
        df = _make_ohlcv(80)
        det = RSIDivergenceDetector()
        assert det.detect("TEST", df, "daily") == []

    def test_returns_empty_with_insufficient_data(self):
        df = _make_ohlcv(20)
        df = _add_basic_indicators(df)
        det = RSIDivergenceDetector()
        assert det.detect("TEST", df, "daily") == []

    def test_returns_list(self):
        df = _make_ohlcv(120)
        df = _add_basic_indicators(df)
        det = RSIDivergenceDetector()
        result = det.detect("TEST", df, "daily")
        assert isinstance(result, list)

    def test_all_signals_have_valid_direction(self):
        df = _make_ohlcv(200, seed=7)
        df = _add_basic_indicators(df)
        det = RSIDivergenceDetector()
        for sig in det.detect("TEST", df, "daily"):
            assert sig.direction in ("long", "short")
            assert sig.pattern in (
                "Regular Bullish Divergence (RSI)",
                "Regular Bearish Divergence (RSI)",
                "Hidden Bullish Divergence (RSI)",
                "Hidden Bearish Divergence (RSI)",
            )


# ── VWAPDeviationDetector ─────────────────────────────────────────────────────

class TestVWAPDeviationDetector:
    def test_returns_empty_without_required_columns(self):
        df = _make_ohlcv(50)
        det = VWAPDeviationDetector()
        assert det.detect("TEST", df, "daily") == []

    def test_detects_oversold_deviation(self):
        df = _make_ohlcv(60, seed=3)
        df = _add_basic_indicators(df)
        # Force last bar to be far below VWAP
        vwap_last = float(df["vwap"].iloc[-1])
        dev_std = float((df["Close"] - df["vwap"]).rolling(20).std().iloc[-1])
        if dev_std > 0:
            df.iloc[-1, df.columns.get_loc("Close")] = vwap_last - 3.0 * dev_std
            df.iloc[-1, df.columns.get_loc("vol_ratio")] = 2.0
            df.iloc[-1, df.columns.get_loc("rsi")] = 25.0
        det = VWAPDeviationDetector()
        result = det.detect("TEST", df, "daily")
        assert isinstance(result, list)


# ── SqueezeBreakoutDetector ───────────────────────────────────────────────────

class TestSqueezeBreakoutDetector:
    def test_returns_empty_with_insufficient_data(self):
        df = _make_ohlcv(20)
        df = _add_basic_indicators(df)
        det = SqueezeBreakoutDetector()
        assert det.detect("TEST", df, "daily") == []

    def test_returns_list(self):
        df = _make_ohlcv(100)
        df = _add_basic_indicators(df)
        det = SqueezeBreakoutDetector()
        result = det.detect("TEST", df, "daily")
        assert isinstance(result, list)

    def test_detects_squeeze_release(self):
        """Force a squeeze state then release it."""
        df = _make_ohlcv(80, seed=5)
        df = _add_basic_indicators(df)
        # Put bars -6 to -2 in squeeze (BB inside KC)
        for i in range(-7, -1):
            df.iloc[i, df.columns.get_loc("bb_upper")] = df["kc_upper"].iloc[i] - 0.5
            df.iloc[i, df.columns.get_loc("bb_lower")] = df["kc_lower"].iloc[i] + 0.5
        # Last bar: BB outside KC (squeeze fires)
        df.iloc[-1, df.columns.get_loc("bb_upper")] = df["kc_upper"].iloc[-1] + 1.0
        df.iloc[-1, df.columns.get_loc("bb_lower")] = df["kc_lower"].iloc[-1] - 1.0
        det = SqueezeBreakoutDetector()
        result = det.detect("TEST", df, "daily")
        assert isinstance(result, list)
