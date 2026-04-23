"""Black-Scholes pricing engine — price, Greeks, and implied vol for European options.

Model assumptions:
  1. Lognormal returns — asset prices follow geometric Brownian motion.
  2. Constant volatility over the option's life (no vol smile/term structure).
  3. Constant risk-free rate.
  4. No dividends.
  5. Frictionless markets — no transaction costs or bid-ask spread.
  6. Continuous trading — delta hedge can be rebalanced at any instant.
"""

from __future__ import annotations

import math

from scipy.optimize import brentq
from scipy.stats import norm

CALENDAR_DAYS_PER_YEAR = 365
ONE_PERCENT = 100

VOL_LOWER_BOUND = 1e-6
VOL_UPPER_BOUND = 10.0
PRICE_TOLERANCE = 1e-8
MAX_ITERATIONS = 500


class IVSolverError(ValueError):
    """Raised when implied vol cannot be found for the given market price."""


# ── Input validation ────────────────────────────────────────────────────────

def _validate_inputs(spot: float, strike: float, vol: float,
                     rate: float, time_to_expiry: float) -> None:
    if spot <= 0:
        raise ValueError(f"spot must be positive, got {spot}")
    if strike <= 0:
        raise ValueError(f"strike must be positive, got {strike}")
    if vol <= 0:
        raise ValueError(f"vol must be positive, got {vol}")
    if time_to_expiry <= 0:
        raise ValueError(f"time_to_expiry must be positive, got {time_to_expiry}")


def _compute_d1_d2(spot: float, strike: float, vol: float,
                   rate: float, time_to_expiry: float) -> tuple[float, float]:
    S, K, sigma, r, T = spot, strike, vol, rate, time_to_expiry
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    return d1, d2


# ── Pricing ──────────────────────────────────────────────────────────────────

def black_scholes_price(spot: float, strike: float, vol: float,
                        rate: float, time_to_expiry: float,
                        option_type: str) -> float:
    """Price a European call or put using Black-Scholes."""
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got '{option_type}'")
    _validate_inputs(spot, strike, vol, rate, time_to_expiry)

    S, K, sigma, r, T = spot, strike, vol, rate, time_to_expiry
    d1, d2 = _compute_d1_d2(S, K, sigma, r, T)
    discount = math.exp(-r * T)

    if option_type == "call":
        return S * norm.cdf(d1) - K * discount * norm.cdf(d2)
    return K * discount * norm.cdf(-d2) - S * norm.cdf(-d1)


# ── Greeks ───────────────────────────────────────────────────────────────────

def black_scholes_greeks(spot: float, strike: float, vol: float,
                         rate: float, time_to_expiry: float,
                         option_type: str) -> dict[str, float]:
    """Compute the five main Greeks for a European option.

    Conventions (strictly enforced):
      delta : per $1 spot move; positive for calls, negative for puts.
      gamma : per $1 spot move; always positive for long options.
      vega  : per 1% vol move (raw / 100).
      theta : per calendar day; negative for long options (raw / 365, no sign flip).
      rho   : per 1% rate move (raw / 100).
    """
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got '{option_type}'")
    _validate_inputs(spot, strike, vol, rate, time_to_expiry)

    S, K, sigma, r, T = spot, strike, vol, rate, time_to_expiry
    d1, d2 = _compute_d1_d2(S, K, sigma, r, T)
    sqrt_T = math.sqrt(T)
    discount = math.exp(-r * T)

    delta = norm.cdf(d1) if option_type == "call" else norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (S * sigma * sqrt_T)
    vega = S * norm.pdf(d1) * sqrt_T / ONE_PERCENT

    raw_theta1 = -(S * norm.pdf(d1) * sigma) / (2 * sqrt_T)
    if option_type == "call":
        raw_theta = raw_theta1 - r * K * discount * norm.cdf(d2)
    else:
        raw_theta = raw_theta1 + r * K * discount * norm.cdf(-d2)
    theta = raw_theta / CALENDAR_DAYS_PER_YEAR

    if option_type == "call":
        rho = K * T * discount * norm.cdf(d2) / ONE_PERCENT
    else:
        rho = -K * T * discount * norm.cdf(-d2) / ONE_PERCENT

    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


# ── Implied Volatility ───────────────────────────────────────────────────────

def implied_vol(market_price: float, spot: float, strike: float,
                rate: float, time_to_expiry: float,
                option_type: str) -> float:
    """Recover implied volatility from a market price using Brent's method.

    Raises IVSolverError if no vol in [1e-6, 10.0] reproduces the market price,
    or if the price violates no-arbitrage bounds.
    """
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got '{option_type}'")
    _validate_inputs(spot, strike, vol=0.01, rate=rate, time_to_expiry=time_to_expiry)

    if market_price <= 0:
        raise IVSolverError(f"market_price must be positive, got {market_price}")

    _check_no_arbitrage_bounds(market_price, spot, strike, rate, time_to_expiry, option_type)

    def objective(vol: float) -> float:
        return black_scholes_price(spot, strike, vol, rate, time_to_expiry, option_type) - market_price

    lo = objective(VOL_LOWER_BOUND)
    hi = objective(VOL_UPPER_BOUND)
    if lo * hi > 0:
        raise IVSolverError(
            f"No implied vol found in [{VOL_LOWER_BOUND}, {VOL_UPPER_BOUND}]. "
            f"Market price {market_price:.4f} may be outside the model's reachable range."
        )

    return float(brentq(objective, VOL_LOWER_BOUND, VOL_UPPER_BOUND,
                        xtol=PRICE_TOLERANCE, maxiter=MAX_ITERATIONS))


def _check_no_arbitrage_bounds(market_price: float, spot: float, strike: float,
                                rate: float, time_to_expiry: float,
                                option_type: str) -> None:
    discount = math.exp(-rate * time_to_expiry)
    if option_type == "call":
        lower = max(spot - strike * discount, 0.0)
        upper = spot
    else:
        lower = max(strike * discount - spot, 0.0)
        upper = strike * discount

    if market_price < lower - 1e-6:
        raise IVSolverError(
            f"{option_type} price {market_price:.4f} is below no-arbitrage lower bound "
            f"{lower:.4f} (intrinsic value)."
        )
    if market_price > upper + 1e-6:
        raise IVSolverError(
            f"{option_type} price {market_price:.4f} exceeds no-arbitrage upper bound {upper:.4f}."
        )
