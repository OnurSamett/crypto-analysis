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
