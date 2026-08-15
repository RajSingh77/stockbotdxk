# Daily Stock Picks Bot

Scans ~75 large/mid-cap stocks daily, scores them for short/medium/long-term
setups using price momentum, analyst targets, and fundamentals, and emails
you the top 5 in each bucket.

## What it does

- **Short-term** score = 1-month momentum + 3-month momentum + RSI(14) positioning
- **Medium-term** score = analyst price-target upside + earnings growth - PEG - analyst rating
- **Long-term** score = forward P/E (inverse) + profit margin + revenue growth - debt/equity + dividend yield

All scores are **relative rankings** within the scanned universe that day, not absolute price predictions.

## One-time setup (~10 min)

### 1. Get a Gmail App Password
You can't use your normal Gmail password for this. Instead:
1. Go to https://myaccount.google.com/security
2. Turn on 2-Step Verification if it's not already on
3. Go to https://myaccount.google.com/apppasswords
4. Create an app password named "stock-bot" -> copy the 16-character code

### 2. Create a GitHub repo
1. Go to https://github.com/new, create a repo (can be private), e.g. `stock-picks-bot`
2. Push these files to it:
```bash
cd stock-bot
git init
git add .
git commit -m "Initial stock bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/stock-picks-bot.git
git push -u origin main
```

### 3. Add secrets
In your repo: **Settings -> Secrets and variables -> Actions -> New repository secret**. Add three:
| Name | Value |
|---|---|
| `EMAIL_ADDRESS` | your Gmail address |
| `EMAIL_APP_PASSWORD` | the 16-character app password from step 1 |
| `TO_EMAIL` | where you want the picks sent (can be same as EMAIL_ADDRESS) |

### 4. Test it
Go to the **Actions** tab -> "Daily Stock Picks Email" -> **Run workflow** (manual trigger). Check your inbox in ~2 minutes.

Once that works, it will run automatically every weekday at 12:00 UTC (7am ET). Edit the `cron` line in `.github/workflows/daily_stock_email.yml` to change the time — cron times are always UTC.

## Customizing

- **Add/remove tickers**: edit the `TICKER_UNIVERSE` list at the top of `stock_bot.py`. Your current holdings (NVDA, MU, WPC) are already in there. Note: SKHY (SK Hynix's new US ADR) may not have full analyst/fundamental data in yfinance yet since it just listed — add it and check, but don't be surprised if some fields show "-".
- **Change how many picks per category**: change `TOP_N` at the top of the file.
- **Adjust scoring weights**: edit the weights (e.g. `* 0.45`) inside `compute_scores()`.

## Running locally instead (optional)
```bash
pip install -r requirements.txt
export EMAIL_ADDRESS="you@gmail.com"
export EMAIL_APP_PASSWORD="your16charcode"
export TO_EMAIL="you@gmail.com"
python stock_bot.py
```

## Notes / limitations
- Free Yahoo Finance data via `yfinance` — occasionally a ticker fails to fetch (rate limiting); the script just skips it and logs a warning, doesn't crash.
- This is a screening tool, not investment advice — analyst targets and momentum scores can be wrong or lag reality.
- GitHub Actions free tier gives 2,000 minutes/month for private repos (unlimited for public) — this job takes ~2-3 min/day, well within limits.
