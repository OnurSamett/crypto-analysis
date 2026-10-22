# Experiment results (English translation, 2026-10-22)

Turkish original: [`RESULTS.md`](RESULTS.md). All numbers are after fees (0.10%) and slippage (0.05%), spot, BTC/ETH/SOL equal weight. Protocol: [`PROTOCOL.en.md`](PROTOCOL.en.md).
Rule: results are published whatever they are. "Test" and "y2025/y2026" rows are in the test zone (see Addendum 1).

## E0–E4 ladder (daily candles)
| Configuration | dev (2022–23) return / Sharpe / maxDD | validation (2024) return / Sharpe / maxDD |
|---|---|---|
| E0 daily voting | +30.4% / 1.23 / −8.2% | −2.6% / −0.31 / −8.8% |
| E1 Donchian | +15.2% / 0.55 / −20.2% | +16.7% / 0.88 / −14.8% |
| E2 + volatility target | +5.2% / 0.23 / −46.8% | +39.4% / 0.99 / −29.4% |
| E3 + BTC 200d filter | +63.0% / 1.08 / −27.2% | +37.8% / 0.96 / −29.4% |
| E4 + entry confirmation | +62.1% / 1.07 / −26.5% | +40.4% / 1.01 / −29.2% |
| Buy-and-hold | −31.4% / 0.04 / −77.0% | +75.0% / 1.23 / −34.0% |

Outcome of the acceptance rule: no rung beat E0 in both dev and validation Sharpe (official result: E0). E3/E4 were taken into forward monitoring by the researcher's decision (Addendum 1).

## Official test (E0 only, one shot, 2025-01-01 → 2026-10-22)
E0: **+0.0%**, Sharpe 0.04, maxDD −5.7%, 6 trades, average exposure 9%. Buy-and-hold: −27.6% (maxDD −63.4%).

## Year by year (exploratory; 2025/2026 are in the test zone)
| Year | Buy-and-hold | E3 | E4 |
|---|---|---|---|
| 2022 | −76.0% | 0.0% | 0.0% |
| 2023 | +386.8% | +63.0% | +62.1% |
| 2024 | +75.0% | +37.8% | +40.4% |
| 2025 | −18.4% | −13.9% | −19.7% |
| 2026 (to Oct 22) | −13.0% | +11.7% | +8.4% |

2022: BTC stayed below its 200-day average for the whole year (0/365 days); the regime filter blocked every entry, so there were zero trades.

## E5: 4-hour fast Donchian (5/10/20 days), Sharpe relative to E3
| | dev | validation |
|---|---|---|
| E3 (daily) | 1.08 | 0.96 |
| **E5 (4h)** | **1.46** | **1.21** |

| | dev return / maxDD / completed trades / fees | validation return / maxDD / completed trades / fees |
|---|---|---|
| E3 | +63.0% / −27.2% / 9 / 52 USDT | +37.8% / −29.4% / 5 / 42 USDT |
| E5 | +119.1% / −25.5% / 23 / 143 USDT | +45.5% / −25.3% / 31 / 209 USDT |

The pre-registered rule (higher Sharpe than E3 in both periods) was **met**. E5 still trails buy-and-hold in 2024 (+83.6%).
Trade frequency: ~1 trade/month (dev), ~2.6 trades/month (validation), completed round trips.

## E6: DCA (100 USDT per week)
| Period | Variant | Invested | Final | Return | maxDD |
|---|---|---|---|---|---|
| dev | D0 plain | 10,400 | 22,621 | +117.5% | −79.2% |
| dev | D1 skip in bear regime | 4,100 | 9,260 | +125.8% | −27.1% |
| dev | D2 double in bear regime | 16,700 | 35,982 | +115.5% | −79.2% |
| validation | D0 | 5,300 | 6,931 | +30.8% | −34.2% |
| validation | D1 | 4,300 | 5,506 | +28.0% | −34.2% |
| validation | D2 | 6,300 | 8,356 | +32.6% | −34.2% |

Outcome of the acceptance rule: D1 and D2 were rejected (D1's return and IRR are lower in validation; D2's return is lower in dev). IRR is extremely volatile in this short
window with few cash flows and should not be interpreted.

## Audit
`audit`: the E0, E3 and E5 signals passed the truncation (look-ahead) test on BTC/ETH/SOL with zero difference. The E3 score equals the one from only the last 300 daily candles; the E5 score equals the one from the last ≥900 four-hour candles.

## Limits
* The three coins were chosen looking back from today (all survived); this inflates buy-and-hold.
* A single market cycle and few independent observations. Results are hints, not proof.
* The compounding of yearly slices assumes a fresh start every year; it differs from a continuous run.
* The kill switch is off in the research runs; in real use it will be on and will cut drawdowns.

## Registry (evidence gate) results: R01, 2026-10-22
Plan, code and results were committed in this order (`95bc64a`, `544caa6`, `baf0860`). Numbers are after a 0.30% round trip; p-values use a circular time-shift permutation, Holm correction with K = 12.

| Variant (all "low funding") | dev mean | Holm p | validation mean | Outcome |
|---|---|---|---|---|
| z0=2.0 · 1 day | +0.18% | 1.00 | −0.24% | failed criterion 4 |
| z0=2.5 · 1 day | −0.40% | 1.00 | −0.16% | failed criterion 3 |
| **z0=2.0 · 3 days** | **+1.86%** | **0.0096** | +0.40% (90% interval −0.67% … +1.56%) | failed criterion 5 |

In the count stage only 3 of 12 variants reached the thresholds; every "high funding" variant was insufficient (closest: 29 dev events vs the threshold of 30). The 3-day variant was significant in dev after correction, but its validation effect was 21% of the dev effect (the rule requires at least 50%). No variant passed.
R08 is the forward, single-hypothesis replication of this variant using data after 2026-10-23 only.
