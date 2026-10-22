# Experiment protocol (English translation)

> **The Turkish [`PROTOCOL.md`](PROTOCOL.md) is the authoritative, pre-registered text.** This file is a translation written on
> 2026-10-22, after the commits that contain the original; it adds nothing new. If the two differ, the Turkish text prevails.

Goal: to test, without tuning on the results, five hypotheses that might explain the weak results of the rule-based system.

## Periods
| Name | Range | Use |
|---|---|---|
| dev | 2022-01-01 → 2024-01-01 | comparison and elimination |
| validation | 2024-01-01 → 2025-01-01 | second confirmation for the elimination decision |
| test | 2025-01-01 → 2026-10-22 | **last, once**, with `--allow-test`; every run is logged to `test_log.jsonl` |

Note: we saw the calendar-year 2022–2025 results of the hourly baseline system before this protocol. 2025 and later are therefore
not "perfectly clean"; the report says so.

## Hypotheses (a ladder; each rung adds to the previous one)
| Id | Change | Fixed parameters |
|---|---|---|
| E0 | Existing voting system, daily candles | same thresholds as `config.toml`, stop 2×ATR |
| E1 | Donchian ensemble, no stop | lookbacks 20/50/100, entry ≥ 2/3 long, exit ≤ 1/3 long |
| E2 | + volatility-target sizing | 20% annual target, 20-day window, cap 30% |
| E3 | + BTC > 200-day average (for new longs) | 200 days |
| E4 | + entry confirmation | 2 consecutive days, volume ≥ 20-day average |

All parameters were taken from common defaults in the literature, not tuned by looking at data.
Common settings: fee 0.10%, slippage 0.05%, kill switch off (`max_drawdown = 0.99`, so it does not end a multi-year run early),
`max_atr_pct = 0.20` (0.05 had been tuned for hourly candles).

## Acceptance rule
Rung k is accepted, relative to **the best configuration accepted so far**, if and only if its Sharpe ratio is higher in both
the `dev` and the `validation` periods. A rejected rung is not carried into later rungs (if needed it is rebuilt and recorded as a separate experiment).

## Test period
The last accepted configuration is run once on the `test` period, together with E0 and buy-and-hold. The result is reported
whatever it is. If parameters change based on the result, that is a new experiment and the test period becomes development data.

## Limits
* The three coins were chosen looking back from today (all survived), which inflates buy-and-hold a little.
* A single market cycle and few independent observations: results are hints, not proof.
* The regime filter and confirmation apply only to long entries (spot).

---

## Addendum 1 (2026-10-22): written AFTER the first results

This addendum was added after the dev and validation results had been seen; the decision below was made looking at the results and this is stated openly.

**Ladder result (summary).** Under the acceptance rule no rung beat E0 in both dev and validation Sharpe. The official outcome: the accepted configuration is **E0**.
E3/E4 were consistent in both periods (Sharpe ≈ 1.0) but trailed E0 in dev.

**Decision (researcher).** E3 and E4 are carried forward as *candidates for forward monitoring* although they did not pass the acceptance rule. This does not mean they passed it.

**Test zone (2025-01-01 → 2026-10-22).**
* For E0 the official, one-shot test is run (the original protocol).
* For E3/E4 every result from this zone is **exploratory**, not a clean validation: the selection was made after the results were seen.
* Every run falling in the test zone (including `y2025`, `y2026`) requires `--allow-test` and is written to `test_log.jsonl`.

**Yearly slices.** `y2022 … y2026` show behaviour in bull/bear regimes. They do not drive acceptance decisions.

**True out-of-sample validation.** Data after 2026-10-22. From that date E3 and E4 are followed in paper trading (`sim`) with separate state files.
* Parameters, thresholds and configuration are **not changed** during monitoring; a change counts as a new experiment and resets the monitoring.
* Time of evaluation: at least **180 days** *and* at least **15 completed trades**, whichever comes later.
* Criterion: Sharpe and maximum drawdown relative to buy-and-hold over the same period. Return alone is not a criterion.
* The result is published even if negative.

---

## Addendum 2 (2026-10-22): E5 and E6, written WITHOUT looking at results

Recorded after reading the documentation of open-source projects (Freqtrade, Hummingbot, TradingAgents), before any new run.

### E5: the frequency hypothesis
*Question:* is the same regime-filtered Donchian structure, on 4-hour candles with short windows (5/10/20 days), better than the daily E3? Expectation: a few trades per month.
* Configuration: `experiments/e5_fast4h.toml`. The only differences from E3 are the candle length and window lengths; calendar durations are fixed (1 day = 6 candles).
* Periods: `dev` and `validation` only (the test zone is not touched).
* Acceptance: **higher Sharpe than E3 in both dev and validation**. Number of trades and total fees are also reported;
  if Sharpe is higher but fees are high, interpretation follows, but the rule does not change.

