"""
BX Intelligence Dashboard — Mobile-first Dash application.
Opens at http://localhost:8050 on local network.
"""
import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime
import threading

from data.price import get_price_data, get_key_levels, get_current_quote
from data.fundamentals import get_fundamentals, get_analyst_ratings, get_earnings_history, get_peer_comparison
from data.news import fetch_all_news
import config

# ── App init ─────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, dbc.icons.FONT_AWESOME],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1, maximum-scale=1"}],
    title="BX Intelligence",
    suppress_callback_exceptions=True,
)
server = app.server

# ── Color palette ─────────────────────────────────────────────────────────────
COLORS = {
    "bg":        "#0d1117",
    "card":      "#161b22",
    "border":    "#30363d",
    "text":      "#e6edf3",
    "muted":     "#8b949e",
    "green":     "#3fb950",
    "red":       "#f85149",
    "yellow":    "#d29922",
    "blue":      "#58a6ff",
    "purple":    "#bc8cff",
    "orange":    "#ffa657",
    "up":        "#26a69a",
    "down":      "#ef5350",
}

CHART_TEMPLATE = {
    "layout": {
        "paper_bgcolor": COLORS["bg"],
        "plot_bgcolor":  COLORS["bg"],
        "font":          {"color": COLORS["text"], "family": "Inter, system-ui, sans-serif"},
        "gridcolor":     COLORS["border"],
        "zerolinecolor": COLORS["border"],
    }
}

# ── Layout ────────────────────────────────────────────────────────────────────

def build_layout():
    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Span("BX", style={"color": COLORS["blue"], "fontWeight": "800", "fontSize": "1.4rem"}),
                    html.Span(" · Blackstone Inc", style={"color": COLORS["muted"], "fontSize": "0.9rem", "marginLeft": "8px"}),
                    html.Div(id="live-price", style={"marginTop": "4px"}),
                ]),
            ], width=8),
            dbc.Col([
                dbc.Badge(id="signal-badge", color="warning", className="fs-6 p-2", style={"float": "right", "marginTop": "8px"}),
            ], width=4),
        ], className="py-3 px-2", style={"borderBottom": f"1px solid {COLORS['border']}"}),

        # Auto-refresh
        dcc.Interval(id="refresh-interval", interval=60_000, n_intervals=0),  # every 60s
        dcc.Store(id="data-store"),

        # Timeframe selector
        dbc.Row([
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button("1M",  id="btn-1m",  size="sm", color="secondary", outline=True),
                    dbc.Button("3M",  id="btn-3m",  size="sm", color="secondary", outline=True),
                    dbc.Button("6M",  id="btn-6m",  size="sm", color="secondary", outline=True),
                    dbc.Button("1Y",  id="btn-1y",  size="sm", color="primary",   outline=False),
                    dbc.Button("2Y",  id="btn-2y",  size="sm", color="secondary", outline=True),
                ], className="mt-2"),
            ]),
        ], className="px-2 mb-2"),

        # ── MAIN CHART ─────────────────────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                dcc.Loading(
                    dcc.Graph(id="main-chart", config={"displayModeBar": False, "responsive": True},
                              style={"height": "70vh"}),
                    color=COLORS["blue"],
                )
            ])
        ], className="mb-3"),

        # ── KPI CARDS ─────────────────────────────────────────────────────────
        dbc.Row(id="kpi-cards", className="px-2 mb-3 g-2"),

        # ── TABS ──────────────────────────────────────────────────────────────
        dbc.Tabs([
            dbc.Tab(html.Div(id="news-tab"),        label="News",        tab_id="tab-news"),
            dbc.Tab(html.Div(id="analyst-tab"),     label="Analysts",    tab_id="tab-analysts"),
            dbc.Tab(html.Div(id="fundamental-tab"), label="Financials",  tab_id="tab-fundamentals"),
            dbc.Tab(html.Div(id="peers-tab"),       label="Peers",       tab_id="tab-peers"),
        ], id="main-tabs", active_tab="tab-news", className="mb-3"),

        # Footer
        html.Div(
            html.Small(f"Last updated: {datetime.now().strftime('%H:%M ET')} · BX Intelligence",
                       style={"color": COLORS["muted"]}),
            className="text-center py-2",
        ),

    ], fluid=True, style={"backgroundColor": COLORS["bg"], "minHeight": "100vh", "padding": "0"})


