# R01 return-stage plan (written and committed BEFORE the code and before any return is computed)
Date: 2026-10-22 · Approved to proceed by the researcher the same day · Applies to: [R01](R01_funding_crowding.md), the 3 variants marked `COUNT_OK` in [R01_counts.md](R01_counts.md)

Variants under test (all `side = low`, expected direction: **positive** forward return):
`z0=2.0 h=1d`, `z0=2.0 h=3d`, `z0=2.5 h=1d`. The other 9 stay `INSUFFICIENT` and are not evaluated; they enter the Holm-Bonferroni correction with p = 1.0, so K stays 12.

## Event returns (fixed now)
1. Events are the **kept** events and **clusters** from the count (same code, same Binance funding data).
2. For a kept event of coin `c` at settlement time `s`: entry = **open of the OKX spot 4H candle starting at `s`** (settlements fall on 00/08/16 UTC, which are 4H candle boundaries); exit = open of the 4H candle starting at `s + h`. Net return = `open[s+h] / open[s] − 1 − 0.0030` (a flat 0.30% round trip, as registered). If a candle is missing the event is skipped and the number skipped is reported.
3. **Cluster return** = equal-weight mean of the net returns of the coins that have a kept event in the cluster (each measured from its own `s`). The independent observation is the cluster. The statistic is the **mean cluster net return**.

## P-value: circular time-shift permutation (chosen now, because of market drift)
The validation year (2024) was a strong up-market, so "mean return > 0" alone would pass for almost any long-only timing. Under the null that event timing is unrelated to returns, the same events moved to random times must do just as well. Therefore:
* For each variant and period `[start, end)`, let `L = end − h − start` (the span in which an event is still eligible). Draw a shift `δ` uniformly from the 8-hour grid points in `[0, L)`. Move **every** event time `t` to `start + ((t − start + δ) mod L)` (the same shift for all coins; cluster structure and event spacing are preserved apart from wrap-around).
* Recompute the same statistic (cluster definition fixed from the original events; members keep their coins). `B = 5000` shifts, seed `20261022`.
* One-sided p-value: `p = (1 + #{shifted mean ≥ observed mean}) / (1 + B)`, computed on `dev`.
* **Holm-Bonferroni** over K = 12 (9 untested variants have p = 1.0), α = 0.05. Gate criterion 4 requires an adjusted p < 0.05.

## Remaining gate criteria, as applied here
* **3 (after costs):** `dev` mean cluster net return > 0 (absolute, as registered).
* **4:** as above.
* **5 (out of sample):** `validation` mean cluster net return > 0 **and** ≥ 0.5 × the `dev` mean. No significance is required in validation; its bootstrap 90% interval is reported for transparency.
* **6 (robustness):** (a) for each of BTC, ETH, SOL separately, the mean net return of that coin's kept events pooled over dev + validation is > 0; a coin with fewer than 5 kept events counts as **not satisfied**. (b) With `z0 × 0.8` and `z0 × 1.2` (the main parameter), the mean cluster net return stays > 0 in both `dev` and `validation`; the event counts under these perturbations are reported. These perturbed variants are robustness checks, not new tests (K unchanged).
* **7 (look-ahead audit):** truncation audit of the z-score series (full-history value must equal the prefix-only value at every checked settlement).
* **8 (forward):** not part of this stage. Passing 1–7 only earns the tier `MONITORING`; forward validation then needs ≥ 90 days and ≥ 15 events of OKX funding via `collect`, with unchanged parameters.

## Output and verdicts
`R01_returns.md` / `R01_returns.json`: for all 12 variants: counts (from the count stage), dev and validation mean cluster net returns, number of clusters used, number of events skipped for missing candles, raw and Holm-adjusted p, unconditional drift context (mean net return of entering **every** 8-hour settlement for the same horizon, per period), pass/fail per criterion, and the final tier: `INSUFFICIENT`, `FAILED GATE (criterion k)` (first failed), or `MONITORING`.
The result is published whatever it is, and run **once**; a bug found afterwards is fixed and re-run only with a note in the status log.

## Expectation stated in advance
I expect weak or null results: the funding-crowding effect is folklore without vetted support, the 0.30% round trip is large for 1–3 day horizons, and the validation year is a bull market. A failure at criterion 4 or 5 is the most likely outcome and would be a legitimate result.
