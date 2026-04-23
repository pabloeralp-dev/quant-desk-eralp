"""Options Pricer — Black-Scholes pricing, Greeks, heatmap, IV, and Monte Carlo."""

from __future__ import annotations

import numpy as np
import streamlit as st
from dotenv import load_dotenv

from ai_analyst import get_commentary
from bs_engine import IVSolverError, black_scholes_greeks, black_scholes_price, implied_vol
from monte_carlo import run_options_simulation
from styles import inject_css, section_header
from utils import fmt_price, fmt_ratio, fmt_pct
from visualization import (
    plot_bs_monte_carlo,
    plot_greeks_vs_spot,
    plot_option_payoff,
    plot_vol_heatmap,
)

load_dotenv()

st.set_page_config(
    page_title="Options Pricer — QuantDesk",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h1 style='font-size:1.1rem;color:#1F6FEB;letter-spacing:0.08em;"
        "text-transform:uppercase'>📈 OPTIONS PRICER</h1>",
        unsafe_allow_html=True,
    )

    ticker = st.session_state.get("ticker", "AAPL")
    live = st.session_state.get("live_price") or {}
    price_sidebar = live.get("price")

    st.markdown(
        f"<p style='color:#8B949E;font-size:0.72rem;text-transform:uppercase;"
        f"letter-spacing:0.1em;margin-bottom:2px'>Ticker</p>"
        f"<p style='color:#E8EAF0;font-size:1.1rem;font-weight:700;margin:0'>"
        f"{ticker}"
        + (f" · ${price_sidebar:,.2f}" if price_sidebar else "")
        + "</p>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("**OPTION PARAMETERS**")

    default_spot = float(price_sidebar) if price_sidebar else 100.0
    S = st.number_input("Spot Price (S)", min_value=0.01, max_value=1e6,
                        value=default_spot, step=1.0, format="%.2f")
    K = st.number_input("Strike (K)", min_value=0.01, max_value=1e6,
                        value=float(round(default_spot, 2)), step=1.0, format="%.2f")
    T = st.number_input("Time to Expiry (years)", min_value=0.01, max_value=10.0,
                        value=1.0, step=0.05, format="%.2f")
    r_pct = st.number_input("Risk-Free Rate (%)", min_value=-5.0, max_value=20.0,
                             value=5.0, step=0.1, format="%.1f")
    r = r_pct / 100.0
    sigma_pct = st.slider("Volatility σ (%)", min_value=1, max_value=200, value=20)
    sigma = sigma_pct / 100.0

    option_type = st.radio("Option Type", ["call", "put"], horizontal=True)

# ── Core computation ─────────────────────────────────────────────────────────
try:
    price = black_scholes_price(S, K, T, r, sigma, option_type)
    greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
    intrinsic = max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    time_val = price - intrinsic
except Exception as e:
    st.error(f"❌ {e}")
    st.stop()

# ── Page header ──────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='text-align:center;font-size:1.6rem;letter-spacing:0.1em;"
    f"text-transform:uppercase;color:#1F6FEB;margin-bottom:0'>"
    f"📈 OPTIONS PRICER</h1>"
    f"<p style='text-align:center;color:#8B949E;font-size:0.78rem;"
    f"letter-spacing:0.15em;margin-top:4px'>"
    f"BLACK-SCHOLES · GREEKS · HEATMAP · IMPLIED VOL · MONTE CARLO</p>",
    unsafe_allow_html=True,
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💰 Pricing", "📐 Greeks", "🗺️ Heatmap", "🔍 Implied Vol", "🎲 Monte Carlo",
])

# ── Tab 1: Pricing ────────────────────────────────────────────────────────────
with tab1:
    section_header("PRICING", f"European {option_type.capitalize()} — Black-Scholes")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{option_type.capitalize()} Price", fmt_price(price))
    c2.metric("Intrinsic Value", fmt_price(intrinsic))
    c3.metric("Time Value", fmt_price(time_val))
    moneyness = "ATM" if abs(S - K) / K < 0.01 else ("ITM" if (
        (option_type == "call" and S > K) or (option_type == "put" and S < K)
    ) else "OTM")
    c4.metric("Moneyness", moneyness)

    # Intrinsic vs time value bar
    import plotly.graph_objects as go
    bar_fig = go.Figure(go.Bar(
        x=["Intrinsic Value", "Time Value"],
        y=[intrinsic, time_val],
        marker_color=["#1F6FEB" if intrinsic >= time_val else "#8B949E", "#8B949E" if intrinsic >= time_val else "#1F6FEB"],
        text=[fmt_price(intrinsic), fmt_price(time_val)],
        textposition="outside",
        textfont=dict(color="#E8EAF0", size=11),
    ))
    bar_fig.update_layout(
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        font=dict(color="#E8EAF0", family="Source Code Pro, monospace"),
        height=280, margin=dict(l=40, r=20, t=30, b=40),
        yaxis=dict(gridcolor="#30363D", tickprefix="$"),
        showlegend=False,
    )
    st.plotly_chart(bar_fig, use_container_width=True)

    st.plotly_chart(plot_option_payoff(S, K, sigma, r, T, option_type), use_container_width=True)

