"""
Universe definitions for all instruments to scan.

Sources:
  - S&P 500 / Nasdaq 100 / DJIA : fetched from Wikipedia
  - STOXX 600 / FTSE 100        : static list (updated manually or via scraping)
  - FX pairs                    : hardcoded majors + crosses
  - Equity indices               : ETF proxies or index tickers
"""

from __future__ import annotations
import requests
import pandas as pd
from functools import lru_cache


# ── FX pairs (Yahoo Finance format) ──────────────────────────────────────────
FX_PAIRS: list[str] = [
    # Majors
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
    "AUDUSD=X", "USDCAD=X", "NZDUSD=X",
    # Crosses
    "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURAUD=X",
    "GBPJPY=X", "GBPCHF=X", "AUDJPY=X", "CADJPY=X",
    # EM
    "USDMXN=X", "USDBRL=X", "USDSGD=X", "USDKRW=X",
    "USDTRY=X", "USDZAR=X", "USDINR=X",
]

# ── Equity indices (ETF / direct tickers) ─────────────────────────────────────
EQUITY_INDICES: list[str] = [
    # US
    "^GSPC",   # S&P 500
    "^DJI",    # Dow Jones
    "^IXIC",   # Nasdaq Composite
    "^NDX",    # Nasdaq 100
    "^RUT",    # Russell 2000
    "^VIX",    # VIX
    # Europe
    "^STOXX50E",  # Euro Stoxx 50
    "^STOXX",     # STOXX 600
    "^FTSE",      # FTSE 100
    "^GDAXI",     # DAX
    "^FCHI",      # CAC 40
    "^IBEX",      # IBEX 35
    "^AEX",       # AEX
    # Asia
    "^N225",   # Nikkei 225
    "^HSI",    # Hang Seng
    "000300.SS",  # CSI 300
    "^AXJO",   # ASX 200
]

# ── Commodities ───────────────────────────────────────────────────────────────
COMMODITIES: list[str] = [
    "GC=F",   # Gold
    "SI=F",   # Silver
    "CL=F",   # Crude Oil WTI
    "BZ=F",   # Brent Crude
    "NG=F",   # Natural Gas
    "ZW=F",   # Wheat
    "ZC=F",   # Corn
    "HG=F",   # Copper
]

# ── DJIA 30 components ────────────────────────────────────────────────────────
DJIA_30: list[str] = [
    "AAPL", "AMGN", "AXP",  "BA",   "CAT",  "CRM",  "CSCO", "CVX",
    "DIS",  "GS",   "HD",   "HON",  "IBM",  "INTC", "JNJ",  "JPM",
    "KO",   "MCD",  "MMM",  "MRK",  "MSFT", "NKE",  "PG",   "TRV",
    "UNH",  "V",    "VZ",   "WBA",  "WMT",  "DOW",
]

# ── FTSE 100 components (static, last updated 2025) ───────────────────────────
FTSE_100: list[str] = [
    "AAL.L",  "ABF.L",  "ADM.L",  "AHT.L",  "ANTO.L", "AZN.L",
    "BA.L",   "BARC.L", "BATS.L", "BEZ.L",  "BKG.L",  "BP.L",
    "BRBY.L", "BT.L",   "CCH.L",  "CNA.L",  "CPG.L",  "CRDA.L",
    "DCC.L",  "DGE.L",  "DPLM.L", "EDV.L",  "ENT.L",  "EXPN.L",
    "EZJ.L",  "FERG.L", "FLTR.L", "FRES.L", "GLEN.L", "GSK.L",
    "HLN.L",  "HMSO.L", "HSBA.L", "IAG.L",  "ICG.L",  "IHG.L",
    "IMB.L",  "INF.L",  "ITRK.L", "JD.L",   "KGF.L",  "LAND.L",
    "LGEN.L", "LLOY.L", "LMP.L",  "LSEG.L", "MKS.L",  "MNDI.L",
    "MNG.L",  "MRO.L",  "NWG.L",  "NXT.L",  "OCDO.L", "PHNX.L",
    "PRU.L",  "PSH.L",  "PSN.L",  "PSON.L", "REL.L",  "RIO.L",
    "RKT.L",  "RMV.L",  "RR.L",   "RS1.L",  "RSA.L",  "SBRY.L",
    "SDR.L",  "SGE.L",  "SGRO.L", "SJP.L",  "SKG.L",  "SMDS.L",
    "SMIN.L", "SMT.L",  "SN.L",   "SPX.L",  "SSE.L",  "STAN.L",
    "SVT.L",  "TSCO.L", "TW.L",   "ULVR.L", "UTG.L",  "UU.L",
    "VOD.L",  "WEIR.L", "WPP.L",  "WTB.L",
]

