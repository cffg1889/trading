"""
Mobile-first Dash layout for the BX Intelligence dashboard.
Designed to be opened in Safari/Chrome on iPhone.
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
from config import TICKER, COMPANY


def conviction_badge(conviction: str, color: str) -> html.Div:
    return html.Div(
        conviction,
        style={
            "background":   color,
            "color":        "white",
            "fontWeight":   "700",
            "fontSize":     "1.1rem",
            "padding":      "6px 18px",
            "borderRadius": "20px",
            "display":      "inline-block",
            "letterSpacing":"0.05em",
        }
    )


def metric_card(label: str, value: str, delta: str = "", delta_color: str = "white") -> dbc.Card:
    return dbc.Card([
        dbc.CardBody([
            html.P(label, className="text-muted mb-1",
                   style={"fontSize": "0.7rem", "letterSpacing": "0.06em",
                          "textTransform": "uppercase"}),
            html.H5(value, className="mb-0",
                    style={"fontWeight": "700", "fontSize": "1.1rem"}),
            html.Small(delta, style={"color": delta_color, "fontWeight": "600"})
            if delta else html.Span(),
        ])
    ], style={"background": "#1a1a2e", "border": "1px solid #2a2a4e",
              "borderRadius": "12px", "minHeight": "80px"})


def news_item_card(item: dict) -> dbc.Card:
    sentiment = item.get("sentiment", "neutral")
    badge_color = {"bullish": "#26a69a", "bearish": "#ef5350"}.get(sentiment, "#666")
    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Span(sentiment.upper(),
                              style={"background": badge_color, "color": "white",
                                     "fontSize": "0.6rem", "padding": "2px 8px",
                                     "borderRadius": "10px", "fontWeight": "700"}),
                    html.Span(f"  {item.get('source','')}", className="text-muted",
                              style={"fontSize": "0.7rem"}),
                ], width=12, className="mb-1"),
                dbc.Col(
                    html.A(item.get("title", ""), href=item.get("url", "#"),
                           target="_blank",
                           style={"color": "#e0e0e0", "fontSize": "0.85rem",
                                  "fontWeight": "500", "textDecoration": "none"}),
                    width=12
                ),
            ])
        ], style={"padding": "10px 14px"})
    ], style={"background": "#1e1e3a", "border": "1px solid #2a2a4e",
              "borderRadius": "10px", "marginBottom": "8px"})


def signal_row(label: str, signal: str, narrative: str) -> html.Div:
    color = {
        "STRONG BUY":  "#00c851", "BUY":     "#4caf50",
        "bullish":     "#4caf50", "improving":"#4caf50",
        "HOLD":        "#ffa500", "neutral":  "#ffa500", "flat": "#ffa500",
        "SELL":        "#f44336", "bearish":  "#f44336", "deteriorating": "#f44336",
        "STRONG SELL": "#b71c1c",
    }.get(signal, "#999")

    return html.Div([
        dbc.Row([
            dbc.Col(html.Span(label, style={"color": "#aaa", "fontSize": "0.75rem",
                                            "textTransform": "uppercase",
                                            "letterSpacing": "0.06em"}), width=4),
            dbc.Col(html.Span(signal, style={"color": color, "fontWeight": "700",
                                             "fontSize": "0.85rem"}), width=3),
            dbc.Col(html.Small(narrative[:80] + "…" if len(narrative) > 80 else narrative,
                               style={"color": "#bbb", "fontSize": "0.75rem"}), width=5),
        ], align="center"),
        html.Hr(style={"borderColor": "#2a2a4e", "margin": "6px 0"}),
    ])


def build_layout() -> html.Div:
    return html.Div([
        # Auto-refresh intervals
        dcc.Interval(id="interval-price",  interval=30_000,  n_intervals=0),  # 30s
        dcc.Interval(id="interval-full",   interval=900_000, n_intervals=0),  # 15min

        # ── Sticky Header ────────────────────────────────────────────────────
        html.Div([
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        html.Span("BX", style={"fontWeight": "800", "fontSize": "1.3rem",
                                               "color": "white"}),
                        html.Span(" · Blackstone", style={"color": "#aaa",
                                                           "fontSize": "0.85rem",
                                                           "marginLeft": "6px"}),
                    ], width="auto"),
                    dbc.Col([
                        html.Span(id="header-price",
                                  style={"fontWeight": "700", "fontSize": "1.4rem",
                                         "color": "white"}),
                        html.Span(id="header-change",
                                  style={"fontSize": "0.9rem", "marginLeft": "8px",
                                         "fontWeight": "600"}),
                    ], width="auto"),
                    dbc.Col([
                        html.Div(id="header-conviction"),
                    ], width="auto", className="ms-auto"),
                ], align="center", justify="between"),
            ], fluid=True),
        ], style={
            "position":       "sticky",
            "top":            "0",
            "zIndex":         "1000",
            "background":     "#0f0f23",
            "borderBottom":   "1px solid #2a2a4e",
            "padding":        "10px 0",
            "backdropFilter": "blur(10px)",
        }),

        # ── Main content ──────────────────────────────────────────────────────
        dbc.Container([

            # ── Recommendation Box ───────────────────────────────────────────
            html.Div(id="recommendation-box", className="my-3"),

            # ── Key Metrics Row ──────────────────────────────────────────────
            html.Div(id="metrics-row"),

            # ── Technical Chart ──────────────────────────────────────────────
            dbc.Card([
                dbc.CardHeader([
                    dbc.Row([
                        dbc.Col(html.Span("Technical Analysis",
                                          style={"fontWeight": "700", "fontSize": "0.9rem"}),
                                width="auto"),
                        dbc.Col(
                            dbc.ButtonGroup([
                                dbc.Button(p, id={"type": "period-btn", "index": p},
                                           size="sm", outline=True,
                                           color="info",
                                           style={"fontSize": "0.7rem", "padding": "2px 8px"})
                                for p in ["1W", "1M", "3M", "1Y", "3Y"]
                            ]),
                            width="auto", className="ms-auto",
                        ),
                    ], align="center"),
                ], style={"background": "#1a1a2e", "border": "none"}),
                dbc.CardBody([
                    dcc.Graph(id="tech-chart",
                              config={"displayModeBar": False,
                                      "scrollZoom": True},
                              style={"height": "700px"}),
                ], style={"padding": "0"}),
            ], style={"background": "#16213e", "border": "1px solid #2a2a4e",
                      "borderRadius": "14px", "overflow": "hidden"},
               className="mb-3"),

            # ── Signal Summary ───────────────────────────────────────────────
            dbc.Card([
                dbc.CardHeader("Signal Summary",
                               style={"background": "#1a1a2e", "border": "none",
                                      "fontWeight": "700", "fontSize": "0.9rem"}),
                dbc.CardBody(id="signal-summary"),
            ], style={"background": "#16213e", "border": "1px solid #2a2a4e",
                      "borderRadius": "14px"},
               className="mb-3"),

            # ── News Feed ────────────────────────────────────────────────────
            dbc.Card([
                dbc.CardHeader("Latest News",
                               style={"background": "#1a1a2e", "border": "none",
                                      "fontWeight": "700", "fontSize": "0.9rem"}),
                dbc.CardBody(id="news-feed"),
            ], style={"background": "#16213e", "border": "1px solid #2a2a4e",
                      "borderRadius": "14px"},
               className="mb-3"),

            # ── Fundamentals ─────────────────────────────────────────────────
            dbc.Accordion([
                dbc.AccordionItem([
                    html.Div(id="fundamentals-content"),
                ], title="Fundamentals & Valuation"),
                dbc.AccordionItem([
                    html.Div(id="analyst-content"),
                ], title="Analyst Ratings"),
                dbc.AccordionItem([
                    html.Div(id="social-content"),
                ], title="Executive Social Media"),
            ], start_collapsed=True,
               style={"background": "transparent"},
               className="mb-3"),

            # Footer
            html.Div(
                f"BX Intelligence · Updated every 15 min · Not financial advice",
                className="text-center text-muted pb-4",
                style={"fontSize": "0.7rem"},
            ),
        ], fluid=True, style={"maxWidth": "600px", "padding": "0 12px"}),

        # Store for period selection
        dcc.Store(id="selected-period", data="1Y"),
        dcc.Store(id="summary-data",    data={}),

    ], style={
        "background":  "#0f0f23",
        "minHeight":   "100vh",
        "color":       "#e0e0e0",
        "fontFamily":  "Inter, -apple-system, sans-serif",
    })
