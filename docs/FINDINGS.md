# Findings log

Consolidated results of the `crypto-analysis` project as of 2026-10-22. Primary sources: `experiments/PROTOCOL*.md`, `experiments/RESULTS*.md`,
`experiments/registry/`. Everything here was produced with the safeguards listed in section 2. Numbers are after fees (0.10%) and slippage (0.05%) unless stated.

## 1. What was built
A deterministic, rule-based decision system for OKX spot (BTC, ETH, SOL) with a backtest engine, paper trading, a notification bot, a data collector and a statistical evidence gate for new signal sources. The system is meant as the **baseline that LLM trading agents must beat**.

## 2. Safeguards (the methodological contribution)
* **Pre-registration in git.** Protocol, configurations and candidate definitions are committed *before* the runs they govern; every addendum states whether it was written before or after results were seen. Config files are hashed (`config_hash`).
* **No look-ahead by construction and by test.** Decisions at candle close, fills at the next open; a unit test replaces future candles with random values and checks that past decisions do not change; the `audit` command repeats a truncation test on real data (idea taken from Freqtrade's `lookahead-analysis`).
* **Test-zone discipline.** Everything from 2025-01-01 requires an explicit flag and is logged in `test_log.jsonl`.
* **Counts before returns.** Candidate signals are first counted by price-free code; insufficient candidates never get a return statistic.
* **Drift-robust significance.** A circular time-shift permutation test (so that an up-market cannot pass by itself) and Holm-Bonferroni over all declared variants.
* **Forward validation.** E3/E4 paper-trade from 2026-10-22; R08 replicates the one interesting candidate on post-registration data only.

## 3. Results
### 3.1 Initial exploration (hourly system, before the protocol; not pre-registered)
Calendar-year comparison, total return (max drawdown): the hourly rule system / a ±10% range grid / buy-and-hold.
2022: −18.7% / −69.6% / −71.8% · 2023: +54.4% / +26.3% / +298.9% · 2024: +27.2% / +1.7% / +86.7% · 2025: −6.0% / −38.3% / −25.2%. Compounded: +50.2% / −75.9% / +57.2%.
The rule system lost 41 of 50 trades to its stop in a first year-long run. This motivated the protocol. The grid result is for **one** parameterization (re-centering on exit) and says nothing general about grid bots.

### 3.2 Pre-registered ladder (daily candles) and the official test
No rung beat the plain voting baseline E0 in both dev and validation Sharpe, so E0 was the accepted configuration. On the one-shot test (2025-01-01 → 2026-10-22) E0 returned +0.0% with a −5.7% drawdown while buy-and-hold lost −27.6% (−63.4% drawdown); it was almost always in cash (average exposure 9%).
E3/E4 (Donchian ensemble + BTC 200-day regime filter + volatility-target sizing) were consistent in both periods (Sharpe ≈ 1.0) but were carried forward by a **post-hoc researcher decision**, documented as such.

### 3.3 Regimes
Year by year, E3/E4 were fully in cash in the 2022 bear market (0% vs −76%), captured about 16% of the 2023 rally and about 50% of 2024, lost roughly the market's amount in 2025 with half the drawdown, and were positive in 2026 so far. 2025–2026 results for E3/E4 are exploratory (inside the test zone).

### 3.4 Trade frequency (E5)
The same structure on 4-hour candles with 5/10/20-day windows beat E3 in both periods (Sharpe 1.46 / 1.21 vs 1.08 / 0.96) at 3–5× the fees; about one completed trade a month in dev and 2.6 a month in validation.

### 3.5 Accumulation (E6)
Skipping or doubling weekly buys when BTC is below its 200-day average did **not** beat plain DCA under the pre-registered rule. Skipping reduced drawdown from −79% to −27% in dev, but only by not buying in the 2022 bear market, which also cut the amount accumulated by more than half.

### 3.6 Candidate signals (evidence gate)
* **R01, funding crowding.** Counts: 3 of 12 variants reached the event thresholds (all "low funding"); every "high funding" variant was insufficient (closest: 29 vs 30 events, not bent). Returns: the 3-day variant was significant in dev after Holm (+1.86%, adjusted p = 0.0096) but only +0.40% in validation (21% of the dev effect) → failed criterion 5. The other two failed criteria 3 and 4. **No variant passed.**
* **R08** (forward replication of the R01 3-day variant) is registered and running; the first evaluation is not before 180 days and 15 clusters.
* R02/R03 (long/short ratio, taker flow): forward-only, waiting for data. R04 (halving) declared untestable. R05/R06 (weekday, session) registered, not run. R07 (Telegram VIP channel) designed, no message seen.

## 4. Lessons
1. A result that is significant after multiple-testing correction in the development period can still shrink by about 80% out of sample; selection is dangerous even with corrections.
2. Majority of simple ideas fail the gate; counting events first prevents most p-hacking opportunities.
3. Up-markets make long-only timing look good; the permutation design is necessary, not optional.
4. Even a careful backtest can mislead on how good "being in cash" looks; the 2022 result is partly the choice of the three surviving coins and one bear market.

## 5. Limitations
Three coins chosen with hindsight (survivors); one market cycle; a handful of independent trades per year for the daily systems; Binance funding used as a proxy for R01; the kill switch is off in research runs; no market-impact or latency model beyond a flat slippage; paper trading fills at the close. Past results do not predict future returns. This is research, not investment advice.

## 6. Reproducing
```bash
python3 -m pytest -q
python3 -m okx_karar evaluate --configs experiments/e0_daily_baseline.toml,experiments/e3_regime.toml --periods dev,validation
python3 -m okx_karar audit --config experiments/e3_regime.toml
python3 -m okx_karar events --candidate R01 --stage counts      # price-free
python3 -m okx_karar events --candidate R01 --stage returns     # reads prices; run once
```
Data is fetched from public OKX and Binance endpoints (no keys). Raw data and any private material stay out of git.
