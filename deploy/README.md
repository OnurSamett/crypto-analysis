**English** | [Türkçe](README.tr.md)

# Setup on a Mac mini (Telegram notifications + data collector)

This setup **never places orders**. It (1) sends a Telegram message when a signal state changes, and (2) collects our own market data every 5 minutes.

## 1) Prerequisites
```bash
git clone https://github.com/OnurSamett/crypto-analysis.git && cd crypto-analysis
python3 --version            # 3.11 or newer (for tomllib)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q   # everything should pass
```

## 2) Telegram bot
1. In Telegram open **@BotFather** → `/newbot` → pick a name and username → it gives you a **token**.
2. `cp .env.example .env` and put `TELEGRAM_BOT_TOKEN=...` in `.env`. **Never share the token with anyone, including in chats.**
3. Open your new bot in Telegram and send **/start**.
4. Run `.venv/bin/python -m okx_karar notify --get-chat-id` and add the printed `TELEGRAM_CHAT_ID=...` line to `.env`.
5. Run `.venv/bin/python -m okx_karar notify --test`: a "connection test" message should arrive on your phone.

`.env` is never committed (`.gitignore`). The bot only writes to the chat matching `TELEGRAM_CHAT_ID`.

## 3) Dry run and first summary
```bash
.venv/bin/python -m okx_karar notify --dry-run     # prints only, saves no state
.venv/bin/python -m okx_karar notify               # first summary goes to Telegram, state is saved
.venv/bin/python -m okx_karar collect --summary    # data collector summary
```
On the first run old breakouts are not reported as new entries; you only get a "current state" summary. After that you
get messages only when an **event** happens (entry, exit, blocked by a filter, regime change) plus a weekly summary on Mondays.

## 4) Automatic runs (launchd)
```bash
./deploy/install_macos.sh
```
* `notify` runs at minute 5 of every hour and sends nothing if there is no newly closed candle.
* `collect` takes a snapshot every 5 minutes (`data/collector.db`).

Logs: `~/Library/Logs/crypto-analysis/`. Remove with `./deploy/uninstall_macos.sh`.

## 5) Mac mini settings (important)
* **System Settings → Energy**: turn **on** "Prevent automatic sleeping when the display is off" and "Start up automatically after a power failure".
* Automatic login must be on (a LaunchAgent runs in the user session).
* Set date and time automatically.

## 6) Troubleshooting
* Nothing arrives in Telegram: run `notify --test`, then check `~/Library/Logs/crypto-analysis/notify.err.log`.
* The same bar is never sent twice; state lives in `state/notify_*.json`. For a fresh summary use `notify --force-snapshot`.
* On errors you get at most one "⚠️ failed" message per day.
