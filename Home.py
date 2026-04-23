"""QuantDesk — entry point. Ticker search and module navigation."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from data_fetcher import fetch_live_price
from styles import inject_css

load_dotenv()

st.set_page_config(
    page_title="QuantDesk",
    page_icon="⬛",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

# ── Session state defaults ───────────────────────────────────────────────────
if "ticker" not in st.session_state:
    st.session_state["ticker"] = "AAPL"
if "live_price" not in st.session_state:
    st.session_state["live_price"] = None

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h1 style='font-size:1.1rem;color:#1F6FEB;letter-spacing:0.12em;"
        "text-transform:uppercase'>⬛ QUANTDESK</h1>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    ticker = st.session_state.get("ticker", "AAPL")
    live = st.session_state.get("live_price") or {}
    price = live.get("price")
    change = live.get("change_pct")
    market_open = live.get("market_open", False)

    st.markdown(
        f"<p style='color:#8B949E;font-size:0.72rem;text-transform:uppercase;"
        f"letter-spacing:0.1em;margin-bottom:2px'>Active Ticker</p>"
        f"<p style='color:#E8EAF0;font-size:1.3rem;font-weight:700;margin:0'>{ticker}</p>",
        unsafe_allow_html=True,
    )

    if price:
        change_color = "#00C805" if (change or 0) >= 0 else "#FF3B3B"
        change_str = f"{change * 100:+.2f}%" if change is not None else ""
        market_str = "OPEN" if market_open else "CLOSED"
        market_color = "#00C805" if market_open else "#FF3B3B"
        st.markdown(
            f"<p style='color:#E8EAF0;font-size:1.1rem;margin:4px 0'>${price:,.2f} "
            f"<span style='color:{change_color};font-size:0.85rem'>{change_str}</span></p>"
            f"<p style='color:{market_color};font-size:0.72rem;letter-spacing:0.08em'>"
            f"● {market_str}</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<p style='color:#8B949E;font-size:0.8rem'>No price loaded — search above</p>",
            unsafe_allow_html=True,
        )

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='text-align:center;font-size:2.2rem;letter-spacing:0.15em;"
    "text-transform:uppercase;color:#1F6FEB;margin-bottom:0'>⬛ QUANTDESK</h1>"
    "<p style='text-align:center;color:#8B949E;font-size:0.8rem;"
    "letter-spacing:0.2em;margin-top:4px'>"
    "QUANTITATIVE FINANCE · BLACK-SCHOLES · DCF VALUATION · AI ANALYST</p>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Ticker search ─────────────────────────────────────────────────────────────
col_input, col_btn, col_spacer = st.columns([3, 1, 3])
with col_input:
    ticker_input = st.text_input(
        "Ticker Symbol",
        value=st.session_state.get("ticker", "AAPL"),
        max_chars=10,
        label_visibility="collapsed",
        placeholder="Enter ticker (e.g. AAPL)",
    )
with col_btn:
    search = st.button("Search", use_container_width=True, type="primary")

if search and ticker_input.strip():
    with st.spinner(f"Fetching {ticker_input.upper()}…"):
        live_data = fetch_live_price(ticker_input)
    if live_data.get("error"):
        st.warning(f"⚠️ {live_data['error']} — ticker set anyway.")
    st.session_state["ticker"] = ticker_input.strip().upper()
    st.session_state["live_price"] = live_data
    st.rerun()

st.markdown("---")

# ── Module cards ──────────────────────────────────────────────────────────────
card_style = (
    "background-color:#161B22;border:1px solid #30363D;border-radius:6px;"
    "padding:28px 24px;height:220px;display:flex;flex-direction:column;"
    "justify-content:space-between"
)

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        f"<div style='{card_style}'>"
        "<p style='color:#1F6FEB;font-size:0.72rem;text-transform:uppercase;"
        "letter-spacing:0.12em;margin:0'>MODULE 01</p>"
        "<h2 style='color:#E8EAF0;font-size:1.3rem;margin:8px 0'>Options Pricer</h2>"
        "<p style='color:#8B949E;font-size:0.82rem;line-height:1.5;margin:0'>"
        "Black-Scholes pricing · Delta · Gamma · Theta · Vega · Rho<br>"
        "Heatmaps · Implied Vol · Monte Carlo simulation</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Open Options Pricer →", key="nav_options", use_container_width=True):
        st.switch_page("pages/1_Options_Pricer.py")

with col2:
    st.markdown(
        f"<div style='{card_style}'>"
        "<p style='color:#1F6FEB;font-size:0.72rem;text-transform:uppercase;"
        "letter-spacing:0.12em;margin:0'>MODULE 02</p>"
        "<h2 style='color:#E8EAF0;font-size:1.3rem;margin:8px 0'>DCF Valuation</h2>"
        "<p style='color:#8B949E;font-size:0.82rem;line-height:1.5;margin:0'>"
        "Revenue projections · WACC · Terminal value · Sensitivity tables<br>"
        "Football field · Monte Carlo · AI analyst commentary</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Open DCF Valuation →", key="nav_dcf", use_container_width=True):
        st.switch_page("pages/2_DCF_Valuation.py")

st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#8B949E;font-size:0.72rem;"
    "letter-spacing:0.08em'>QUANTDESK · POWERED BY CLAUDE · FOR EDUCATIONAL USE ONLY</p>",
    unsafe_allow_html=True,
)
