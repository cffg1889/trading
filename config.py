import os
from dotenv import load_dotenv

load_dotenv()

# ── Target stock ──────────────────────────────────────────────────────────────
TICKER = "BX"
COMPANY = "Blackstone Inc"
EXCHANGE = "NYSE"

# ── Peers for relative comparison ────────────────────────────────────────────
PEERS = ["APO", "KKR", "CG", "ARES"]

# ── Blackstone LinkedIn profiles to monitor ───────────────────────────────────
LINKEDIN_PROFILES = [
    "https://www.linkedin.com/in/stephen-schwarzman/",
    "https://www.linkedin.com/in/jon-gray-blackstone/",
]

# ── Credentials ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID")

WSJ_EMAIL         = os.getenv("WSJ_EMAIL")
WSJ_PASSWORD      = os.getenv("WSJ_PASSWORD")
CNBC_EMAIL        = os.getenv("CNBC_EMAIL")
CNBC_PASSWORD     = os.getenv("CNBC_PASSWORD")
LINKEDIN_EMAIL    = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# ── Dashboard ─────────────────────────────────────────────────────────────────
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8050")
PORT          = int(os.getenv("PORT", 8050))

# ── Technical defaults ────────────────────────────────────────────────────────
CHART_PERIODS = {
    "1W":  ("7d",  "15m"),
    "1M":  ("1mo", "1h"),
    "3M":  ("3mo", "1d"),
    "1Y":  ("1y",  "1d"),
    "3Y":  ("3y",  "1wk"),
}
DEFAULT_PERIOD = "1Y"

# ── Alert thresholds ──────────────────────────────────────────────────────────
PRICE_ALERT_PCT   = 3.0    # alert if price moves ±3% intraday
RSI_OVERSOLD      = 30
RSI_OVERBOUGHT    = 70

# ── Conviction score weights ──────────────────────────────────────────────────
WEIGHTS = {
    "technical":   0.30,
    "fundamental": 0.25,
    "news":        0.20,
    "analyst":     0.15,
    "social":      0.10,
}

# ── Model ─────────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"
