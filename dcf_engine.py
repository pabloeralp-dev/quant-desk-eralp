"""DCF calculation engine — all pure functions, no Streamlit imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


class ValidationError(Exception):
    """Raised when input parameters fail validation."""


def compute_wacc(
    rf: float,
    beta: float,
    erp: float,
    cost_of_debt: float,
    tax_rate: float,
    debt_weight: float,
) -> float:
    """Compute Weighted Average Cost of Capital via CAPM."""
    equity_weight = 1.0 - debt_weight
    cost_of_equity = rf + beta * erp
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)


def compute_fcff(
    revenue: float,
    ebitda_margin: float,
    tax_rate: float,
    da_pct: float,
    capex_pct: float,
    nwc_pct: float,
) -> float:
    """Compute Free Cash Flow to Firm: NOPAT + D&A - CapEx - ΔNWC."""
    ebitda = revenue * ebitda_margin
    da = revenue * da_pct
    ebit = ebitda - da
    nopat = ebit * (1 - tax_rate)
    capex = revenue * capex_pct
    delta_nwc = revenue * nwc_pct
    return nopat + da - capex - delta_nwc


def project_financials(
    base_revenue: float,
    growth_rates: List[float],
    ebitda_margin: float,
    da_pct: float,
    capex_pct: float,
    nwc_pct: float,
    tax_rate: float,
) -> pd.DataFrame:
    """Project Revenue → EBITDA → EBIT → NOPAT → FCFF for each forecast year."""
    rows = []
    revenue = base_revenue
    for i, g in enumerate(growth_rates, start=1):
        revenue = revenue * (1 + g)
        ebitda = revenue * ebitda_margin
        da = revenue * da_pct
        ebit = ebitda - da
        nopat = ebit * (1 - tax_rate)
        capex = revenue * capex_pct
        delta_nwc = revenue * nwc_pct
        fcff = nopat + da - capex - delta_nwc
        rows.append({
            "Year": i,
            "Revenue": revenue,
            "EBITDA": ebitda,
            "D&A": da,
            "EBIT": ebit,
            "NOPAT": nopat,
            "CapEx": capex,
            "ΔNWC": delta_nwc,
            "FCFF": fcff,
        })
    return pd.DataFrame(rows)


def terminal_value_perpetuity(fcf_n: float, growth: float, wacc: float) -> float:
    """Gordon Growth Model: TV = FCF_n × (1+g) / (WACC - g)."""
    if wacc <= 0:
        raise ValueError("WACC must be positive.")
    if growth >= wacc:
        raise ValueError(
            f"Terminal growth ({growth:.2%}) must be less than WACC ({wacc:.2%})."
        )
    return fcf_n * (1 + growth) / (wacc - growth)


def terminal_value_exit(ebitda_n: float, multiple: float) -> float:
    """Exit multiple method: TV = EBITDA_n × multiple."""
    return ebitda_n * multiple


def compute_ev(fcfs: List[float], wacc: float, terminal_value: float) -> float:
    """Enterprise Value = PV of FCFs + PV of terminal value."""
    n = len(fcfs)
    pv_fcfs = sum(cf / (1 + wacc) ** t for t, cf in enumerate(fcfs, start=1))
    pv_tv = terminal_value / (1 + wacc) ** n
    return pv_fcfs + pv_tv


def compute_equity_value(ev: float, net_debt: float) -> float:
    """Equity value = EV - net debt."""
    return ev - net_debt


def compute_implied_price(equity_value: float, shares: float) -> float:
    """Implied share price = equity value / shares outstanding."""
    if shares <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")
    return equity_value / shares


@dataclass
class DCFInputs:
    """All inputs needed to run a DCF model."""
    base_revenue: float
    growth_rates: List[float]
    ebitda_margin: float
    da_pct: float
    capex_pct: float
    nwc_pct: float
    tax_rate: float
    wacc: float
    terminal_growth: float
    exit_multiple: float
    use_perpetuity: bool
    net_debt: float
    shares: float
    current_price: float


def run_dcf(inputs: DCFInputs) -> dict:
    """Run the full DCF pipeline. Returns df, ev, equity_value, implied_price, etc."""
    df = project_financials(
        inputs.base_revenue, inputs.growth_rates, inputs.ebitda_margin,
        inputs.da_pct, inputs.capex_pct, inputs.nwc_pct, inputs.tax_rate,
    )

    fcf_n = df["FCFF"].iloc[-1]
    ebitda_n = df["EBITDA"].iloc[-1]

    if inputs.use_perpetuity:
        tv = terminal_value_perpetuity(fcf_n, inputs.terminal_growth, inputs.wacc)
    else:
        tv = terminal_value_exit(ebitda_n, inputs.exit_multiple)

    fcfs = df["FCFF"].tolist()
    n = len(fcfs)
    pv_fcfs = sum(cf / (1 + inputs.wacc) ** t for t, cf in enumerate(fcfs, start=1))
    pv_tv = tv / (1 + inputs.wacc) ** n
    ev = pv_fcfs + pv_tv
    tv_pct_ev = pv_tv / ev if ev != 0 else 0.0

    equity_value = compute_equity_value(ev, inputs.net_debt)
    implied_price = compute_implied_price(equity_value, inputs.shares)

    return {
        "df": df,
        "ev": ev,
        "pv_fcfs": pv_fcfs,
        "pv_tv": pv_tv,
        "terminal_value": tv,
        "tv_pct_ev": tv_pct_ev,
        "equity_value": equity_value,
        "implied_price": implied_price,
    }


def sensitivity_table(
    inputs: DCFInputs,
    wacc_values: List[float],
    tg_values: List[float],
) -> pd.DataFrame:
    """2D sensitivity: implied share price vs WACC (cols) × terminal growth (rows)."""
    data = {}
    for w in wacc_values:
        col = []
        for g in tg_values:
            try:
                override = DCFInputs(**{**inputs.__dict__, "wacc": w, "terminal_growth": g})
                col.append(run_dcf(override)["implied_price"])
            except (ValueError, ZeroDivisionError):
                col.append(float("nan"))
        data[w] = col
    df = pd.DataFrame(data, index=tg_values)
    df.index.name = "Terminal Growth"
    df.columns.name = "WACC"
    return df


def sensitivity_table_exit_multiple(
    inputs: DCFInputs,
    wacc_values: List[float],
    multiple_values: List[float],
) -> pd.DataFrame:
    """2D sensitivity: implied share price vs WACC (cols) × exit multiple (rows)."""
    data = {}
    for w in wacc_values:
        col = []
        for m in multiple_values:
            try:
                override = DCFInputs(**{**inputs.__dict__, "wacc": w, "exit_multiple": m, "use_perpetuity": False})
                col.append(run_dcf(override)["implied_price"])
            except (ValueError, ZeroDivisionError):
                col.append(float("nan"))
        data[w] = col
    df = pd.DataFrame(data, index=multiple_values)
    df.index.name = "Exit Multiple"
    df.columns.name = "WACC"
    return df
