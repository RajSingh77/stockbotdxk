"""
Daily Stock Picks Bot
---------------------
Scans a universe of stocks, pulls fundamentals, analyst data, and financial
statement metrics via yfinance, scores them for SHORT / MEDIUM / LONG term
setups, and emails you a diversified (bullish/neutral/bearish) set of picks
per bucket plus a full data table for every ticker scanned.

Run manually:   python stock_bot.py
Run on schedule: see .github/workflows/daily_stock_email.yml
"""

import os
import random
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

# Larger pools grouped by sector/industry. Each run randomly samples a few
# tickers from EVERY sector below, so every day covers the same industries
# but with different actual companies -- no more seeing the same 95 names.
SECTOR_POOLS = {
    "Tech / Software": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "ORCL", "CRM", "ADBE",
        "AMD", "INTC", "CSCO", "IBM", "NOW", "PANW", "SNPS", "CDNS", "WDAY",
        "INTU", "SHOP", "ADSK", "ANSS", "TEAM", "DDOG", "NET", "CRWD", "ZS",
        "OKTA", "MDB", "SNOW", "TTD", "PYPL", "EBAY", "ETSY", "SPOT", "PINS",
        "TWLO", "DOCU", "ZM", "HUBS", "GTLB", "FTNT", "JNPR", "ANET", "MSI",
        "ROP", "TDY", "KEYS", "GLW", "DELL",
    ],
    "Semiconductors": [
        "NVDA", "MU", "TXN", "QCOM", "AMAT", "LRCX", "KLAC", "ASML", "ON",
        "MCHP", "NXPI", "STM", "TSM", "ADI", "MRVL", "SWKS", "QRVO", "MPWR",
        "ENTG", "TER", "LSCC", "RMBS", "CRUS", "DIOD", "ALGM", "POWI", "SITM",
        "WOLF", "ONTO", "UCTT", "FORM", "ICHR", "AEIS", "COHU", "KLIC",
        "AMKR", "VECO", "ACLS", "IPGP", "SIMO", "HIMX", "OLED",
    ],
    "Financials": [
        "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP", "SCHW", "C",
        "USB", "PNC", "TFC", "COF", "BK", "STT", "TRV", "ALL", "PGR", "MET",
        "PRU", "AIG", "CB", "MMC", "AON", "AJG", "BRO", "ICE", "CME", "NDAQ",
        "MCO", "SPGI", "FI", "GPN", "SYF", "DFS", "ALLY", "RJF", "LPLA",
        "IVZ", "HBAN", "RF",
    ],
    "Healthcare": [
        "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR",
        "BMY", "GILD", "CVS", "AMGN", "VRTX", "REGN", "ISRG", "ZTS", "ELV",
        "CI", "HUM", "CNC", "MDT", "SYK", "BSX", "BDX", "EW", "IDXX", "IQV",
        "MRNA", "BIIB", "ALGN", "DXCM", "HOLX", "RMD", "WST", "MTD", "A",
        "ILMN", "INCY", "VTRS", "COR", "MCK",
    ],
    "Consumer": [
        "WMT", "COST", "HD", "MCD", "NKE", "SBUX", "PG", "KO", "PEP", "DIS",
        "TGT", "LOW", "YUM", "CL", "KMB", "GIS", "KHC", "MDLZ", "MO", "PM",
        "STZ", "HSY", "K", "CPB", "CAG", "SJM", "MKC", "CLX", "CHD", "EL",
        "KDP", "MNST", "TAP", "DG", "DLTR", "ROST", "TJX", "BBY", "ULTA",
        "LULU", "DECK", "CMG", "DPZ",
    ],
    "Industrials": [
        "CAT", "BA", "HON", "UPS", "GE", "LMT", "RTX", "DE", "MMM", "FDX",
        "NOC", "GD", "TXT", "EMR", "ETN", "ITW", "PH", "DOV", "XYL", "AME",
        "ROK", "CMI", "PCAR", "WAB", "CSX", "UNP", "NSC", "ODFL", "JBHT",
        "CHRW", "EXPD", "WM", "RSG", "PWR", "JCI", "CARR", "OTIS", "IEX",
        "FAST", "GWW",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC", "OXY", "VLO", "WMB",
        "KMI", "OKE", "HAL", "BKR", "DVN", "FANG", "HES", "MRO", "APA",
        "CTRA", "EQT", "TRGP", "NOV", "AR", "RRC", "SWN", "PBF", "DINO",
        "DK", "CVI", "TPL", "SM", "MTDR", "CRC", "VNOM", "OVV", "CNX",
    ],
    "REITs": [
        "WPC", "O", "PLD", "AMT", "SPG", "EQIX", "PSA", "DLR", "WELL", "AVB",
        "EQR", "VTR", "ESS", "MAA", "INVH", "EXR", "CPT", "UDR", "ARE",
        "BXP", "VNO", "KIM", "REG", "FRT", "HST", "IRM", "CCI", "SBAC",
        "GLPI", "VICI", "EGP", "FR", "REXR", "STAG", "NNN",
    ],
    "Communication": [
        "NFLX", "T", "VZ", "CMCSA", "TMUS", "CHTR", "WBD", "PARA", "FOXA",
        "FOX", "NWSA", "NWS", "LYV", "MTCH", "IAC", "OMC", "IPG", "TGNA",
        "LUMN", "CABO", "ATUS", "SIRI", "NYT", "EA", "TTWO", "ANGI", "ZG",
        "Z", "YELP", "RNG", "VG", "CCOI", "SHEN", "USM",
    ],
    "Auto / EV": [
        "TSLA", "F", "GM", "RIVN", "LCID", "NIO", "TM", "HMC", "STLA",
        "XPEV", "LI", "PSNY", "CVNA", "LAD", "KMX", "AN", "GPC", "LKQ",
        "BWA", "APTV", "LEA", "MGA", "ADNT", "DAN", "THRM", "VC", "ALSN",
        "OSK", "WBC", "RUSHA", "GNTX", "SAH", "GT",
    ],
    "Popular / High-Retail-Attention": [
        "PLTR", "COIN", "SOFI", "SMCI", "SNAP", "UBER", "ABNB", "DKNG",
        "ROKU", "SQ", "MARA", "RIOT", "SOUN", "IONQ", "AFRM", "RBLX", "HOOD",
        "LYFT", "DASH", "CHPT", "BLNK", "QS", "CLSK", "HUT", "BITF", "WULF",
        "APLD", "RGTI", "QBTS", "ARQQ", "UPST", "PATH", "AI", "BBAI", "GRAB",
        "SE", "MELI", "CPNG", "W", "CHWY", "CART", "TOST", "DUOL", "ARM",
        "RDDT", "APP",
    ],
}

