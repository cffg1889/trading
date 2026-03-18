"""
Telegram alert system.
— First run: sends /start to the bot to capture your chat_id.
— Then sends daily briefs and live alerts with a deep link to the dashboard.
"""
import asyncio
import os
import requests
from dotenv import load_dotenv, set_key
from pathlib import Path

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DASHBOARD_URL

ENV_PATH = Path(__file__).parent.parent / ".env"


# ── Low-level send ────────────────────────────────────────────────────────────

def _send(text: str, chat_id: str = None, parse_mode: str = "HTML") -> bool:
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid:
        print("[Telegram] No chat_id — run setup first (python main.py --setup)")
        return False
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": cid, "text": text, "parse_mode": parse_mode,
            "disable_web_page_preview": False}
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram] Send error: {e}")
        return False


# ── Setup — capture chat_id ───────────────────────────────────────────────────

def setup_and_get_chat_id() -> str | None:
    """
    Polls for updates to capture the first message sent to the bot.
    Instructions: Open Telegram → find your bot → send /start
    """
    print("\n[Telegram Setup]")
    print(f"1. Open Telegram on your phone")
    print(f"2. Search for your bot")
    print(f"3. Send any message (e.g. /start)")
    print(f"Waiting for message... (30 seconds)\n")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    for _ in range(30):
        try:
            r    = requests.get(url, params={"timeout": 1}, timeout=5)
            data = r.json()
            updates = data.get("result", [])
            if updates:
                chat_id = str(updates[-1]["message"]["chat"]["id"])
                print(f"[Telegram] Got chat_id: {chat_id}")
                # Save to .env
                set_key(str(ENV_PATH), "TELEGRAM_CHAT_ID", chat_id)
                # Send confirmation
                _send(
                    "✅ <b>BX Intelligence connected!</b>\n\n"
                    "You will receive:\n"
                    "• 📊 Pre-market brief (6 AM ET)\n"
                    "• 🔔 Live alerts on major events\n"
                    "• 📈 Daily close summary (4:30 PM ET)\n\n"
                    f"<a href='{DASHBOARD_URL}'>Open Dashboard</a>",
                    chat_id=chat_id,
                )
                return chat_id
        except Exception:
            pass
        import time
        time.sleep(1)

    print("[Telegram] Timeout. Try again.")
    return None


# ── Alert types ───────────────────────────────────────────────────────────────

def send_daily_brief(summary: dict):
    """Pre-market or post-market daily summary."""
    quote = summary.get("quote", {})
    conv  = summary.get("conviction", "—")
    score = summary.get("conviction_score", 0)
    rec   = summary.get("recommendation", "")[:400]

    price  = quote.get("price", "—")
    change = quote.get("change_pct", 0)
    arrow  = "🟢" if change >= 0 else "🔴"

    top_events = summary.get("key_events", [])[:3]
    events_str = ""
    for e in top_events:
        sent = e.get("sentiment", e.get("type", ""))
        emoji = {"bullish":"🟢","bearish":"🔴","analyst":"📊","news":"📰"}.get(sent,"•")
        events_str += f"\n{emoji} {e.get('title','')[:80]}"

    text = (
        f"<b>📊 BX Intelligence — Daily Brief</b>\n\n"
        f"{arrow} <b>BX: ${price}</b>  ({change:+.2f}%)\n"
        f"Conviction: <b>{conv}</b>  (score: {score:+.2f})\n"
        f"\n<b>🎯 Recommendation:</b>\n{rec}\n"
        f"\n<b>📰 Key Events:</b>{events_str if events_str else chr(10)+'Nothing material.'}\n"
        f"\n<a href='{DASHBOARD_URL}'>📈 Open Full Dashboard</a>"
    )
    return _send(text)


def send_price_alert(price: float, change_pct: float, context: str = ""):
    """Fires when BX moves ±3% intraday."""
    arrow    = "🚀" if change_pct > 0 else "🔻"
    direction= "UP" if change_pct > 0 else "DOWN"
    text = (
        f"{arrow} <b>BX PRICE ALERT</b>\n\n"
        f"BX is <b>{direction} {abs(change_pct):.1f}%</b> today\n"
        f"Current price: <b>${price:.2f}</b>\n"
        + (f"\nContext: {context}" if context else "") +
        f"\n\n<a href='{DASHBOARD_URL}'>📈 View Technical Analysis</a>"
    )
    return _send(text)


def send_analyst_alert(firm: str, action: str, new_rating: str,
                       new_target: str, old_target: str = ""):
    """Fires immediately on analyst upgrade/downgrade."""
    action_lower = action.lower()
    emoji = "📈" if "upgrade" in action_lower else "📉"
    text = (
        f"{emoji} <b>BX ANALYST ALERT</b>\n\n"
        f"<b>{firm}</b> — {action}\n"
        f"New rating: <b>{new_rating}</b>\n"
        + (f"Price target: <b>{new_target}</b>"
           + (f" (was {old_target})" if old_target else "") if new_target else "") +
        f"\n\n<a href='{DASHBOARD_URL}'>📊 View Full Analysis</a>"
    )
    return _send(text)


def send_filing_alert(filing_type: str, description: str, url: str = ""):
    """Fires when BX files an 8-K or similar material event."""
    text = (
        f"📋 <b>BX SEC FILING</b>\n\n"
        f"Form: <b>{filing_type}</b>\n"
        f"{description[:200]}\n"
        + (f"\n<a href='{url}'>View Filing</a>" if url else "") +
        f"\n\n<a href='{DASHBOARD_URL}'>📊 Open Dashboard</a>"
    )
    return _send(text)


def send_conviction_change(old: str, new: str, score: float, reason: str = ""):
    """Fires when overall conviction shifts category."""
    old_emoji = {"STRONG BUY":"🟢","BUY":"🟢","HOLD":"🟡",
                 "SELL":"🔴","STRONG SELL":"🔴"}.get(old, "⚪")
    new_emoji = {"STRONG BUY":"🟢","BUY":"🟢","HOLD":"🟡",
                 "SELL":"🔴","STRONG SELL":"🔴"}.get(new, "⚪")
    text = (
        f"⚡ <b>BX CONVICTION CHANGE</b>\n\n"
        f"{old_emoji} {old}  →  {new_emoji} <b>{new}</b>\n"
        f"Score: {score:+.2f}\n"
        + (f"\n{reason[:200]}" if reason else "") +
        f"\n\n<a href='{DASHBOARD_URL}'>📈 View Full Analysis</a>"
    )
    return _send(text)
