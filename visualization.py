"""Plotly chart builders for QuantDesk — DCF and Options Pricer."""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Shared theme constants (CLAUDE.md palette) ──────────────────────────────
BG = "#0A0A0F"
GRID_COLOR = "#30363D"
FONT_COLOR = "#E8EAF0"
FONT_FAMILY = "Source Code Pro, Courier New, monospace"
ACCENT_BLUE = "#1F6FEB"
GREEN = "#00C805"
RED = "#FF3B3B"
MUTED = "#8B949E"
CALL_COLOR = "#1F6FEB"
PUT_COLOR = "#FF3B3B"


def _base_layout(title: str = "", height: int = 420) -> dict:
    return dict(
        title=dict(text=title, font=dict(color=ACCENT_BLUE, size=14, family=FONT_FAMILY)),
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=FONT_COLOR, family=FONT_FAMILY, size=11),
        height=height,
        margin=dict(l=60, r=30, t=50, b=50),
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
    )


# ── DCF Charts ───────────────────────────────────────────────────────────────

def plot_fcff_waterfall(df: pd.DataFrame) -> go.Figure:
    """Bar + line chart: Revenue, EBITDA, and FCFF projection."""
    fig = go.Figure()
    years = df["Year"].astype(str).apply(lambda y: f"Year {y}")

    fig.add_trace(go.Bar(x=years, y=df["Revenue"], name="Revenue",
                         marker_color="#1E4A80", opacity=0.7))
    fig.add_trace(go.Bar(x=years, y=df["EBITDA"], name="EBITDA",
                         marker_color="#2A6AAD", opacity=0.85))
    fig.add_trace(go.Scatter(x=years, y=df["FCFF"], name="FCFF",
                             mode="lines+markers",
                             line=dict(color=ACCENT_BLUE, width=2),
                             marker=dict(size=7, color=ACCENT_BLUE)))

    layout = _base_layout("Projected Financials & Free Cash Flow", height=400)
    layout["barmode"] = "overlay"
    layout["legend"] = dict(orientation="h", x=0, y=1.12,
                             font=dict(size=10, family=FONT_FAMILY),
                             bgcolor="rgba(0,0,0,0)")
    layout["yaxis"]["tickprefix"] = "$"
    layout["yaxis"]["tickformat"] = ",.0f"
    fig.update_layout(**layout)
    return fig


def plot_ev_bridge(pv_fcfs: float, pv_tv: float, net_debt: float) -> go.Figure:
    """Waterfall bridge: PV(FCFs) + PV(TV) → EV → Equity Value."""
    ev = pv_fcfs + pv_tv
    equity = ev - net_debt

    labels = ["PV of FCFs", "PV of Terminal Value", "Enterprise Value", "Less: Net Debt", "Equity Value"]
    values = [pv_fcfs, pv_tv, 0, -net_debt, 0]
    measures = ["relative", "relative", "total", "relative", "total"]

    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measures, x=labels, y=values,
        connector=dict(line=dict(color=GRID_COLOR, width=1)),
        increasing=dict(marker_color=ACCENT_BLUE),
        decreasing=dict(marker_color=RED),
        totals=dict(marker_color=GREEN if equity > 0 else RED),
        text=[f"${v:,.0f}" if v != 0 else f"${ev:,.0f}" if i == 2 else f"${equity:,.0f}"
              for i, v in enumerate(values)],
        textposition="outside",
        textfont=dict(size=9, color=FONT_COLOR, family=FONT_FAMILY),
    ))

    layout = _base_layout("Enterprise Value → Equity Value Bridge", height=380)
    layout["yaxis"]["tickprefix"] = "$"
    layout["yaxis"]["tickformat"] = ",.0f"
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig


def plot_sensitivity_heatmap(table: pd.DataFrame, current_price: float) -> go.Figure:
    """Plotly heatmap of implied share prices across WACC × terminal growth."""
    z = table.values
    x_labels = [f"{c:.1%}" for c in table.columns]
    y_labels = [f"{r:.1%}" for r in table.index]
    text = [[f"${v:,.2f}" if not np.isnan(v) else "N/A" for v in row] for row in z]

    fig = go.Figure(go.Heatmap(
        z=z, x=x_labels, y=y_labels, text=text,
        texttemplate="%{text}", textfont=dict(size=10, family=FONT_FAMILY),
        colorscale=[[0.0, "#3A0A0A"], [0.4, "#2E1010"], [0.5, "#161B22"],
                    [0.6, "#0D2818"], [1.0, "#0D3320"]],
        zmid=current_price, showscale=True,
        colorbar=dict(title=dict(text="Implied Price", font=dict(color=MUTED, size=10)),
                      tickfont=dict(color=FONT_COLOR, size=9), tickprefix="$"),
    ))

    layout = _base_layout("Sensitivity: Implied Share Price", height=400)
    layout["xaxis"]["title"] = "WACC"
    layout["yaxis"]["title"] = "Terminal Growth Rate"
    fig.update_layout(**layout)
    return fig


