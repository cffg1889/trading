"""
BX Intelligence Agent — Claude-powered autonomous monitor.

Two capabilities:
  1. Intelligent intraday analysis every 15 min (Claude decides if worth alerting)
  2. Telegram command handler: /status /snapshot /chart /news /brief /ask /help
"""
import io
import threading
import time
import requests
import anthropic
import config
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")
_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
_last_update_id = 0   # tracks Telegram polling offset


# ── Helpers ───────────────────────────────────────────────────────────────────

def _send_telegram(text: str, parse_mode: str = None):
    """Send a plain text message to Telegram."""
    token   = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload, timeout=10,
        )
    except Exception as e:
        print(f"[agent] Telegram send error: {e}")


def _send_photo(img_bytes: bytes, caption: str = ""):
    """Send a PNG image to Telegram."""
    token   = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": ("chart.png", io.BytesIO(img_bytes), "image/png")},
            timeout=30,
        )
    except Exception as e:
        print(f"[agent] Photo send error: {e}")


def _get_updates(offset: int = 0) -> list:
    token = config.TELEGRAM_BOT_TOKEN
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 10, "limit": 20},
            timeout=15,
        )
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception:
        pass
    return []


def _build_context_block() -> str:
    """Return a compact current-state block for Claude prompts."""
    from data.price import get_price_data, get_key_levels, get_current_quote
    df     = get_price_data(period="3mo")
    levels = get_key_levels(df)
    quote  = get_current_quote()
    price  = quote["price"]
    chg_p  = quote["change_pct"]
    rsi    = levels["rsi"]
    macd   = levels["macd"]
    sig    = levels["macd_signal"]
    ema20  = df["ema20"].iloc[-1]
    sma200 = df["sma200"].iloc[-1]
    bb_pct = df["bb_pct"].iloc[-1] * 100
    vol_r  = levels["volume_ratio"]
    atr    = levels["atr"]
    sup    = ", ".join([f"${s:.0f}" for s in levels["supports"][:3]])
    res    = ", ".join([f"${r:.0f}" for r in levels["resistances"][:3]])
    return (
        f"Price: ${price:.2f} ({chg_p:+.2f}% today)\n"
        f"RSI(14): {rsi:.1f}  |  BB%: {bb_pct:.0f}%  |  Volume: {vol_r:.1f}x avg\n"
        f"MACD: {'Bullish' if macd > sig else 'Bearish'} ({macd:.3f} vs {sig:.3f})\n"
        f"vs EMA20: {'above' if price > ema20 else 'below'} (${ema20:.2f})\n"
        f"vs SMA200: {'above' if price > sma200 else 'below'} (${sma200:.2f})\n"
        f"ATR: ${atr:.2f}  |  Supports: {sup}  |  Resistances: {res}"
    )


# ── 1. Intelligent intraday analysis ─────────────────────────────────────────

def agent_analyze_and_alert():
    """
    Called every 15 min during market hours.
    Gathers all signals → asks Claude if anything is worth alerting.
    Claude decides: SKIP or write a concise Telegram message.
    """
    try:
        from data.news import fetch_all_news
        context = _build_context_block()
        news    = fetch_all_news(hours_back=1)
        now_et  = datetime.now(ET).strftime("%H:%M ET")

        recent_news = "\n".join([
            f"- [{n.sentiment.upper()}] {n.title} ({n.source})"
            for n in news[:5]
        ]) if news else "No new news in the past hour."

        prompt = f"""You are monitoring Blackstone (BX) stock for a sophisticated private investor.
It is {now_et}. Analyze the current data and decide if anything is genuinely worth alerting about.

CURRENT DATA:
{context}

RECENT NEWS (last 1 hour):
{recent_news}

DECISION RULES:
- Only alert if something NOTABLE is happening: unusual price move, RSI extreme (<30 or >70),
  key level break (SMA200, major support/resistance), strong MACD crossover, high-impact news.
- Do NOT alert for routine, uneventful market action.
- If nothing notable: respond with exactly: SKIP
- If notable: write a concise Telegram message (3-4 lines max, plain text, no HTML tags).
  Start with an emoji + signal word, e.g.:
  🔴 BX ALERT — RSI Oversold
  🟢 BX SIGNAL — SMA200 Breakout
  ⚠️  BX WATCH — Approaching key resistance

Respond with ONLY "SKIP" or the message text. Nothing else."""

        response = _client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        if text.upper().startswith("SKIP"):
            print(f"[agent] {now_et} — Nothing notable, no alert sent")
            return

        print(f"[agent] {now_et} — Sending intelligent alert")
        _send_telegram(text)

    except Exception as e:
        print(f"[agent] Analyze error: {e}")


