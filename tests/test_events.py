import pathlib
import re

import numpy as np
import pandas as pd
import pytest

from okx_karar.binance_funding import fetch_funding, interval_audit
from okx_karar.events import (HORIZONS, cluster_across_coins, count_variants, eligible, merge_same_coin, regular_steps,
                              verdict, zscores)

T0 = pd.Timestamp("2022-01-01", tz="UTC")
H = pd.Timedelta(days=1)


def funding_series(n=700, spikes=None, seed=0, start=T0, step=pd.Timedelta(hours=8)):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq=step)
    # bounded noise: for a uniform distribution |z| <= sqrt(3) ~ 1.73 < 2.0, so only the injected spikes are events
    values = 0.0001 + rng.uniform(-1e-6, 1e-6, n)
    for pos, v in (spikes or {}).items():
        values[pos] = v
    return pd.Series(values, index=idx)


def test_zscore_excludes_current_value_and_matches_manual_computation():
    f = funding_series(spikes={400: 0.001})
    z = zscores(f)
    prev = f.iloc[400 - 270:400]
    assert z.iloc[400] == pytest.approx((f.iloc[400] - prev.mean()) / prev.std(ddof=1))
    assert z.iloc[400] > 100                      # the spike does not dampen its own z-score
    assert z.iloc[:270].isna().all() and not np.isnan(z.iloc[270])


def test_irregular_step_blanks_z_for_the_next_window_only():
    f = funding_series(n=900)
    f = f.drop(f.index[300])                       # one missing settlement -> one 16h step
    z = zscores(f)
    assert not regular_steps(f.index).iloc[300]
    assert z.iloc[300:300 + 269].isna().all()      # windows that contain the gap are invalid
    assert not np.isnan(z.iloc[300 + 270 + 1])


def test_eligibility_at_both_period_edges():
    start, end = T0, T0 + pd.Timedelta(days=10)
    times = [start - pd.Timedelta(hours=1), start, end - H, end - H + pd.Timedelta(hours=1), end]
    assert eligible(times, start, end, H) == [start, end - H]       # s + h <= end, and s >= start


def test_merge_within_coin_is_greedy_and_chronological():
    times = [T0, T0 + pd.Timedelta(hours=8), T0 + H, T0 + H + pd.Timedelta(hours=8), T0 + 2 * H]
    assert merge_same_coin(times, H) == [T0, T0 + H, T0 + 2 * H]    # an event exactly one horizon later is kept


def test_cluster_across_coins_anchored_at_first_event():
    per_coin = {"BTC": [T0], "ETH": [T0 + pd.Timedelta(hours=12)], "SOL": [T0 + H]}
    clusters = cluster_across_coins(per_coin, H)
    assert len(clusters) == 2                       # SOL at exactly t0 + h starts a new cluster
    assert [c for _, c in clusters[0][1]] == ["BTC", "ETH"] and clusters[1][1][0][1] == "SOL"


def test_count_variants_end_to_end_with_known_events():
    n = 1500
    spikes_btc = {400: 0.001, 700: 0.001, 702: 0.001}            # 702 is within 1d of 700 -> merged away
    f = {"BTC": funding_series(n, spikes_btc, seed=1), "ETH": funding_series(n, {400: 0.001, 1300: 0.001}, seed=2),
         "SOL": funding_series(n, {401: 0.001}, seed=3)}
    periods = {"dev": (T0, T0 + pd.Timedelta(days=400)), "validation": (T0 + pd.Timedelta(days=400), T0 + pd.Timedelta(days=500))}
    rows = {r["variant"]: r for r in count_variants(f, periods, z0s=(2.0,), horizons={"1d": H}, sides=("high",))}
    r = rows["z0=2.0 h=1d side=high"]
    # dev: BTC 400, ETH 400 and SOL 401 form ONE cluster; BTC 700 (and merged 702) is a second -> 2 independent events
    assert r["coins_dev"] == {"BTC": 2, "ETH": 1, "SOL": 1} and r["n_dev"] == 2
    assert r["n_validation"] == 1 and r["coins_validation"] == {"BTC": 0, "ETH": 1, "SOL": 0}
    assert r["verdict"] == "INSUFFICIENT"
    assert verdict(30, 15) == "COUNT_OK" and verdict(29, 15) == "INSUFFICIENT" and verdict(30, 14) == "INSUFFICIENT"


def test_low_side_uses_negative_z():
    f = {"BTC": funding_series(900, {400: -0.001}, seed=4)}
    periods = {"dev": (T0, T0 + pd.Timedelta(days=500)), "validation": (T0 + pd.Timedelta(days=500), T0 + pd.Timedelta(days=700))}
    rows = {r["side"]: r for r in count_variants(f, periods, z0s=(2.0,), horizons={"1d": H})}
    assert rows["low"]["n_dev"] == 1 and rows["high"]["n_dev"] == 0


def test_counting_module_is_price_free():
    src = pathlib.Path(__file__).resolve().parent.parent / "okx_karar" / "events.py"
    imports = [l for l in src.read_text().splitlines() if re.match(r"\s*(import|from)\s", l)]
    forbidden = ("data", "okx_client", "backtest", "signals", "executors", "paper", "metrics")
    assert not [l for l in imports if any(re.search(rf"\b{w}\b", l.split("import")[0] + " " + l) for w in forbidden
                                           if w not in ("data",)) or "okx_karar" in l]
    assert imports and all(("numpy" in l or "pandas" in l or "__future__" in l) for l in imports)


class FakeResp:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params))
        page = [r for r in self.rows if params["startTime"] <= int(r["fundingTime"]) < params["endTime"]]
        return FakeResp(page[: params["limit"]])


def test_fetch_funding_pages_and_dedupes(monkeypatch):
    monkeypatch.setattr("okx_karar.binance_funding.time.sleep", lambda s: None)
    base = int(T0.timestamp() * 1000)
    rows = [{"fundingTime": base + k * 8 * 3600 * 1000, "fundingRate": "0.0001"} for k in range(2500)]
    s = fetch_funding("BTCUSDT", T0, T0 + pd.Timedelta(days=2000), FakeSession(rows))
    assert len(s) == 2500 and s.index.is_monotonic_increasing and s.index.is_unique
    audit = interval_audit(s)
    assert audit["irregular"] == [] and audit["rows"] == 2500
