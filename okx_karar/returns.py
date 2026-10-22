"""R01 return stage (plan: experiments/registry/R01_returns_plan.md).

Unlike events.py this module reads OKX prices. It evaluates only the variants that reached the count thresholds.
Statistic: mean over independent clusters of the equal-weight net return of the coins in the cluster.
P-value: circular time-shift permutation, so that market drift cannot pass the test by itself.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from okx_karar.audit import truncation_audit
from okx_karar.events import EIGHT_HOURS, HORIZONS, WINDOW, variant_events, zscores

COST = 0.0030          # flat 0.30% round trip, as registered
B = 5000               # permutations / bootstrap resamples
SEED = 20261022
ALPHA = 0.05


def holm_adjust(p: list[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values (monotone), in the input order."""
    m = len(p)
    order = np.argsort(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adjusted[i] = running
    return adjusted.tolist()


def return_grid(opens: pd.Series, start: pd.Timestamp, end: pd.Timestamp, h: pd.Timedelta, cost: float = COST):
    """Net return of entering at the open at every 8-hour grid time k (t = start + k*8h) and exiting h later.
    Returns (array of length lsteps + 1, lsteps) with lsteps = (end - h - start) / 8h; NaN where a candle is missing."""
    lsteps = int((end - h - start) / EIGHT_HOURS)
    grid = pd.date_range(start, periods=lsteps + 1, freq=EIGHT_HOURS)
    o0 = opens.reindex(grid).to_numpy(dtype=float)
    o1 = opens.reindex(grid + h).to_numpy(dtype=float)
    return o1 / o0 - 1 - cost, lsteps


def cluster_members(clusters: list, start: pd.Timestamp) -> list:
    """Clusters as lists of (coin, grid index)."""
    return [[(coin, int(round((t - start) / EIGHT_HOURS))) for t, coin in members] for _, members in clusters]


def cluster_values(members: list, grids: dict, lsteps: int, shift: int = 0) -> np.ndarray:
    """Equal-weight mean net return per cluster at a given circular shift (shift 0 = the observed events)."""
    vals = []
    for cluster in members:
        rs = []
        for coin, idx in cluster:
            j = idx if shift == 0 else (idx + shift) % lsteps
            r = grids[coin][j]
            if not np.isnan(r):
                rs.append(r)
        if rs:
            vals.append(sum(rs) / len(rs))
    return np.array(vals)


def permutation_p(members: list, grids: dict, lsteps: int, rng: np.random.Generator, b: int = B) -> tuple:
    """(observed mean, one-sided p, mean of the null distribution)."""
    obs_vals = cluster_values(members, grids, lsteps)
    if len(obs_vals) == 0 or lsteps < 2:
        return float("nan"), 1.0, float("nan")
    obs = float(obs_vals.mean())
    null = np.empty(b)
    for i, shift in enumerate(rng.integers(1, lsteps, size=b)):
        v = cluster_values(members, grids, lsteps, int(shift))
        null[i] = v.mean() if len(v) else np.nan
    return obs, float((1 + np.sum(null >= obs)) / (1 + b)), float(np.nanmean(null))


def bootstrap_interval(values: np.ndarray, rng: np.random.Generator, b: int = B, level: float = 0.90) -> tuple:
    if len(values) == 0:
        return float("nan"), float("nan")
    means = rng.choice(values, size=(b, len(values)), replace=True).mean(axis=1)
    lo, hi = np.quantile(means, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def _period_stats(funding, opens, period, z0, side, h):
    start, end = period
    kept, clusters = variant_events(funding, period, z0, side, h)
    grids, lsteps = {}, None
    for coin in funding:
        grids[coin], lsteps = return_grid(opens[coin], start, end, h)
    members = cluster_members(clusters, start)
    per_coin = {coin: [grids[coin][int(round((t - start) / EIGHT_HOURS))] for t in ts] for coin, ts in kept.items()}
    per_coin = {c: [x for x in v if not np.isnan(x)] for c, v in per_coin.items()}
    skipped = sum(1 for ts in kept.values() for _ in ts) - sum(len(v) for v in per_coin.values())
    drift = float(np.nanmean(np.concatenate([g for g in grids.values()])))
    return {"members": members, "grids": grids, "lsteps": lsteps, "per_coin": per_coin, "skipped": skipped,
            "drift": drift, "n_clusters": len(clusters)}


def audit_zscore(funding: pd.Series) -> bool:
    """Gate criterion 7: the z-score at every checked settlement must not change when later data is removed."""
    df = pd.DataFrame({"f": funding})
    report = truncation_audit(df, lambda d: pd.DataFrame({"z": zscores(d["f"])}), step=25, tail=1000)
    return not report["has_bias"]


def run_r01(funding: dict, opens: dict, periods: dict, count_rows: list, seed: int = SEED, b: int = B) -> list:
    """Evaluate every registered variant in the order of count_rows. Untested variants get p = 1.0 (K stays 12)."""
    rng = np.random.default_rng(seed)
    results, raw_p = [], []
    audit_ok = {coin: audit_zscore(series) for coin, series in funding.items()}
    for row in count_rows:
        res = {"variant": row["variant"], "z0": row["z0"], "horizon": row["horizon"], "side": row["side"],
               "n_dev": row["n_dev"], "n_validation": row["n_validation"], "count_verdict": row["verdict"]}
        if row["verdict"] != "COUNT_OK":
            res.update(tier="INSUFFICIENT", p_dev=1.0)
            results.append(res)
            raw_p.append(1.0)
            continue
        h, side, z0 = HORIZONS[row["horizon"]], row["side"], row["z0"]
        stats = {name: _period_stats(funding, opens, per, z0, side, h) for name, per in periods.items()}
        dev, val = stats["dev"], stats["validation"]
        obs_dev, p_dev, null_dev = permutation_p(dev["members"], dev["grids"], dev["lsteps"], rng, b)
        vals_val = cluster_values(val["members"], val["grids"], val["lsteps"])
        obs_val = float(vals_val.mean()) if len(vals_val) else float("nan")
        ci_val = bootstrap_interval(vals_val, rng, b)
        _, p_val, _ = permutation_p(val["members"], val["grids"], val["lsteps"], rng, b)
        res.update(mean_dev=obs_dev, mean_val=obs_val, p_dev=p_dev, p_val_info=p_val, null_mean_dev=null_dev,
                   ci90_val=ci_val, clusters_used_dev=int(len(cluster_values(dev["members"], dev["grids"], dev["lsteps"]))),
                   clusters_used_val=int(len(vals_val)), events_skipped_dev=dev["skipped"], events_skipped_val=val["skipped"],
                   drift_dev=dev["drift"], drift_val=val["drift"])
        pooled = {c: dev["per_coin"][c] + val["per_coin"][c] for c in funding}
        res["per_coin_mean"] = {c: (float(np.mean(v)) if len(v) else None) for c, v in pooled.items()}
        res["per_coin_n"] = {c: len(v) for c, v in pooled.items()}
        robust = {}
        for tag, factor in (("x0.8", 0.8), ("x1.2", 1.2)):
            means = {}
            for name, per in periods.items():
                st = _period_stats(funding, opens, per, round(z0 * factor, 4), side, h)
                v = cluster_values(st["members"], st["grids"], st["lsteps"])
                means[name] = (float(v.mean()) if len(v) else None, int(len(v)))
            robust[tag] = means
        res["robustness"] = robust
        res["audit_ok"] = all(audit_ok.values())
        results.append(res)
        raw_p.append(p_dev)
    adj = holm_adjust(raw_p)
    for res, a in zip(results, adj):
        res["p_dev_holm"] = a
        if "tier" in res:          # untested variants (INSUFFICIENT) already carry their tier
            continue
        failed = None
        if not res["mean_dev"] > 0:
            failed = 3
        elif not a < ALPHA:
            failed = 4
        elif not (res["mean_val"] > 0 and res["mean_val"] >= 0.5 * res["mean_dev"]):
            failed = 5
        elif not (all(res["per_coin_n"][c] >= 5 and res["per_coin_mean"][c] is not None and res["per_coin_mean"][c] > 0
                      for c in res["per_coin_n"])
                  and all(m[0] is not None and m[0] > 0 for r in res["robustness"].values() for m in r.values())):
            failed = 6
        elif not res["audit_ok"]:
            failed = 7
        res["failed_criterion"] = failed
        res["tier"] = "MONITORING" if failed is None else f"FAILED GATE (criterion {failed})"
    return results


def render_markdown(results: list, generated_at: str) -> str:
    pct = lambda x: "n/a" if x is None or x != x else f"{100 * x:+.2f}%"
    out = ["# R01 return-stage results", "",
           f"Generated {generated_at}. Plan: `R01_returns_plan.md`. Run once. Net returns are after a flat 0.30% round trip; "
           f"permutation p-values use {B} circular time shifts (seed {SEED}); Holm-Bonferroni over K = 12.", "",
           "| Variant | clusters dev/val | mean dev | mean val (90% CI) | p dev | Holm p | drift dev/val | Tier |",
           "|---|---|---|---|---|---|---|---|"]
    for r in results:
        if "mean_dev" not in r:
            out.append(f"| {r['variant']} | {r['n_dev']}/{r['n_validation']} | - | - | - | - | - | {r['tier']} |")
            continue
        ci = r["ci90_val"]
        out.append(f"| {r['variant']} | {r['clusters_used_dev']}/{r['clusters_used_val']} | {pct(r['mean_dev'])} | "
                   f"{pct(r['mean_val'])} ({pct(ci[0])}, {pct(ci[1])}) | {r['p_dev']:.4f} | {r['p_dev_holm']:.4f} | "
                   f"{pct(r['drift_dev'])}/{pct(r['drift_val'])} | **{r['tier']}** |")
    out += ["", "## Robustness detail (tested variants)", ""]
    for r in results:
        if "mean_dev" not in r:
            continue
        pc = ", ".join(f"{c}: {pct(r['per_coin_mean'][c])} (n={r['per_coin_n'][c]})" for c in r["per_coin_mean"])
        rb = "; ".join(f"{k}: dev {pct(v['dev'][0])} (n={v['dev'][1]}), val {pct(v['validation'][0])} (n={v['validation'][1]})"
                       for k, v in r["robustness"].items())
        out.append(f"* **{r['variant']}**: per coin {pc}. Perturbed z0: {rb}. Look-ahead audit: "
                   f"{'pass' if r['audit_ok'] else 'FAIL'}. Events skipped (missing candles): dev {r['events_skipped_dev']}, "
                   f"val {r['events_skipped_val']}.")
    out.append("")
    return "\n".join(out)
