"""
Fundamental data for Blackstone: earnings, analyst ratings, short interest, peers.
Uses yfinance (free) as primary source.
"""
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import config


PEER_TICKERS = ["APO", "KKR", "CG", "ARES", "BX"]
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_fundamentals() -> dict:
    """Fetch key fundamental metrics for BX."""
    ticker = yf.Ticker(config.TICKER)
    info = ticker.info

    return {
        "market_cap":      _fmt_billions(info.get("marketCap")),
        "pe_ratio":        info.get("trailingPE"),
        "forward_pe":      info.get("forwardPE"),
        "price_to_book":   info.get("priceToBook"),
        "dividend_yield":  round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
        "eps_ttm":         info.get("trailingEps"),
        "eps_next_year":   info.get("forwardEps"),
        "revenue_ttm":     _fmt_billions(info.get("totalRevenue")),
        "profit_margin":   round(info.get("profitMargins", 0) * 100, 2) if info.get("profitMargins") else None,
        "roe":             round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else None,
        "debt_to_equity":  info.get("debtToEquity"),
        "beta":            info.get("beta"),
        "shares_short":    info.get("sharesShort"),
        "short_ratio":     info.get("shortRatio"),
        "short_pct_float": round(info.get("shortPercentOfFloat", 0) * 100, 2) if info.get("shortPercentOfFloat") else None,
        "52w_high":        info.get("fiftyTwoWeekHigh"),
        "52w_low":         info.get("fiftyTwoWeekLow"),
        "analyst_target":  info.get("targetMeanPrice"),
        "analyst_low":     info.get("targetLowPrice"),
        "analyst_high":    info.get("targetHighPrice"),
        "recommendation":  info.get("recommendationKey", "").upper(),
        "num_analysts":    info.get("numberOfAnalystOpinions"),
        "next_earnings":   info.get("earningsTimestamp"),
    }


def get_analyst_ratings() -> list:
    """Get analyst upgrades/downgrades from yfinance."""
    ticker = yf.Ticker(config.TICKER)
    try:
        upgrades = ticker.upgrades_downgrades
        if upgrades is not None and not upgrades.empty:
            recent = upgrades.head(10).reset_index()
            return [
                {
                    "date":     str(row.get("GradeDate", ""))[:10],
                    "firm":     row.get("Firm", ""),
                    "from":     row.get("FromGrade", ""),
                    "to":       row.get("ToGrade", ""),
                    "action":   row.get("Action", ""),
                }
                for _, row in recent.iterrows()
            ]
    except Exception as e:
        print(f"[fundamentals] Analyst ratings error: {e}")
    return []


def get_earnings_history() -> list:
    """Get recent earnings results."""
    ticker = yf.Ticker(config.TICKER)
    try:
        earnings = ticker.earnings_dates
        if earnings is not None and not earnings.empty:
            recent = earnings.head(8).reset_index()
            return [
                {
                    "date":      str(row.get("Earnings Date", ""))[:10],
                    "eps_est":   row.get("EPS Estimate"),
                    "eps_actual": row.get("Reported EPS"),
                    "surprise":  row.get("Surprise(%)"),
                }
                for _, row in recent.iterrows()
            ]
    except Exception as e:
        print(f"[fundamentals] Earnings error: {e}")
    return []


def get_peer_comparison() -> list:
    """Compare BX to alt-asset manager peers."""
    results = []
    for tkr in PEER_TICKERS:
        try:
            t = yf.Ticker(tkr)
            info = t.info
            hist = t.history(period="1y")
            ytd_return = None
            if not hist.empty:
                ytd_return = round((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 1)
            results.append({
                "ticker":    tkr,
                "name":      info.get("shortName", tkr),
                "price":     info.get("regularMarketPrice"),
                "market_cap": _fmt_billions(info.get("marketCap")),
                "pe":        info.get("trailingPE"),
                "div_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
                "ytd_return": ytd_return,
                "rec":       info.get("recommendationKey", "").upper(),
            })
        except Exception as e:
            print(f"[fundamentals] Peer {tkr} error: {e}")
    return results


def _fmt_billions(val) -> str:
    if val is None:
        return None
    if val >= 1e12:
        return f"${val/1e12:.2f}T"
    if val >= 1e9:
        return f"${val/1e9:.2f}B"
    if val >= 1e6:
        return f"${val/1e6:.2f}M"
    return f"${val:,.0f}"
