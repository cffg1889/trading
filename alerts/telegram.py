"""
Telegram bot: sends morning briefs, close summaries, and live alerts.
"""
import asyncio
import io
import requests
import plotly.io as pio
import plotly.graph_objects as go
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
import config
from data.price import get_price_data, get_key_levels, get_current_quote
from data.news import fetch_all_news
from data.fundamentals import get_fundamentals, get_analyst_ratings


def _get_bot() -> Bot:
    return Bot(token=config.TELEGRAM_BOT_TOKEN)


def _get_local_ip() -> str:
    """Get local IP for dashboard link."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


async def _send_message(text: str, parse_mode: str = "HTML"):
    bot = _get_bot()
    chat_id = config.TELEGRAM_CHAT_ID
    if not chat_id:
        print("[telegram] No TELEGRAM_CHAT_ID set. Run python main.py --setup first.")
        return
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode,
                                disable_web_page_preview=True)
    except TelegramError as e:
        print(f"[telegram] Send error: {e}")


async def _send_chart_image(df, levels):
    """Send technical chart as PNG image to Telegram."""
    from dashboard.app import build_chart
    bot = _get_bot()
    chat_id = config.TELEGRAM_CHAT_ID
    if not chat_id:
        return
    try:
        fig = build_chart(df, levels)
        fig.update_layout(width=800, height=600)
        img_bytes = pio.to_image(fig, format="png", scale=1.5)
        await bot.send_photo(chat_id=chat_id, photo=io.BytesIO(img_bytes),
                              caption="BX Technical Analysis")
    except Exception as e:
        print(f"[telegram] Chart image error: {e}")


def _sentiment_emoji(s: str) -> str:
    return {"bullish": "[+]", "bearish": "[-]", "neutral": "[~]"}.get(s, "[~]")


def send_morning_brief():
    """Send the 6:30 AM morning brief."""
    asyncio.run(_async_morning_brief())


async def _async_morning_brief():
    try:
        df     = get_price_data(period="1y")
        levels = get_key_levels(df)
        quote  = get_current_quote()
        news   = fetch_all_news(hours_back=16)  # overnight news
        fund   = get_fundamentals()
        ratings = get_analyst_ratings()

        rsi   = levels["rsi"]
        macd_bull = levels["macd"] > levels["macd_signal"]
        price = quote["price"]
        chg   = quote["change"]
        chg_p = quote["change_pct"]
        arrow = "▲" if chg >= 0 else "▼"
        chg_emoji = "[+]" if chg >= 0 else "[-]"

        # Signal
        score = 0
        if rsi < 30: score += 2
        elif rsi < 40: score += 1
        elif rsi > 70: score -= 2
        if macd_bull: score += 1
        else: score -= 1
        if price > df["ema50"].iloc[-1]: score += 1
        else: score -= 1
        signal = "BUY" if score >= 3 else "SELL" if score <= -2 else "HOLD"

        # Analyst consensus
        rec = fund.get("recommendation", "N/A")
        target = fund.get("analyst_target")
        target_str = f"${target:.2f}" if target else "N/A"
        upside = round((target - price) / price * 100, 1) if target else None
        upside_str = f" ({upside:+.1f}%)" if upside else ""

        # Top 5 news
        top_news = news[:5]
        news_lines = "\n".join([
            f"{_sentiment_emoji(n.sentiment)} <a href='{n.url}'>{n.title[:80]}</a> <i>({n.source})</i>"
            for n in top_news
        ]) if top_news else "No major news overnight."

        # Recent rating changes
        recent_ratings = ratings[:3]
        rating_lines = "\n".join([
            f"  • {r['firm']}: {r['from']} → <b>{r['to']}</b> ({r['date']})"
            for r in recent_ratings
        ]) if recent_ratings else "  No recent changes."

        ip = _get_local_ip()
        dashboard_url = f"http://{ip}:{config.DASH_PORT}"

        text = f"""<b>BX MORNING BRIEF</b> — {datetime.now().strftime('%a %d %b %Y')}

{chg_emoji} <b>${price:.2f}</b>  {arrow} {abs(chg):.2f} ({abs(chg_p):.2f}%)
52W Range: ${levels['52w_low']:.2f} – ${levels['52w_high']:.2f}

<b>SIGNAL: {signal}</b>

<b>Technicals</b>
  RSI: <b>{rsi:.0f}</b> {'— Overbought' if rsi > 70 else '— Oversold' if rsi < 30 else ''}
  MACD: {'Bullish crossover' if macd_bull else 'Bearish crossover'}
  vs EMA20: {'Above' if price > df['ema20'].iloc[-1] else 'Below'}
  vs SMA200: {'Above' if price > df['sma200'].iloc[-1] else 'Below'}
  ATR: ${levels['atr']:.2f} | BB%: {df['bb_pct'].iloc[-1]*100:.0f}%

<b>Key Levels</b>
  Support:    {' / '.join([f'${s:.0f}' for s in levels['supports'][:3]]) or 'N/A'}
  Resistance: {' / '.join([f'${r:.0f}' for r in levels['resistances'][:3]]) or 'N/A'}

<b>Analysts</b>  ({fund.get('num_analysts', '?')} covering)
  Consensus: <b>{rec}</b> | Target: <b>{target_str}</b>{upside_str}
  Short Interest: {fund.get('short_pct_float', 'N/A')}%