def plot_football_field(ranges: List[dict], current_price: float) -> go.Figure:
    """Horizontal football field chart showing valuation ranges."""
    bar_colors = ["#1E4A80", "#2A6AAD", "#1A5C3A", "#4A3A0A", "#3A1A5C"]
    bar_border = [ACCENT_BLUE, MUTED, GREEN, "#F0C040", "#9B59B6"]

    fig = go.Figure()
    for i, r in enumerate(reversed(ranges)):
        low, high = r.get("low", 0), r.get("high", 0)
        label = r.get("label", f"Method {i+1}")
        color = bar_colors[i % len(bar_colors)]
        border = bar_border[i % len(bar_border)]
        fig.add_trace(go.Bar(
            x=[high - low], y=[label], base=[low], orientation="h",
            marker=dict(color=color, line=dict(color=border, width=1.5)),
            text=f"${low:,.1f} – ${high:,.1f}", textposition="inside",
            textfont=dict(size=9, color=FONT_COLOR, family=FONT_FAMILY),
            showlegend=False,
            hovertemplate=f"<b>{label}</b><br>Low: ${low:,.2f}<br>High: ${high:,.2f}<extra></extra>",
        ))

    if current_price and current_price > 0:
        fig.add_vline(x=current_price, line=dict(color=ACCENT_BLUE, width=2, dash="dash"),
                      annotation_text=f"Current: ${current_price:,.2f}",
                      annotation_font=dict(color=ACCENT_BLUE, size=10, family=FONT_FAMILY),
                      annotation_position="top")

    layout = _base_layout("Football Field — Valuation Summary",
                          height=max(300, 80 * len(ranges) + 100))
    layout["barmode"] = "overlay"
    layout["xaxis"]["title"] = "Implied Share Price ($)"
    layout["xaxis"]["tickprefix"] = "$"
    layout["xaxis"]["tickformat"] = ",.0f"
    layout["yaxis"]["title"] = ""
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig


def plot_monte_carlo_histogram(
    prices: np.ndarray,
    p10: float, p25: float, p50: float, p75: float, p90: float,
    current_price: float,
    n_bins: int = 80,
) -> go.Figure:
    """Histogram of DCF Monte Carlo implied share price distribution."""
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=prices, nbinsx=n_bins,
        marker=dict(color=ACCENT_BLUE, opacity=0.7, line=dict(color=GRID_COLOR, width=0.5)),
        showlegend=False,
    ))

    for val, label, color, dash in [
        (p10, "P10", RED, "dot"), (p25, "P25", "#E07722", "dash"),
        (p50, "P50", GREEN, "solid"), (p75, "P75", "#E07722", "dash"),
        (p90, "P90", RED, "dot"),
    ]:
        fig.add_vline(x=val, line=dict(color=color, width=1.5, dash=dash),
                      annotation_text=f"{label}: ${val:,.1f}",
                      annotation_font=dict(color=color, size=9, family=FONT_FAMILY),
                      annotation_position="top")

    if current_price and current_price > 0:
        fig.add_vline(x=current_price, line=dict(color="#FFFFFF", width=2, dash="longdash"),
                      annotation_text=f"Current: ${current_price:,.1f}",
                      annotation_font=dict(color="#FFFFFF", size=10, family=FONT_FAMILY),
                      annotation_position="top right")

    layout = _base_layout("Monte Carlo — Implied Share Price Distribution", height=420)
    layout["xaxis"]["title"] = "Implied Share Price ($)"
    layout["xaxis"]["tickprefix"] = "$"
    layout["yaxis"]["title"] = "Frequency"
    layout["bargap"] = 0.05
    fig.update_layout(**layout)
    return fig


