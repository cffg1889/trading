"""
Finviz scraper for short interest and analyst consensus.
No API key needed — public data.
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def get_short_interest(ticker: str = "BX") -> dict:
    """Scrape short interest data from Finviz."""
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        data = {}
        rows = soup.select("table.snapshot-table2 tr")
        for row in rows:
            cells = row.find_all("td")
            for i in range(0, len(cells) - 1, 2):
                key   = cells[i].get_text(strip=True)
                value = cells[i + 1].get_text(strip=True)
                data[key] = value

        return {
            "short_float":   data.get("Short Float", "N/A"),
            "short_ratio":   data.get("Short Ratio", "N/A"),
            "short_shares":  data.get("Short", "N/A"),
            "inst_own":      data.get("Inst Own", "N/A"),
            "inst_trans":    data.get("Inst Trans", "N/A"),
            "analyst_recom": data.get("Recom", "N/A"),
            "target_price":  data.get("Target Price", "N/A"),
            "avg_volume":    data.get("Avg Volume", "N/A"),
            "rel_volume":    data.get("Rel Volume", "N/A"),
            "52w_high":      data.get("52W High", "N/A"),
            "52w_low":       data.get("52W Low", "N/A"),
            "rsi":           data.get("RSI (14)", "N/A"),
        }
    except Exception as e:
        print(f"[Finviz] Error: {e}")
        return {}
