# R01 independent-event counts

Generated 2026-10-22 09:08 UTC. Counts only; **no returns were computed.** Plan: `R01_count_plan.md`. Thresholds: dev >= 30, validation >= 15 independent events.

## Data coverage (Binance USDT-M funding)

| Coin | First | Last | Rows | Irregular 8h steps |
|---|---|---|---|---|
| BTC | 2021-09-01 | 2024-12-31 | 3654 | 0 |
| ETH | 2021-09-01 | 2024-12-31 | 3654 | 0 |
| SOL | 2021-09-01 | 2024-12-31 | 3729 | 101 |

## Variants (K = 12)

| Variant | n_dev | n_validation | per-coin kept (dev) | per-coin kept (validation) | Verdict |
|---|---|---|---|---|---|
| z0=2.0 h=1d side=high | 29 | 39 | BTC:19, ETH:18, SOL:19 | BTC:31, ETH:28, SOL:29 | **INSUFFICIENT** |
| z0=2.0 h=3d side=high | 15 | 17 | BTC:9, ETH:10, SOL:11 | BTC:14, ETH:14, SOL:13 | **INSUFFICIENT** |
| z0=2.0 h=7d side=high | 11 | 10 | BTC:6, ETH:6, SOL:7 | BTC:9, ETH:9, SOL:10 | **INSUFFICIENT** |
| z0=2.5 h=1d side=high | 26 | 32 | BTC:19, ETH:15, SOL:12 | BTC:19, ETH:20, SOL:25 | **INSUFFICIENT** |
| z0=2.5 h=3d side=high | 13 | 13 | BTC:9, ETH:9, SOL:8 | BTC:11, ETH:12, SOL:11 | **INSUFFICIENT** |
| z0=2.5 h=7d side=high | 9 | 9 | BTC:6, ETH:6, SOL:4 | BTC:9, ETH:8, SOL:9 | **INSUFFICIENT** |
| z0=2.0 h=1d side=low | 113 | 37 | BTC:57, ETH:58, SOL:55 | BTC:22, ETH:15, SOL:19 | **COUNT_OK** |
| z0=2.0 h=3d side=low | 67 | 17 | BTC:41, ETH:35, SOL:34 | BTC:11, ETH:9, SOL:11 | **COUNT_OK** |
| z0=2.0 h=7d side=low | 41 | 10 | BTC:29, ETH:28, SOL:22 | BTC:5, ETH:6, SOL:8 | **INSUFFICIENT** |
| z0=2.5 h=1d side=low | 72 | 21 | BTC:25, ETH:29, SOL:39 | BTC:14, ETH:7, SOL:9 | **COUNT_OK** |
| z0=2.5 h=3d side=low | 45 | 12 | BTC:21, ETH:20, SOL:26 | BTC:9, ETH:4, SOL:6 | **INSUFFICIENT** |
| z0=2.5 h=7d side=low | 33 | 8 | BTC:19, ETH:16, SOL:18 | BTC:5, ETH:3, SOL:5 | **INSUFFICIENT** |

3 of 12 variants reached the thresholds. K stays 12 in the Holm-Bonferroni correction.
