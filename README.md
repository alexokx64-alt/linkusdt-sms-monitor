# LINKUSDT SMC Monitor (educational prototype)

This GitHub Actions workflow checks public OKX market candles on a scheduled basis and sends a Telegram message when a simple rule-based SMC candidate is detected.

## Files
- `main.py` — reads public OKX candles and checks a basic structure + sweep/displacement proxy.
- `.github/workflows/monitor.yml` — runs manually and on a five-minute schedule.
- `state.json` — created after the first signal to reduce duplicate messages.

## Required GitHub Actions secrets
In repository Settings → Secrets and variables → Actions → New repository secret, add:
- `BOT_TOKEN` — token from BotFather
- `CHAT_ID` — your private Telegram chat ID (numeric)

Never put these values in code or commit them.

## Important limitations
- GitHub scheduled runs are best-effort, not exact real-time alerts; they can be delayed.
- The SMC rules here are a simplified heuristic, not a full discretionary SMC analysis.
- A signal is only a candidate. It does not include stop-loss or position sizing.
- No exchange account/API keys are used and the script cannot place orders.
- The script filters out unconfirmed candles as returned by OKX.
