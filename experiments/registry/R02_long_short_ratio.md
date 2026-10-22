# R02: long/short account ratio crowding (contrarian)
Tarih / Date: 2026-10-22 · Durum / Status: REGISTERED, not run · Tür / Type: own-data indicator (forward-only)

**Özet (TR):** Uzun/kısa hesap oranı aşırı yüksekse kalabalık long beklenir; sonraki 1–3 günde getirinin düşük olması beklenir.

**Hypothesis.** An extremely high OKX contract long/short *account* ratio is followed by a lower 1–3 day return; an extremely low ratio by a higher one. (Directions fixed: high → negative, low → positive.)
**Mechanism.** Account-count ratios mostly reflect retail positioning; one-sided retail positioning is a crowding proxy, followed by squeezes against the crowd.
**Evidence level.** Practitioner folklore; no vetted study found. Weak prior.

**Event definition.** Per coin, on hourly samples: `z = (ratio − mean)/std` over the previous 30 days (720 hourly samples); event when `z ≥ 2.0` (high) or `≤ −2.0` (low). Forward return from the open of the next 1H OKX candle. Same-coin events closer than the horizon are merged; same-horizon events across coins are clustered into one.
**Horizon:** 1d, 3d. **Variants (K = 4):** `side ∈ {high, low}` × `h ∈ {1d, 3d}` at `z0 = 2.0`.
**Metric.** As R01 (net of 0.30% round trip; "avoid" value for high events). Holm–Bonferroni over K = 4, α = 0.05.

**Data.** OKX `rubik/stat/contracts/long-short-account-ratio`. History available at registration: only ~180 days (daily) / 30 days (hourly) — **too short for dev/validation**. Therefore the backfilled data is **exploration only**, and the candidate is evaluated **forward-only** from 2026-10-22 via `collect` (criteria 2 and 8 work together as events accumulate). Expect months to years before 30 independent events exist.

**Pre-check rule (integrity):** the number of independent events is counted **first**. If it is below the Gate thresholds (30 dev / 15 validation, or the forward counts), the candidate is reported as `INSUFFICIENT` and **no return statistics are computed or shown**.