def plot_terminal_value_comparison(pv_perpetuity: float, pv_exit: float) -> go.Figure:
    """Side-by-side bar: PV of terminal value under perpetuity vs exit multiple."""
    fig = go.Figure(go.Bar(
        x=["Perpetuity Growth", "Exit Multiple"],
        y=[pv_perpetuity, pv_exit],
        marker=dict(color=[ACCENT_BLUE, MUTED], line=dict(color=[ACCENT_BLUE, MUTED], width=1)),
        text=[f"${pv_perpetuity:,.0f}", f"${pv_exit:,.0f}"],
        textposition="outside",
        textfont=dict(size=11, family=FONT_FAMILY, color=FONT_COLOR),
    ))
    layout = _base_layout("Terminal Value Comparison", height=320)
    layout["yaxis"]["tickprefix"] = "$"
    layout["yaxis"]["tickformat"] = ",.0f"
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig


# ── Options Charts ───────────────────────────────────────────────────────────

def plot_option_payoff(
    spot: float, strike: float, vol: float, rate: float,
    time_to_expiry: float, option_type: str,
) -> go.Figure:
    """Plot at-expiry payoff alongside current BS price curve vs spot."""
    from bs_engine import black_scholes_price

    spots = np.linspace(spot * 0.5, spot * 1.5, 200)
    color = CALL_COLOR if option_type == "call" else PUT_COLOR

    if option_type == "call":
        payoff = np.maximum(spots - strike, 0.0)
    else:
        payoff = np.maximum(strike - spots, 0.0)

    bs_prices = np.array([
        black_scholes_price(s, strike, vol, rate, time_to_expiry, option_type)
        for s in spots
    ])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spots, y=payoff, name="Payoff at expiry",
                             line=dict(color=MUTED, width=1.5, dash="dash")))
    fig.add_trace(go.Scatter(x=spots, y=bs_prices,
                             name=f"BS price today (T={time_to_expiry:.2f}y)",
                             line=dict(color=color, width=2)))

    fig.add_vline(x=strike, line=dict(color=MUTED, width=1, dash="dot"),
                  annotation_text="K", annotation_font=dict(color=MUTED, size=10))
    fig.add_vline(x=spot, line=dict(color=color, width=1, dash="dot"),
                  annotation_text="S", annotation_font=dict(color=color, size=10))

    layout = _base_layout(f"European {option_type.capitalize()} — Payoff vs Current Price", height=380)
    layout["xaxis"]["title"] = "Spot Price ($)"
    layout["yaxis"]["title"] = "Option Value ($)"
    layout["legend"] = dict(orientation="h", x=0, y=1.1, bgcolor="rgba(0,0,0,0)",
                             font=dict(size=10, family=FONT_FAMILY))
    fig.update_layout(**layout)
    return fig


def plot_greeks_vs_spot(
    spot: float, strike: float, vol: float, rate: float,
    time_to_expiry: float, option_type: str,
) -> go.Figure:
    """2×3 subplot grid: option price + all five Greeks vs spot."""
    from bs_engine import black_scholes_price, black_scholes_greeks

    color = CALL_COLOR if option_type == "call" else PUT_COLOR
    spots = np.linspace(spot * 0.6, spot * 1.4, 200)

    metrics = ["price", "delta", "gamma", "vega", "theta", "rho"]
    labels = {
        "price": "Price ($)", "delta": "Delta", "gamma": "Gamma",
        "vega": "Vega (per 1% vol)", "theta": "Theta (per day)", "rho": "Rho (per 1% rate)",
    }

    def series(metric: str) -> np.ndarray:
        out = []
        for s in spots:
            try:
                if metric == "price":
                    out.append(black_scholes_price(s, strike, vol, rate, time_to_expiry, option_type))
                else:
                    out.append(black_scholes_greeks(s, strike, vol, rate, time_to_expiry, option_type)[metric])
            except Exception:
                out.append(float("nan"))
        return np.array(out)

    fig = make_subplots(rows=2, cols=3, subplot_titles=[labels[m] for m in metrics])

    for idx, metric in enumerate(metrics):
        row, col = divmod(idx, 3)
        fig.add_trace(
            go.Scatter(x=spots, y=series(metric), line=dict(color=color, width=1.8),
                       showlegend=False),
            row=row + 1, col=col + 1,
        )

    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=FONT_COLOR, family=FONT_FAMILY, size=10),
        height=500, margin=dict(l=50, r=20, t=60, b=40),
        title=dict(
            text=f"European {option_type.capitalize()} — Price & Greeks vs Spot",
            font=dict(color=ACCENT_BLUE, size=13, family=FONT_FAMILY),
        ),
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    return fig


