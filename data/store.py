"""
SQLite persistence layer.
All agents write here; dashboard reads from here.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bx.db"


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS news (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT,
            title       TEXT,
            url         TEXT UNIQUE,
            published   TEXT,
            summary     TEXT,
            sentiment   TEXT,
            impact      TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS technical_signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            period      TEXT,
            trend       TEXT,
            signal      TEXT,
            confidence  INTEGER,
            support     TEXT,
            resistance  TEXT,
            patterns    TEXT,
            narrative   TEXT,
            raw_data    TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS fundamentals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            data        TEXT,
            narrative   TEXT,
            signal      TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS analyst_ratings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            firm        TEXT,
            analyst     TEXT,
            action      TEXT,
            old_rating  TEXT,
            new_rating  TEXT,
            old_target  REAL,
            new_target  REAL,
            date        TEXT,
            narrative   TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS social_posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            platform    TEXT,
            author      TEXT,
            content     TEXT,
            url         TEXT,
            posted_at   TEXT,
            sentiment   TEXT,
            relevance   TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_summary (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT UNIQUE,
            conviction      TEXT,
            conviction_score REAL,
            recommendation  TEXT,
            key_events      TEXT,
            technical_view  TEXT,
            fundamental_view TEXT,
            news_view       TEXT,
            analyst_view    TEXT,
            social_view     TEXT,
            full_narrative  TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alerts_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type  TEXT,
            message     TEXT,
            sent        INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        """)


# ── News ──────────────────────────────────────────────────────────────────────

def save_news(items: list[dict]):
    with _conn() as con:
        for item in items:
            try:
                con.execute("""
                    INSERT OR IGNORE INTO news
                        (source, title, url, published, summary, sentiment, impact)
                    VALUES (?,?,?,?,?,?,?)
                """, (item.get("source"), item.get("title"), item.get("url"),
                      item.get("published"), item.get("summary"),
                      item.get("sentiment"), item.get("impact")))
            except Exception:
                pass


def get_recent_news(hours: int = 24) -> list[dict]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT * FROM news
            WHERE created_at >= datetime('now', ? || ' hours')
            ORDER BY created_at DESC LIMIT 50
        """, (f"-{hours}",)).fetchall()
    return [dict(r) for r in rows]


# ── Technical signals ─────────────────────────────────────────────────────────

def save_technical(data: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO technical_signals
                (period, trend, signal, confidence, support, resistance, patterns, narrative, raw_data)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (data.get("period"), data.get("trend"), data.get("signal"),
              data.get("confidence"), json.dumps(data.get("support", [])),
              json.dumps(data.get("resistance", [])),
              json.dumps(data.get("patterns", [])),
              data.get("narrative"), json.dumps(data.get("raw_data", {}))))


def get_latest_technical() -> dict | None:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM technical_signals ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("support", "resistance", "patterns", "raw_data"):
        try:
            d[k] = json.loads(d[k])
        except Exception:
            pass
    return d


# ── Fundamentals ──────────────────────────────────────────────────────────────

def save_fundamentals(data: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO fundamentals (data, narrative, signal)
            VALUES (?,?,?)
        """, (json.dumps(data.get("data", {})),
              data.get("narrative"), data.get("signal")))


def get_latest_fundamentals() -> dict | None:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM fundamentals ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["data"] = json.loads(d["data"])
    except Exception:
        pass
    return d


# ── Analyst ratings ───────────────────────────────────────────────────────────

def save_analyst_rating(rating: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO analyst_ratings
                (firm, analyst, action, old_rating, new_rating, old_target, new_target, date, narrative)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (rating.get("firm"), rating.get("analyst"), rating.get("action"),
              rating.get("old_rating"), rating.get("new_rating"),
              rating.get("old_target"), rating.get("new_target"),
              rating.get("date"), rating.get("narrative")))


def get_recent_analyst_ratings(days: int = 30) -> list[dict]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT * FROM analyst_ratings
            WHERE created_at >= datetime('now', ? || ' days')
            ORDER BY created_at DESC LIMIT 20
        """, (f"-{days}",)).fetchall()
    return [dict(r) for r in rows]


# ── Social posts ──────────────────────────────────────────────────────────────

def save_social_posts(posts: list[dict]):
    with _conn() as con:
        for p in posts:
            try:
                con.execute("""
                    INSERT OR IGNORE INTO social_posts
                        (platform, author, content, url, posted_at, sentiment, relevance)
                    VALUES (?,?,?,?,?,?,?)
                """, (p.get("platform"), p.get("author"), p.get("content"),
                      p.get("url"), p.get("posted_at"),
                      p.get("sentiment"), p.get("relevance")))
            except Exception:
                pass


def get_recent_social(days: int = 7) -> list[dict]:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT * FROM social_posts
            WHERE created_at >= datetime('now', ? || ' days')
            ORDER BY created_at DESC LIMIT 30
        """, (f"-{days}",)).fetchall()
    return [dict(r) for r in rows]


# ── Daily summary ─────────────────────────────────────────────────────────────

def save_daily_summary(data: dict):
    date = datetime.now().strftime("%Y-%m-%d")
    with _conn() as con:
        con.execute("""
            INSERT OR REPLACE INTO daily_summary
                (date, conviction, conviction_score, recommendation,
                 key_events, technical_view, fundamental_view,
                 news_view, analyst_view, social_view, full_narrative)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (date, data.get("conviction"), data.get("conviction_score"),
              data.get("recommendation"),
              json.dumps(data.get("key_events", [])),
              data.get("technical_view"), data.get("fundamental_view"),
              data.get("news_view"), data.get("analyst_view"),
              data.get("social_view"), data.get("full_narrative")))


def get_latest_summary() -> dict | None:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM daily_summary ORDER BY date DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["key_events"] = json.loads(d["key_events"])
    except Exception:
        pass
    return d


# ── Alerts log ────────────────────────────────────────────────────────────────

def log_alert(alert_type: str, message: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO alerts_log (alert_type, message) VALUES (?,?)",
            (alert_type, message)
        )