app.layout = build_layout()


# ── Main chart callback ───────────────────────────────────────────────────────

@app.callback(
    Output("main-chart", "figure"),
    Output("live-price", "children"),
    Output("signal-badge", "children"),
    Output("signal-badge", "color"),
    Output("kpi-cards", "children"),
    Input("refresh-interval", "n_intervals"),
    Input("btn-1m", "n_clicks"),
    Input("btn-3m", "n_clicks"),
    Input("btn-6m", "n_clicks"),
    Input("btn-1y", "n_clicks"),
    Input("btn-2y", "n_clicks"),
    prevent_initial_call=False,
)
def update_dashboard(n_intervals, btn1m, btn3m, btn6m, btn1y, btn2y):
    # Determine selected period
    ctx = dash.callback_context
    period_map = {"btn-1m": "1mo", "btn-3m": "3mo", "btn-6m": "6mo", "btn-1y": "1y", "btn-2y": "2y"}
    period = "1y"
    if ctx.triggered and ctx.triggered[0]["prop_id"] != "refresh-interval.n_intervals":
        btn_id = ctx.triggered[0]["prop_id"].split(".")[0]
        period = period_map.get(btn_id, "1y")

    try:
        df = get_price_data(period=period)
        quote = get_current_quote()
        levels = get_key_levels(df)
        fig = build_chart(df, levels)
        price_component = build_price_header(quote)
        signal, signal_color = compute_signal(df, levels)
        kpis = build_kpi_cards(df, levels, quote)
        return fig, price_component, signal, signal_color, kpis
    except Exception as e:
        empty_fig = go.Figure()
        empty_fig.update_layout(template="plotly_dark", paper_bgcolor=COLORS["bg"])
        return empty_fig, f"Error: {e}", "ERROR", "danger", []


