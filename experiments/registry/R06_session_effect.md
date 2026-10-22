# R06: trading-session effect (UTC, 8-hour sessions)
Tarih / Date: 2026-10-22 · Durum / Status: REGISTERED, not run · Tür / Type: calendar pattern

**Özet (TR):** Asya / Avrupa / ABD seansları arasında getiri farkı var mı? Büyük çalışmalar tutarlı bir etki bulmadı; kapı ölçütü 3 muhtemelen karşılanmaz.

**Hypothesis.** The mean return within at least one 8-hour UTC session (Asia 00–08, Europe 08–16, US 16–24) differs from the mean of the other two sessions (two-sided).
**Mechanism.** Liquidity and information flow differ by session (US equity hours). The largest study we found (Baur et al., 2019, 15M+ observations from seven exchanges) reports time-varying effects without consistent persistence; we register this as a low-prior test.
**Event definition.** One event = one session return (two consecutive 4H candles) of one coin; non-overlapping; pooled equal-weight across BTC, ETH, SOL.
**Horizon:** one session. **Variants (K = 3):** each session vs the other two, two-sided.
**Metric.** Difference of means; tradable action "hold only that session" is net of **0.30%** round trip per day. Block-bootstrap p-value (blocks of 2 weeks), Holm–Bonferroni over K = 3, α = 0.05.
**Data / periods.** OKX 4H candles; dev 2022–2024, validation 2024; test zone untouched.
**Not registered (to limit multiplicity):** 24 separate hours of the day, month-of-year effects, holiday effects. They would need their own entry with their own K.

**Pre-check rule (integrity):** the number of independent events is counted **first**. If it is below the Gate thresholds (30 dev / 15 validation, or the forward counts), the candidate is reported as `INSUFFICIENT` and **no return statistics are computed or shown**.
