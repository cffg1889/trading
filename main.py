"""
BX Intelligence — entry point.

Usage:
  python main.py           # Start dashboard + scheduler
  python main.py --setup   # First-time Telegram setup
  python main.py --run     # Run analysis now (no server)
"""
import sys
import threading
from data.store import init_db
from config import PORT

def main():
    args = sys.argv[1:]

    # ── Init DB ───────────────────────────────────────────────────────────────
    init_db()

    # ── Telegram setup mode ───────────────────────────────────────────────────
    if "--setup" in args:
        from alerts.telegram import setup_and_get_chat_id
        chat_id = setup_and_get_chat_id()
        if chat_id:
            print(f"\n✅ Setup complete. Chat ID saved: {chat_id}")
            print("Run `python main.py` to start the full system.")
        else:
            print("\n❌ Setup failed. Check your bot token.")
        return

    # ── One-shot analysis mode ────────────────────────────────────────────────
    if "--run" in args:
        print("Running full analysis...")
        from agents import orchestrator
        summary = orchestrator.run()
        print(f"\nConviction: {summary['conviction']} ({summary['conviction_score']:+.2f})")
        print(f"\n{summary['recommendation']}")
        return

    # ── Full mode: scheduler + dashboard ─────────────────────────────────────
    print("╔══════════════════════════════════════╗")
    print("║       BX Intelligence System         ║")
    print("╚══════════════════════════════════════╝")

    # Start scheduler in background thread
    from scheduler.jobs import create_scheduler, job_full_analysis
    scheduler = create_scheduler()
    scheduler.start()
    print(f"[Scheduler] Started. Jobs: {len(scheduler.get_jobs())}")

    # Run initial analysis in background so dashboard shows data immediately
    def initial_run():
        print("[Startup] Running initial analysis…")
        job_full_analysis("startup")
    threading.Thread(target=initial_run, daemon=True).start()

    # Start Dash server (blocking)
    from dashboard.app import app
    print(f"[Dashboard] Starting on port {PORT}…")
    print(f"[Dashboard] Open: http://localhost:{PORT}")
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
