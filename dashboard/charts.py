"""
Technical chart — 4-panel Plotly figure optimised for mobile.
"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import argrelextrema
import pandas as pd


COLORS = {
    "candle_up":   "#26a69a",
    "candle_down": "#ef5350",
    "ma20":        "#ff9800",
    "ma50":        "#2196f3",
    "ma200":       "#9c27b0",
    "bb":          "rgba(33,150,243,0.15)",
    "bb_line":     "rgba(33,150,243,0.6)",
    "volume_up":   "rgba(38,166,154,0.5)",
    "volume_down": "rgba(239,83,80,0.5)",
    "rsi_line":    "#ff9800",
    "macd_line":   "#2196f3",
    "signal_line": "#ff5722",
    "macd_hist_p": "rgba(38,166,154,0.7)",
    "macd_hist_n": "rgba(239,83,80,0.7)",
    "support":     "rgba(38,166,154,0.8)",
    "resistance":  "rgba(239,83,80,0.8)",
    "background":  "#1a1a2e",
    "grid":        "rgba(255,255,255,0.08)",
    "text":        "#e0e0e0",
    "paper":       "#16213e",
}


def _find_key_levels(df: pd.DataFrame, order: int = 8) -> tuple[list, list]:
    highs = df["high"].values
    lows  = df["low"].values
    max_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
    min_idx = argrelextrema(lows,  np.less_equal,   order=order)[0]
    resistances = sorted({round(float(highs[i]), 2) for i in max_idx[-6:]})
    supports    = sorted({round(float(lows[i]),  2) for i in min_idx[-6:]})
    return supports, resistances


def create_technical_chart(df: pd.DataFrame,
                           period_label: str = "1Y",
                           analyst_target: float = None,
                           stop_loss: float = None) -> go.Figure:
    """
    Full 4-panel technical chart:
      Row 1 (55%): Candlestick + Bollinger + MAs + Support/Resistance
      Row 2 (15%): Volume
      Row 3 (15%): RSI
      Row 4 (15%): MACD
    """
    df = df.dropna(subset=["close", "open", "high", "low"]).copy()
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False,
                           font=dict(color=COLORS["text"], size=18))
        return fig

    supports, resistances = _find_key_levels(df)
    close = df["close"]
    dates = df.index

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        subplot_titles=("", "", "RSI (14)", "MACD"),
    )

    # ── Row 1: Candlestick ────────────────────────────────────────────────────
    colors_candle = [
        COLORS["candle_up"] if c >= o else COLORS["candle_down"]
        for c, o in zip(df["close"], df["open"])
    ]

    fig.add_trace(go.Candlestick(
        x=dates, open=df["open"], high=df["high"],
        low=df["low"], close=close,
        name="BX",
        increasing_line_color=COLORS["candle_up"],
        decreasing_line_color=COLORS["candle_down"],
        increasing_fillcolor=COLORS["candle_up"],
        decreasing_fillcolor=COLORS["candle_down"],
        line_width=1,
    ), row=1, col=1)

    # Bollinger Bands
    if "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=dates, y=df["bb_upper"], name="BB Upper",
            line=dict(color=COLORS["bb_line"], width=1, dash="dot"),
            showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=df["bb_lower"], name="BB Lower",
            line=dict(color=COLORS["bb_line"], width=1, dash="dot"),
            fill="tonexty", fillcolor=COLORS["bb"],
            showlegend=False,
        ), row=1, col=1)

    # Moving Averages
    for col, color, name in [
        ("ma20",  COLORS["ma20"],  "MA 20"),
        ("ma50",  COLORS["ma50"],  "MA 50"),
        ("ma200", COLORS["ma200"], "MA 200"),
    ]:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=dates, y=df[col], name=name,
                line=dict(color=color, width=1.5),
                opacity=0.85,
            ), row=1, col=1)

    # VWAP
    if "vwap" in df.columns:
        fig.add_trace(go.Scatter(
            x=dates, y=df["vwap"], name="VWAP",
            line=dict(color="#00bcd4", width=1, dash="dash"),
            opacity=0.7,
        ), row=1, col=1)

    # Support levels
    current_price = float(close.iloc[-1])
    for s in supports:
        if s < current_price * 1.05:
            fig.add_hline(
                y=s, line_color=COLORS["support"],
                line_width=1, line_dash="dash",
                annotation_text=f"S ${s}",
                annotation_font_color=COLORS["support"],
                annotation_font_size=10,
                row=1, col=1,
            )

    # Resistance levels
    for r in resistances:
        if r > current_price * 0.95:
            fig.add_hline(
                y=r, line_color=COLORS["resistance"],
                line_width=1, line_dash="dash",
                annotation_text=f"R ${r}",
                annotation_font_color=COLORS["resistance"],
                annotation_font_size=10,
                row=1, col=1,
            )

    # Analyst target
    if analyst_target:
        fig.add_hline(
            y=analyst_target, line_color="#ffd700",
            line_width=1.5, line_dash="dot",
            annotation_text=f"Analyst Target ${analyst_target}",
            annotation_font_color="#ffd700",
            annotation_font_size=10,
            row=1, col=1,
        )

    # Stop loss
    if stop_loss:
        fig.add_hline(
            y=stop_loss, line_color="#ff6b6b",
            line_width=1.5, line_dash="dot",
            annotation_text=f"Stop ${stop_loss}",
            annotation_font_color="#ff6b6b",
            annotation_font_size=10,
            row=1, col=1,
        )

    # ── Row 2: Volume ─────────────────────────────────────────────────────────
    vol_colors = [
        COLORS["volume_up"] if c >= o else COLORS["volume_down"]
        for c, o in zip(df["close"], df["open"])
    ]
    fig.add_trace(go.Bar(
        x=dates, y=df["volume"], name="Volume",
        marker_color=vol_colors, showlegend=False,
    ), row=2, col=1)

    # Volume 20d MA
    if "vol_ratio" in df.columns:
        vol_ma = df["volume"].rolling(20).mean()
        fig.add_trace(go.Scatter(
            x=dates, y=vol_ma, name="Vol MA20",
            line=dict(color="#ff9800", width=1),
            showlegend=False,
        ), row=2, col=1)

    # ── Row 3: RSI ────────────────────────────────────────────────────────────
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(
            x=dates, y=df["rsi"], name="RSI",
            line=dict(color=COLORS["rsi_line"], width=1.5),
            showlegend=False,
        ), row=3, col=1)
        # Overbought/oversold bands
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,83,80,0.07)",
                      line_width=0, row=3, col=1)
        fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(38,166,154,0.07)",
                      line_width=0, row=3, col=1)
        for level, color in [(70, COLORS["candle_down"]), (30, COLORS["candle_up"]),
                             (50, "rgba(255,255,255,0.2)")]:
            fig.add_hline(y=level, line_color=color,
                          line_width=0.8, line_dash="dot",
                          row=3, col=1)

    # ── Row 4: MACD ───────────────────────────────────────────────────────────
    if "macd" in df.columns:
        hist_colors = [
            COLORS["macd_hist_p"] if v >= 0 else COLORS["macd_hist_n"]
            for v in df["macd_hist"].fillna(0)
        ]
        fig.add_trace(go.Bar(
            x=dates, y=df["macd_hist"], name="MACD Hist",
            marker_color=hist_colors, showlegend=False,
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=df["macd"], name="MACD",
            line=dict(color=COLORS["macd_line"], width=1.5),
            showlegend=False,
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=df["macd_signal"], name="Signal",
            line=dict(color=COLORS["signal_line"], width=1.5),
            showlegend=False,
        ), row=4, col=1)
        fig.add_hline(y=0, line_color="rgba(255,255,255,0.2)",
                      line_width=0.8, row=4, col=1)

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        height=700,
        paper_bgcolor=COLORS["paper"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text"], family="Inter, sans-serif", size=11),
        margin=dict(l=10, r=60, t=30, b=10),
        legend=dict(
            orientation="h", x=0, y=1.02,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10),
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        title=dict(
            text=f"<b>BX — Blackstone Inc</b>  |  {period_label}",
            font=dict(size=14, color=COLORS["text"]),
            x=0.01,
        ),
    )

    # Grid styling for all rows
    for i in range(1, 5):
        fig.update_xaxes(
            gridcolor=COLORS["grid"], zeroline=False,
            tickfont=dict(size=9), showspikes=True,
            spikecolor="rgba(255,255,255,0.3)", spikethickness=1,
            row=i, col=1,
        )
        fig.update_yaxes(
            gridcolor=COLORS["grid"], zeroline=False,
            tickfont=dict(size=9), showspikes=True,
            spikecolor="rgba(255,255,255,0.3)", spikethickness=1,
            side="right",
            row=i, col=1,
        )

    # Row labels
    fig.update_yaxes(title_text="Volume", title_font_size=9, row=2, col=1)
    fig.update_yaxes(title_text="RSI",    title_font_size=9, row=3, col=1)
    fig.update_yaxes(title_text="MACD",   title_font_size=9, row=4, col=1)

    return fig
