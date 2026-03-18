"""
Price and market data for BX via yfinance.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from config import TICKER, PEERS


def get_ohlcv(period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data and attach technical indicators."""
    df = yf.download(TICKER, period=period, interval=interval,
                     auto_adjust=True, progress=False)
    if df.empty:
        return df

    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower()
                  for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].copy()
    df.dropna(inplace=True)

    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    vol   = df["volume"]

    # Moving averages
    df["ma20"]  = close.rolling(20).mean()
    df["ma50"]  = close.rolling(50).mean()
    df["ma200"] = close.rolling(200).mean()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"]   = bb.bollinger_mavg()

    # RSI
    df["rsi"] = ta.momentum.RSIIndicator(close, window=14).rsi()

    # MACD
    macd = ta.trend.MACD(close)
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()

    # ATR
    df["atr"] = ta.volatility.AverageTrueRange(high, low, close).average_true_range()

    # Volume ratio vs 20d avg
    df["vol_ratio"] = vol / vol.rolling(20).mean()

    # VWAP (rolling 20-day for daily charts)
    typical = (high + low + close) / 3
    df["vwap"] = (typical * vol).rolling(20).sum() / vol.rolling(20).sum()

    return df


def get_current_price() -> dict:
    """Return latest quote info for BX."""
    ticker = yf.Ticker(TICKER)
    info   = ticker.fast_info
    hist   = ticker.history(period="2d", interval="1d")

    prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
    last_price = float(hist["Close"].iloc[-1]) if len(hist) >= 1 else None

    change     = last_price - prev_close if (last_price and prev_close) else 0
    change_pct = (change / prev_close * 100) if prev_close else 0

    return {
        "price":        last_price,
        "prev_close":   prev_close,
        "change":       round(change, 2),
        "change_pct":   round(change_pct, 2),
        "volume":       getattr(info, "last_volume", None),
        "market_cap":   getattr(info, "market_cap", None),
        "week52_high":  getattr(info, "fifty_two_week_high", None),
        "week52_low":   getattr(info, "fifty_two_week_low", None),
    }


def get_fundamentals() -> dict:
    """Return key fundamental data for BX."""
    ticker = yf.Ticker(TICKER)
    info   = ticker.info

    return {
        "pe_ratio":        info.get("trailingPE"),
        "forward_pe":      info.get("forwardPE"),
        "price_to_book":   info.get("priceToBook"),
        "dividend_yield":  info.get("dividendYield"),
        "dividend_rate":   info.get("dividendRate"),
        "revenue":         info.get("totalRevenue"),
        "net_income":      info.get("netIncomeToCommon"),
        "profit_margin":   info.get("profitMargins"),
        "roe":             info.get("returnOnEquity"),
        "beta":            info.get("beta"),
        "shares_short":    info.get("sharesShort"),
        "short_ratio":     info.get("shortRatio"),
        "short_pct_float": info.get("shortPercentOfFloat"),
        "analyst_count":   info.get("numberOfAnalystOpinions"),
        "target_mean":     info.get("targetMeanPrice"),
        "target_high":     info.get("targetHighPrice"),
        "target_low":      info.get("targetLowPrice"),
        "recommendation":  info.get("recommendationKey"),
        "description":     info.get("longBusinessSummary"),
        "employees":       info.get("fullTimeEmployees"),
        "sector":          info.get("sector"),
        "industry":        info.get("industry"),
    }


def get_peers_performance() -> pd.DataFrame:
    """Return 1-month performance comparison vs peers."""
    tickers = [TICKER] + PEERS
    rows = []
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="1mo", interval="1d")
            if len(hist) >= 2:
                ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
                rows.append({"ticker": t, "1mo_return": round(float(ret), 2)})
        except Exception:
            pass
    return pd.DataFrame(rows)


def get_options_data() -> dict:
    """Return basic options chain summary for BX."""
    ticker = yf.Ticker(TICKER)
    try:
        exp_dates = ticker.options
        if not exp_dates:
            return {}
        # Nearest expiry
        chain = ticker.option_chain(exp_dates[0])
        calls = chain.calls
        puts  = chain.puts

        total_call_oi = int(calls["openInterest"].sum())
        total_put_oi  = int(puts["openInterest"].sum())
        pc_ratio      = round(total_put_oi / total_call_oi, 2) if total_call_oi else None

        return {
            "expiry":         exp_dates[0],
            "call_oi":        total_call_oi,
            "put_oi":         total_put_oi,
            "put_call_ratio": pc_ratio,
            "next_expiries":  list(exp_dates[:4]),
        }
    except Exception:
        return {}
