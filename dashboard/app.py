"""
Main Dash application with all callbacks.
"""
import json
from dash import Dash, Input, Output, State, callback_context, html, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from config import TICKER, CHART_PERIODS, DEFAULT_PERIOD
from data.price import get_ohlcv, get_current_price
from data.scrapers.finviz import get_short_interest
from data import store
from dashboard.charts import create_technical_chart
from dashboard.layout import (build_layout, conviction_badge, news_item_card,
                               signal_row, metric_card)

app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.SLATE,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap",
    ],
    title="BX Intelligence",
    meta_tags=[
        {"name": "viewport",
         "content": "width=device-width, initial-scale=1, maximum-scale=1"},
        {"name": "apple-mobile-web-app-capable", "content": "yes"},
        {"name": "theme-color", "content": "#0f0f23"},
    ],
    suppress_callback_exceptions=True,
)

app.layout = build_layout()


# ── Live price header ─────────────────────────────────────────────────────────
@app.callback(
    Output("header-price",      "children"),
    Output("header-change",     "children"),
    Output("header-change",     "style"),
    Output("header-conviction", "children"),
    Input("interval-price",     "n_intervals"),
)
def update_header(_):
    quote = get_current_price()
    price = quote.get("price")
    chg   = quote.get("change", 0)
    pct   = quote.get("change_pct", 0)

    price_str = f"${price:.2f}" if price else "—"
    chg_str   = f"{'+' if chg >= 0 else ''}{chg:.2f} ({'+' if pct >= 0 else ''}{pct:.2f}%)"
    chg_color = "#26a69a" if chg >= 0 else "#ef5350"
    chg_style = {"fontSize": "0.9rem", "marginLeft": "8px",
                 "fontWeight": "600", "color": chg_color}

    summary = store.get_latest_summary()
    conv    = summary.get("conviction", "—") if summary else "—"
    color   = summary.get("conviction_color", "#ffa500") if summary else "#ffa500"

    badge = conviction_badge(conv, color)
    return price_str, chg_str, chg_style, badge


# ── Period selector ───────────────────────────────────────────────────────────
@app.callback(
    Output("selected-period", "data"),
    Input({"type": "period-btn", "index": "1W"}, "n_clicks"),
    Input({"type": "period-btn", "index": "1M"}, "n_clicks"),
    Input({"type": "period-btn", "index": "3M"}, "n_clicks"),
    Input({"type": "period-btn", "index": "1Y"}, "n_clicks"),
    Input({"type": "period-btn", "index": "3Y"}, "n_clicks"),
    prevent_initial_call=True,
)
def select_period(*_):
    ctx = callback_context
    if not ctx.triggered:
        return DEFAULT_PERIOD
    button_id = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])
    return button_id["index"]


# ── Technical chart ───────────────────────────────────────────────────────────
@app.callback(
    Output("tech-chart", "figure"),
    Input("selected-period",    "data"),
    Input("interval-full",      "n_intervals"),
)
def update_chart(period, _):
    period_cfg = CHART_PERIODS.get(period, CHART_PERIODS[DEFAULT_PERIOD])
    df = get_ohlcv(period=period_cfg[0], interval=period_cfg[1])

    # Get analyst target from last summary
    summary       = store.get_latest_summary()
    tech          = summary.get("technical", {}) if summary else {}
    analyst_target = tech.get("price_target")
    stop_loss      = tech.get("stop_loss")

    return create_technical_chart(
        df,
        period_label=period,
        analyst_target=float(analyst_target) if analyst_target else None,
        stop_loss=float(stop_loss) if stop_loss else None,
    )


# ── Recommendation box ────────────────────────────────────────────────────────
@app.callback(
    Output("recommendation-box", "children"),
    Input("interval-full", "n_intervals"),
)
def update_recommendation(_):
    summary = store.get_latest_summary()
    if not summary:
        return dbc.Alert("No analysis available. Run the orchestrator first.",
                         color="warning")

    conv  = summary.get("conviction", "—")
    color = summary.get("conviction_color", "#ffa500")
    rec   = summary.get("recommendation", "No recommendation available.")

    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.P("TODAY'S RECOMMENDATION", className="text-muted mb-1",
                           style={"fontSize": "0.65rem", "letterSpacing": "0.1em"}),
                    conviction_badge(conv, color),
                ], width=12, className="mb-2"),
                dbc.Col(
                    html.P(rec, style={"fontSize": "0.88rem", "lineHeight": "1.5",
                                       "color": "#e0e0e0", "marginBottom": "0"}),
                    width=12,
                ),
            ])
        ])
    ], style={"background": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
              "border":     f"1px solid {color}",
              "borderLeft": f"4px solid {color}",
              "borderRadius":"14px"})


