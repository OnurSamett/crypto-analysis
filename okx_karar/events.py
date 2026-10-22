"""Independent-event counting for registry candidate R01 (see experiments/registry/R01_count_plan.md).

STRUCTURAL SAFEGUARD: this module only accepts timestamps and funding-rate series. It does not import any price,
candle or backtest code, so counting cannot leak return information (a unit test checks the imports).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 270                      # previous settlements used for the z-score (about 90 days at 8h spacing)
Z0S = (2.0, 2.5)
HORIZONS = {"1d": pd.Timedelta(days=1), "3d": pd.Timedelta(days=3), "7d": pd.Timedelta(days=7)}
SIDES = ("high", "low")
DEV_MIN, VAL_MIN = 30, 15
EIGHT_HOURS = pd.Timedelta(hours=8)


def regular_steps(index: pd.DatetimeIndex, tolerance: pd.Timedelta = pd.Timedelta(minutes=1)) -> pd.Series:
    """True where a settlement is exactly 8 hours (± tolerance) after the previous one."""
    diffs = pd.Series(index, index=index).diff()
    return ((diffs - EIGHT_HOURS).abs() <= tolerance).fillna(False)


def zscores(funding: pd.Series, window: int = WINDOW) -> pd.Series:
    """z_s = (f_s - mean) / std over the previous `window` settlements, EXCLUDING s (sample std, ddof = 1).

    NaN until `window` previous settlements exist, when std is zero, or when any of the `window` steps leading
    to s is not a regular 8-hour step (irregular spans are excluded, never repaired).
    """
    mean = funding.rolling(window).mean().shift(1)
    std = funding.rolling(window).std().shift(1)
    z = (funding - mean) / std
    z[std == 0] = np.nan
    steps = regular_steps(funding.index).astype(float)
    window_ok = steps.rolling(window).min() == 1.0          # the `window` steps ending at s are all regular
    return z.where(window_ok)


def candidate_times(z: pd.Series, z0: float, side: str) -> list[pd.Timestamp]:
    mask = (z >= z0) if side == "high" else (z <= -z0)
    return list(z.index[mask.fillna(False)])


def eligible(times: list, start: pd.Timestamp, end: pd.Timestamp, horizon: pd.Timedelta) -> list:
    """Keep events with start <= s and s + horizon <= end (the horizon must finish inside the period)."""
    return [t for t in times if start <= t and t + horizon <= end]


def merge_same_coin(times: list, horizon: pd.Timedelta) -> list:
    """Chronologically keep the first event, drop later ones with s < kept + horizon, then continue."""
    kept: list = []
    for t in sorted(times):
        if not kept or t >= kept[-1] + horizon:
            kept.append(t)
    return kept


def cluster_across_coins(per_coin: dict, horizon: pd.Timedelta) -> list:
    """Pool the kept events of all coins. A cluster starts at the first pooled event t0 and contains every event
    with s < t0 + horizon; the next cluster starts at the first event >= t0 + horizon.
    Returns a list of (t0, sorted list of (time, coin))."""
    pooled = sorted((t, c) for c, ts in per_coin.items() for t in ts)
    clusters: list = []
    for t, c in pooled:
        if clusters and t < clusters[-1][0] + horizon:
            clusters[-1][1].append((t, c))
        else:
            clusters.append((t, [(t, c)]))
    return clusters


def count_variants(funding: dict, periods: dict, z0s=Z0S, horizons=None, sides=SIDES, window: int = WINDOW) -> list:
    """One row per variant: independent-event count and per-coin kept-event counts for each period."""
    horizons = horizons or HORIZONS
    z = {coin: zscores(series, window) for coin, series in funding.items()}
    rows = []
    for side in sides:
        for z0 in z0s:
            for hname, h in horizons.items():
                row = {"variant": f"z0={z0} h={hname} side={side}", "z0": z0, "horizon": hname, "side": side}
                for pname, (start, end) in periods.items():
                    kept = {coin: merge_same_coin(eligible(candidate_times(zs, z0, side), start, end, h), h)
                            for coin, zs in z.items()}
                    row[f"n_{pname}"] = len(cluster_across_coins(kept, h))
                    row[f"coins_{pname}"] = {coin: len(v) for coin, v in kept.items()}
                row["verdict"] = verdict(row.get("n_dev", 0), row.get("n_validation", 0))
                rows.append(row)
    return rows


def variant_events(funding: dict, period: tuple, z0: float, side: str, horizon: pd.Timedelta, window: int = WINDOW):
    """Kept events per coin and the cross-coin clusters of ONE variant in ONE period (timestamps only)."""
    start, end = period
    kept = {coin: merge_same_coin(eligible(candidate_times(zscores(series, window), z0, side), start, end, horizon), horizon)
            for coin, series in funding.items()}
    return kept, cluster_across_coins(kept, horizon)


def verdict(n_dev: int, n_val: int) -> str:
    return "COUNT_OK" if (n_dev >= DEV_MIN and n_val >= VAL_MIN) else "INSUFFICIENT"


def render_markdown(rows: list, coverage: dict, generated_at: str) -> str:
    out = ["# R01 independent-event counts", "",
           f"Generated {generated_at}. Counts only; **no returns were computed.** Plan: `R01_count_plan.md`. "
           f"Thresholds: dev >= {DEV_MIN}, validation >= {VAL_MIN} independent events.", "",
           "## Data coverage (Binance USDT-M funding)", "",
           "| Coin | First | Last | Rows | Irregular 8h steps |", "|---|---|---|---|---|"]
    for coin, a in coverage.items():
        out.append(f"| {coin} | {a['first']:%Y-%m-%d} | {a['last']:%Y-%m-%d} | {a['rows']} | {len(a['irregular'])} |")
    out += ["", "## Variants (K = 12)", "",
            "| Variant | n_dev | n_validation | per-coin kept (dev) | per-coin kept (validation) | Verdict |",
            "|---|---|---|---|---|---|"]
    for r in rows:
        dev = ", ".join(f"{c}:{n}" for c, n in r["coins_dev"].items())
        val = ", ".join(f"{c}:{n}" for c, n in r["coins_validation"].items())
        out.append(f"| {r['variant']} | {r['n_dev']} | {r['n_validation']} | {dev} | {val} | **{r['verdict']}** |")
    ok = sum(r["verdict"] == "COUNT_OK" for r in rows)
    out += ["", f"{ok} of {len(rows)} variants reached the thresholds. K stays 12 in the Holm-Bonferroni correction.", ""]
    return "\n".join(out)
