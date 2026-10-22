# R08: forward replication of R01 `z0=2.0 h=3d side=low`
Date: 2026-10-22 · Status: REGISTERED, not run · Type: single-hypothesis out-of-sample replication

**Summary (TR):** R01'in tek ilginç bulgusu (düşük funding sonrası 3 günlük getiri) dev'de Holm sonrası anlamlıydı ama validation'da küçüldü. Bu kayıt, aynı tanımı yalnızca kayıttan SONRAKİ veriyle, bir kez ve tek hipotezle sınar.

**Hypothesis.** After an extremely low funding rate (`z ≤ −2.0` against the previous 270 settlements), the net 3-day forward return of the same coin is positive.
**Mechanism.** As R01: one-sided leverage (crowded shorts) unwinds through short squeezes; shorts also pay carry.
**Why this entry exists.** In R01 this variant was significant in dev after Holm over K = 12 (+1.86%, adjusted p = 0.0096) but fell to +0.40% in validation (21% of the dev effect) and failed Gate criterion 5. The dev estimate is subject to selection (winner's curse). A forward replication on data that did not exist at registration is the only clean way to decide between "weak or decayed effect" and "noise".

## Fixed definition (identical to R01, nothing may change)
* Funding data: Binance USDT-M public history for BTCUSDT, ETHUSDT, SOLUSDT (the same source as R01), continued forward. OKX funding collected by `collect` is stored as a secondary series and is **not** used for the test.
* Event: `z0 = 2.0`, `side = low`, `h = 3d`, 270-settlement z-score excluding the current settlement, irregular spans excluded, same-coin merge and cross-coin clustering exactly as in `R01_count_plan.md`.
* Prices and costs: OKX spot 4H candle open at settlement time `s` and at `s + 3d`; flat 0.30% round trip; cluster return = equal-weight mean of the coins in the cluster.
* **Forward window:** events with `s ≥ 2026-10-23 00:00 UTC` (the first day after registration) and `s + 3d ≤ evaluation time`.

## Test (K = 1)
Statistic: mean cluster net return. P-value: circular time-shift permutation within the forward window (all event times moved by one common random shift on the 8-hour grid, `B = 5000`, seed `20261023`), one-sided. **Success:** mean > 0 **and** p < 0.05. No multiple-testing correction is needed (a single pre-registered hypothesis).
Reported but not gating: the ratio of the forward mean to the R01 dev mean (+1.86%), a 90% bootstrap interval, per-coin means, and the same statistic at `z0 × 0.8` and `× 1.2`.

## Single evaluation rule (no peeking)
The test is evaluated **exactly once**, at the first date on which **both** hold: (a) at least **180 days** have elapsed since 2026-10-23 and (b) at least **15 independent clusters** have completed their 3-day horizon. Whether (b) holds is decided by a **price-free counter** (the existing `events` counting code), which may be run at any time. **No return statistic is computed or looked at before the evaluation date.** If (b) is not met after **18 months**, the result is reported as `INSUFFICIENT` and no return is computed.
The evaluation code is committed before the evaluation date; the evaluation is run once. Parameters are never changed; a change would start a new registry entry.

## Outcomes (stated in advance)
* **Success →** R01-3d-low is reported as *replicated forward (single hypothesis)*. It may then be sent as a labelled "monitoring" notification; promotion beyond that needs a review of the whole R01 history, because Gate criterion 5 failed in R01.
* **Failure →** the effect is reported as not replicated. Publication either way.

## Expectation stated in advance
A null result is more likely than not: the dev estimate is inflated by selection and validation already shrank it by about 80%.
