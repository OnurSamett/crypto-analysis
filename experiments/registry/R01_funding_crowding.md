# R01: funding-rate crowding (contrarian)
Tarih / Date: 2026-10-22 · Durum / Status: REGISTERED, not run · Tür / Type: own-data indicator (historical proxy + forward)

**Özet (TR):** Aşırı pozitif funding, kalabalık long pozisyonu gösterir; sonraki günlerde getirinin düşük, aşırı negatif funding'in ise yüksek olması beklenir.

**Hypothesis.** After an extreme positive funding rate, the next 1–7 day return of the same coin is lower than usual; after an extreme negative one, it is higher.
**Mechanism.** The side that pays funding is the crowded, leveraged side. Extreme levels mean one-sided leverage, which tends to unwind through liquidation cascades (mean reversion), and longs also pay carry. Directions are fixed in advance: *high funding → negative forward return; low funding → positive forward return* (one-sided).
**Evidence level.** Practitioner folklore; no vetted peer-reviewed support was found in our search. Treat as weak prior.

**Event definition.** For each coin (BTC, ETH, SOL) and each 8-hour funding settlement time `s`: the **settled** funding rate `f_s`; `z_s = (f_s − mean) / std` using only the previous 270 settlements (90 days). Event "high" if `z_s ≥ z0`, "low" if `z_s ≤ −z0`. Forward return is measured on OKX spot from the **open of the first 4H candle starting at or after `s`** to the open `h` later. Events of the same coin closer than the horizon are merged (keep the first); events on different coins within one horizon window are clustered into **one** independent event (the coins are highly correlated).
**Horizon `h`:** 1d, 3d, 7d.
**Variants (K = 12):** `z0 ∈ {2.0, 2.5}` × `h ∈ {1d, 3d, 7d}` × `side ∈ {high, low}`. Nothing else is tried.
**Metric.** Mean forward return of the **tradable long-only action**: for *low* events "buy at event, sell after h" (net of 0.30% round trip); for *high* events "exit/avoid long for h" (value = −forward return − 0.30%). One-sided block-bootstrap p-value, Holm–Bonferroni over K = 12, α = 0.05.

**Data.** Historical: Binance USDT-M public funding history (`/fapi/v1/fundingRate`, from 2019; a **cross-exchange proxy** for market-wide crowding). OKX's own funding history only goes back to 2026-07-20 (inventory 2026-10-22), so OKX is used for the forward period via `collect`. Prices and execution assumptions: OKX spot candles. A coin lacking Binance history is dropped from dev and noted.
**Periods.** dev 2022-01-01→2024-01-01, validation 2024-01-01→2025-01-01 (Binance funding). Test zone untouched; forward period from 2026-10-22 (OKX funding) for Gate criterion 8.

**Pre-check rule (integrity):** the number of independent events is counted **first**. If it is below the Gate thresholds (30 dev / 15 validation, or the forward counts), the candidate is reported as `INSUFFICIENT` and **no return statistics are computed or shown**.
**Known weaknesses.** Binance funding ≠ OKX funding (different venue, different user base); funding is also driven by interest-rate and premium components.