# ── Tab 2: Greeks ─────────────────────────────────────────────────────────────
with tab2:
    section_header("GREEKS", "Sensitivity metrics for the current option")

    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric("Delta (Δ)", fmt_ratio(greeks["delta"]), help="Price change per $1 spot move")
    g2.metric("Gamma (Γ)", fmt_ratio(greeks["gamma"]), help="Delta change per $1 spot move")
    g3.metric("Vega (ν)", fmt_price(greeks["vega"]), help="Price change per 1% vol move")
    g4.metric("Theta (Θ)", fmt_price(greeks["theta"]), help="Daily time decay (negative for long)")
    g5.metric("Rho (ρ)", fmt_price(greeks["rho"]), help="Price change per 1% rate move")

    if greeks["theta"] > 0:
        st.warning("⚠️ Positive theta is unusual for a long option — verify inputs.")

    st.markdown("---")
    st.plotly_chart(plot_greeks_vs_spot(S, K, sigma, r, T, option_type), use_container_width=True)

# ── Tab 3: Heatmap ────────────────────────────────────────────────────────────
with tab3:
    section_header("HEATMAP", "Option price across Spot × Volatility grid")
    st.plotly_chart(plot_vol_heatmap(K, r, T, S, option_type), use_container_width=True)

# ── Tab 4: Implied Vol ────────────────────────────────────────────────────────
with tab4:
    section_header("IMPLIED VOLATILITY", "Recover σ from an observed market price")

    col_mkt, col_res = st.columns([2, 3])
    with col_mkt:
        market_price = st.number_input(
            "Market Option Price ($)",
            min_value=0.001, max_value=1e6,
            value=round(price, 2), step=0.01, format="%.4f",
        )
        solve_btn = st.button("Solve for IV", type="primary")

    with col_res:
        if solve_btn:
            try:
                iv = implied_vol(market_price, S, K, r, T, option_type)
                iv_pct = iv * 100
                diff = iv - sigma
                st.metric("Implied Volatility", f"{iv_pct:.2f}%",
                          delta=f"{diff * 100:+.2f}% vs model σ")
                st.markdown(
                    f"<p style='color:#8B949E;font-size:0.8rem'>"
                    f"Model σ: {sigma * 100:.1f}% → Market IV: {iv_pct:.2f}% "
                    f"({'rich' if iv > sigma else 'cheap'} vs model)</p>",
                    unsafe_allow_html=True,
                )
            except IVSolverError as e:
                st.error(f"❌ {e}")
            except Exception as e:
                st.error(f"❌ {e}")
        else:
            st.info("ℹ️ Enter a market price and click **Solve for IV** to recover implied volatility.")

# ── Tab 5: Monte Carlo ────────────────────────────────────────────────────────
with tab5:
    section_header("MONTE CARLO", "10,000 GBM paths — terminal price & P&L distribution")

    n_sims = st.slider("Simulations", 1_000, 50_000, 10_000, 1_000)
    if n_sims > 25_000:
        st.warning("⚠️ > 25,000 simulations may be slow.")

    run_mc = st.button("▶  RUN MONTE CARLO", type="primary")
    if not run_mc:
        st.info("ℹ️ Click **Run Monte Carlo** to simulate GBM paths.")
    else:
        with st.spinner(f"Simulating {n_sims:,} paths…"):
            try:
                mc = run_options_simulation(S, K, T, r, sigma, option_type, n=n_sims)
            except Exception as e:
                st.error(f"❌ {e}")
                st.stop()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Option Cost", fmt_price(mc["option_cost"]))
        m2.metric("Mean P&L", fmt_price(mc["mean_pnl"]))
        m3.metric("% Profitable", fmt_pct(mc["pct_profit"]))
        m4.metric("P90 P&L", fmt_price(mc["p90"]))

        p1, p2, p3 = st.columns(3)
        p1.metric("P10 P&L", fmt_price(mc["p10"]))
        p2.metric("P50 P&L", fmt_price(mc["p50"]))
        p3.metric("Mean Terminal", fmt_price(mc["mean_terminal"]))

        st.plotly_chart(plot_bs_monte_carlo(mc, S, K, option_type), use_container_width=True)

# ── AI Analyst ────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("AI ANALYST", "Powered by Claude")

context = {
    "option_type": option_type,
    "spot": S, "strike": K, "T_years": T, "r_pct": r_pct, "sigma_pct": sigma_pct,
    "price": round(price, 4),
    "intrinsic": round(intrinsic, 4), "time_value": round(time_val, 4),
    "delta": round(greeks["delta"], 4), "gamma": round(greeks["gamma"], 4),
    "vega": round(greeks["vega"], 4), "theta": round(greeks["theta"], 4),
    "rho": round(greeks["rho"], 4),
}

with st.expander("📊 Generate analyst brief", expanded=False):
    if st.button("Generate Brief", key="gen_brief"):
        with st.spinner("Consulting analyst…"):
            try:
                brief = get_commentary(context)
                st.markdown(
                    f"<div style='background:#161B22;border:1px solid #30363D;"
                    f"border-radius:4px;padding:16px;font-size:0.85rem;line-height:1.6'>"
                    f"{brief}</div>",
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.error(f"❌ AI analyst unavailable: {e}")

st.markdown("**Ask the Analyst**")
question = st.text_input("Ask a question about this option…", key="analyst_q",
                         placeholder="e.g. What is the break-even price at expiry?")
if question:
    with st.spinner("Thinking…"):
        try:
            answer = get_commentary(context, question=question)
            st.markdown(
                f"<div style='background:#161B22;border:1px solid #30363D;"
                f"border-radius:4px;padding:16px;font-size:0.85rem;line-height:1.6'>"
                f"{answer}</div>",
                unsafe_allow_html=True,
            )
        except Exception as e:
            st.error(f"❌ AI analyst unavailable: {e}")