SAMPLE_PER_SECTOR = 4      # how many tickers to randomly pull from each sector, per run
PICKS_PER_SENTIMENT = 2    # how many bullish / neutral / bearish picks per term
PICKS_PER_TERM = PICKS_PER_SENTIMENT * 3  # total shown per short/medium/long bucket
NEWS_LOOKBACK_HOURS = 72   # how recent a headline must be to count as a "catalyst"
MAX_NEWS_ITEMS = 15        # cap on headlines shown in the email


def build_universe() -> list[str]:
    """Randomly sample tickers from every sector so the scanned set changes
    daily while still covering the same industries each time."""
    universe = []
    for sector, pool in SECTOR_POOLS.items():
        n = min(SAMPLE_PER_SECTOR, len(pool))
        universe.extend(random.sample(pool, n))
    return list(dict.fromkeys(universe))  # dedupe, keep order, in case a ticker sits in 2 pools

# ---------------------------------------------------------------------------
# HELPERS: pulling specific line items out of messy financial statements
# ---------------------------------------------------------------------------

def fetch_recent_news(t, hours: int = NEWS_LOOKBACK_HOURS) -> list[dict]:
    """Pull recent published news headlines for a ticker (real articles, with
    links) from Yahoo Finance. This surfaces genuine catalysts (upgrades,
    stake disclosures, earnings, M&A) IF Yahoo has published something about
    it recently -- it does not detect events same-day if no article exists
    yet (e.g. 13F institutional-holding disclosures lag ~45 days by law)."""
    from datetime import datetime, timezone

    try:
        raw_items = t.news or []
    except Exception:
        return []

    now = datetime.now(timezone.utc)
    results = []
    for item in raw_items:
        content = item.get("content", item)  # newer yfinance nests under "content"

        title = content.get("title") or item.get("title")
        if not title:
            continue

        provider = content.get("provider")
        publisher = (
            provider.get("displayName") if isinstance(provider, dict)
            else content.get("publisher") or item.get("publisher") or "Yahoo Finance"
        )

        canonical = content.get("canonicalUrl")
        link = (
            canonical.get("url") if isinstance(canonical, dict)
            else content.get("link") or item.get("link")
        )

        pub_dt = None
        pub_epoch = item.get("providerPublishTime")
        if pub_epoch:
            pub_dt = datetime.fromtimestamp(pub_epoch, tz=timezone.utc)
        else:
            pub_date_str = content.get("pubDate")
            if pub_date_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                except Exception:
                    pub_dt = None

        if pub_dt and (now - pub_dt).total_seconds() <= hours * 3600:
            results.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "published": pub_dt,
            })

    return results