def build_chart(df: pd.DataFrame, levels: dict) -> go.Figure:
    """Build the comprehensive 4-panel technical analysis chart."""

    # 4 rows: Price (60%), Volume (15%), RSI (12%), MACD (13%)
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.60, 0.15, 0.12, 0.13],
        subplot_titles=("", "Volume", "RSI (14)", "MACD (12/26/9)"),
    )

    # ── ROW 1: Candlesticks + overlays ───────────────────────────
    # Bollinger Bands (shaded)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bb_upper"], name="BB Upper",
        line=dict(color="rgba(88,166,255,0.3)", width=1, dash="dot"),
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bb_lower"], name="BB Lower",
        line=dict(color="rgba(88,166,255,0.3)", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(88,166,255,0.05)",
        showlegend=False,
    ), row=1, col=1)

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        name="BX",
        increasing_line_color=COLORS["up"],
        decreasing_line_color=COLORS["down"],
        increasing_fillcolor=COLORS["up"],
        decreasing_fillcolor=COLORS["down"],
        whiskerwidth=0.3,
        line_width=0.8,
    ), row=1, col=1)

    # Moving averages
    fig.add_trace(go.Scatter(x=df.index, y=df["ema20"],  name="EMA 20",  line=dict(color=COLORS["blue"],   width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["ema50"],  name="EMA 50",  line=dict(color=COLORS["orange"], width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["sma200"], name="SMA 200", line=dict(color=COLORS["red"],    width=1.8, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["vwap"],   name="VWAP",    line=dict(color=COLORS["purple"], width=1.0, dash="dot")), row=1, col=1)

    # Support/Resistance horizontal lines
    current_price = df["close"].iloc[-1]
    for s in levels["supports"][:2]:
        fig.add_hline(y=s, line_dash="dot", line_color="rgba(63,185,80,0.5)", line_width=1,
                      annotation_text=f"S ${s:.0f}", annotation_font_color=COLORS["green"],
                      annotation_position="right", row=1, col=1)
    for r in levels["resistances"][:2]:
        fig.add_hline(y=r, line_dash="dot", line_color="rgba(248,81,73,0.5)", line_width=1,
                      annotation_text=f"R ${r:.0f}", annotation_font_color=COLORS["red"],
                      annotation_position="right", row=1, col=1)

    # 52-week high/low annotations
    fig.add_hline(y=levels["52w_high"], line_dash="dash", line_color="rgba(248,81,73,0.3)",
                  annotation_text=f"52W High ${levels['52w_high']:.2f}",
                  annotation_font_color="rgba(248,81,73,0.7)", row=1, col=1)
    fig.add_hline(y=levels["52w_low"], line_dash="dash", line_color="rgba(63,185,80,0.3)",
                  annotation_text=f"52W Low ${levels['52w_low']:.2f}",
                  annotation_font_color="rgba(63,185,80,0.7)", row=1, col=1)

    # Current price line
    fig.add_hline(y=current_price, line_color="rgba(230,236,243,0.4)", line_width=0.8,
                  annotation_text=f"  ${current_price:.2f}", annotation_font_color=COLORS["text"],
                  annotation_position="right", row=1, col=1)

    # ── ROW 2: Volume ─────────────────────────────────────────────
    colors_vol = [COLORS["up"] if c >= o else COLORS["down"]
                  for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"], name="Volume",
        marker_color=colors_vol, showlegend=False, opacity=0.7,
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["volume_ma20"], name="Vol MA20",
        line=dict(color=COLORS["orange"], width=1.2), showlegend=False,
    ), row=2, col=1)

    # ── ROW 3: RSI ────────────────────────────────────────────────
    rsi_val = df["rsi"].iloc[-1]
    rsi_color = COLORS["red"] if rsi_val > 70 else COLORS["green"] if rsi_val < 30 else COLORS["blue"]
    fig.add_trace(go.Scatter(
        x=df.index, y=df["rsi"], name=f"RSI {rsi_val:.0f}",
        line=dict(color=rsi_color, width=1.5), showlegend=False,
    ), row=3, col=1)
    # Zones
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(248,81,73,0.08)", line_width=0, row=3, col=1)
    fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(63,185,80,0.08)",  line_width=0, row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color=COLORS["red"],   line_width=0.8, row=3, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color=COLORS["muted"], line_width=0.5, row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color=COLORS["green"], line_width=0.8, row=3, col=1)

    # ── ROW 4: MACD ───────────────────────────────────────────────
    hist_colors = [COLORS["up"] if v >= 0 else COLORS["down"] for v in df["macd_hist"]]
    fig.add_trace(go.Bar(
        x=df.index, y=df["macd_hist"], name="MACD Hist",
        marker_color=hist_colors, showlegend=False, opacity=0.7,
    ), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd"],        name="MACD",   line=dict(color=COLORS["blue"],  width=1.3), showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Signal", line=dict(color=COLORS["orange"], width=1.3), showlegend=False), row=4, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color=COLORS["muted"], line_width=0.5, row=4, col=1)

    # ── Layout ────────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["text"], family="Inter, system-ui, sans-serif", size=11),
        margin=dict(l=0, r=60, t=10, b=0),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=COLORS["card"], font_color=COLORS["text"], font_size=11),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)", font_size=10,
        ),
        xaxis_rangeslider_visible=False,
    )

    for i in range(1, 5):
        fig.update_yaxes(
            gridcolor=COLORS["border"], gridwidth=0.5,
            zerolinecolor=COLORS["border"],
            tickfont_color=COLORS["muted"],
            showgrid=True, row=i, col=1,
        )
        fig.update_xaxes(
            gridcolor=COLORS["border"], gridwidth=0.5,
            showgrid=False,
            tickfont_color=COLORS["muted"],
            row=i, col=1,
        )

    # Y-axis labels
    fig.update_yaxes(tickprefix="$", row=1, col=1)
    fig.update_yaxes(row=3, col=1, range=[0, 100], dtick=20)

    return fig


