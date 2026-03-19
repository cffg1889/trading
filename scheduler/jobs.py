"""
APScheduler jobs: morning brief, close summary, intraday checks.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import config

ET = pytz.timezone("America/New_York")
_scheduler = None
_last_price = None
_alerted_news_urls: set = set()   # dedup — never alert same article twice
_alerted_rsi_state: str = ""      # "oversold" / "overbought" / "" — avoid repeat fires


def check_intraday_alerts():
    """Check for price moves, RSI extremes, and breaking news every 15 min."""
    global _last_price, _alerted_news_urls, _alerted_rsi_state
    try:
        from data.price import get_current_quote, get_price_data, get_key_levels
        from data.news import fetch_all_news
        from alerts.telegram import send_price_alert, send_news_alert, send_rsi_alert

        quote  = get_current_quote()
        price  = quote["price"]

        # ── 1. Price movement alert ────────────────────────────────────────────
        if _last_price is not None:
            change_pct = (price - _last_price) / _last_price * 100
            if abs(change_pct) >= config.PRICE_ALERT_PCT:
                direction = "up" if change_pct > 0 else "down"
                send_price_alert(price, change_pct, direction)

        _last_price = price

        # ── 2. RSI extreme alert (fires once per extreme, resets when neutral) ─
        try:
            df     = get_price_data(period="3mo")
            levels = get_key_levels(df)
            rsi    = levels["rsi"]
            if rsi < config.RSI_OVERSOLD and _alerted_rsi_state != "oversold":
                send_rsi_alert(rsi, "oversold", price)
                _alerted_rsi_state = "oversold"
            elif rsi > config.RSI_OVERBOUGHT and _alerted_rsi_state != "overbought":
                send_rsi_alert(rsi, "overbought", price)
                _alerted_rsi_state = "overbought"
            elif config.RSI_OVERSOLD + 5 <= rsi <= config.RSI_OVERBOUGHT - 5:
                _alerted_rsi_state = ""  # reset when back to neutral zone
        except Exception as e:
            print(f"[scheduler] RSI check error: {e}")

        # ── 3. Breaking news alert (dedup by URL) ─────────────────────────────
        news = fetch_all_news(hours_back=1)
        for item in news:
            if item.url in _alerted_news_urls:
                continue
            if item.impact >= 4 or item.sentiment in ("bullish", "bearish"):
                send_news_alert(item.title, item.source, item.url, item.sentiment, item.impact)
                _alerted_news_urls.add(item.url)
        # Keep set bounded (max 500 URLs)
        if len(_alerted_news_urls) > 500:
            _alerted_news_urls = set(list(_alerted_news_urls)[-200:])

    except Exception as e:
        print(f"[scheduler] Intraday check error: {e}")


def start_scheduler():
    """Start background scheduler."""
    global _scheduler
    from alerts.telegram import send_morning_brief, send_close_summary

    _scheduler = BackgroundScheduler(timezone=ET)

    # Morning brief: 6:30 AM ET on weekdays
    _scheduler.add_job(
        send_morning_brief,
        CronTrigger(hour=config.MORNING_BRIEF_HOUR, minute=config.MORNING_BRIEF_MINUTE,
                    day_of_week="mon-fri", timezone=ET),
        id="morning_brief",
    )

    # Close summary: 4:30 PM ET on weekdays
    _scheduler.add_job(
        send_close_summary,
        CronTrigger(hour=config.CLOSE_SUMMARY_HOUR, minute=config.CLOSE_SUMMARY_MINUTE,
                    day_of_week="mon-fri", timezone=ET),
        id="close_summary",
    )

    # Intraday check: every 15 min, 9:30 AM-4:30 PM ET weekdays
    _scheduler.add_job(
        check_intraday_alerts,
        CronTrigger(minute=f"*/{config.INTRADAY_CHECK_MINUTES}",
                    hour="9-16", day_of_week="mon-fri", timezone=ET),
        id="intraday_check",
    )

    _scheduler.start()
    print("Scheduler started (Morning 6:30 AM ET / Close 4:30 PM ET / Intraday every 15min)")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
