"""
SEC EDGAR scraper — completely free, no API key.
Fetches 8-K, 10-Q, 10-K filings for Blackstone (CIK 0001393818).
"""
import requests
from datetime import datetime, timedelta

EDGAR_BASE   = "https://data.sec.gov"
EFTS_BASE    = "https://efts.sec.gov"
BX_CIK       = "0001393818"
HEADERS      = {"User-Agent": "bx-intelligence contact@bx-intel.com"}

FORM_LABELS = {
    "8-K":  "Material Event",
    "10-Q": "Quarterly Report",
    "10-K": "Annual Report",
    "DEF 14A": "Proxy Statement",
    "SC 13G": "Ownership Filing",
    "4":    "Insider Transaction",
}


def get_recent_filings(days: int = 30) -> list[dict]:
    """Return recent BX SEC filings from the last N days."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url   = (f"{EFTS_BASE}/LATEST/search-index"
             f"?q=%22blackstone%22&dateRange=custom"
             f"&startdt={since}"
             f"&forms=8-K,10-Q,10-K,4,DEF+14A")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
    except Exception as e:
        print(f"[EDGAR] Search error: {e}")
        return []

    results = []
    for h in hits[:20]:
        src  = h.get("_source", {})
        form = src.get("form_type", "")
        results.append({
            "source":    "SEC EDGAR",
            "title":     f"{FORM_LABELS.get(form, form)}: {src.get('display_names', ['Blackstone'])[0]}",
            "url":       f"https://www.sec.gov/Archives/{src.get('file_date','')}/{src.get('accession_no','').replace('-','')}",
            "published": src.get("file_date", ""),
            "summary":   f"Form {form} filed on {src.get('file_date','')}",
            "sentiment": "neutral",
            "impact":    "high" if form in ("8-K", "10-Q", "10-K") else "medium",
        })
    return results


def get_insider_transactions(days: int = 90) -> list[dict]:
    """Fetch Form 4 filings (insider buy/sell) for BX."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url   = (f"{EDGAR_BASE}/submissions/CIK{BX_CIK}.json")
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        recent = data.get("filings", {}).get("recent", {})
        forms   = recent.get("form", [])
        dates   = recent.get("filingDate", [])
        acc_nos = recent.get("accessionNumber", [])
        descriptions = recent.get("primaryDocument", [])
    except Exception as e:
        print(f"[EDGAR] CIK fetch error: {e}")
        return []

    transactions = []
    for i, form in enumerate(forms):
        if form != "4":
            continue
        filing_date = dates[i] if i < len(dates) else ""
        if filing_date < since:
            continue
        acc = acc_nos[i].replace("-", "") if i < len(acc_nos) else ""
        transactions.append({
            "source":    "SEC Form 4",
            "title":     f"Insider Transaction – {filing_date}",
            "url":       f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={BX_CIK}&type=4",
            "published": filing_date,
            "summary":   f"Form 4 insider transaction filed {filing_date}",
            "sentiment": None,
            "impact":    "high",
        })
    return transactions[:10]