def plot_vol_heatmap(
    strike: float, rate: float, time_to_expiry: float,
    spot_center: float, option_type: str,
) -> go.Figure:
    """Heatmap of option price across spot × volatility grid."""
    from bs_engine import black_scholes_price

    spots = np.linspace(spot_center * 0.7, spot_center * 1.3, 50)
    vols = np.linspace(0.05, 0.80, 50)

    price_grid = np.array([
        [black_scholes_price(s, strike, v, rate, time_to_expiry, option_type)
         for s in spots]
        for v in vols
    ])

    fig = go.Figure(go.Heatmap(
        z=price_grid,
        x=[f"${s:.0f}" for s in spots],
        y=[f"{v:.0%}" for v in vols],
        colorscale=[[0.0, "#0E1117"], [0.5, "#1F3A6E"], [1.0, ACCENT_BLUE]],
        showscale=True,
        colorbar=dict(
            title=dict(text="Option Price ($)", font=dict(color=MUTED, size=10)),
            tickfont=dict(color=FONT_COLOR, size=9), tickprefix="$",
        ),
    ))

    fig.add_vline(x=f"${strike:.0f}", line=dict(color=MUTED, width=1.5, dash="dash"),
                  annotation_text="Strike", annotation_font=dict(color=MUTED, size=10))

    layout = _base_layout(
        f"Option Price — Spot × Volatility Heatmap ({option_type.capitalize()})", height=420
    )
    layout["xaxis"]["title"] = "Spot Price ($)"
    layout["yaxis"]["title"] = "Implied Volatility"
    fig.update_layout(**layout)
    return fig


def plot_bs_monte_carlo(
    mc_result: dict,
    S: float, K: float, option_type: str,
) -> go.Figure:
    """Three-panel MC chart: GBM paths, terminal price distribution, P&L histogram."""
    sample_paths = mc_result["sample_paths"]
    terminal_prices = mc_result["terminal_prices"]
    pnl = mc_result["pnl"]
    option_cost = mc_result["option_cost"]
    n_steps = sample_paths.shape[1] - 1

    color = CALL_COLOR if option_type == "call" else PUT_COLOR
    t_axis = np.linspace(0, 1, n_steps + 1)

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=["GBM Paths (sample)", "Terminal Price Distribution", "P&L Distribution"],
    )

    # Panel 1: GBM paths
    for path in sample_paths[:50]:
        fig.add_trace(
            go.Scatter(x=t_axis, y=path, line=dict(color=color, width=0.4),
                       opacity=0.3, showlegend=False),
            row=1, col=1,
        )
    fig.add_hline(y=K, line=dict(color=MUTED, width=1.5, dash="dash"), row=1, col=1)

    # Panel 2: Terminal price distribution
    fig.add_trace(
        go.Histogram(x=terminal_prices, nbinsx=60,
                     marker=dict(color=color, opacity=0.7, line=dict(color=GRID_COLOR, width=0.5)),
                     showlegend=False),
        row=1, col=2,
    )
    fig.add_vline(x=K, line=dict(color=MUTED, width=1.5, dash="dash"),
                  annotation_text="K", annotation_font=dict(color=MUTED, size=9),
                  row=1, col=2)
    fig.add_vline(x=S, line=dict(color=ACCENT_BLUE, width=1.5, dash="dot"),
                  annotation_text="S₀", annotation_font=dict(color=ACCENT_BLUE, size=9),
                  row=1, col=2)

    # Panel 3: P&L distribution
    profit_pnl = pnl[pnl >= 0]
    loss_pnl = pnl[pnl < 0]
    if len(profit_pnl):
        fig.add_trace(
            go.Histogram(x=profit_pnl, nbinsx=40,
                         marker=dict(color=GREEN, opacity=0.7),
                         showlegend=False),
            row=1, col=3,
        )
    if len(loss_pnl):
        fig.add_trace(
            go.Histogram(x=loss_pnl, nbinsx=40,
                         marker=dict(color=RED, opacity=0.7),
                         showlegend=False),
            row=1, col=3,
        )
    fig.add_vline(x=0, line=dict(color=MUTED, width=1.5, dash="dash"),
                  row=1, col=3)

    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=FONT_COLOR, family=FONT_FAMILY, size=10),
        height=380, margin=dict(l=50, r=20, t=60, b=40),
        barmode="overlay", showlegend=False,
        title=dict(
            text="Monte Carlo — GBM Simulation",
            font=dict(color=ACCENT_BLUE, size=13, family=FONT_FAMILY),
        ),
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    return fig