# ── Metrics row ───────────────────────────────────────────────────────────────
@app.callback(
    Output("metrics-row", "children"),
    Input("interval-price", "n_intervals"),
)
def update_metrics(_):
    quote     = get_current_price()
    short_int = get_short_interest()

    def fmt_num(n):
        if n is None:
            return "—"
        if n >= 1e9:
            return f"${n/1e9:.1f}B"
        if n >= 1e6:
            return f"${n/1e6:.0f}M"
        return f"{n:,.0f}"

    price = quote.get("price", 0) or 0
    h52   = quote.get("week52_high")
    l52   = quote.get("week52_low")
    vol   = quote.get("volume")

    h52_pct = f"{(price/h52-1)*100:+.1f}% from high" if h52 else ""
    l52_pct = f"{(price/l52-1)*100:+.1f}% from low"  if l52 else ""

    return dbc.Row([
        dbc.Col(metric_card("52W High", f"${h52:.2f}" if h52 else "—",
                            h52_pct, "#ef5350"),
                width=6, className="mb-2"),
        dbc.Col(metric_card("52W Low", f"${l52:.2f}" if l52 else "—",
                            l52_pct, "#26a69a"),
                width=6, className="mb-2"),
        dbc.Col(metric_card("Volume", fmt_num(vol)), width=6, className="mb-2"),
        dbc.Col(metric_card("Short Float", short_int.get("short_float", "—"),
                            f"Ratio: {short_int.get('short_ratio','—')}d"),
                width=6, className="mb-2"),
    ])


# ── Signal summary ────────────────────────────────────────────────────────────
@app.callback(
    Output("signal-summary", "children"),
    Input("interval-full", "n_intervals"),
)
def update_signals(_):
    summary = store.get_latest_summary()
    if not summary:
        return html.P("Run analysis to see signals.", className="text-muted")

    tech  = summary.get("technical",    {})
    fund  = summary.get("fundamental",  {})
    news_ = summary.get("news",         {})
    anal  = summary.get("analyst",      {})
    soc   = summary.get("social",       {})

    rows = [
        signal_row("Technical",    tech.get("signal", "—"),  tech.get("narrative", "")),
        signal_row("Fundamental",  fund.get("signal", "—"),  fund.get("narrative", "")),
        signal_row("News",         news_.get("signal", "—"), news_.get("narrative", "")),
        signal_row("Analysts",     anal.get("signal", "—"),  anal.get("narrative", "")),
        signal_row("Social",       soc.get("signal", "—"),   soc.get("narrative", "")),
    ]
    score = summary.get("conviction_score", 0)
    rows.append(html.Div([
        html.Small(f"Weighted conviction score: {score:+.2f}",
                   style={"color": "#999", "fontSize": "0.7rem"}),
        html.Br(),
        html.Small(f"Last updated: {summary.get('created_at', '—')}",
                   style={"color": "#666", "fontSize": "0.65rem"}),
    ]))
    return rows


# ── News feed ─────────────────────────────────────────────────────────────────
@app.callback(
    Output("news-feed", "children"),
    Input("interval-full", "n_intervals"),
)
def update_news(_):
    items = store.get_recent_news(hours=24)
    if not items:
        return html.P("No recent news.", className="text-muted")

    sorted_items = sorted(
        items,
        key=lambda x: (x.get("impact") == "high", x.get("sentiment") != "neutral"),
        reverse=True,
    )
    return [news_item_card(item) for item in sorted_items[:12]]


