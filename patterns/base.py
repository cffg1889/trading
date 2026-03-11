"""
Base classes for pattern detection.
Every pattern detector must implement detect() and return a list of Signal objects.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class Signal:
    """A detected trading signal."""
    ticker:      str
    pattern:     str            # human-readable pattern name
    direction:   str            # "long" | "short"
    timeframe:   str            # "daily" | "hourly" | "intraday"
    detected_at: pd.Timestamp   # bar where pattern was confirmed

    # Price levels
    entry:       float
    stop:        float
    target:      float

    # Quality metrics
    confidence:  float = 0.0    # 0–100 score
    risk_reward: float = 0.0    # |target-entry| / |entry-stop|

    # Backtest stats (filled in by backtest engine)
    win_rate:    float = 0.0
    avg_rr:      float = 0.0
    n_samples:   int   = 0

    # Extra context
    notes:       str   = ""
    extra:       dict  = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.entry != self.stop:
            self.risk_reward = abs(self.target - self.entry) / abs(self.entry - self.stop)

    @property
    def summary(self) -> str:
        return (
            f"{self.ticker:<10} | {self.pattern:<35} | {self.direction.upper():<5} | "
            f"Entry {self.entry:.4f}  Stop {self.stop:.4f}  Target {self.target:.4f} | "
            f"R:R {self.risk_reward:.1f} | Conf {self.confidence:.0f}/100"
        )


class PatternDetector:
    """
    Abstract base class for pattern detectors.

    Subclasses must implement:
        name  (class attribute)
        detect(df) -> list[Signal]
    """
    name: str = "base"

    def detect(self, ticker: str, df: pd.DataFrame, timeframe: str = "daily") -> list[Signal]:
        raise NotImplementedError

    # ── Helpers shared by all detectors ──────────────────────────────────────

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Return ATR series (uses pre-computed column if available)."""
        if "atr" in df.columns:
            return df["atr"]
        prev_close = df["Close"].shift(1)
        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"]  - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _pivot_lows(series: pd.Series, window: int = 5) -> pd.Series:
        """Return a boolean series marking local minima."""
        rolled_min = series.rolling(window=2 * window + 1, center=True).min()
        return series == rolled_min

    @staticmethod
    def _pivot_highs(series: pd.Series, window: int = 5) -> pd.Series:
        """Return a boolean series marking local maxima."""
        rolled_max = series.rolling(window=2 * window + 1, center=True).max()
        return series == rolled_max
