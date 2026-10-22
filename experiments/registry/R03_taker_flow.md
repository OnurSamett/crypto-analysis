# R03: taker (aggressor) volume imbalance — short-term continuation
Tarih / Date: 2026-10-22 · Durum / Status: REGISTERED, not run · Tür / Type: own-data indicator (forward-only)

**Özet (TR):** Alıcı-baskın (agresif alım) saatlerinin ardından kısa vadeli getirinin yüksek olması beklenir (devam).

**Hypothesis.** When aggressive buying dominates, the next 4–24 hour return is higher than usual; when aggressive selling dominates, lower. (Directions fixed: continuation, buy-heavy → positive, sell-heavy → negative.)
**Mechanism.** Impatient/informed order flow is persistent (order-splitting, slow information diffusion). A related academic finding is that the first part of the day predicts the last part in intraday Bitcoin data, attributed to liquidity provision; it does not by itself prove this exact effect.
**Evidence level.** Weak-to-moderate for intraday persistence in general; unverified for this specific indicator.

**Event definition.** Per coin and hour: `share = buy_vol / (buy_vol + sell_vol)` (OKX `rubik/stat/taker-volume`, SPOT). `z` over the previous 30 days of hourly shares (720 samples). Event: `z ≥ 2.0` (buy-heavy) or `≤ −2.0` (sell-heavy). Forward return from the next 1H candle open. Merging/clustering as in R01.
**Horizon:** 4h, 24h. **Variants (K = 4):** `side ∈ {buy-heavy, sell-heavy}` × `h ∈ {4h, 24h}`.
**Metric.** As R01 (tradable action: buy-heavy → long for h, net of 0.30% round trip; sell-heavy → "avoid long" value). Holm–Bonferroni over K = 4, α = 0.05.

**Data.** OKX taker volume: ~30 days hourly / ~180 days daily at registration — **forward-only** evaluation from 2026-10-22; backfill is exploration only.
**Note.** At a 4-hour horizon the 0.30% round trip is large relative to typical edges; the candidate is expected to struggle on Gate criterion 3.

**Pre-check rule (integrity):** the number of independent events is counted **first**. If it is below the Gate thresholds (30 dev / 15 validation, or the forward counts), the candidate is reported as `INSUFFICIENT` and **no return statistics are computed or shown**.
