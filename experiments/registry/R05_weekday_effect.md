# R05: day-of-week effect (UTC)
Tarih / Date: 2026-10-22 · Durum / Status: REGISTERED, not run · Tür / Type: calendar pattern

**Özet (TR):** Haftanın günlerinin getirisi farklı mı? Literatür karışık; mekanizma zayıf. Maliyet duvarı yüksek, başarısız olması beklenir.

**Hypothesis.** The mean daily return of at least one weekday differs from the mean of the other six days (two-sided).
**Mechanism.** Weekend liquidity and the timing of US-hours institutional flows could shift returns by weekday. Evidence in our search is mixed and the effect appears to be time-varying (one study finds higher Monday returns, another finds no persistent patterns).
**Event definition.** One event = one UTC daily candle (close-to-close return) of one coin on a given weekday. Non-overlapping, so independence holds. Pooled across BTC, ETH, SOL by equal-weight daily return.
**Horizon:** 1 day. **Variants (K = 7):** each weekday vs the other six, two-sided.
**Metric.** Difference of means; for the tradable long-only action "hold only that weekday", value = mean return − **0.30%** per round trip. Block-bootstrap p-value (blocks of 4 weeks), Holm–Bonferroni over K = 7, α = 0.05.
**Data / periods.** OKX daily candles; dev 2022–2024 (≈104 events per weekday), validation 2024; test zone untouched.
**Expectation (stated in advance).** Gate criterion 3 requires > 0.30% mean per event after costs; most plausible weekday effects are smaller. A failure is the expected outcome and will be reported as such.

**Pre-check rule (integrity):** the number of independent events is counted **first**. If it is below the Gate thresholds (30 dev / 15 validation, or the forward counts), the candidate is reported as `INSUFFICIENT` and **no return statistics are computed or shown**.
