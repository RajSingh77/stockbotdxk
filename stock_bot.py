"""
Daily Stock Picks Bot
---------------------
Scans a universe of large/mid-cap stocks, pulls fundamentals + analyst data
via yfinance, scores them for SHORT / MEDIUM / LONG term setups, and emails
you the top picks in each bucket.

Run manually:   python stock_bot.py
Run on schedule: see .github/workflows/daily_stock_email.yml
"""

import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

# Diversified universe of liquid large/mid caps across sectors.
# Add/remove tickers freely -- this list is just a starting point.
TICKER_UNIVERSE = [
    # Tech / software
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "ORCL", "CRM", "ADBE",
    "AMD", "INTC", "CSCO", "IBM", "NOW", "PANW", "SNPS", "CDNS",
    # Semis
    "NVDA", "MU", "TXN", "QCOM", "AMAT", "LRCX", "KLAC", "ASML",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP", "SCHW",
    # Healthcare
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR",
    # Consumer
    "WMT", "COST", "HD", "MCD", "NKE", "SBUX", "PG", "KO", "PEP", "DIS",
    # Industrials
    "CAT", "BA", "HON", "UPS", "GE", "LMT", "RTX",
    # Energy
    "XOM", "CVX", "COP", "SLB",
    # REITs
    "WPC", "O", "PLD", "AMT",
    # Communication
    "NFLX", "T", "VZ", "CMCSA",
    # Auto / EV
    "TSLA", "F", "GM",
]

TOP_N = 5  # how many picks to show per category

# ---------------------------------------------------------------------------
# DATA FETCHING
# ---------------------------------------------------------------------------

