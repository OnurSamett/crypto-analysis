# R01 event-count plan (written and committed BEFORE the code and before any count)
Tarih / Date: 2026-10-22 · Approved by the researcher the same day · Applies to: [R01](R01_funding_crowding.md)

**Özet (TR):** R01 için 12 varyantın bağımsız olay sayısı, yalnızca zaman damgası ve funding serisiyle sayılır (fiyat verisi sayım koduna hiç verilmez). Eşik: dev ≥ 30, validation ≥ 15. Altındakiler `INSUFFICIENT` olur, getiri hesaplanmaz.

## Purpose
Count independent events for each of the 12 registered variants (`z0 ∈ {2.0, 2.5}` × `h ∈ {1d, 3d, 7d}` × `side ∈ {high, low}`) in `dev` (2022-01-01 → 2024-01-01) and `validation` (2024-01-01 → 2025-01-01). **No returns are computed or shown at this stage.**

## Algorithm (fixed now)
1. **Data.** Binance USDT-M public funding history for BTCUSDT, ETHUSDT, SOLUSDT from 2021-09-01 to 2025-01-01 (warm-up for the z-score). Cached locally. Prices are **not** loaded.
2. **Interval audit.** Settlements should be 8 hours apart (± 1 minute tolerance). Periods with other spacing are excluded and reported (the definition is not changed). Coverage per coin (first/last date, row count) is reported.
3. **z-score.** For settlement `s`: `z_s = (f_s − mean) / std`, with mean and sample standard deviation (ddof = 1) over the **previous 270 settlements, excluding `s`**. Undefined (NaN) until 270 previous settlements exist or when std = 0.
4. **Candidates.** `high`: `z_s ≥ z0`; `low`: `z_s ≤ −z0`.
5. **Processing is per period and per variant, independently.** For period `[start, end)` and horizon `h`, only settlements with `start ≤ s` and `s + h ≤ end` are eligible. This keeps a dev event's horizon from running into validation and a validation event's horizon from running into the test zone (2025+), which stays untouched.
6. **Merge within a coin (depends on h).** Chronologically keep the first eligible event, drop every later one with `s < kept + h`, then keep the next, and so on.
7. **Cluster across coins (depends on h).** Pool the kept events of all coins. A cluster starts at the first pooled event `t0` and contains every event with `s < t0 + h`; the next cluster starts at the first event `≥ t0 + h`. **The number of clusters is the number of independent events.**
8. **Output.** `experiments/registry/R01_counts.md` (table + data coverage + audit findings) and `R01_counts.json`. Columns: variant, `n_dev`, `n_val`, per-coin kept-event counts, verdict.
9. **Verdict.** `n_dev ≥ 30` **and** `n_val ≥ 15` → `COUNT_OK` (proceeds to the return stage, which needs a separate go-ahead); otherwise `INSUFFICIENT` (no returns will be computed for that variant). `K` stays **12** in the Holm–Bonferroni correction regardless of how many variants survive (conservative).

## Structural safeguard
The counting module (`okx_karar/events.py`) accepts only timestamps and funding series. It imports no price data and no candle loader, and a unit test checks this. Counting cannot leak return information.

## Checks before running
* Unit tests with synthetic series of known event counts: z-score excludes the current value, merge, cross-coin clustering, period eligibility at both boundaries.
* The code is committed **before** the real run. The run is executed **once**; if a bug is found afterwards, the fix and a re-run are recorded in the status log in `INDEX.md` with the reason.

## Prior expectation (theoretical, stated before seeing data)
Funding is fat-tailed and autocorrelated, so extreme observations cluster. 1-day variants are expected to reach the thresholds more often than 7-day ones; most 7-day variants may end `INSUFFICIENT`. This is a guess, not a finding.

## Publication
The counts file is published whatever the outcome.