def compute_signal(df, levels) -> tuple:
    """Compute overall BUY/HOLD/SELL signal."""
    score = 0
    rsi = levels["rsi"]
    macd = levels["macd"]
    macd_sig = levels["macd_signal"]
    current = levels["current"]
    ema20 = df["ema20"].iloc[-1]
    ema50 = df["ema50"].iloc[-1]
    sma200 = df["sma200"].iloc[-1]

    # RSI
    if rsi < 30:   score += 2
    elif rsi < 40: score += 1
    elif rsi > 70: score -= 2
    elif rsi > 60: score -= 1

    # MACD
    if macd > macd_sig: score += 1
    else: score -= 1

    # Trend
    if current > ema20 > ema50: score += 2
    elif current < ema20 < ema50: score -= 2

    # Price vs SMA200
    if current > sma200: score += 1
    else: score -= 1

    if score >= 3:
        return "BUY", "success"
    elif score <= -3:
        return "SELL", "danger"
    else:
        return "HOLD", "warning"


def build_price_header(quote: dict):
    color = COLORS["green"] if quote["change"] >= 0 else COLORS["red"]
    arrow = "▲" if quote["change"] >= 0 else "▼"
    return html.Div([
        html.Span(f"${quote['price']:.2f}", style={"fontSize": "1.6rem", "fontWeight": "700", "color": COLORS["text"]}),
        html.Span(f"  {arrow} {abs(quote['change']):.2f} ({abs(quote['change_pct']):.2f}%)",
                  style={"fontSize": "1rem", "color": color, "marginLeft": "8px"}),
    ])


def build_kpi_cards(df, levels, quote):
    rsi = levels["rsi"]
    rsi_color = "danger" if rsi > 70 else "success" if rsi < 30 else "info"
    rsi_label = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"

    vol_ratio = levels["volume_ratio"]
    vol_color = "warning" if vol_ratio > 1.5 else "secondary"

    macd_bull = levels["macd"] > levels["macd_signal"]

    bb_pct = df["bb_pct"].iloc[-1] if "bb_pct" in df.columns else 0.5

    cards = [
        ("RSI", f"{rsi:.0f} — {rsi_label}", rsi_color),
        ("Volume", f"{vol_ratio:.1f}x avg", vol_color),
        ("MACD", "Bullish" if macd_bull else "Bearish", "success" if macd_bull else "danger"),
        ("ATR", f"${levels['atr']:.2f}", "secondary"),
        ("BB%", f"{bb_pct*100:.0f}%", "info"),
        ("vs 52W High", f"-{((levels['52w_high'] - levels['current']) / levels['52w_high'] * 100):.0f}%", "danger"),
    ]

    return [
        dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    html.Small(label, style={"color": COLORS["muted"], "fontSize": "0.7rem", "textTransform": "uppercase"}),
                    html.Div(value, style={"fontWeight": "700", "fontSize": "0.85rem", "color": COLORS[color_map.get(color, "text")]}),
                ])
            ], style={"backgroundColor": COLORS["card"], "border": f"1px solid {COLORS['border']}"},
            className="text-center"),
        width=4)
        for label, value, color in cards
    ]


color_map = {
    "success": "green", "danger": "red", "warning": "yellow",
    "info": "blue", "secondary": "muted",
}


# ── News tab callback ─────────────────────────────────────────────────────────