<b>Rating Changes</b>
{rating_lines}

<b>Overnight News</b>
{news_lines}

<a href="{dashboard_url}">View Full Dashboard</a>"""

        await _send_message(text)
        # Also send chart image
        await _send_chart_image(df, levels)

    except Exception as e:
        await _send_message(f"Morning brief error: {e}")


def send_close_summary():
    """Send the 4:30 PM close summary."""
    asyncio.run(_async_close_summary())


async def _async_close_summary():
    try:
        df     = get_price_data(period="6mo")
        levels = get_key_levels(df)
        quote  = get_current_quote()
        news   = fetch_all_news(hours_back=8)

        price = quote["price"]
        chg   = quote["change"]
        chg_p = quote["change_pct"]
        vol   = levels["volume_ratio"]
        arrow = "▲" if chg >= 0 else "▼"
        chg_emoji = "[+]" if chg >= 0 else "[-]"

        top_news = news[:4]
        news_lines = "\n".join([
            f"{_sentiment_emoji(n.sentiment)} <a href='{n.url}'>{n.title[:80]}</a>"
            for n in top_news
        ]) if top_news else "Quiet day on news."

        ip = _get_local_ip()
        dashboard_url = f"http://{ip}:{config.DASH_PORT}"

        text = f"""<b>BX CLOSE SUMMARY</b> — {datetime.now().strftime('%a %d %b')}

{chg_emoji} Closed at <b>${price:.2f}</b>  {arrow} {abs(chg):.2f} ({abs(chg_p):.2f}%)
Volume: <b>{vol:.1f}x</b> average {'— Unusual volume' if vol > 1.5 else ''}

RSI: {levels['rsi']:.0f} | MACD: {'Bullish' if levels['macd'] > levels['macd_signal'] else 'Bearish'}

<b>Today's Key News</b>
{news_lines}

<a href="{dashboard_url}">Full Analysis</a>"""

        await _send_message(text)
    except Exception as e:
        await _send_message(f"Close summary error: {e}")


def send_price_alert(price: float, change_pct: float, direction: str):
    """Send an instant price movement alert."""
    asyncio.run(_async_price_alert(price, change_pct, direction))


async def _async_price_alert(price: float, change_pct: float, direction: str):
    arrow = "▲" if direction == "up" else "▼"
    ip = _get_local_ip()
    text = f"""<b>BX PRICE ALERT</b>

${price:.2f}  {arrow} {abs(change_pct):.2f}% in last 15 min

<a href="http://{ip}:{config.DASH_PORT}">View Dashboard</a>"""
    await _send_message(text)


def send_news_alert(title: str, source: str, url: str, sentiment: str, impact: int = 3):
    """Send a breaking news alert."""
    asyncio.run(_async_news_alert(title, source, url, sentiment, impact))


async def _async_news_alert(title, source, url, sentiment, impact=3):
    emoji  = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(sentiment, "⚪")
    label  = {"bullish": "BULLISH", "bearish": "BEARISH", "neutral": "NEWS"}.get(sentiment, "NEWS")
    stars  = "★" * impact + "☆" * (5 - impact)
    ip = _get_local_ip()
    text = f"""{emoji} <b>BX {label}</b>  {stars}

<a href="{url}">{title}</a>
<i>{source}</i>

<a href="http://{ip}:{config.DASH_PORT}">Dashboard</a>"""
    await _send_message(text)


def send_rsi_alert(rsi: float, state: str, price: float):
    """Send RSI extreme alert (oversold / overbought)."""
    asyncio.run(_async_rsi_alert(rsi, state, price))


async def _async_rsi_alert(rsi: float, state: str, price: float):
    emoji = "🟢" if state == "oversold" else "🔴"
    label = "OVERSOLD" if state == "oversold" else "OVERBOUGHT"
    note  = "Potential buying opportunity" if state == "oversold" else "Potential selling pressure"
    ip = _get_local_ip()
    text = f"""{emoji} <b>BX RSI {label}</b>

RSI: <b>{rsi:.1f}</b>  (threshold: {'&lt;' if state == 'oversold' else '&gt;'}{config.RSI_OVERSOLD if state == 'oversold' else config.RSI_OVERBOUGHT})
Price: <b>${price:.2f}</b>
{note}

<a href="http://{ip}:{config.DASH_PORT}">View Dashboard</a>"""
    await _send_message(text)


async def setup_chat_id():
    """One-time setup: get the chat ID from the first message sent to the bot."""
    print(f"\nOpen Telegram, find your bot, and send it any message (e.g. 'hello')")
    print("   Waiting for message...\n")
    bot = _get_bot()
    for _ in range(60):  # wait up to 60 seconds
        await asyncio.sleep(1)
        try:
            updates = await bot.get_updates(timeout=1)
            if updates:
                chat_id = str(updates[-1].message.chat_id)
                print(f"Chat ID found: {chat_id}")
                # Save to .env
                _update_env("TELEGRAM_CHAT_ID", chat_id)
                return chat_id
        except Exception:
            pass
    print("No message received. Try again.")
    return None


def _update_env(key: str, value: str):
    """Update a key in .env file."""
    env_path = ".env"
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
        new_lines = []
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key}={value}\n")
        with open(env_path, "w") as f:
            f.writelines(new_lines)
        print(f"{key} saved to .env")
    except Exception as e:
        print(f"Could not update .env: {e}. Set {key}={value} manually.")
