# R01 return-stage results

Generated 2026-10-22 09:14 UTC. Plan: `R01_returns_plan.md`. Run once. Net returns are after a flat 0.30% round trip; permutation p-values use 5000 circular time shifts (seed 20261022); Holm-Bonferroni over K = 12.

| Variant | clusters dev/val | mean dev | mean val (90% CI) | p dev | Holm p | drift dev/val | Tier |
|---|---|---|---|---|---|---|---|
| z0=2.0 h=1d side=high | 29/39 | - | - | - | - | - | INSUFFICIENT |
| z0=2.0 h=3d side=high | 15/17 | - | - | - | - | - | INSUFFICIENT |
| z0=2.0 h=7d side=high | 11/10 | - | - | - | - | - | INSUFFICIENT |
| z0=2.5 h=1d side=high | 26/32 | - | - | - | - | - | INSUFFICIENT |
| z0=2.5 h=3d side=high | 13/13 | - | - | - | - | - | INSUFFICIENT |
| z0=2.5 h=7d side=high | 9/9 | - | - | - | - | - | INSUFFICIENT |
| z0=2.0 h=1d side=low | 113/37 | +0.18% | -0.24% (-1.18%, +0.74%) | 0.1128 | 1.0000 | -0.26%/-0.07% | **FAILED GATE (criterion 4)** |
| z0=2.0 h=3d side=low | 67/17 | +1.86% | +0.40% (-0.67%, +1.56%) | 0.0008 | 0.0096 | -0.17%/+0.36% | **FAILED GATE (criterion 5)** |
| z0=2.0 h=7d side=low | 41/10 | - | - | - | - | - | INSUFFICIENT |
| z0=2.5 h=1d side=low | 72/21 | -0.40% | -0.16% (-1.72%, +1.53%) | 0.6099 | 1.0000 | -0.26%/-0.07% | **FAILED GATE (criterion 3)** |
| z0=2.5 h=3d side=low | 45/12 | - | - | - | - | - | INSUFFICIENT |
| z0=2.5 h=7d side=low | 33/8 | - | - | - | - | - | INSUFFICIENT |

## Robustness detail (tested variants)

* **z0=2.0 h=1d side=low**: per coin BTC: +0.72% (n=79), ETH: -0.29% (n=73), SOL: -0.60% (n=74). Perturbed z0: x0.8: dev +0.17% (n=163), val +0.10% (n=49); x1.2: dev -0.59% (n=86), val -0.12% (n=26). Look-ahead audit: pass. Events skipped (missing candles): dev 0, val 0.
* **z0=2.0 h=3d side=low**: per coin BTC: +1.45% (n=52), ETH: +0.50% (n=44), SOL: +0.63% (n=45). Perturbed z0: x0.8: dev +1.04% (n=88), val +0.90% (n=22); x1.2: dev +0.95% (n=53), val +1.53% (n=14). Look-ahead audit: pass. Events skipped (missing candles): dev 0, val 0.
* **z0=2.5 h=1d side=low**: per coin BTC: +0.76% (n=39), ETH: -1.21% (n=36), SOL: -1.49% (n=48). Perturbed z0: x0.8: dev +0.18% (n=113), val -0.24% (n=37); x1.2: dev -0.53% (n=51), val -0.67% (n=12). Look-ahead audit: pass. Events skipped (missing candles): dev 0, val 0.
