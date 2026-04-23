"""DCF Valuation — full discounted cash flow model with Monte Carlo and AI analyst."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ai_analyst import get_commentary
from data_fetcher import fetch_ticker_data
from dcf_engine import (
    DCFInputs,
    ValidationError,
    compute_wacc,
    run_dcf,
    sensitivity_table,
    sensitivity_table_exit_multiple,
    terminal_value_perpetuity,
    terminal_value_exit,
)
from monte_carlo import MonteCarloInputs, run_dcf_simulation
from styles import build_sensitivity_html, inject_css, section_header
from utils import fmt_billions, fmt_currency, fmt_millions, fmt_pct
from visualization import (
    plot_ev_bridge,
    plot_fcff_waterfall,
    plot_football_field,
    plot_monte_carlo_histogram,
    plot_sensitivity_heatmap,
    plot_terminal_value_comparison,
)

load_dotenv()

st.set_page_config(
    page_title="DCF Valuation — QuantDesk",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

# ── Session state defaults ───────────────────────────────────────────────────
for k, v in {"wacc": 0.10, "valuation_run": False, "dcf_result": None, "dcf_inputs": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Sidebar ──────────────────────────────────────────────────────────────────
def render_sidebar() -> dict | None:
    with st.sidebar:
        st.markdown(
            "<h1 style='font-size:1.1rem;color:#1F6FEB;letter-spacing:0.08em;"
            "text-transform:uppercase'>⬛ DCF PARAMETERS</h1>",
            unsafe_allow_html=True,
        )

        # Ticker from Home.py session state
        default_ticker = st.session_state.get("ticker", "AAPL")

        st.markdown("---")
        st.markdown("**TICKER LOOKUP**")
        ticker_input = st.text_input("Ticker Symbol", value=default_ticker, max_chars=10)
        fetch_btn = st.button("Fetch Data", key="fetch_btn")

        fetched = {}
        if fetch_btn and ticker_input.strip():
            with st.spinner("Fetching data…"):
                fetched = fetch_ticker_data(ticker_input)
            if fetched.get("error"):
                st.warning(f"⚠️ {fetched['error']}")
            else:
                st.success(f"✓ {fetched['ticker']} loaded")
                st.session_state["fetched"] = fetched
                st.session_state["ticker"] = fetched["ticker"]
        fetched = st.session_state.get("fetched", {})

        st.markdown("---")
        st.markdown("**COMPANY BASICS**")

        default_revenue = fetched.get("revenue") or 1_000_000_000.0
        revenue = st.number_input("Base Revenue ($)", min_value=1.0, max_value=1e12,
                                   value=float(default_revenue), step=1_000_000.0, format="%.0f")
        if revenue <= 0:
            st.error("❌ Revenue must be positive.")
            return None

        default_shares = fetched.get("shares_outstanding") or 100_000_000
        shares = st.number_input("Shares Outstanding", min_value=1, max_value=int(1e12),
                                  value=int(default_shares), step=1_000_000)
        if shares <= 0:
            st.error("❌ Shares outstanding must be greater than zero.")
            return None

        default_price = fetched.get("current_price") or 50.0
        current_price = st.number_input("Current Share Price ($)", min_value=0.01, max_value=1e6,
                                         value=float(default_price), step=0.01)
        if current_price <= 0:
            st.error("❌ Share price must be positive.")
            return None

        net_debt = st.number_input("Net Debt ($)  [negative = net cash]",
                                    min_value=-1e12, max_value=1e12,
                                    value=float(fetched.get("net_debt") or 0.0),
                                    step=1_000_000.0, format="%.0f")

        st.markdown("---")
        st.markdown("**PROJECTION ASSUMPTIONS**")

        n_years = st.slider("Projection Years", min_value=3, max_value=10, value=5, step=1)

        st.markdown("*Annual Revenue Growth Rates*")
        growth_rates = []
        for i in range(n_years):
            g = st.number_input(f"Year {i+1} Growth (%)", min_value=-50.0, max_value=100.0,
                                 value=8.0 if i < 3 else 5.0, step=0.5, key=f"growth_{i}")
            if g > 30:
                st.warning(f"⚠️ Year {i+1}: {g:.1f}% growth is unusually high.")
            if g > 100 or g < -50:
                st.error(f"❌ Year {i+1}: growth must be between -50% and 100%.")
                return None
            growth_rates.append(g / 100.0)

        ebitda_margin = st.slider("EBITDA Margin (%)", min_value=-100.0, max_value=90.0, value=20.0, step=0.5)
        if ebitda_margin > 90:
            st.error("❌ EBITDA margin > 90% is unrealistic.")
            return None
        if ebitda_margin < 0:
            st.warning("⚠️ Negative EBITDA — company is unprofitable.")

        da_pct = st.slider("D&A (% of Revenue)", min_value=0.0, max_value=50.0, value=5.0, step=0.5)
        capex_pct = st.slider("CapEx (% of Revenue)", min_value=0.0, max_value=80.0, value=8.0, step=0.5)
        if capex_pct < da_pct:
            st.warning("⚠️ CapEx < D&A — company may be underinvesting.")

        nwc_pct = st.slider("ΔNWC (% of Revenue)", min_value=-30.0, max_value=30.0, value=2.0, step=0.5)
        tax_rate = st.slider("Tax Rate (%)", min_value=0.0, max_value=60.0, value=25.0, step=0.5)

        st.markdown("---")
        st.markdown("**WACC INPUTS**")

        rf = st.number_input("Risk-Free Rate (%)", min_value=0.0, max_value=20.0, value=4.5, step=0.1)
        default_beta = fetched.get("beta") or 1.0
        beta = st.number_input("Beta", min_value=0.01, max_value=5.0, value=float(default_beta), step=0.05)
        erp = st.number_input("Equity Risk Premium (%)", min_value=1.0, max_value=15.0, value=6.5, step=0.1)
        cost_of_debt = st.number_input("Cost of Debt (%)", min_value=0.0, max_value=25.0, value=5.0, step=0.1)
        debt_weight = st.slider("Debt Weight D/(D+E) (%)", min_value=0.0, max_value=95.0, value=30.0, step=1.0)

        wacc = compute_wacc(
            rf=rf / 100, beta=beta, erp=erp / 100,
            cost_of_debt=cost_of_debt / 100,
            tax_rate=tax_rate / 100,
            debt_weight=debt_weight / 100,
        )
        st.session_state["wacc"] = wacc

        if wacc < 0.03 or wacc > 0.25:
            st.warning(f"⚠️ WACC of {wacc:.2%} is unusual.")

        st.markdown(
            f"<div style='background:#161B22;border:1px solid #1F6FEB;border-radius:4px;"
            f"padding:10px;text-align:center;margin-top:8px'>"
            f"<span style='color:#8B949E;font-size:0.75rem;text-transform:uppercase;"
            f"letter-spacing:0.1em'>Computed WACC</span><br>"
            f"<span style='color:#1F6FEB;font-size:1.4rem;font-weight:700'>{wacc:.2%}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("**TERMINAL VALUE**")

        use_perpetuity = st.radio(
            "Terminal Value Method",
            options=["Perpetuity Growth", "Exit Multiple"],
            index=0, horizontal=True,
        ) == "Perpetuity Growth"

        terminal_growth = st.number_input("Terminal Growth Rate (%)", min_value=0.0, max_value=5.0, value=2.5, step=0.1)
        if terminal_growth / 100 >= wacc:
            st.error(
                f"❌ Terminal growth ({terminal_growth:.1f}%) must be < WACC ({wacc:.2%})."
            )
            return None

        exit_multiple = st.number_input("Exit EV/EBITDA Multiple", min_value=1.0, max_value=50.0, value=10.0, step=0.5)
        if exit_multiple > 25:
            st.warning("⚠️ Very aggressive exit multiple (> 25x).")

        st.markdown("---")
        run_btn = st.button("▶  RUN VALUATION", use_container_width=True, type="primary")

        return {
            "revenue": revenue, "shares": shares, "current_price": current_price,
            "net_debt": net_debt, "n_years": n_years, "growth_rates": growth_rates,
            "ebitda_margin": ebitda_margin / 100, "da_pct": da_pct / 100,
            "capex_pct": capex_pct / 100, "nwc_pct": nwc_pct / 100,
            "tax_rate": tax_rate / 100, "rf": rf / 100, "beta": beta,
            "erp": erp / 100, "cost_of_debt": cost_of_debt / 100,
            "debt_weight": debt_weight / 100, "wacc": wacc,
            "terminal_growth": terminal_growth / 100, "exit_multiple": exit_multiple,
            "use_perpetuity": use_perpetuity, "run": run_btn,
            "ticker": fetched.get("ticker", default_ticker),
            "week52_high": fetched.get("week52_high"),
            "week52_low": fetched.get("week52_low"),
        }


# ── Tab renderers ─────────────────────────────────────────────────────────────

def render_tab_dcf(params: dict, result: dict) -> None:
    section_header("DCF MODEL", "Free Cash Flow to Firm — Projected Financials")

    df = result["df"]
    display_df = df.copy()
    for col in ["Revenue", "EBITDA", "D&A", "EBIT", "NOPAT", "CapEx", "ΔNWC", "FCFF"]:
        display_df[col] = display_df[col].apply(fmt_currency)
    display_df["Year"] = display_df["Year"].apply(lambda y: f"Year {y}")
    st.dataframe(display_df.set_index("Year"), use_container_width=True)

    neg_years = df[df["FCFF"] < 0]["Year"].tolist()
    if neg_years:
        st.info(f"ℹ️ Negative free cash flow in years: {neg_years}.")

    st.plotly_chart(plot_fcff_waterfall(df), use_container_width=True)

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    ev = result["ev"]
    equity = result["equity_value"]
    price = result["implied_price"]
    tv_pct = result["tv_pct_ev"]

    col1.metric("Enterprise Value", fmt_billions(ev))
    col2.metric("Equity Value", fmt_billions(equity))
    col3.metric("Implied Share Price", fmt_currency(price))
    col4.metric("TV % of EV", fmt_pct(tv_pct))

    if tv_pct > 0.85:
        st.warning(f"⚠️ Terminal value is {tv_pct:.0%} of EV — heavily long-dated.")
    if equity < 0:
        st.error(f"❌ Equity value negative ({fmt_currency(equity)}). Debt exceeds EV.")

    upside = (price - params["current_price"]) / params["current_price"] if params["current_price"] > 0 else 0
    updown = "▲" if upside >= 0 else "▼"
    color = "#00C805" if upside >= 0 else "#FF3B3B"
    st.markdown(
        f"<p style='text-align:center;font-size:1rem;font-family:Source Code Pro,monospace'>"
        f"Implied vs Current: <span style='color:{color};font-weight:700'>"
        f"{updown} {abs(upside):.1%}</span> "
        f"({fmt_currency(params['current_price'])} → {fmt_currency(price)})</p>",
        unsafe_allow_html=True,
    )

    st.plotly_chart(plot_ev_bridge(result["pv_fcfs"], result["pv_tv"], params["net_debt"]),
                    use_container_width=True)


def render_tab_wacc(params: dict) -> None:
    section_header("WACC CALCULATOR", "Weighted Average Cost of Capital — CAPM")

    rf, beta, erp = params["rf"], params["beta"], params["erp"]
    cd, t, dw = params["cost_of_debt"], params["tax_rate"], params["debt_weight"]
    ew = 1 - dw
    ce = rf + beta * erp
    wacc = params["wacc"]
    after_tax_cd = cd * (1 - t)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Cost of Equity (CAPM)")
        st.markdown(
            f"| Component | Value |\n|---|---|\n"
            f"| Risk-Free Rate (Rf) | {fmt_pct(rf)} |\n"
            f"| Beta (β) | {beta:.2f} |\n"
            f"| Equity Risk Premium (ERP) | {fmt_pct(erp)} |\n"
            f"| **Cost of Equity = Rf + β × ERP** | **{fmt_pct(ce)}** |"
        )
    with col2:
        st.markdown("#### WACC Composition")
        st.markdown(
            f"| Component | Weight | Rate | Contribution |\n|---|---|---|---|\n"
            f"| Equity | {fmt_pct(ew)} | {fmt_pct(ce)} | {fmt_pct(ew * ce)} |\n"
            f"| Debt (after-tax) | {fmt_pct(dw)} | {fmt_pct(after_tax_cd)} | {fmt_pct(dw * after_tax_cd)} |\n"
            f"| **WACC** | **100%** | | **{fmt_pct(wacc)}** |"
        )

    st.markdown("---")
    st.markdown(
        f"<div style='background:#161B22;border:1px solid #1F6FEB;border-radius:6px;"
        f"padding:20px;text-align:center'>"
        f"<p style='color:#8B949E;font-size:0.8rem;text-transform:uppercase;"
        f"letter-spacing:0.12em;margin:0'>WEIGHTED AVERAGE COST OF CAPITAL</p>"
        f"<p style='color:#1F6FEB;font-size:2.5rem;font-weight:700;margin:8px 0'>{fmt_pct(wacc)}</p>"
        f"<p style='color:#8B949E;font-size:0.75rem;margin:0'>"
        f"Ce = {fmt_pct(rf)} + {beta:.2f} × {fmt_pct(erp)} = {fmt_pct(ce)}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_tab_tv(params: dict, result: dict) -> None:
    section_header("TERMINAL VALUE", "Perpetuity Growth vs Exit Multiple")

    df = result["df"]
    fcf_n = float(df["FCFF"].iloc[-1])
    ebitda_n = float(df["EBITDA"].iloc[-1])
    wacc = params["wacc"]
    g = params["terminal_growth"]
    multiple = params["exit_multiple"]
    n = params["n_years"]

    try:
        tv_perp = terminal_value_perpetuity(fcf_n, g, wacc)
        pv_perp = tv_perp / (1 + wacc) ** n
    except ValueError:
        tv_perp = float("nan")
        pv_perp = float("nan")

    tv_exit = terminal_value_exit(ebitda_n, multiple)
    pv_exit = tv_exit / (1 + wacc) ** n

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Perpetuity Growth Method")
        st.markdown(
            f"| Item | Value |\n|---|---|\n"
            f"| Final Year FCF (Year {n}) | {fmt_currency(fcf_n)} |\n"
            f"| Terminal Growth Rate (g) | {fmt_pct(g)} |\n"
            f"| WACC | {fmt_pct(wacc)} |\n"
            f"| Terminal Value | **{fmt_billions(tv_perp) if not np.isnan(tv_perp) else 'N/A'}** |\n"
            f"| PV of Terminal Value | **{fmt_billions(pv_perp) if not np.isnan(pv_perp) else 'N/A'}** |"
        )
    with col2:
        st.markdown("#### Exit Multiple Method")
        st.markdown(
            f"| Item | Value |\n|---|---|\n"
            f"| Final Year EBITDA (Year {n}) | {fmt_currency(ebitda_n)} |\n"
            f"| EV/EBITDA Exit Multiple | {multiple:.1f}x |\n"
            f"| Terminal Value | **{fmt_billions(tv_exit)}** |\n"
            f"| PV of Terminal Value | **{fmt_billions(pv_exit)}** |"
        )

    active = "Perpetuity Growth" if params["use_perpetuity"] else "Exit Multiple"
    st.info(f"ℹ️ Currently using: **{active}** method.")

    if not np.isnan(pv_perp) and not np.isnan(pv_exit):
        st.plotly_chart(plot_terminal_value_comparison(pv_perp, pv_exit), use_container_width=True)

    ev = result["ev"]
    tv_pct = result["pv_tv"] / ev if ev else 0
    st.metric("Active Terminal Value (PV)", fmt_billions(result["pv_tv"]), f"{tv_pct:.0%} of EV")
    if tv_pct > 0.85:
        st.warning(f"⚠️ Terminal value is {tv_pct:.0%} of EV — heavily sensitive to long-term assumptions.")


def render_tab_sensitivity(params: dict, result: dict) -> None:
    section_header("SENSITIVITY TABLE", "Implied Share Price — WACC × Terminal Growth / Exit Multiple")

    wacc_base = params["wacc"]
    tg_base = params["terminal_growth"]
    n_steps = 5

    sens_mode = st.radio("Sensitivity axes",
                          ["WACC × Terminal Growth Rate", "WACC × Exit Multiple"], horizontal=True)

    st.markdown(
        "<p style='font-size:0.78rem;color:#8B949E'>🟢 Green = above current price  "
        "🔴 Red = below current price  ⬛ Highlighted = current assumption</p>",
        unsafe_allow_html=True,
    )

    wacc_range = [max(0.03, wacc_base + (i - n_steps // 2) * 0.01) for i in range(n_steps)]

    dcf_inputs = DCFInputs(
        base_revenue=params["revenue"], growth_rates=params["growth_rates"],
        ebitda_margin=params["ebitda_margin"], da_pct=params["da_pct"],
        capex_pct=params["capex_pct"], nwc_pct=params["nwc_pct"],
        tax_rate=params["tax_rate"], wacc=wacc_base, terminal_growth=tg_base,
        exit_multiple=params["exit_multiple"], use_perpetuity=params["use_perpetuity"],
        net_debt=params["net_debt"], shares=params["shares"],
        current_price=params["current_price"],
    )

    if sens_mode == "WACC × Terminal Growth Rate":
        tg_range = [tg_base + (i - n_steps // 2) * 0.005 for i in range(n_steps)]
        tg_range = [max(0.0, min(0.049, g)) for g in tg_range if g < min(wacc_range)]
        if not tg_range:
            st.warning("⚠️ Cannot generate table — all terminal growth values exceed WACC.")
            return

        with st.spinner("Building sensitivity table…"):
            table = sensitivity_table(dcf_inputs, wacc_range, tg_range)
        st.markdown(build_sensitivity_html(table, params["current_price"], wacc_base, tg_base,
                                            row_label="g", col_label="WACC"),
                    unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        try:
            st.plotly_chart(plot_sensitivity_heatmap(table, params["current_price"]),
                            use_container_width=True)
        except Exception as e:
            st.warning(f"⚠️ Chart could not render. ({e})")
    else:
        multiple_range = [max(1.0, params["exit_multiple"] + (i - n_steps // 2) * 2.0) for i in range(n_steps)]
        with st.spinner("Building sensitivity table…"):
            table = sensitivity_table_exit_multiple(dcf_inputs, wacc_range, multiple_range)
        st.markdown(build_sensitivity_html(table, params["current_price"], wacc_base, tg_base,
                                            row_label="Exit Multiple", col_label="WACC"),
                    unsafe_allow_html=True)


def render_tab_football(params: dict, result: dict) -> None:
    section_header("FOOTBALL FIELD", "Valuation Range Summary — Investment Banking Style")

    wacc_base = params["wacc"]
    ranges = []

    try:
        res_low = run_dcf(DCFInputs(**{**params_to_dcf(params), "wacc": max(0.03, wacc_base - 0.01)}))
        res_high = run_dcf(DCFInputs(**{**params_to_dcf(params), "wacc": min(0.30, wacc_base + 0.01)}))
        lo = min(res_low["implied_price"], res_high["implied_price"])
        hi = max(res_low["implied_price"], res_high["implied_price"])
        if lo < hi:
            ranges.append({"label": "DCF (WACC ±1%)", "low": lo, "high": hi})
    except Exception:
        pass

    st.markdown("**Comparable Companies (EV/EBITDA)**")
    cc1, cc2 = st.columns(2)
    comps_low = cc1.number_input("Comps Low Multiple", 1.0, 50.0, 8.0, 0.5)
    comps_high = cc2.number_input("Comps High Multiple", 1.0, 50.0, 14.0, 0.5)
    ebitda_n = float(result["df"]["EBITDA"].iloc[-1])
    nd = params["net_debt"]
    sh = params["shares"]
    if ebitda_n > 0 and sh > 0:
        for mult_lo, mult_hi, label in [(comps_low, comps_high, "Comparable Companies")]:
            lo = (ebitda_n * mult_lo - nd) / sh
            hi = (ebitda_n * mult_hi - nd) / sh
            if lo < hi:
                ranges.append({"label": label, "low": lo, "high": hi})

    st.markdown("**Precedent Transactions (EV/EBITDA)**")
    pt1, pt2 = st.columns(2)
    prec_low = pt1.number_input("Precedents Low Multiple", 1.0, 50.0, 10.0, 0.5)
    prec_high = pt2.number_input("Precedents High Multiple", 1.0, 50.0, 18.0, 0.5)
    if ebitda_n > 0 and sh > 0:
        lo = (ebitda_n * prec_low - nd) / sh
        hi = (ebitda_n * prec_high - nd) / sh
        if lo < hi:
            ranges.append({"label": "Precedent Transactions", "low": lo, "high": hi})

    w52_hi = params.get("week52_high")
    w52_lo = params.get("week52_low")
    if w52_hi and w52_lo and w52_lo < w52_hi:
        ranges.append({"label": "52-Week Price Range", "low": w52_lo, "high": w52_hi})
    elif not (w52_hi and w52_lo):
        st.info("ℹ️ 52-week range not available — fetch a ticker first.")

    if not ranges:
        st.warning("⚠️ No valuation ranges. Run a valuation first.")
        return

    try:
        st.plotly_chart(plot_football_field(ranges, params["current_price"]), use_container_width=True)
    except Exception as e:
        st.warning(f"⚠️ Chart error: {e}")
        for r in ranges:
            st.write(f"**{r['label']}**: ${r['low']:,.2f} – ${r['high']:,.2f}")


def render_tab_monte_carlo(params: dict) -> None:
    section_header("MONTE CARLO SIMULATION", "Probabilistic Valuation — Correlated Parameters")

    n_sims = st.slider("Number of Simulations", 1_000, 50_000, 10_000, 1_000)
    if n_sims > 25_000:
        st.warning("⚠️ > 25,000 simulations may be slow.")

    run_mc = st.button("▶  RUN MONTE CARLO", type="primary")
    if not run_mc:
        st.info("ℹ️ Click **Run Monte Carlo** to simulate.")
        return

    mc_inputs = MonteCarloInputs(
        base_revenue=params["revenue"],
        growth_rate=params["growth_rates"][0] if params["growth_rates"] else 0.05,
        ebitda_margin=params["ebitda_margin"], da_pct=params["da_pct"],
        capex_pct=params["capex_pct"], nwc_pct=params["nwc_pct"],
        tax_rate=params["tax_rate"], wacc=params["wacc"],
        terminal_growth=params["terminal_growth"], exit_multiple=params["exit_multiple"],
        use_perpetuity=params["use_perpetuity"], net_debt=params["net_debt"],
        shares=params["shares"], current_price=params["current_price"],
        n_years=params["n_years"],
    )

    with st.spinner(f"Running {n_sims:,} simulations…"):
        try:
            mc = run_dcf_simulation(mc_inputs, n_sims=n_sims)
        except Exception as e:
            st.error(f"❌ Simulation failed: {e}")
            return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mean Price", fmt_currency(mc.mean))
    col2.metric("Median Price", fmt_currency(mc.median))
    col3.metric("Std Deviation", fmt_currency(mc.std))
    col4.metric("Prob. of Upside", fmt_pct(mc.prob_upside))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("P10 (Bear)", fmt_currency(mc.p10))
    col6.metric("P25", fmt_currency(mc.p25))
    col7.metric("P75", fmt_currency(mc.p75))
    col8.metric("P90 (Bull)", fmt_currency(mc.p90))

    st.metric("Value at Risk (5th pctile)", fmt_currency(mc.var5))

    try:
        st.plotly_chart(
            plot_monte_carlo_histogram(mc.prices, mc.p10, mc.p25, mc.p50, mc.p75, mc.p90,
                                        params["current_price"]),
            use_container_width=True,
        )
    except Exception as e:
        st.warning(f"⚠️ Histogram error: {e}")

    st.dataframe(
        pd.DataFrame({
            "Percentile": ["P10", "P25", "P50 (Median)", "P75", "P90"],
            "Implied Price": [fmt_currency(mc.p10), fmt_currency(mc.p25),
                               fmt_currency(mc.p50), fmt_currency(mc.p75), fmt_currency(mc.p90)],
        }).set_index("Percentile"),
        use_container_width=True,
    )


def params_to_dcf(params: dict) -> dict:
    """Extract DCFInputs fields from the params dict."""
    return dict(
        base_revenue=params["revenue"], growth_rates=params["growth_rates"],
        ebitda_margin=params["ebitda_margin"], da_pct=params["da_pct"],
        capex_pct=params["capex_pct"], nwc_pct=params["nwc_pct"],
        tax_rate=params["tax_rate"], wacc=params["wacc"],
        terminal_growth=params["terminal_growth"], exit_multiple=params["exit_multiple"],
        use_perpetuity=params["use_perpetuity"], net_debt=params["net_debt"],
        shares=params["shares"], current_price=params["current_price"],
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(
        "<h1 style='text-align:center;font-size:1.8rem;letter-spacing:0.1em;"
        "text-transform:uppercase;color:#1F6FEB;margin-bottom:0'>"
        "⬛ DCF VALUATION</h1>"
        "<p style='text-align:center;color:#8B949E;font-size:0.8rem;"
        "letter-spacing:0.15em;margin-top:4px'>"
        "DISCOUNTED CASH FLOW · M&A GRADE · TERMINAL VALUE · MONTE CARLO</p>",
        unsafe_allow_html=True,
    )

    params = render_sidebar()
    if params is None:
        st.stop()

    if params["run"]:
        with st.spinner("Running DCF model…"):
            try:
                dcf_inputs = DCFInputs(**params_to_dcf(params))
                result = run_dcf(dcf_inputs)

                if np.isnan(result["ev"]) or np.isinf(result["ev"]):
                    st.error("❌ Calculation produced invalid results. Check inputs.")
                    st.stop()
                if abs(result["ev"]) > 1e15:
                    st.warning("⚠️ Enterprise value exceeds $1 quadrillion — inputs may be unrealistic.")

                st.session_state["dcf_result"] = result
                st.session_state["dcf_inputs"] = dcf_inputs
                st.session_state["valuation_run"] = True
                st.session_state["last_params"] = params

            except ValueError as e:
                st.error(f"❌ {e}")
                st.stop()
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")
                st.stop()

    if not st.session_state["valuation_run"]:
        st.info("ℹ️ Configure parameters in the sidebar and click **▶ RUN VALUATION**.")
        st.stop()

    result = st.session_state["dcf_result"]
    saved_params = st.session_state.get("last_params", params)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 DCF Model", "⚖️ WACC Calculator", "🔭 Terminal Value",
        "🗂️ Sensitivity Table", "🏈 Football Field", "🎲 Monte Carlo",
    ])

    with tab1:
        try:
            render_tab_dcf(saved_params, result)
        except Exception as e:
            st.error(f"❌ {e}")

    with tab2:
        try:
            render_tab_wacc(saved_params)
        except Exception as e:
            st.error(f"❌ {e}")

    with tab3:
        try:
            render_tab_tv(saved_params, result)
        except Exception as e:
            st.error(f"❌ {e}")

    with tab4:
        try:
            render_tab_sensitivity(saved_params, result)
        except Exception as e:
            st.error(f"❌ {e}")

    with tab5:
        try:
            render_tab_football(saved_params, result)
        except Exception as e:
            st.error(f"❌ {e}")

    with tab6:
        try:
            render_tab_monte_carlo(saved_params)
        except Exception as e:
            st.error(f"❌ {e}")

    # ── AI Analyst ────────────────────────────────────────────────────────────
    st.markdown("---")
    section_header("AI ANALYST", "Powered by Claude")

    context = {
        "ticker": saved_params.get("ticker", ""),
        "implied_price": round(result["implied_price"], 2),
        "current_price": round(saved_params["current_price"], 2),
        "ev": round(result["ev"], 0),
        "equity_value": round(result["equity_value"], 0),
        "wacc_pct": round(saved_params["wacc"] * 100, 2),
        "terminal_growth_pct": round(saved_params["terminal_growth"] * 100, 2),
        "tv_pct_ev": round(result["tv_pct_ev"] * 100, 1),
        "exit_multiple": saved_params["exit_multiple"],
        "use_perpetuity": saved_params["use_perpetuity"],
        "n_years": saved_params["n_years"],
        "ebitda_margin_pct": round(saved_params["ebitda_margin"] * 100, 1),
    }

    with st.expander("📊 Generate analyst brief", expanded=False):
        if st.button("Generate Brief", key="dcf_gen_brief"):
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
    question = st.text_input("Ask a question about this valuation…", key="dcf_analyst_q",
                              placeholder="e.g. How sensitive is this to terminal growth?")
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


main()
