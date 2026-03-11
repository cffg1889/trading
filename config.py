"""
Global configuration for the trading signal detector.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
CACHE_DIR  = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── Data settings ─────────────────────────────────────────────────────────────
TIMEFRAMES = {
    "daily":   {"period": "2y",   "interval": "1d"},
    "hourly":  {"period": "60d",  "interval": "1h"},
    "intraday":{"period": "7d",   "interval": "15m"},
}

DEFAULT_TIMEFRAME = "daily"

# Cache expiry in hours
CACHE_EXPIRY_HOURS = {
    "daily":    24,
    "hourly":   1,
    "intraday": 0.25,   # 15 minutes
}

# ── Pattern settings ──────────────────────────────────────────────────────────
MIN_PATTERN_BARS      = 10   # minimum bars needed before detecting
DOUBLE_BOTTOM_WINDOW  = 60   # bars to scan for double bottom
BREAKOUT_VOL_MULT     = 1.5  # volume must be 1.5x average
RSI_PERIOD            = 14
RSI_OVERSOLD          = 35
RSI_OVERBOUGHT        = 65
VWAP_STD_THRESHOLD    = 2.0  # VWAP deviation in std devs
BB_PERIOD             = 20
BB_STD               = 2.0
KELTNER_PERIOD        = 20
KELTNER_MULT          = 1.5

# ── Backtest settings ─────────────────────────────────────────────────────────
BACKTEST_PERIOD = "5y"
RISK_REWARD_MIN = 1.5         # minimum R:R to include signal
STOP_ATR_MULT   = 1.5         # stop = entry ± 1.5 × ATR
TARGET_ATR_MULT = 3.0         # target = entry ± 3.0 × ATR

# ── Options settings ──────────────────────────────────────────────────────────
DEFAULT_RISK_FREE_RATE = 0.05   # 5%
OPTIONS_MATURITIES     = [7, 14, 21, 30, 45]  # days to expiry candidates

# ── Output ────────────────────────────────────────────────────────────────────
TOP_N_SIGNALS = 20   # how many signals to display in the report
