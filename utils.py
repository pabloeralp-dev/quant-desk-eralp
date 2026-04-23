"""Formatting helpers for QuantDesk."""

from __future__ import annotations


def fmt_currency(val: float) -> str:
    """$1,234.56"""
    if val is None:
        return "N/A"
    formatted = f"{abs(val):,.2f}"
    return f"-${formatted}" if val < 0 else f"${formatted}"


def fmt_millions(val: float) -> str:
    """$1,234.5M"""
    if val is None:
        return "N/A"
    return f"${val / 1_000_000:,.1f}M"


def fmt_billions(val: float) -> str:
    """$1.23B"""
    if val is None:
        return "N/A"
    return f"${val / 1_000_000_000:,.2f}B"


def fmt_pct(val: float, decimals: int = 2) -> str:
    """10.50% — expects decimal fraction (0.105 → 10.50%)"""
    if val is None:
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def fmt_ratio(val: float) -> str:
    """0.6368 — four decimal places, no suffix"""
    if val is None:
        return "N/A"
    return f"{val:.4f}"


def fmt_multiple(val: float, decimals: int = 1) -> str:
    """10.0x"""
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}x"


def fmt_price(val: float) -> str:
    """$100.00"""
    if val is None:
        return "N/A"
    return f"${val:.2f}"