def get_row_value(df, keywords):
    """Return the most recent value of the first row whose label matches any keyword."""
    if df is None or df.empty:
        return None
    for idx in df.index:
        label = str(idx).lower()
        if any(kw.lower() in label for kw in keywords):
            try:
                val = df.loc[idx].iloc[0]
                return None if pd.isna(val) else float(val)
            except Exception:
                return None
    return None


def get_row_series(df, keywords):
    """Return the full time series (most recent first) for the first matching row."""
    if df is None or df.empty:
        return []
    for idx in df.index:
        label = str(idx).lower()
        if any(kw.lower() in label for kw in keywords):
            return [v for v in df.loc[idx].values]
    return []


def fcf_trend_label(fcf_series):
    """Classify whether free cash flow has been trending up, down, or mixed."""
    values = [v for v in fcf_series if pd.notna(v)]
    if len(values) < 2:
        return "N/A"
    values = values[::-1]  # yfinance columns are most-recent-first; flip to chronological
    increases = sum(1 for i in range(1, len(values)) if values[i] > values[i - 1])
    decreases = sum(1 for i in range(1, len(values)) if values[i] < values[i - 1])
    if increases > decreases:
        return "Increasing"
    if decreases > increases:
        return "Decreasing"
    return "Mixed"


def fetch_financials(t) -> dict:
    """Pull key metrics from the balance sheet, income statement, and cash flow statement."""
    try:
        bs = t.balance_sheet
    except Exception:
        bs = None
    try:
        cf = t.cashflow
    except Exception:
        cf = None
    try:
        inc = t.income_stmt
    except Exception:
        inc = None

    cash = get_row_value(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents"])
    curr_assets = get_row_value(bs, ["Current Assets"])
    curr_liab = get_row_value(bs, ["Current Liabilities"])
    current_ratio = (curr_assets / curr_liab) if curr_assets and curr_liab else None

    net_income = get_row_value(inc, ["Net Income"])
    total_revenue = get_row_value(inc, ["Total Revenue"])
    net_margin_calc = (net_income / total_revenue) if net_income is not None and total_revenue else None

    fcf_series = get_row_series(cf, ["Free Cash Flow"])
    if not fcf_series:
        ocf_series = get_row_series(cf, ["Operating Cash Flow"])
        capex_series = get_row_series(cf, ["Capital Expenditure"])
        if ocf_series and capex_series and len(ocf_series) == len(capex_series):
            fcf_series = [
                (o + c) if pd.notna(o) and pd.notna(c) else None
                for o, c in zip(ocf_series, capex_series)
            ]

    return {
        "cash_position": cash,
        "current_ratio": current_ratio,
        "net_profit_margin_calc": net_margin_calc,
        "fcf_trend": fcf_trend_label(fcf_series),
    }


def compute_rsi(closes: pd.Series, period: int = 14) -> float:
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean().iloc[-1]
    avg_loss = loss.rolling(period).mean().iloc[-1]
    if avg_loss == 0 or pd.isna(avg_loss):
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ---------------------------------------------------------------------------
# DATA FETCHING
# ---------------------------------------------------------------------------

def fetch_stock_data(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="6mo")

        if hist.empty or len(hist) < 30:
            return None

        current_price = info.get("currentPrice") or hist["Close"].iloc[-1]

        price_1m_ago = hist["Close"].iloc[-21] if len(hist) >= 21 else hist["Close"].iloc[0]
        price_3m_ago = hist["Close"].iloc[-63] if len(hist) >= 63 else hist["Close"].iloc[0]
        mom_1m = (current_price - price_1m_ago) / price_1m_ago * 100
        mom_3m = (current_price - price_3m_ago) / price_3m_ago * 100
        rsi = compute_rsi(hist["Close"])

        target_mean = info.get("targetMeanPrice")
        analyst_upside = (
            (target_mean - current_price) / current_price * 100 if target_mean else None
        )

        fin = fetch_financials(t)
        recent_news = fetch_recent_news(t)

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
            "recommendation_mean": info.get("recommendationMean"),
            "earnings_growth": info.get("earningsGrowth"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margin": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": info.get("dividendYield"),
            "mom_1m_pct": mom_1m,
            "mom_3m_pct": mom_3m,
            "rsi_14": rsi,
            "recent_news": recent_news,
            **fin,
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
# SCORING + SENTIMENT
# ---------------------------------------------------------------------------

def zscore(series: pd.Series) -> pd.Series:
    s = series.astype(float)
    mean, std = s.mean(skipna=True), s.std(skipna=True)
    if not std or pd.isna(std):
        return s.fillna(0) * 0
    return ((s - mean) / std).fillna(0)


def rsi_bonus(rsi: float) -> float:
    if pd.isna(rsi):
        return 0
    if 50 <= rsi <= 70:
        return 1.0
    if 40 <= rsi < 80:
        return 0.3
    return -0.5


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["short_score"] = (
        zscore(df["mom_1m_pct"]) * 0.45
        + zscore(df["mom_3m_pct"]) * 0.30
        + df["rsi_14"].apply(rsi_bonus) * 0.25
    )

    df["medium_score"] = (
        zscore(df["analyst_upside_pct"]) * 0.40
        + zscore(df["earnings_growth"]) * 0.25
        - zscore(df["peg_ratio"]) * 0.15
        - zscore(df["recommendation_mean"]) * 0.20
    )

    df["long_score"] = (
        -zscore(df["forward_pe"]) * 0.25
        + zscore(df["profit_margin"]) * 0.25
        + zscore(df["revenue_growth"]) * 0.20
        - zscore(df["debt_to_equity"]) * 0.15
        + zscore(df["dividend_yield"]) * 0.15
    )

    return df


def classify_sentiment(row) -> str:
    rec = str(row.get("recommendation", "")).lower()
    if rec in ("strong_buy", "buy"):
        return "Bullish"
    if rec in ("sell", "strong_sell", "underperform"):
        return "Bearish"
    if rec == "hold":
        return "Neutral"
    upside = row.get("analyst_upside_pct")
    if pd.notna(upside):
        if upside > 10:
            return "Bullish"
        if upside < -5:
            return "Bearish"
    return "Neutral"


def diversified_picks(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Pick a mix of bullish/neutral/bearish names instead of pure top-score,
    so the list actually varies and reflects a range of views."""
    chunks = []
    for sentiment in ["Bullish", "Neutral", "Bearish"]:
        sub = df[df["sentiment"] == sentiment].sort_values(score_col, ascending=False)
        chunks.append(sub.head(PICKS_PER_SENTIMENT))
    result = pd.concat(chunks)

    if len(result) < PICKS_PER_TERM:
        remaining = df[~df["ticker"].isin(result["ticker"])].sort_values(score_col, ascending=False)
        result = pd.concat([result, remaining.head(PICKS_PER_TERM - len(result))])

    return result.sort_values(score_col, ascending=False)


# ---------------------------------------------------------------------------
# FORMATTING
# ---------------------------------------------------------------------------

def fmt_pct(x):
    if pd.isna(x):
        return "-"
    return f"{x*100:.1f}%" if abs(x) < 5 else f"{x:.1f}%"


def fmt_num(x, decimals=2):
    return f"{x:.{decimals}f}" if pd.notna(x) else "-"


def fmt_money(x):
    if x is None or pd.isna(x):
        return "-"
    x = float(x)
    if abs(x) >= 1e9:
        return f"${x/1e9:.1f}B"
    if abs(x) >= 1e6:
        return f"${x/1e6:.1f}M"
    return f"${x:,.0f}"


SENTIMENT_COLOR = {"Bullish": "#1a7f37", "Neutral": "#9a6700", "Bearish": "#cf222e"}


def render_term_table(df: pd.DataFrame) -> str:
    header_cols = [
        "Ticker", "Price", "Sentiment", "Rating", "Trailing P/E", "Fwd P/E",
        "Analyst Upside", "Current Ratio", "Net Margin", "FCF Trend",
    ]
    header = "".join(f"<th style='padding:6px 8px;border-bottom:2px solid #333;text-align:left'>{h}</th>" for h in header_cols)

    rows_html = ""
    for _, row in df.iterrows():
        color = SENTIMENT_COLOR.get(row["sentiment"], "#333")
        rows_html += (
            "<tr>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd;font-weight:bold'>{row['ticker']}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>${fmt_num(row['price'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd;color:{color};font-weight:bold'>{row['sentiment']}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{row['recommendation']}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{fmt_num(row['trailing_pe'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{fmt_num(row['forward_pe'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{fmt_num(row['analyst_upside_pct'], 1)}%</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{fmt_num(row['current_ratio'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{fmt_pct(row['net_profit_margin_calc'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{row['fcf_trend']}</td>"
            "</tr>"
        )

    return f"<table style='border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px'><tr>{header}</tr>{rows_html}</table>"


def render_full_table(df: pd.DataFrame) -> str:
    header_cols = [
        "Ticker", "Price", "Sentiment", "Trailing P/E", "Fwd P/E", "PEG",
        "Cash", "Current Ratio", "Net Margin", "FCF Trend",
    ]
    header = "".join(f"<th style='padding:5px 7px;border-bottom:2px solid #333;text-align:left'>{h}</th>" for h in header_cols)

    rows_html = ""
    for _, row in df.sort_values("ticker").iterrows():
        color = SENTIMENT_COLOR.get(row["sentiment"], "#333")
        rows_html += (
            "<tr>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee;font-weight:bold'>{row['ticker']}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee'>${fmt_num(row['price'])}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee;color:{color}'>{row['sentiment']}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee'>{fmt_num(row['trailing_pe'])}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee'>{fmt_num(row['forward_pe'])}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee'>{fmt_num(row['peg_ratio'])}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee'>{fmt_money(row['cash_position'])}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee'>{fmt_num(row['current_ratio'])}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee'>{fmt_pct(row['net_profit_margin_calc'])}</td>"
            f"<td style='padding:5px 7px;border-bottom:1px solid #eee'>{row['fcf_trend']}</td>"
            "</tr>"
        )

    return f"<table style='border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:12px'><tr>{header}</tr>{rows_html}</table>"


def collect_news(df: pd.DataFrame) -> list[dict]:
    """Flatten each ticker's recent_news list into one sorted, capped list."""
    all_items = []
    for _, row in df.iterrows():
        for item in row.get("recent_news", []) or []:
            all_items.append({**item, "ticker": row["ticker"]})
    all_items.sort(key=lambda x: x["published"], reverse=True)
    return all_items[:MAX_NEWS_ITEMS]


def render_news_section(news_items: list[dict]) -> str:
    if not news_items:
        return "<p style='color:#666;font-size:13px'>No fresh headlines (last 72h) on today's scanned tickers.</p>"

    rows_html = ""
    for item in news_items:
        hours_ago = int((pd.Timestamp.now(tz="UTC") - item["published"]).total_seconds() // 3600)
        when = f"{hours_ago}h ago" if hours_ago < 48 else f"{hours_ago // 24}d ago"
        link = item.get("link") or "#"
        rows_html += (
            "<div style='padding:8px 0;border-bottom:1px solid #eee'>"
            f"<span style='font-weight:bold'>{item['ticker']}</span> "
            f"<span style='color:#999;font-size:12px'>({item['publisher']}, {when})</span><br>"
            f"<a href='{link}' style='color:#1a56db;text-decoration:none'>{item['title']}</a>"
            "</div>"
        )
    return f"<div style='font-family:Arial,sans-serif;font-size:14px'>{rows_html}</div>"


def build_email_html(short_df, medium_df, long_df, full_df, news_items) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:800px;margin:auto">
      <h2>📊 Daily Stock Picks</h2>
      <p style="color:#666;font-size:13px">
        Screened {len(full_df)} tickers. Each bucket below shows {PICKS_PER_SENTIMENT} Bullish,
        {PICKS_PER_SENTIMENT} Neutral, and {PICKS_PER_SENTIMENT} Bearish-rated names -- not just
        one-sided "best" picks -- so you see the range of views, not a repeat of the same names.
        Not financial advice.
      </p>

      <h3>🟢 Short-Term (momentum)</h3>
      {render_term_table(short_df)}

      <h3 style="margin-top:24px">🟡 Medium-Term (analyst upside + growth)</h3>
      {render_term_table(medium_df)}

      <h3 style="margin-top:24px">🔵 Long-Term (fundamentals / value)</h3>
      {render_term_table(long_df)}

      <h3 style="margin-top:28px">📰 Recent News & Catalysts (last 72h)</h3>
      <p style="color:#666;font-size:12px">
        Real published headlines on today's scanned tickers -- upgrades, earnings, stake
        disclosures, M&amp;A, etc. This only catches events Yahoo Finance has already published
        an article about; it can't detect same-day institutional buys before they hit news
        (13F filings disclosing holdings like Berkshire's stakes lag by law, ~45 days).
      </p>
      {render_news_section(news_items)}

      <h3 style="margin-top:28px">📋 Full Data -- Every Company Scanned</h3>
      <p style="color:#666;font-size:12px">
        Cash = latest balance sheet cash position. Current Ratio = current assets / current
        liabilities (liquidity). Net Margin = net income / revenue, computed from the income
        statement. FCF Trend = direction of free cash flow across available annual reports
        (from the cash flow statement).
      </p>
      {render_full_table(full_df)}

      <p style="color:#999;font-size:12px;margin-top:24px">
        Data via Yahoo Finance (yfinance). Scores are relative rankings within today's scanned
        universe, not price predictions.
      </p>
    </div>
    """


# ---------------------------------------------------------------------------
# EMAIL
# ---------------------------------------------------------------------------

def send_email(html_body: str, subject: str):
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_APP_PASSWORD"]
    raw_recipients = os.environ.get("TO_EMAIL", sender)
    recipients = [addr.strip() for addr in raw_recipients.split(",") if addr.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())

    print(f"Email sent to {', '.join(recipients)}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    ticker_universe = build_universe()
    print(f"Scanning {len(ticker_universe)} tickers (randomized across {len(SECTOR_POOLS)} sectors): {ticker_universe}")
    df = build_dataset(ticker_universe)
    print(f"Got data for {len(df)} tickers.")

    if df.empty:
        print("No data fetched -- aborting.", file=sys.stderr)
        sys.exit(1)

    df = compute_scores(df)
    df["sentiment"] = df.apply(classify_sentiment, axis=1)

    short_df = diversified_picks(df, "short_score")
    medium_df = diversified_picks(df, "medium_score")
    long_df = diversified_picks(df, "long_score")
    news_items = collect_news(df)

    html = build_email_html(short_df, medium_df, long_df, df, news_items)

    from datetime import date
    subject = f"Stock Picks - {date.today().isoformat()}"
    send_email(html, subject)


if __name__ == "__main__":
    main()