def compute_rsi(closes: pd.Series, period: int = 14) -> float:
    """Standard 14-day RSI from a series of closing prices."""
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean().iloc[-1]
    avg_loss = loss.rolling(period).mean().iloc[-1]
    if avg_loss == 0 or pd.isna(avg_loss):
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def fetch_stock_data(ticker: str) -> dict | None:
    """Pull fundamentals, analyst estimates, and price history for one ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="6mo")

        if hist.empty or len(hist) < 30:
            return None

        current_price = info.get("currentPrice") or hist["Close"].iloc[-1]

        # Momentum
        price_1m_ago = hist["Close"].iloc[-21] if len(hist) >= 21 else hist["Close"].iloc[0]
        price_3m_ago = hist["Close"].iloc[-63] if len(hist) >= 63 else hist["Close"].iloc[0]
        mom_1m = (current_price - price_1m_ago) / price_1m_ago * 100
        mom_3m = (current_price - price_3m_ago) / price_3m_ago * 100
        rsi = compute_rsi(hist["Close"])

        # Analyst data
        target_mean = info.get("targetMeanPrice")
        analyst_upside = (
            (target_mean - current_price) / current_price * 100
            if target_mean else None
        )

        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "sector": info.get("sector", "N/A"),
            "price": round(current_price, 2),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio") or info.get("trailingPegRatio"),
            "target_mean_price": round(target_mean, 2) if target_mean else None,
            "analyst_upside_pct": analyst_upside,
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "recommendation": info.get("recommendationKey", "n/a"),
            "recommendation_mean": info.get("recommendationMean"),  # 1=Strong Buy, 5=Sell
            "earnings_growth": info.get("earningsGrowth"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margin": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": info.get("dividendYield"),
            "mom_1m_pct": mom_1m,
            "mom_3m_pct": mom_3m,
            "rsi_14": rsi,
        }
    except Exception as e:
        print(f"  [skip] {ticker}: {e}", file=sys.stderr)
        return None


def build_dataset(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] fetching {ticker}...")
        row = fetch_stock_data(ticker)
        if row:
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------

def zscore(series: pd.Series) -> pd.Series:
    """Z-score a column; missing values become neutral (0) instead of dropping rows."""
    s = series.astype(float)
    mean, std = s.mean(skipna=True), s.std(skipna=True)
    if not std or pd.isna(std):
        return s.fillna(0) * 0
    return ((s - mean) / std).fillna(0)


def rsi_bonus(rsi: float) -> float:
    """Reward RSI in a healthy uptrend zone (50-70); penalize overbought/oversold."""
    if pd.isna(rsi):
        return 0
    if 50 <= rsi <= 70:
        return 1.0
    if 40 <= rsi < 80:
        return 0.3
    return -0.5


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- SHORT TERM: momentum-driven ---
    df["short_score"] = (
        zscore(df["mom_1m_pct"]) * 0.45
        + zscore(df["mom_3m_pct"]) * 0.30
        + df["rsi_14"].apply(rsi_bonus) * 0.25
    )

    # --- MEDIUM TERM: analyst conviction + growth ---
    df["medium_score"] = (
        zscore(df["analyst_upside_pct"]) * 0.40
        + zscore(df["earnings_growth"]) * 0.25
        - zscore(df["peg_ratio"]) * 0.15
        - zscore(df["recommendation_mean"]) * 0.20  # lower mean = stronger buy
    )

    # --- LONG TERM: fundamentals / quality / value ---
    df["long_score"] = (
        -zscore(df["forward_pe"]) * 0.25
        + zscore(df["profit_margin"]) * 0.25
        + zscore(df["revenue_growth"]) * 0.20
        - zscore(df["debt_to_equity"]) * 0.15
        + zscore(df["dividend_yield"]) * 0.15
    )

    return df


def top_picks(df: pd.DataFrame, score_col: str, n: int = TOP_N) -> pd.DataFrame:
    return df.sort_values(score_col, ascending=False).head(n)


# ---------------------------------------------------------------------------
# EMAIL
# ---------------------------------------------------------------------------

def fmt_pct(x):
    return f"{x*100:.1f}%" if pd.notna(x) and abs(x) < 5 else (f"{x:.1f}%" if pd.notna(x) else "-")


def fmt_num(x, decimals=2):
    return f"{x:.{decimals}f}" if pd.notna(x) else "-"


def render_table(df: pd.DataFrame, term: str) -> str:
    if term == "short":
        cols = [
            ("ticker", "Ticker"), ("price", "Price"), ("mom_1m_pct", "1M %"),
            ("mom_3m_pct", "3M %"), ("rsi_14", "RSI"), ("recommendation", "Analyst Rec"),
        ]
    elif term == "medium":
        cols = [
            ("ticker", "Ticker"), ("price", "Price"), ("target_mean_price", "Analyst Target"),
            ("analyst_upside_pct", "Upside %"), ("peg_ratio", "PEG"), ("recommendation", "Rec"),
        ]
    else:
        cols = [
            ("ticker", "Ticker"), ("price", "Price"), ("forward_pe", "Fwd P/E"),
            ("profit_margin", "Profit Margin"), ("revenue_growth", "Rev Growth"),
            ("dividend_yield", "Div Yield"),
        ]

    header = "".join(f"<th style='padding:6px 10px;border-bottom:2px solid #333;text-align:left'>{label}</th>" for _, label in cols)
    rows_html = ""
    for _, row in df.iterrows():
        cells = ""
        for key, _ in cols:
            val = row.get(key)
            if key in ("mom_1m_pct", "mom_3m_pct", "analyst_upside_pct"):
                val = fmt_num(val, 1) + "%" if pd.notna(val) else "-"
            elif key in ("profit_margin", "revenue_growth", "dividend_yield"):
                val = fmt_pct(val)
            elif key in ("price", "target_mean_price", "forward_pe", "peg_ratio", "rsi_14"):
                val = fmt_num(val)
            cells += f"<td style='padding:6px 10px;border-bottom:1px solid #ddd'>{val}</td>"
        rows_html += f"<tr>{cells}</tr>"

    return f"<table style='border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px'><tr>{header}</tr>{rows_html}</table>"


def build_email_html(short_df, medium_df, long_df) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:auto">
      <h2>📊 Daily Stock Picks</h2>
      <p style="color:#666;font-size:13px">Automated screen across {len(TICKER_UNIVERSE)} tickers. Not financial advice -- do your own diligence.</p>

      <h3>🟢 Short-Term (momentum)</h3>
      {render_table(short_df, "short")}

      <h3 style="margin-top:24px">🟡 Medium-Term (analyst upside + growth)</h3>
      {render_table(medium_df, "medium")}

      <h3 style="margin-top:24px">🔵 Long-Term (fundamentals / value)</h3>
      {render_table(long_df, "long")}

      <p style="color:#999;font-size:12px;margin-top:24px">
        Data via Yahoo Finance (yfinance). Scores are relative rankings within today's scanned universe, not absolute predictions.
      </p>
    </div>
    """


def send_email(html_body: str, subject: str): sender = os.environ["EMAIL_ADDRESS"] password = os.environ["EMAIL_APP_PASSWORD"] raw_recipients = os.environ.get("TO_EMAIL", sender) recipients = [addr.strip() for addr in raw_recipients.split(",") if addr.strip()] msg = MIMEMultipart("alternative") msg["Subject"] = subject msg["From"] = sender msg["To"] = ", ".join(recipients) msg.attach(MIMEText(html_body, "html")) with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server: server.login(sender, password) server.sendmail(sender, recipients, msg.as_string()) print(f"Email sent to {', '.join(recipients)}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print(f"Scanning {len(TICKER_UNIVERSE)} tickers...")
    df = build_dataset(TICKER_UNIVERSE)
    print(f"Got data for {len(df)} tickers.")

    if df.empty:
        print("No data fetched -- aborting.", file=sys.stderr)
        sys.exit(1)

    df = compute_scores(df)

    short_df = top_picks(df, "short_score")
    medium_df = top_picks(df, "medium_score")
    long_df = top_picks(df, "long_score")

    html = build_email_html(short_df, medium_df, long_df)

    from datetime import date
    subject = f"Stock Picks - {date.today().isoformat()}"
    send_email(html, subject)


if __name__ == "__main__":
    main()