# ── 2. Telegram command handlers ──────────────────────────────────────────────

def _cmd_help():
    _send_telegram(
        "BX Intelligence Agent\n\n"
        "/status   — Price, RSI, signal right now\n"
        "/snapshot — Full Claude AI analysis\n"
        "/chart    — Technical chart image\n"
        "/news     — Top news last 24h\n"
        "/brief    — Full morning brief\n"
        "/ask [q]  — Ask anything about BX\n"
        "/help     — This menu"
    )


def _cmd_status():
    try:
        from data.price import get_price_data, get_key_levels, get_current_quote
        df     = get_price_data(period="3mo")
        levels = get_key_levels(df)
        quote  = get_current_quote()
        price  = quote["price"]
        chg    = quote["change"]
        chg_p  = quote["change_pct"]
        rsi    = levels["rsi"]
        macd   = levels["macd"]
        sig    = levels["macd_signal"]
        ema20  = df["ema20"].iloc[-1]
        sma200 = df["sma200"].iloc[-1]
        bb_pct = df["bb_pct"].iloc[-1] * 100
        arrow  = "▲" if chg >= 0 else "▼"

        score = 0
        if rsi < 30:       score += 2
        elif rsi < 40:     score += 1
        elif rsi > 70:     score -= 2
        if macd > sig:     score += 1
        else:              score -= 1
        if price > ema20:  score += 1
        else:              score -= 1
        label = "🟢 BUY" if score >= 3 else "🔴 SELL" if score <= -2 else "🟡 HOLD"

        _send_telegram(
            f"BX — {datetime.now(ET).strftime('%H:%M ET')}\n"
            f"${price:.2f}  {arrow} {abs(chg):.2f} ({abs(chg_p):.2f}%)\n\n"
            f"Signal: {label}\n"
            f"RSI: {rsi:.0f}  |  BB%: {bb_pct:.0f}%\n"
            f"MACD: {'Bullish' if macd > sig else 'Bearish'}\n"
            f"vs EMA20: {'Above' if price > ema20 else 'Below'}\n"
            f"vs SMA200: {'Above' if price > sma200 else 'Below'}"
        )
    except Exception as e:
        _send_telegram(f"Status error: {e}")


def _cmd_snapshot():
    _send_telegram("Generating AI snapshot...")
    try:
        from data.price import get_price_data, get_key_levels, get_current_quote
        from data.news import fetch_all_news

        df     = get_price_data(period="1y")
        levels = get_key_levels(df)
        quote  = get_current_quote()
        news   = fetch_all_news(hours_back=24)
        context = _build_context_block()

        news_ctx = "\n".join([
            f"- {n.title} ({n.source}, {n.sentiment})"
            for n in sorted(news, key=lambda x: x.impact, reverse=True)[:8]
        ]) if news else "No significant news."

        prompt = (
            "Provide a concise investment snapshot for Blackstone (BX) for a sophisticated investor.\n"
            "Write exactly 3 paragraphs, each max 60 words, labeled:\n"
            "TECHNICAL: current technical picture\n"
            "FUNDAMENTAL: key business/macro drivers\n"
            "CONCLUSION: actionable view with specific price levels to watch\n\n"
            f"CURRENT DATA:\n{context}\n\n"
            f"TOP NEWS (24h):\n{news_ctx}\n\n"
            "Plain text only, no markdown, no HTML."
        )

        with _client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=600,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            final = stream.get_final_message()

        text = next(b.text for b in final.content if b.type == "text")
        _send_telegram(
            f"BX AI SNAPSHOT — {datetime.now(ET).strftime('%a %d %b %H:%M ET')}\n\n{text}"
        )
    except Exception as e:
        _send_telegram(f"Snapshot error: {e}")


