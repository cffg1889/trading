"""
APScheduler jobs — all timed intelligence tasks.

Schedule (all times ET):
  06:00 — Pre-market full analysis + Telegram brief
  09:25 — Opening setup (quick technical refresh)
  Every 15 min (09:30–16:00) — Technical + news refresh + price alerts
  16:30 — Post-market full analysis + Telegram brief
  Every 30 min (09:00–16:30) — Analyst rating check
"""
import os
from datetime import datetime, time as dtime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import PRICE_ALERT_PCT
from data.price import get_current_price
from data import store
from alerts import telegram

# Track last conviction to detect shifts
_last_conviction: str | None = None
_last_price:      float | None = None


def job_full_analysis(label: str = "scheduled"):
    """Run all agents via orchestrator and send Telegram brief."""
    global _last_conviction
    print(f"[Scheduler] Full analysis ({label}) starting…")
    try:
        from agents import orchestrator
        summary = orchestrator.run()

        new_conviction = summary.get("conviction")
        if (_last_conviction and
                new_conviction and
                new_conviction != _last_conviction):
            telegram.send_conviction_change(
                old=_last_conviction,
                new=new_conviction,
                score=summary.get("conviction_score", 0),
                reason=summary.get("recommendation", ""),
            )

        _last_conviction = new_conviction
        telegram.send_daily_brief(summary)
        print(f"[Scheduler] Full analysis done. Conviction: {new_conviction}")
    except Exception as e:
        print(f"[Scheduler] Full analysis error: {e}")


def job_price_check():
    """Check for ±PRICE_ALERT_PCT% intraday move and alert if triggered."""
    global _last_price
    try:
        quote = get_current_price()
        price = quote.get("price")
        pct   = quote.get("change_pct", 0)

        if price and abs(pct) >= PRICE_ALERT_PCT:
            # Only fire once per direction per day
            summary = store.get_latest_summary()
            tech    = summary.get("technical", {}) if summary else {}
            context = tech.get("narrative", "")[:150]
            telegram.send_price_alert(price, pct, context)

        _last_price = price
    except Exception as e:
        print(f"[Scheduler] Price check error: {e}")


def job_news_refresh():
    """Quick news-only refresh every 15 min during market hours."""
    try:
        from agents import news
        result = news.run()
        # Alert on high-impact news
        for item in result.get("top_items", []):
            if item.get("impact") == "high" and item.get("sentiment") == "bearish":
                store.log_alert("news_high_impact", item.get("title",""))
    except Exception as e:
        print(f"[Scheduler] News refresh error: {e}")


def job_analyst_check():
    """Check for new analyst ratings every 30 min."""
    try:
        from agents import analyst
        result = analyst.run()
        ratings = result.get("recent_ratings", [])
        for r in ratings:
            action = (r.get("action") or "").lower()
            if "upgrade" in action or "downgrade" in action:
                # Only alert if filed today
                today = datetime.now().strftime("%Y-%m-%d")
                if r.get("created_at", "").startswith(today):
                    telegram.send_analyst_alert(
                        firm=r.get("firm",""),
                        action=r.get("action",""),
                        new_rating=r.get("new_rating",""),
                        new_target=r.get("new_target",""),
                        old_target=r.get("old_target",""),
                    )
    except Exception as e:
        print(f"[Scheduler] Analyst check error: {e}")


def job_edgar_check():
    """Check for new SEC filings once per hour."""
    try:
        from data.scrapers.edgar import get_recent_filings
        filings = get_recent_filings(days=1)
        for f in filings:
            if f.get("impact") == "high":
                today = datetime.now().strftime("%Y-%m-%d")
                if f.get("published", "") >= today:
                    telegram.send_filing_alert(
                        filing_type=f.get("title",""),
                        description=f.get("summary",""),
                        url=f.get("url",""),
                    )
    except Exception as e:
        print(f"[Scheduler] EDGAR check error: {e}")


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="America/New_York")

    # Pre-market full analysis — 6:00 AM ET
    scheduler.add_job(
        lambda: job_full_analysis("pre-market"),
        CronTrigger(hour=6, minute=0, timezone="America/New_York"),
        id="pre_market",
        replace_existing=True,
    )

    # Opening setup — 9:25 AM ET
    scheduler.add_job(
        lambda: job_full_analysis("opening"),
        CronTrigger(hour=9, minute=25, timezone="America/New_York"),
        id="opening",
        replace_existing=True,
    )

    # Post-market full analysis — 4:30 PM ET
    scheduler.add_job(
        lambda: job_full_analysis("close"),
        CronTrigger(hour=16, minute=30, timezone="America/New_York"),
        id="close",
        replace_existing=True,
    )

    # Price alert — every 5 min during market hours (9:30–16:00)
    scheduler.add_job(
        job_price_check,
        CronTrigger(minute="*/5", hour="9-16",
                    day_of_week="mon-fri",
                    timezone="America/New_York"),
        id="price_check",
        replace_existing=True,
    )

    # News refresh — every 15 min during market hours
    scheduler.add_job(
        job_news_refresh,
        CronTrigger(minute="*/15", hour="9-17",
                    day_of_week="mon-fri",
                    timezone="America/New_York"),
        id="news_refresh",
        replace_existing=True,
    )

    # Analyst check — every 30 min
    scheduler.add_job(
        job_analyst_check,
        CronTrigger(minute="*/30", hour="9-17",
                    day_of_week="mon-fri",
                    timezone="America/New_York"),
        id="analyst_check",
        replace_existing=True,
    )

    # EDGAR filing check — every hour
    scheduler.add_job(
        job_edgar_check,
        CronTrigger(minute=0, hour="6-20",
                    day_of_week="mon-fri",
                    timezone="America/New_York"),
        id="edgar_check",
        replace_existing=True,
    )

    return scheduler
