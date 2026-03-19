"""
BX Intelligence — Entry point.

Usage:
  python main.py           # start dashboard + scheduler
  python main.py --setup   # one-time Telegram setup
  python main.py --brief   # send morning brief now (test)
  python main.py --chart   # send chart to Telegram now (test)
"""
import sys
import asyncio
import socket
import threading

def print_banner():
    ip = _get_ip()
    print(f"""
+----------------------------------------------+
|         BX INTELLIGENCE — Blackstone        |
+----------------------------------------------+
|  Dashboard:  http://{ip}:{8050:<5}           |
|  Ticker:     BX (NYSE)                       |
|  Scheduler:  ON (6:30AM / 4:30PM ET)         |
+----------------------------------------------+
  -> Open the dashboard URL on your iPhone
""")

def _get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost     "


if __name__ == "__main__":
    import config

    # ── --setup: one-time Telegram chat ID setup ──────────────────
    if "--setup" in sys.argv:
        from alerts.telegram import setup_chat_id
        asyncio.run(setup_chat_id())
        sys.exit(0)

    # ── --brief: send morning brief immediately ───────────────────
    if "--brief" in sys.argv:
        print("Sending morning brief to Telegram...")
        from alerts.telegram import send_morning_brief
        send_morning_brief()
        print("Done.")
        sys.exit(0)

    # ── --chart: send chart image immediately ─────────────────────
    if "--chart" in sys.argv:
        print("Sending chart to Telegram...")
        from alerts.telegram import _send_chart_image, _get_bot
        from data.price import get_price_data, get_key_levels
        df = get_price_data(period="1y")
        levels = get_key_levels(df)
        asyncio.run(_send_chart_image(df, levels))
        print("Done.")
        sys.exit(0)

    # ── Normal mode: start scheduler + agent + dashboard ─────────
    print_banner()

    from scheduler.jobs import start_scheduler
    from agent.bx_agent import start_command_polling
    from dashboard.app import run_dashboard

    start_scheduler()
    start_command_polling()   # Telegram /commands available immediately
    run_dashboard()           # blocks here (Dash runs in main thread)
