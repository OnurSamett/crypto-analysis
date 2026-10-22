# Registry index / Aday dizini

All entries registered **2026-10-22**, before any test. Gate: `../PROTOCOL.md` → Ek 3 (English: `../PROTOCOL.en.md` → Addendum 3).

| Id | Candidate | Type | K | Data available for dev/validation? | Expected difficulty |
|---|---|---|---|---|---|
| [R01](R01_funding_crowding.md) | Funding crowding (contrarian) | own-data | 12 | **Yes**, via Binance public funding history (proxy); OKX forward | Moderate: the only candidate with real historical coverage |
| [R02](R02_long_short_ratio.md) | Long/short account ratio crowding | own-data | 4 | No (≈180 days) → **forward-only** | Slow: months to years for enough events |
| [R03](R03_taker_flow.md) | Taker flow imbalance | own-data | 4 | No (≈30 days hourly) → **forward-only** | Hard: short horizon vs 0.30% cost |
| [R04](R04_halving_cycle.md) | Halving / four-year cycle | cycle | 0 | n = 3–4 cycles | **Not testable**; descriptive only |
| [R05](R05_weekday_effect.md) | Day-of-week | calendar | 7 | Yes (daily candles) | Hard: effect must exceed 0.30%/day |
| [R06](R06_session_effect.md) | Trading session | calendar | 3 | Yes (4H candles) | Hard: literature finds no persistence |
| [R07](R07_vip_channel_signals.md) | Telegram VIP channel | external | 1 | After export (chronological split) | Likely null; integrity report is the main value |

**Not registered on purpose:** hour-of-day (24 hypotheses), month-of-year, holidays: too many comparisons for too little evidence. Each would need its own entry.

**Status legend:** REGISTERED (not run) → RUNNING → `INSUFFICIENT` | `FAILED GATE (criterion n)` | `MONITORING` | `VALIDATED`. Updates are appended below, never edited in place.

## Status log
- 2026-10-22: R01–R07 registered. No test has been run.
- 2026-10-22: R01 count plan committed (`50ac6a1`), counting code committed (`01e5ad1`), then the count was run **once**. No returns computed. Results: [`R01_counts.md`](R01_counts.md) / `R01_counts.json`.
  3 of 12 variants reached the thresholds (all `side=low`: `z0=2.0 h=1d`, `z0=2.0 h=3d`, `z0=2.5 h=1d`); the other 9 are `INSUFFICIENT` and will not be evaluated. K stays 12 for Holm-Bonferroni.
  Near miss, not bent: `z0=2.0 h=1d side=high` has n_dev = 29 (threshold 30).
  Data note: SOL had 101 irregular funding steps (98 of 2 h, 3 of 4 h), all between 2022-11-09 and 2022-11-18. Per plan, windows containing them are excluded, which leaves SOL with a defined z-score for 84% of its dev settlements (BTC and ETH: 100%).
  The return stage for the 3 surviving variants requires a separate go-ahead.
- 2026-10-22: R01 return stage run **once** (plan `95bc64a`, code `544caa6`). Results: [`R01_returns.md`](R01_returns.md) / `R01_returns.json`. No variant reached `MONITORING`.
  * `z0=2.0 h=1d low`: dev +0.18%, raw p = 0.113, Holm p = 1.0 → FAILED GATE (criterion 4).
  * `z0=2.5 h=1d low`: dev −0.40% → FAILED GATE (criterion 3).
  * `z0=2.0 h=3d low`: dev +1.86%, raw p = 0.0008, **Holm p = 0.0096** (criteria 3 and 4 passed); validation +0.40% (90% interval −0.67% … +1.56%), i.e. 21% of the dev effect, below the 50% required → **FAILED GATE (criterion 5)**. Criteria 6 and 7 would have passed (all three coins positive, both z0 perturbations positive, audit passed) but are not reached under the first-failure rule. The verdict is not bent.
  Interpretation: a dev result that is significant even after correcting for 12 variants did not hold up out of sample; same sign, much smaller. Consistent with a weak or decayed effect, or noise. Nothing is sent as a signal.
