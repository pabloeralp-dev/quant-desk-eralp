# CLAUDE.md — QuantDesk

## Project Overview

QuantDesk is a professional quantitative finance dashboard built with Python and Streamlit. It combines two tools into one unified app:

1. **Black-Scholes Options Pricer** — pricing, Greeks, heatmaps, Monte Carlo
2. **DCF Valuation Engine** — cash flow projections, WACC, terminal value, sensitivity tables

Bloomberg dark terminal aesthetic throughout. AI analyst commentary powered by the Anthropic API.

---

## Setup

```bash
pip install -r requirements.txt
streamlit run Home.py
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-xxxxxx
FINNHUB_API_KEY=xxxxxx
```

---

## Project Structure

```
quantdesk/
├── Home.py                  # Entry point — ticker search + module nav
├── pages/
│   ├── 1_Options_Pricer.py
│   └── 2_DCF_Valuation.py
├── styles.py                # Shared dark terminal CSS
├── data_fetcher.py          # yfinance + Finnhub wrappers
├── bs_engine.py             # Black-Scholes math + Greeks
├── dcf_engine.py            # DCF math
├── monte_carlo.py           # Monte Carlo simulations
├── visualization.py         # Shared Plotly chart builders
├── ai_analyst.py            # Anthropic API calls
├── utils.py                 # Formatting helpers
├── requirements.txt
└── .env                     # Never commit this — add to .gitignore
```

---

## Design Rules

- **Background**: `#0E1117`
- **Card background**: `#161B22`
- **Accent (blue)**: `#1F6FEB`
- **Positive (green)**: `#00C805`
- **Negative (red)**: `#FF3B3B`
- **Secondary text**: `#8B949E`
- **Border**: `#30363D`
- **Font**: `Source Code Pro` or `JetBrains Mono` for all data labels
- Override all default Streamlit styling via `styles.py` injected with `st.markdown`
- Sidebar = all inputs. Main area = all outputs and charts.

---

## Shared State

```python
# Set from any page
st.session_state["ticker"] = "AAPL"

# Read from any page
ticker = st.session_state.get("ticker", "AAPL")
```

Every page sidebar shows: current ticker, last price, market status.

---

## Home.py

- Ticker search bar at top (live price via Finnhub on submit)
- Two module cards: **Options Pricer** and **DCF Valuation** with nav buttons
- Shared sidebar: ticker + live price + market status

---

## Module 1 — Options Pricer

**Sidebar inputs**: Spot (S), Strike (K), Time to expiry (T), Risk-free rate (r), Volatility (σ), Call/Put toggle

**Tabs**:
1. **Pricing** — call/put price, intrinsic vs time value bar chart
2. **Greeks** — Delta, Gamma, Theta, Vega, Rho as metric cards
3. **Heatmap** — option price across spot × volatility grid
4. **Implied Vol** — solve for IV from market price input
5. **Monte Carlo** — 10,000 paths, terminal price distribution, P&L histogram

**AI Analyst**: After pricing, stream a 3-4 sentence brief via Claude (Greek risk, time value commentary, vol sensitivity). Add "Ask the analyst" text input below.

---

## Module 2 — DCF Valuation

**Sidebar inputs**: Ticker (auto-fetch from yfinance) or manual — base revenue, growth rates Y1–Y5, EBITDA margin, D&A %, CapEx %, NWC %, tax rate

**Tabs**:
1. **DCF Model** — projected financials: Revenue → EBITDA → EBIT → NOPAT → FCFF
2. **WACC** — CAPM inputs, cost of debt, weights → WACC output
3. **Terminal Value** — Perpetuity Growth vs Exit Multiple, side by side
4. **Results** — EV, net debt, equity value, implied share price, upside/downside
5. **Sensitivity** — color-coded table: share price across WACC × terminal growth
6. **Football Field** — horizontal bar chart of valuation ranges

**AI Analyst**: After every DCF run, stream a brief (EV sanity check, terminal value concentration risk, WACC sensitivity). Add "Ask the analyst" input below.

---

## AI Analyst (`ai_analyst.py`)

```python
import anthropic
import os

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_commentary(context: dict, question: str = None) -> str:
    system = "You are a senior M&A analyst. Be concise, precise, professional. No disclaimers."
    prompt = f"Model context: {context}\n\n"
    prompt += f"Question: {question}" if question else "Write a 3-4 sentence analyst brief covering key risks."

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
```

---

## Data Fetching Rules

- All API calls go through `data_fetcher.py` only — never inline in page files
- Use `@st.cache_data(ttl=300)` on all fetches (5 min cache)
- On fetch failure: fall back to cached value, show stale indicator in UI
- Never log or display API keys

---

## Utils (`utils.py`)

```python
def fmt_currency(val):  return f"${val:,.2f}"
def fmt_millions(val):  return f"${val/1e6:,.1f}M"
def fmt_pct(val):       return f"{val:.2f}%"
def fmt_ratio(val):     return f"{val:.4f}"
def fmt_price(val):     return f"${val:.2f}"
```

---

## Code Style

- Named exports only — no `import *`
- All heavy computation in engine files, never in page files
- `st.cache_data` on all expensive operations
- Format monetary values only at display time
- No `st.experimental_*` — stable APIs only

---

## Requirements

```
streamlit
plotly
numpy
scipy
yfinance
anthropic
finnhub-python
python-dotenv
pandas
```

---

## Deployment (Streamlit Cloud)

- Push to GitHub (make sure `.env` is in `.gitignore`)
- Connect repo on share.streamlit.io
- Entry point: `Home.py`
- Add secrets in Streamlit Cloud dashboard:
  ```toml
  ANTHROPIC_API_KEY = "sk-ant-xxxxxx"
  FINNHUB_API_KEY = "xxxxxx"
  ```