# ── Fundamentals ──────────────────────────────────────────────────────────────
@app.callback(
    Output("fundamentals-content", "children"),
    Input("interval-full", "n_intervals"),
)
def update_fundamentals(_):
    summary = store.get_latest_summary()
    if not summary:
        return html.P("Run analysis to see fundamentals.", className="text-muted")

    fund = summary.get("fundamental", {})
    raw  = fund.get("raw_data", {})

    def fmt_pct(v):
        return f"{v*100:.1f}%" if v else "—"

    items = [
        ("P/E (Trailing)",    raw.get("pe_ratio"),                  None),
        ("P/E (Forward)",     raw.get("forward_pe"),                None),
        ("Price/Book",        raw.get("price_to_book"),             None),
        ("Dividend Yield",    fmt_pct(raw.get("dividend_yield")),   None),
        ("Profit Margin",     fmt_pct(raw.get("profit_margin")),    None),
        ("ROE",               fmt_pct(raw.get("roe")),              None),
        ("Beta",              raw.get("beta"),                      None),
        ("Analyst Target",    f"${raw.get('target_mean','—')}",     None),
    ]

    table_rows = [
        html.Tr([
            html.Td(label, style={"color": "#aaa", "fontSize": "0.8rem",
                                  "padding": "4px 8px"}),
            html.Td(str(val) if val is not None else "—",
                    style={"color": "#e0e0e0", "fontWeight": "600",
                           "fontSize": "0.85rem", "textAlign": "right",
                           "padding": "4px 8px"}),
        ])
        for label, val, _ in items
    ]

    narrative = fund.get("narrative", "")

    return html.Div([
        html.Table(table_rows,
                   style={"width": "100%", "borderCollapse": "collapse"}),
        html.Hr(style={"borderColor": "#2a2a4e", "margin": "10px 0"}),
        html.P(narrative, style={"fontSize": "0.82rem", "color": "#ccc",
                                 "lineHeight": "1.5"}),
    ])


# ── Analyst content ───────────────────────────────────────────────────────────
@app.callback(
    Output("analyst-content", "children"),
    Input("interval-full", "n_intervals"),
)
def update_analyst(_):
    summary = store.get_latest_summary()
    if not summary:
        return html.P("Run analysis to see ratings.", className="text-muted")

    anal     = summary.get("analyst", {})
    ratings  = anal.get("recent_ratings", [])
    narrative= anal.get("narrative", "")

    rating_rows = []
    for r in ratings[:8]:
        action = r.get("action", "")
        color  = "#26a69a" if "upgrade" in action.lower() else (
                 "#ef5350" if "downgrade" in action.lower() else "#ffa500")
        rating_rows.append(html.Div([
            dbc.Row([
                dbc.Col(html.Small(r.get("date",""),
                                   style={"color":"#777","fontSize":"0.7rem"}), width=3),
                dbc.Col(html.Small(r.get("firm",""),
                                   style={"color":"#ccc","fontSize":"0.8rem",
                                          "fontWeight":"600"}), width=4),
                dbc.Col(html.Small(action,
                                   style={"color": color, "fontSize":"0.75rem",
                                          "fontWeight":"700"}), width=3),
                dbc.Col(html.Small(r.get("new_target",""),
                                   style={"color":"#4caf50","fontSize":"0.75rem"}), width=2),
            ], align="center"),
            html.Hr(style={"borderColor":"#2a2a4e","margin":"4px 0"}),
        ]))

    return html.Div([
        html.Div(rating_rows) if rating_rows else html.P("No recent ratings."),
        html.P(narrative, style={"fontSize":"0.82rem","color":"#ccc","lineHeight":"1.5",
                                 "marginTop":"10px"}),
    ])


# ── Social content ────────────────────────────────────────────────────────────
@app.callback(
    Output("social-content", "children"),
    Input("interval-full", "n_intervals"),
)
def update_social(_):
    summary = store.get_latest_summary()
    if not summary:
        return html.P("Run analysis.", className="text-muted")

    soc  = summary.get("social", {})
    posts= soc.get("posts", [])
    narr = soc.get("narrative", "No recent executive posts.")

    post_cards = []
    for p in posts[:5]:
        post_cards.append(html.Div([
            html.Small(f"{p.get('author','')} · {p.get('platform','')}",
                       style={"color":"#888","fontSize":"0.7rem","fontWeight":"600"}),
            html.P(p.get("content","")[:200] + "…",
                   style={"color":"#ccc","fontSize":"0.82rem","margin":"4px 0",
                          "lineHeight":"1.4"}),
            html.Small(p.get("key_insight",""),
                       style={"color":"#4caf50","fontSize":"0.75rem","fontStyle":"italic"}),
            html.Hr(style={"borderColor":"#2a2a4e","margin":"8px 0"}),
        ]))

    return html.Div([
        html.P(narr, style={"fontSize":"0.85rem","color":"#e0e0e0",
                            "lineHeight":"1.5","marginBottom":"12px"}),
        html.Div(post_cards) if post_cards else html.P("No posts available."),
    ])
