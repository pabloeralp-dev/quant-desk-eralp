"""Custom CSS injection for the QuantDesk dark terminal aesthetic."""

from __future__ import annotations

import streamlit as st

# ── Design token constants (mirrors CLAUDE.md palette) ──────────────────────
ACCENT_BLUE = "#1F6FEB"
POSITIVE = "#00C805"
NEGATIVE = "#FF3B3B"
SECONDARY = "#8B949E"
BORDER = "#30363D"
CARD_BG = "#161B22"
BG = "#0A0A0F"
TEXT = "#E8EAF0"


def inject_css() -> None:
    """Inject custom CSS to enforce the dark terminal aesthetic."""
    st.markdown(
        """
        <style>
        /* ── Base font ── */
        @import url('https://fonts.googleapis.com/css2?family=Source+Code+Pro:wght@300;400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Source Code Pro', 'Courier New', monospace !important;
        }

        /* ── Main background ── */
        .stApp {
            background-color: #0A0A0F;
        }

        /* ── Main container ── */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            background-color: #0A0A0F;
        }

        /* ── Sidebar ── */
        section[data-testid="stSidebar"] {
            background-color: #0F1117 !important;
            border-right: 1px solid #1F6FEB;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
        }
        /* All text inside sidebar: bright white */
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div,
        section[data-testid="stSidebar"] .stMarkdown {
            color: #FFFFFF !important;
        }
        section[data-testid="stSidebar"] .stMarkdown p {
            color: #CCCCCC !important;
            font-size: 0.82rem;
        }

        /* ── Global text ── */
        p, span, div, label {
            color: #FFFFFF;
        }

        /* ── Headers ── */
        h1 { color: #1F6FEB !important; font-weight: 700; letter-spacing: 0.06em; font-size: 1.6rem !important; }
        h2 { color: #FFFFFF !important; font-weight: 600; letter-spacing: 0.03em; font-size: 1.2rem !important; }
        h3 { color: #CCCCCC !important; font-weight: 400; font-size: 1rem !important; }

        /* ── Metric cards ── */
        [data-testid="metric-container"] {
            background-color: #111318;
            border: 1px solid #1F6FEB;
            border-radius: 3px;
            padding: 0.75rem 1rem;
        }
        [data-testid="metric-container"] label {
            color: #8B949E !important;
            font-size: 0.72rem !important;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        [data-testid="metric-container"] [data-testid="stMetricValue"] {
            color: #FFFFFF !important;
            font-size: 1.4rem !important;
            font-weight: 700;
        }

        /* ── Tabs ── */
        button[data-baseweb="tab"] {
            font-family: 'Source Code Pro', monospace !important;
            font-size: 0.8rem !important;
            letter-spacing: 0.05em;
            color: #8B949E !important;
            background: transparent !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #1F6FEB !important;
            border-bottom: 2px solid #1F6FEB !important;
        }

        /* ── Buttons ── */
        .stButton > button {
            background-color: #0A0A0F;
            color: #1F6FEB;
            border: 1px solid #1F6FEB;
            border-radius: 2px;
            font-family: 'Source Code Pro', monospace !important;
            font-size: 0.82rem;
            letter-spacing: 0.1em;
            font-weight: 700;
            padding: 0.5rem 1.5rem;
            text-transform: uppercase;
            transition: all 0.1s ease;
        }
        .stButton > button:hover {
            background-color: #1F6FEB;
            color: #000000;
        }

        /* ── Input widgets ── */
        .stNumberInput input, .stTextInput input {
            background-color: #111318 !important;
            color: #FFFFFF !important;
            border: 1px solid #30363D !important;
            border-radius: 2px;
            font-family: 'Source Code Pro', monospace !important;
        }
        .stNumberInput input:focus, .stTextInput input:focus {
            border-color: #1F6FEB !important;
        }

        /* ── Sliders ── */
        .stSlider [data-baseweb="slider"] div[role="slider"] {
            background-color: #1F6FEB !important;
        }
        .stSlider p { color: #FFFFFF !important; }

        /* ── Radio ── */
        .stRadio label { color: #CCCCCC !important; }

        /* ── Select / dropdown ── */
        .stSelectbox label { color: #CCCCCC !important; }

        /* ── Info / warning / error boxes ── */
        .stAlert {
            border-radius: 2px;
            font-family: 'Source Code Pro', monospace !important;
            font-size: 0.82rem;
        }

        /* ── Dividers ── */
        hr { border-color: #222233; }

        /* ── Dataframes ── */
        .stDataFrame { border: 1px solid #30363D; }

        /* ── Expanders ── */
        details summary {
            color: #8B949E !important;
            font-size: 0.85rem;
        }

        /* ── Custom sensitivity table ── */
        .sensitivity-table {
            font-family: 'Source Code Pro', monospace;
            font-size: 0.78rem;
            border-collapse: collapse;
            width: 100%;
        }
        .sensitivity-table th {
            background-color: #111318;
            color: #8B949E;
            padding: 6px 10px;
            text-align: center;
            border: 1px solid #30363D;
            letter-spacing: 0.06em;
        }
        .sensitivity-table td {
            padding: 5px 10px;
            text-align: center;
            border: 1px solid #222233;
            font-weight: 400;
        }
        .sensitivity-table td.highlight {
            border: 2px solid #1F6FEB !important;
            font-weight: 700;
        }

        /* ── Scrollbar ── */
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: #0A0A0F; }
        ::-webkit-scrollbar-thumb { background: #30363D; border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: #1F6FEB; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    """Render a styled section header."""
    st.markdown(f"### {title}")
    if subtitle:
        st.markdown(
            f"<p style='color:#8B949E;font-size:0.8rem;margin-top:-0.5rem;"
            f"font-family:Source Code Pro,monospace;letter-spacing:0.04em'>{subtitle}</p>",
            unsafe_allow_html=True,
        )


def build_sensitivity_html(
    df,
    current_price: float,
    base_wacc: float,
    base_tg: float,
    row_label: str = "Terminal Growth",
    col_label: str = "WACC",
) -> str:
    """Build a color-coded HTML sensitivity table.

    Green = above current price, red = below. Highlighted cell = current assumption.
    """
    import math

    def cell_color(price: float) -> tuple[str, str]:
        if math.isnan(price):
            return "#161B22", "#666"
        if current_price <= 0:
            return "#161B22", "#E8EAF0"
        ratio = price / current_price
        if ratio >= 1.2:
            bg = "#0D3320"
            fg = "#00C805"
        elif ratio >= 1.05:
            bg = "#0D2818"
            fg = "#2ECC71"
        elif ratio >= 0.95:
            bg = "#161B22"
            fg = "#E8EAF0"
        elif ratio >= 0.8:
            bg = "#2E1010"
            fg = "#FF3B3B"
        else:
            bg = "#3A0A0A"
            fg = "#FF3B3B"
        return bg, fg

    rows = list(df.index)
    cols = list(df.columns)

    html = ['<table class="sensitivity-table">']
    html.append("<thead><tr>")
    html.append(f"<th>{row_label} \\ {col_label}</th>")
    for c in cols:
        html.append(f"<th>{c:.1%}</th>")
    html.append("</tr></thead>")

    html.append("<tbody>")
    for r in rows:
        html.append("<tr>")
        html.append(f"<th>{r:.1%}</th>")
        for c in cols:
            price = df.loc[r, c]
            bg, fg = cell_color(price)
            is_highlight = abs(r - base_tg) < 1e-6 and abs(c - base_wacc) < 1e-6
            cls = ' class="highlight"' if is_highlight else ""
            if math.isnan(price):
                cell_text = "N/A"
            else:
                cell_text = f"${price:,.2f}"
            html.append(
                f'<td{cls} style="background-color:{bg};color:{fg}">{cell_text}</td>'
            )
        html.append("</tr>")
    html.append("</tbody></table>")

    return "\n".join(html)