@app.callback(Output("news-tab", "children"), Input("main-tabs", "active_tab"))
def render_news(active_tab):
    if active_tab != "tab-news":
        return []
    try:
        news = fetch_all_news(hours_back=24)
    except Exception:
        news = []

    sent_colors = {"bullish": COLORS["green"], "bearish": COLORS["red"], "neutral": COLORS["muted"]}
    sent_icons  = {"bullish": "[+]", "bearish": "[-]", "neutral": "[~]"}

    if not news:
        return html.P("No news found.", style={"color": COLORS["muted"], "padding": "1rem"})

    return html.Div([
        html.Div([
            html.Div([
                html.Div([
                    html.Span(sent_icons[item.sentiment] + " ", style={"fontSize": "0.85rem"}),
                    html.A(item.title, href=item.url, target="_blank",
                           style={"color": sent_colors[item.sentiment], "textDecoration": "none",
                                  "fontWeight": "600", "fontSize": "0.85rem"}),
                ]),
                html.Small(f"{item.source} · {item.published[:16] if item.published else ''}",
                           style={"color": COLORS["muted"], "fontSize": "0.72rem"}),
                html.P(item.summary[:150] + "..." if len(item.summary) > 150 else item.summary,
                       style={"color": COLORS["text"], "fontSize": "0.78rem", "margin": "4px 0 0 0"}),
            ], style={"padding": "10px 12px", "borderBottom": f"1px solid {COLORS['border']}"}),
        ]) for item in news
    ], style={"backgroundColor": COLORS["card"], "borderRadius": "8px"})


# ── Analyst tab callback ──────────────────────────────────────────────────────

@app.callback(Output("analyst-tab", "children"), Input("main-tabs", "active_tab"))
def render_analysts(active_tab):
    if active_tab != "tab-analysts":
        return []
    try:
        ratings = get_analyst_ratings()
        fundamentals = get_fundamentals()
    except Exception:
        return html.P("Error loading analyst data.", style={"color": COLORS["muted"]})

    target = fundamentals.get("analyst_target")
    rec    = fundamentals.get("recommendation", "N/A")
    n_ana  = fundamentals.get("num_analysts", "N/A")

    rec_color = {"BUY": COLORS["green"], "STRONG_BUY": COLORS["green"],
                 "HOLD": COLORS["yellow"], "SELL": COLORS["red"],
                 "UNDERPERFORM": COLORS["red"]}.get(rec, COLORS["muted"])

    return html.Div([
        # Consensus summary
        dbc.Row([
            dbc.Col(html.Div([
                html.Small("Consensus", style={"color": COLORS["muted"]}),
                html.Div(rec, style={"color": rec_color, "fontWeight": "700", "fontSize": "1.2rem"}),
                html.Small(f"{n_ana} analysts", style={"color": COLORS["muted"]}),
            ], className="text-center"), width=4),
            dbc.Col(html.Div([
                html.Small("Avg Target", style={"color": COLORS["muted"]}),
                html.Div(f"${target:.2f}" if target else "N/A",
                         style={"color": COLORS["blue"], "fontWeight": "700", "fontSize": "1.2rem"}),
                html.Small(f"Range: ${fundamentals.get('analyst_low', 0) or 0:.0f}–${fundamentals.get('analyst_high', 0) or 0:.0f}",
                           style={"color": COLORS["muted"]}),
            ], className="text-center"), width=4),
            dbc.Col(html.Div([
                html.Small("Short Interest", style={"color": COLORS["muted"]}),
                html.Div(f"{fundamentals.get('short_pct_float', 'N/A')}%",
                         style={"color": COLORS["red"], "fontWeight": "700", "fontSize": "1.2rem"}),
                html.Small(f"Ratio: {fundamentals.get('short_ratio', 'N/A')}d", style={"color": COLORS["muted"]}),
            ], className="text-center"), width=4),
        ], className="p-3"),

        html.Hr(style={"borderColor": COLORS["border"]}),

        # Recent ratings changes
        html.H6("Recent Rating Changes", style={"color": COLORS["muted"], "padding": "0 12px", "fontSize": "0.8rem", "textTransform": "uppercase"}),
        html.Div([
            html.Div([
                html.Div([
                    html.Span(row["firm"], style={"fontWeight": "600", "fontSize": "0.85rem", "color": COLORS["text"]}),
                    html.Span(f"  {row['from']} → {row['to']}" if row["from"] else f"  {row['to']}",
                              style={"color": COLORS["blue"], "fontSize": "0.82rem"}),
                    html.Span(f"  {row['action'].upper()}",
                              style={"color": COLORS["green"] if "up" in row["action"].lower() else COLORS["red"],
                                     "fontSize": "0.75rem", "fontWeight": "700", "marginLeft": "4px"}),
                ]),
                html.Small(row["date"], style={"color": COLORS["muted"], "fontSize": "0.72rem"}),
            ], style={"padding": "8px 12px", "borderBottom": f"1px solid {COLORS['border']}"})
            for row in ratings
        ]) if ratings else html.P("No recent changes.", style={"color": COLORS["muted"], "padding": "1rem"}),
    ], style={"backgroundColor": COLORS["card"], "borderRadius": "8px"})


