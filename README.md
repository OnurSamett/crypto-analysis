**English** | [Türkçe](README.tr.md)

# crypto-analysis

Python package `okx_karar`: a rule-based (LLM-free) decision system for OKX with backtesting and paper trading.

It implements the **analyst → debate → risk → trader** roles of TradingAgents-style systems with plain deterministic
code. The goal is to provide the **baseline that LLM agents must beat**. The same backtest engine and the same
`signal → decision` interface can be used for agents later.

> This is a research tool, not investment advice. Trading on a real account is disabled in this version.
> Code comments, CLI output and bot messages are currently in Turkish; the documentation is available in English and Turkish.

## Note: pre-registered experiments

The protocol and the E0–E4 configurations under `experiments/` were committed to the SmartInvest AI repository
(under `okx_karar/`) before the first run. This repository starts from a copy of those files; changing them afterwards
counts as a new experiment. The Turkish `experiments/PROTOCOL.md` is the authoritative pre-registered text;
[`experiments/PROTOCOL.en.md`](experiments/PROTOCOL.en.md) is a translation. Results (including negative ones) are in
[`experiments/RESULTS.en.md`](experiments/RESULTS.en.md).

## Findings

A consolidated log of every result (including negative ones) is in [`docs/FINDINGS.md`](docs/FINDINGS.md); thoughts on a possible paper are in [`docs/PAPER_OUTLINE.md`](docs/PAPER_OUTLINE.md).

## Install

```bash
cd crypto-analysis
python3 -m pip install -r requirements.txt     # Python 3.11+
python3 -m pytest
```

## Usage

```bash
python3 -m okx_karar fetch --days 365            # download candles (cached under data/)
python3 -m okx_karar backtest --days 365         # strategy vs buy-and-hold, results saved under results/
python3 -m okx_karar backtest --start 2024-01-01 --end 2025-01-01 --offline
python3 -m okx_karar paper --executor sim        # local paper trading, decides at every candle close
python3 -m okx_karar paper --executor demo       # on an OKX demo account (API key needed)
python3 -m okx_karar status --executor sim
python3 -m okx_karar evaluate --configs experiments/e3_regime.toml --periods dev,validation
python3 -m okx_karar audit --config experiments/e3_regime.toml   # look-ahead / recursion audit on real data
python3 -m okx_karar dca --periods dev,validation                 # DCA experiment (E6)
```

## Notification bot and data collector (they never place orders)

```bash
python3 -m okx_karar notify --dry-run     # print the signal state (E3 daily + E5 4-hour)
python3 -m okx_karar notify               # send to Telegram when something changed
python3 -m okx_karar collect              # funding, open interest, book depth, long/short ratio -> data/collector.db
```
Mac mini setup and the Telegram bot: [`deploy/README.md`](deploy/README.md).

## Decision flow

| Role | Module | What it does |
|---|---|---|
| Data | `data.py`, `okx_client.py` | closed candles from the OKX public API (no key needed) |
| Analyst | `signals.py` | trend (EMA 20/50), MACD, RSI, volume, Donchian ensemble, (swap) funding, each in −1…+1 |
| Debate | `decision.py` | weighted vote → one score; entry/exit thresholds with hysteresis |
| Risk | `risk.py` | ATR or volatility-target sizing, stop, volatility veto, drawdown kill switch |
| Trader | `backtest.py`, `paper.py`, `executors.py` | target position → order (simulation or OKX demo) |
| Advisory | `advisory.py`, `notifier.py` | same decisions, but only reported (Telegram / macOS / console) |

All settings live in `config.toml` and `experiments/*.toml`.

## No look-ahead rules

* The decision is made at the **close of candle t** using only data up to that moment; the order fills at the **open of t+1**.
* An unclosed candle (`confirm = "0"`) is never used.
* A funding rate is matched to a bar using the last value known at that bar's close.
* `tests/test_no_lookahead.py` verifies that replacing future candles with random values does not change past decisions.
* The `audit` command repeats this on real data (a truncation test inspired by Freqtrade's `lookahead-analysis`).
* `decision.scores_from_callable` gives a bar-by-bar strategy (e.g. an LLM agent) only the past, so look-ahead is structurally impossible.

## Fixing parameters

A backtest report includes the SHA-256 digest of the config (`config_hash`). For a fair test:

1. Choose parameters on a **development period**.
2. Commit the config.
3. Look at the **test period** once. If you change anything after seeing it, that period becomes development data.

`experiments/PROTOCOL.en.md` applies this discipline (dev / validation / test zone, acceptance rules, a log of every run in the test zone).

## Paper trading

* `sim`: a local ledger (`state/sim_account_<config>.json`) with the same cost model as the backtest. No key needed.
* `demo`: OKX demo trading. Create a key on okx.com → Demo Trading → API with **read + trade** permission only, copy
  `.env.example` to `.env` and fill it in. The client adds `x-simulated-trading: 1` to every private request. Live mode is disabled in code.
* A candle is never processed twice (`state/paper_*.json`); the order id (`clOrdId`) is derived from the candle time.
* Limitation: stops are checked by the bot at candle closes; there is no resting stop order on the exchange.

## Futures (swap): disabled

`futures.py` supports shorts, leveraged position caps, a funding signal and funding payments; the backtest and the demo
executor are ready and tested. To enable:

```toml
[market]
mode = "swap"
[futures]
enabled = true
```

While `enabled = false`, swap mode is rejected when the config is loaded. The demo account must be in **net** position
mode. Liquidation is not modelled; keep leverage low and stops far from liquidation.