# ── Euro STOXX 50 components ──────────────────────────────────────────────────
STOXX_50: list[str] = [
    "ABI.BR",  "AD.AS",   "ADS.DE",  "AI.PA",   "AIR.PA",
    "ALV.DE",  "AMS.AS",  "ASML.AS", "BAS.DE",  "BAYN.DE",
    "BMW.DE",  "BN.PA",   "BNP.PA",  "CRH.L",   "CS.PA",
    "DB1.DE",  "DPW.DE",  "DTE.DE",  "ENEL.MI", "ENI.MI",
    "EL.PA",   "FCA.MI",  "FP.PA",   "FLTR.L",  "IFX.DE",
    "INGA.AS", "ISP.MI",  "KER.PA",  "MC.PA",   "MUV2.DE",
    "OR.PA",   "ORA.PA",  "PHIA.AS", "PRX.AS",  "RMS.PA",
    "RWE.DE",  "SAN.MC",  "SAP.DE",  "SGO.PA",  "SIE.DE",
    "SU.PA",   "TTE.PA",  "UCG.MI",  "VIV.PA",  "VOW3.DE",
    "VWS.CO",  "WKL.AS",
]


@lru_cache(maxsize=None)
def get_sp500() -> list[str]:
    """Fetch current S&P 500 components from Wikipedia."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        )
        tickers = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        return tickers
    except Exception as e:
        print(f"[universe] Could not fetch S&P 500 from Wikipedia: {e}")
        return []


@lru_cache(maxsize=None)
def get_nasdaq100() -> list[str]:
    """Fetch current Nasdaq 100 components from Wikipedia."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/Nasdaq-100"
        )
        # Find the table with a 'Ticker' or 'Symbol' column
        for t in tables:
            cols_lower = [c.lower() for c in t.columns]
            if "ticker" in cols_lower:
                idx = cols_lower.index("ticker")
                return t.iloc[:, idx].dropna().tolist()
            if "symbol" in cols_lower:
                idx = cols_lower.index("symbol")
                return t.iloc[:, idx].dropna().tolist()
        return []
    except Exception as e:
        print(f"[universe] Could not fetch Nasdaq 100 from Wikipedia: {e}")
        return []


def get_universe(
    include_sp500:    bool = True,
    include_nasdaq:   bool = True,
    include_djia:     bool = True,
    include_ftse:     bool = True,
    include_stoxx:    bool = True,
    include_fx:       bool = True,
    include_indices:  bool = True,
    include_commodities: bool = False,
) -> dict[str, list[str]]:
    """
    Returns a dict of category -> list of tickers.
    Deduplicates across categories within each.
    """
    universe: dict[str, list[str]] = {}

    if include_sp500:
        sp500 = get_sp500()
        universe["SP500"] = sp500 if sp500 else []

    if include_nasdaq:
        ndx = get_nasdaq100()
        universe["Nasdaq100"] = ndx if ndx else []

    if include_djia:
        universe["DJIA"] = DJIA_30

    if include_ftse:
        universe["FTSE100"] = FTSE_100

    if include_stoxx:
        universe["STOXX50"] = STOXX_50

    if include_fx:
        universe["FX"] = FX_PAIRS

    if include_indices:
        universe["Indices"] = EQUITY_INDICES

    if include_commodities:
        universe["Commodities"] = COMMODITIES

    return universe


def get_flat_universe(**kwargs) -> list[str]:
    """Returns a deduplicated flat list of all tickers."""
    universe = get_universe(**kwargs)
    seen: set[str] = set()
    result: list[str] = []
    for tickers in universe.values():
        for t in tickers:
            if t not in seen:
                seen.add(t)
                result.append(t)
    return result


if __name__ == "__main__":
    u = get_universe()
    total = sum(len(v) for v in u.values())
    print(f"\nUniverse summary ({total} instruments):")
    for cat, tickers in u.items():
        print(f"  {cat:12s}: {len(tickers):4d} instruments")