# ── Fundamentals tab callback ─────────────────────────────────────────────────

@app.callback(Output("fundamental-tab", "children"), Input("main-tabs", "active_tab"))
def render_fundamentals(active_tab):
    if active_tab != "tab-fundamentals":
        return []
    try:
        f = get_fundamentals()
    except Exception:
        return html.P("Error loading fundamentals.", style={"color": COLORS["muted"]})

    rows = [
        ("Market Cap",      f.get("market_cap")),
        ("P/E (TTM)",       f.get("pe_ratio")),
        ("Forward P/E",     f.get("forward_pe")),
        ("EPS (TTM)",       f"${f.get('eps_ttm') or 'N/A'}"),
        ("EPS Next Year",   f"${f.get('eps_next_year') or 'N/A'}"),
        ("Dividend Yield",  f"{f.get('dividend_yield')}%" if f.get("dividend_yield") else "N/A"),
        ("Revenue TTM",     f.get("revenue_ttm")),
        ("Profit Margin",   f"{f.get('profit_margin')}%" if f.get("profit_margin") else "N/A"),
        ("ROE",             f"{f.get('roe')}%" if f.get("roe") else "N/A"),
        ("Debt/Equity",     f.get("debt_to_equity")),
        ("Beta",            f.get("beta")),
    ]

    return html.Div([
        html.Div([
            html.Div([
                html.Span(label, style={"color": COLORS["muted"], "fontSize": "0.82rem"}),
                html.Span(str(value) if value is not None else "N/A",
                          style={"color": COLORS["text"], "fontWeight": "600", "fontSize": "0.82rem", "float": "right"}),
            ], style={"padding": "8px 12px", "borderBottom": f"1px solid {COLORS['border']}"})
            for label, value in rows
        ])
    ], style={"backgroundColor": COLORS["card"], "borderRadius": "8px"})


# ── Peers tab callback ────────────────────────────────────────────────────────

@app.callback(Output("peers-tab", "children"), Input("main-tabs", "active_tab"))
def render_peers(active_tab):
    if active_tab != "tab-peers":
        return []
    try:
        peers = get_peer_comparison()
    except Exception:
        return html.P("Error loading peers.", style={"color": COLORS["muted"]})

    return html.Div([
        html.Div([
            dbc.Row([
                dbc.Col(html.Span(p["ticker"], style={"fontWeight": "700", "color": COLORS["blue"] if p["ticker"] == "BX" else COLORS["text"]}), width=2),
                dbc.Col(html.Span(f"${p['price'] or 'N/A'}", style={"fontSize": "0.82rem"}), width=3),
                dbc.Col(html.Span(f"{p['ytd_return']:+.1f}%" if p["ytd_return"] else "N/A",
                                  style={"color": COLORS["green"] if (p["ytd_return"] or 0) >= 0 else COLORS["red"],
                                         "fontSize": "0.82rem"}), width=3),
                dbc.Col(html.Span(p["rec"] or "N/A", style={"fontSize": "0.75rem", "color": COLORS["muted"]}), width=4),
            ], style={"padding": "8px 12px", "borderBottom": f"1px solid {COLORS['border']}"})
        ]) for p in peers
    ], style={"backgroundColor": COLORS["card"], "borderRadius": "8px"})


def run_dashboard():
    """Start the Dash server."""
    app.run(host=config.DASH_HOST, port=config.DASH_PORT, debug=False, use_reloader=False)