### E6: accumulation (DCA) and the regime tilt
The user buys regularly instead of selling, so the relevant comparison is DCA, not buy-and-hold.
*Question:* does changing the purchase amount while BTC is below its 200-day average improve DCA?
* Rules (fixed): every Monday 00:00 UTC, 100 USDT split equally across BTC/ETH/SOL; fee 0.10%, slippage 0.05%.
* Variants: **D0** plain DCA. **D1** no purchase while BTC < 200-day average (the unspent amount does not count as invested).
  **D2** double purchase while BTC < 200-day average.
* Metrics: total invested, final value, return on invested amount, money-weighted annual return (IRR), average cost, maximum drawdown of portfolio value.
* Periods: `dev` and `validation`. Acceptance (D1 or D2 vs D0): IRR **and** return on invested amount higher in both periods, and maximum drawdown no more than 5 points worse than D0.
* Note: no peer-reviewed evidence on DCA comparisons of this kind was found; industry sources (e.g. a Bull Bitcoin report) are unverified.

### Audit (a method, not a hypothesis)
The `audit` command applies the ideas of Freqtrade's `lookahead-analysis` (comparison with truncated data) and `recursive-analysis`
(dependence on history length) to real data. A configuration's backtest results must pass the audit before being reported.

### Known defect (documented, not fixed)
The `risk.vol_window` field is not used anywhere; annual volatility is computed with `signals.volume_window`. In E2–E4 both are 20,
so results were not affected. E5 uses `signals.volume_window = 120` (20 days). The fix will be a separate change; past runs do not change.

---

## Addendum 3 (2026-10-22): evidence gate for new signal sources (written WITHOUT looking at results)

This addendum applies to calendar/cycle patterns (halving, day/time-of-day effects), Telegram VIP channel signals, and indicators
built from our own collected data (funding, open interest, long/short ratio, book depth). A source cannot be sent as a **"signal"**
in a notification before it passes the gate below.

### Pre-registration (before scanning)
For every candidate, a file `experiments/registry/<id>.md` is committed **before** any test is run. Contents: the hypothesis,
**why it should work** (mechanism), **the number K and list of all variants to be tried**, the event definition, the holding period (horizon), the metric.
A variant not in the registry is "exploration" and does not enter the gate. No bulk scanning without a rationale.

### Gate criteria (all must hold)
1. **Rationale:** a mechanism written in the registry.
2. **Enough independent observations:** an *independent event* is one at least a horizon apart on the same instrument. At least **30** events in `dev` and **15** in `validation`. If insufficient, the result is only noted (e.g. the halving cycle: 3–4 observations → automatically insufficient).
3. **After costs:** mean return per event > 0 after deducting a 0.30% round trip (fee + slippage).
4. **Multiple-testing correction:** the p-value comes from a block bootstrap / permutation test; **Holm–Bonferroni** over the K variants, α = 0.05.
5. **Out of sample:** in `validation` the effect has the same sign and is at least **half** the `dev` effect.
6. **Robustness:** the same sign on **all three** of BTC, ETH, SOL; the effect stays positive when the main parameter is scaled ×0.8 and ×1.2.
7. **Look-ahead audit:** `audit` (truncation test) must pass; no information after the event time may be used.
8. **Forward validation:** ≥ **90 days** and ≥ **15 events** of paper monitoring with unchanged parameters. A change resets the counter.

### Tiers
| Tier | Condition | Notification |
|---|---|---|
| **Experimental** | not in the gate / criteria 1–7 incomplete | not sent (or sent to a separate channel clearly labelled "EXPERIMENTAL", if preferred) |
| **Monitoring** | 1–7 passed, 8 in progress | labelled "monitoring" |
| **Validated** | 1–8 passed | sent as a "signal" |

### VIP channel signals
A channel's signals are tested as one strategy: entry at the first price **after** the message time (slippage + fee); whichever of TP/SL is hit first.
The comparison is against a **random-entry** baseline (same instruments and hours, same TP/SL rule, 1000 permutations). Deleted/edited messages and
delayed posts are reported separately. Raw messages stay under `private/` and never enter the repository; only aggregate statistics without the channel name are published.

### Our own data collector
Data accumulated by `collect` (funding, open interest, depth) is **forward-only from 2026-10-22**; there is no dev/validation, so criteria 2 and 8 work together as events accumulate. The 30 days of
backfilled ratio and taker volume alone do not satisfy criterion 2.

### Periods
The existing `dev` / `validation` / test-zone definitions apply unchanged. Every run in the test zone (2025+) requires `--allow-test` and is written to `test_log.jsonl`.