def _cmd_chart():
    _send_telegram("Generating chart...")
    try:
        import plotly.io as pio
        from data.price import get_price_data, get_key_levels
        from dashboard.app import build_chart

        df     = get_price_data(period="1y")
        levels = get_key_levels(df)
        fig    = build_chart(df, levels)
        fig.update_layout(width=900, height=700)
        img    = pio.to_image(fig, format="png", scale=1.5)
        _send_photo(img, caption=f"BX — {datetime.now(ET).strftime('%d %b %H:%M ET')}")
    except Exception as e:
        _send_telegram(f"Chart error: {e}")


def _cmd_news():
    try:
        from data.news import fetch_all_news
        news = fetch_all_news(hours_back=24)
        top  = sorted(news, key=lambda x: x.impact, reverse=True)[:6]
        if not top:
            _send_telegram("No significant news in the last 24h.")
            return
        lines = [f"BX TOP NEWS — {datetime.now(ET).strftime('%d %b')}\n"]
        emojis = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}
        for n in top:
            e = emojis.get(n.sentiment, "⚪")
            stars = "★" * n.impact
            lines.append(f"{e} {stars} {n.title[:70]}\n   {n.source} · {n.time_ago}\n   {n.url}\n")
        _send_telegram("\n".join(lines))
    except Exception as e:
        _send_telegram(f"News error: {e}")


def _cmd_brief():
    _send_telegram("Generating brief...")
    try:
        from alerts.telegram import send_morning_brief
        send_morning_brief()
    except Exception as e:
        _send_telegram(f"Brief error: {e}")


def _cmd_ask(question: str):
    if not question.strip():
        _send_telegram("Usage: /ask [your question about BX]")
        return
    _send_telegram("Thinking...")
    try:
        context = _build_context_block()
        prompt = (
            f"You are a Blackstone (BX) expert. Answer this question concisely (max 150 words).\n\n"
            f"CURRENT DATA:\n{context}\n\n"
            f"Question: {question}"
        )
        response = _client.messages.create(
            model="claude-opus-4-6",
            max_tokens=400,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        _send_telegram(text)
    except Exception as e:
        _send_telegram(f"Error: {e}")


def handle_command(text: str):
    """Route a Telegram command text to the right handler."""
    parts = text.strip().split(None, 1)
    cmd   = parts[0].lower().split("@")[0]  # strip @botname suffix
    args  = parts[1] if len(parts) > 1 else ""

    dispatch = {
        "/help":     _cmd_help,
        "/status":   _cmd_status,
        "/snapshot": _cmd_snapshot,
        "/chart":    _cmd_chart,
        "/news":     _cmd_news,
        "/brief":    _cmd_brief,
        "/start":    lambda: _send_telegram(
            "BX Intelligence Agent online.\nType /help to see available commands."
        ),
    }

    if cmd == "/ask":
        threading.Thread(target=_cmd_ask, args=(args,), daemon=True).start()
    elif cmd in dispatch:
        threading.Thread(target=dispatch[cmd], daemon=True).start()
    else:
        _send_telegram(f"Unknown command: {cmd}\nType /help for the menu.")


# ── 3. Command polling loop ───────────────────────────────────────────────────

def _poll_loop():
    """Background thread: poll Telegram every 3 s for new commands."""
    global _last_update_id
    print("[agent] Telegram command polling started — send /help to your bot")
    while True:
        try:
            updates = _get_updates(offset=_last_update_id + 1)
            for update in updates:
                _last_update_id = update["update_id"]
                msg = update.get("message") or update.get("edited_message")
                if not msg:
                    continue
                text = msg.get("text", "")
                if text.startswith("/"):
                    print(f"[agent] Command: {text}")
                    handle_command(text)
        except Exception as e:
            print(f"[agent] Poll error: {e}")
        time.sleep(3)


def start_command_polling():
    """Start the Telegram command polling thread (call once at startup)."""
    t = threading.Thread(target=_poll_loop, daemon=True, name="bx-agent-poll")
    t.start()
    return t
