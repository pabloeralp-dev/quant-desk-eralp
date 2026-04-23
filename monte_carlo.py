"""Monte Carlo simulation engine for DCF valuation and options pricing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from scipy import stats

from dcf_engine import DCFInputs, run_dcf


# ── DCF Monte Carlo ──────────────────────────────────────────────────────────

@dataclass
class MonteCarloInputs:
    """Parameters for the DCF Monte Carlo simulation."""
    base_revenue: float
    growth_rate: float
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
    n_years: int = 5

    growth_spread: float = 0.05
    margin_spread_down: float = 0.05
    margin_spread_up: float = 0.03
    wacc_sigma: float = 0.01
    tg_spread: float = 0.01
    multiple_sigma: float = 2.0


@dataclass
class MonteCarloResults:
    """Output of the DCF Monte Carlo simulation."""
    prices: np.ndarray
    mean: float
    median: float
    std: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    var5: float
    prob_upside: float
    cv: float


def run_dcf_simulation(inputs: MonteCarloInputs, n_sims: int = 10_000) -> MonteCarloResults:
    """Run correlated DCF Monte Carlo simulation. Returns implied share price distribution.

    Uses Cholesky decomposition on a 4×4 correlation matrix (growth, margin, wacc, tg).
    Correlation structure: growth↔margin +0.3, wacc↔tg +0.2, all others independent.
    WACC > terminal growth enforced with 0.5% buffer in every simulation.
    """
    rng = np.random.default_rng()

    corr = np.array([
        [1.0, 0.3, 0.0, 0.0],
        [0.3, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.2],
        [0.0, 0.0, 0.2, 1.0],
    ])
    L = np.linalg.cholesky(corr)
    Z = rng.standard_normal((n_sims, 4))
    correlated = Z @ L.T
    u = stats.norm.cdf(correlated)

    g = inputs.growth_rate
    g_min, g_max = g - inputs.growth_spread, g + inputs.growth_spread
    c_g = (g - g_min) / (g_max - g_min) if g_max != g_min else 0.5
    growth_draws = stats.triang.ppf(u[:, 0], c=c_g, loc=g_min, scale=g_max - g_min)

    m = inputs.ebitda_margin
    m_min, m_max = m - inputs.margin_spread_down, m + inputs.margin_spread_up
    c_m = (m - m_min) / (m_max - m_min) if m_max != m_min else 0.5
    margin_draws = stats.triang.ppf(u[:, 1], c=c_m, loc=m_min, scale=m_max - m_min)

    wacc_draws = stats.truncnorm.ppf(u[:, 2], a=-3, b=3, loc=inputs.wacc, scale=inputs.wacc_sigma)

    tg_min, tg_max = inputs.terminal_growth - inputs.tg_spread, inputs.terminal_growth + inputs.tg_spread
    tg_draws = stats.uniform.ppf(u[:, 3], loc=tg_min, scale=tg_max - tg_min)
    tg_draws = np.minimum(tg_draws, wacc_draws - 0.005)

    em = inputs.exit_multiple
    em_lo = max(1.0, em - 6.0)
    em_hi = em + 6.0
    em_a = (em_lo - em) / inputs.multiple_sigma
    em_b = (em_hi - em) / inputs.multiple_sigma
    multiple_draws = stats.truncnorm.ppf(u[:, 0], a=em_a, b=em_b, loc=em, scale=inputs.multiple_sigma)

    prices = np.empty(n_sims)
    for i in range(n_sims):
        dcf_inputs = DCFInputs(
            base_revenue=inputs.base_revenue,
            growth_rates=[float(growth_draws[i])] * inputs.n_years,
            ebitda_margin=float(margin_draws[i]),
            da_pct=inputs.da_pct,
            capex_pct=inputs.capex_pct,
            nwc_pct=inputs.nwc_pct,
            tax_rate=inputs.tax_rate,
            wacc=float(wacc_draws[i]),
            terminal_growth=float(tg_draws[i]),
            exit_multiple=float(multiple_draws[i]),
            use_perpetuity=inputs.use_perpetuity,
            net_debt=inputs.net_debt,
            shares=inputs.shares,
            current_price=inputs.current_price,
        )
        try:
            prices[i] = run_dcf(dcf_inputs)["implied_price"]
        except Exception:
            prices[i] = float("nan")

    valid = prices[~np.isnan(prices)]
    if len(valid) == 0:
        valid = np.array([0.0])

    mean = float(np.mean(valid))
    median = float(np.median(valid))
    std = float(np.std(valid))
    p10, p25, p50, p75, p90 = (float(x) for x in np.percentile(valid, [10, 25, 50, 75, 90]))
    var5 = float(np.percentile(valid, 5))
    prob_upside = float(np.mean(valid > inputs.current_price)) if inputs.current_price > 0 else 0.0
    cv = std / mean if mean != 0 else 0.0

    return MonteCarloResults(
        prices=valid, mean=mean, median=median, std=std,
        p10=p10, p25=p25, p50=p50, p75=p75, p90=p90,
        var5=var5, prob_upside=prob_upside, cv=cv,
    )


# ── Options Monte Carlo (GBM) ────────────────────────────────────────────────

def run_options_simulation(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    n: int = 10_000,
    n_steps: int = 252,
) -> dict:
    """Simulate GBM paths and compute option P&L distribution.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry (years).
        r: Risk-free rate (decimal).
        sigma: Annualised volatility (decimal).
        option_type: 'call' or 'put'.
        n: Number of simulations.
        n_steps: Time steps per path (252 = daily).

    Returns:
        Dict with keys: sample_paths, terminal_prices, pnl, option_cost,
        pct_profit, p10, p50, p90, mean_pnl, mean_terminal.
    """
    from bs_engine import black_scholes_price

    rng = np.random.default_rng()
    dt = T / n_steps

    Z = rng.standard_normal((n, n_steps))
    log_returns = (r - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z
    paths = np.empty((n, n_steps + 1))
    paths[:, 0] = S
    paths[:, 1:] = S * np.exp(np.cumsum(log_returns, axis=1))

    terminal_prices = paths[:, -1]

    option_cost = black_scholes_price(S, K, sigma, r, T, option_type)

    if option_type == "call":
        payoffs = np.maximum(terminal_prices - K, 0.0)
    else:
        payoffs = np.maximum(K - terminal_prices, 0.0)

    pnl = payoffs - option_cost
    pct_profit = float(np.mean(pnl > 0))

    # Sample 200 representative paths for display
    sample_idx = rng.choice(n, size=min(200, n), replace=False)

    return {
        "sample_paths": paths[sample_idx],
        "terminal_prices": terminal_prices,
        "pnl": pnl,
        "option_cost": float(option_cost),
        "pct_profit": pct_profit,
        "p10": float(np.percentile(pnl, 10)),
        "p50": float(np.percentile(pnl, 50)),
        "p90": float(np.percentile(pnl, 90)),
        "mean_pnl": float(np.mean(pnl)),
        "mean_terminal": float(np.mean(terminal_prices)),
    }
