"""Data fetching — yfinance for fundamentals, Finnhub for live quotes."""

from __future__ import annotations

import os
import re
import time
from typing import Optional

import streamlit as st
import yfinance as yf


def _clean_ticker(ticker: str) -> str:
    """Sanitise and normalise a ticker symbol."""
    cleaned = ticker.strip().upper()[:10]
    if not cleaned:
        raise ValueError("Ticker symbol cannot be empty.")
    if not re.match(r"^[A-Z0-9.]+$", cleaned):
        raise ValueError(f"Invalid ticker symbol: '{ticker}'. Use letters, numbers, and dots only.")
    return cleaned


@st.cache_data(ttl=300)
def fetch_live_price(ticker: str) -> dict:
    """Fetch live quote from Finnhub (price, change%, market status).

    Returns dict with keys: ticker, price, change_pct, market_open, error.
    Never raises.
    """
    result: dict = {
        "ticker": ticker,
        "price": None,
        "change_pct": None,
        "market_open": False,
        "error": None,
    }

    api_key = os.getenv("FINNHUB_API_KEY", "")
    if not api_key:
        result["error"] = "FINNHUB_API_KEY not configured"
        return result

    try:
        cleaned = _clean_ticker(ticker)
    except ValueError as e:
        result["error"] = str(e)
        return result

    result["ticker"] = cleaned

    try:
        import finnhub
        fc = finnhub.Client(api_key=api_key)
        quote = fc.quote(cleaned)
        current = quote.get("c")
        if not current:
            result["error"] = f"No quote data for '{cleaned}'"
            return result
        result["price"] = float(current)
        result["change_pct"] = float(quote.get("dp", 0.0)) / 100
        # Market open heuristic: last trade timestamp within 15 min
        import time as _time
        ts = quote.get("t", 0)
        result["market_open"] = bool(ts and (_time.time() - ts) < 900)
    except Exception as exc:
        result["error"] = str(exc)

    return result


@st.cache_data(ttl=300)
def fetch_ticker_data(ticker: str) -> dict:
    """Fetch financial data for a given ticker from yfinance.

    Retries once on failure. Never raises.

    Returns dict with keys: ticker, beta, current_price, week52_high,
    week52_low, shares_outstanding, net_debt, revenue, ebitda, error.
    """
    result: dict = {
        "ticker": ticker,
        "beta": None,
        "current_price": None,
        "week52_high": None,
        "week52_low": None,
        "shares_outstanding": None,
        "net_debt": None,
        "revenue": None,
        "ebitda": None,
        "error": None,
    }

    try:
        cleaned = _clean_ticker(ticker)
    except ValueError as e:
        result["error"] = str(e)
        return result

    result["ticker"] = cleaned

    for attempt in range(2):
        try:
            stock = yf.Ticker(cleaned)
            info = stock.info or {}

            if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
                try:
                    fi = stock.fast_info
                    result["current_price"] = _safe_float(getattr(fi, "last_price", None))
                    result["week52_high"] = _safe_float(getattr(fi, "year_high", None))
                    result["week52_low"] = _safe_float(getattr(fi, "year_low", None))
                    result["shares_outstanding"] = _safe_int(getattr(fi, "shares", None))
                except Exception:
                    pass
                if result["current_price"] is None:
                    result["error"] = f"Ticker '{cleaned}' not found or has no price data."
                    return result
            else:
                result["current_price"] = _safe_float(
                    info.get("currentPrice") or info.get("regularMarketPrice")
                )
                result["week52_high"] = _safe_float(info.get("fiftyTwoWeekHigh"))
                result["week52_low"] = _safe_float(info.get("fiftyTwoWeekLow"))
                result["shares_outstanding"] = _safe_int(info.get("sharesOutstanding"))
                result["beta"] = _safe_float(info.get("beta"))
                result["revenue"] = _safe_float(info.get("totalRevenue"))
                result["ebitda"] = _safe_float(info.get("ebitda"))

                total_debt = _safe_float(info.get("totalDebt")) or 0.0
                cash = _safe_float(info.get("cashAndCashEquivalents") or info.get("totalCash")) or 0.0
                result["net_debt"] = total_debt - cash

            break

        except Exception as exc:
            if attempt == 0:
                time.sleep(2)
            else:
                result["error"] = f"Could not fetch data for '{cleaned}': {exc}"

    return result


def _safe_float(value) -> Optional[float]:
    try:
        v = float(value)
        return v if v == v else None  # NaN check
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
