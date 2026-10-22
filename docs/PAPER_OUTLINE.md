# Possible paper: outline and honest assessment

## Working title
*A pre-registered, leakage-audited baseline for crypto trading research: simple rule-based systems, an evidence gate for new signals, and what survives out of sample.*

## What would be new (contributions)
1. **A reproducible evaluation protocol** for retail-grade crypto trading ideas: pre-registration in version control, price-free event counting before returns, drift-robust permutation tests with Holm correction, test-zone logging, and a look-ahead audit adapted from open-source backtesters.
2. **Transparent null and shrinking results**: the regime-filtered Donchian ensemble, the 4-hour frequency hypothesis, DCA tilts, and funding-crowding signals, including a development-period result that was significant after correction and shrank by about 80% out of sample.
3. **An open baseline for LLM trading agents**: the same `signal → decision` interface and backtest used for rule-based systems can score multi-agent LLM systems (e.g. TradingAgents-style), under the same leakage controls.
4. **A forward-test log** (E3/E4 paper trading, R08 replication) that is time-stamped before the data exists.

## What it is not
It is not a profitable-strategy paper. The honest headline is a methodology plus mostly negative or modest results. Papers framed otherwise would not survive review.

## Gaps to close before submitting anywhere serious
* **Forward results:** E3/E4 need ≥ 180 days and ≥ 15 trades (earliest ≈ April 2027); R08 needs ≈ 1 year. A paper with real out-of-sample outcomes is much stronger than one with only backtests.
* **More assets and venues:** 3 survivor coins are a weak sample. Add more coins (including delisted ones if data can be found) and at least one other exchange for prices.
* **Cost realism:** replace the flat slippage with a model fitted to order-book depth from the collector.
* **Statistical power analysis:** state, for each claim, how many independent events would be needed to detect the effect sizes seen.
* **Comparison with LLM agents:** if the multi-agent study in the CV is finished, the strongest paper is a *joint* one: this rule-based baseline + the agents, same protocol, same leakage controls, with the contamination issue handled by testing after the models' knowledge cutoffs.
* **External timestamps:** register the protocol on OSF (or similar) and archive a tagged release on Zenodo for a DOI, so that the pre-registration does not rest only on our own git history.
* **A faculty co-author or advisor** to help choose a venue and to review the claims.

## Venue types (check current calls; this is not a guarantee of anything)
* Preprint servers (SSRN, OSF Preprints, arXiv q-fin; arXiv may require endorsement for a first submission): feasible now.
* Workshop or short-paper tracks on AI/ML in finance and on negative results or reproducibility: the realistic first target.
* A software paper for the tool (Journal of Open Source Software): needs substantial scholarly effort and a public development history; unlikely to be accepted for a small codebase on its own.
* A finance or computational-finance journal: realistic only after the forward results, a larger asset set and an advisor-reviewed manuscript.

## Suggested timeline
1. Now: keep the repository, this findings log and the registry as the living record; tag `v0.1` and archive on Zenodo.
2. Next 2-3 months: finish the Mac mini bot and collector, run R07 if the channel export is available, extend the asset set, write the technical report.
3. About April 2027: first E3/E4 forward evaluation. About late 2027: R08 evaluation. Then write the full paper with real out-of-sample results.
