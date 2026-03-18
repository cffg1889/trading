import os
from dotenv import load_dotenv
load_dotenv()

TICKER = "BX"
COMPANY_NAME = "Blackstone Inc"

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Credentials
WSJ_EMAIL = os.getenv("WSJ_EMAIL")
WSJ_PASSWORD = os.getenv("WSJ_PASSWORD")
CNBC_EMAIL = os.getenv("CNBC_EMAIL")
CNBC_PASSWORD = os.getenv("CNBC_PASSWORD")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# Dashboard
DASH_PORT = 8050
DASH_HOST = "0.0.0.0"  # accessible on local network for iPhone

# Chart settings
CHART_LOOKBACK_DAYS = 365  # 1 year default
MA_SHORT = 20
MA_MID = 50
MA_LONG = 200

# Alert thresholds
PRICE_ALERT_PCT = 3.0   # alert if price moves ±3%
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Scheduling (ET times)
MORNING_BRIEF_HOUR = 6
MORNING_BRIEF_MINUTE = 30
CLOSE_SUMMARY_HOUR = 16
CLOSE_SUMMARY_MINUTE = 30
INTRADAY_CHECK_MINUTES = 15
