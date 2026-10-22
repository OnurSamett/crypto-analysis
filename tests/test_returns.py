import numpy as np
import pandas as pd
import pytest

from okx_karar import events as ev
from okx_karar.events import EIGHT_HOURS, count_variants
from okx_karar.returns import (cluster_members, cluster_values, holm_adjust, permutation_p, return_grid, run_r01)

START = pd.Timestamp("2022-01-01", tz="UTC")
H = pd.Timedelta(days=1)


def test_holm_adjust_known_example():
    assert holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm_adjust([1.0, 0.5]) == pytest.approx([1.0, 1.0])
    assert max(holm_adjust([0.0001] * 12)) == pytest.approx(0.0012)


def test_return_grid_net_of_cost_and_missing_candles():
    idx = pd.date_range(START, periods=50, freq="4h")
    opens = pd.Series(np.arange(100.0, 150.0), index=idx)
    opens = opens.drop(idx[12])                                # candle at +48h is missing
    grid, lsteps = return_grid(opens, START, START + pd.Timedelta(days=5), H, cost=0.003)
    assert lsteps == 12                                        # (5d - 1d) / 8h
    assert grid[0] == pytest.approx(opens.iloc[6] / opens.iloc[0] - 1 - 0.003)
    assert np.isnan(grid[1 + 5])                               # k=6 -> t=+48h -> entry candle missing


def _grids(spiky_offsets, n=200, jump=0.05):
    """4H price series at 100 with +5% only at the exit candle of the informative events."""
    idx = pd.date_range(START, periods=n * 2 + 12, freq="4h")
    opens = pd.Series(100.0, index=idx)
    for k in spiky_offsets:
        opens.loc[START + k * EIGHT_HOURS + H:] = opens.loc[START + k * EIGHT_HOURS + H:]    # no-op for clarity
        opens.loc[START + k * EIGHT_HOURS + H] = 100.0 * (1 + jump)
    end = START + EIGHT_HOURS * n + H
    grid, lsteps = return_grid(opens, START, end, H, cost=0.003)
    return {"BTC": grid}, lsteps


def test_permutation_detects_informative_timing():
    offsets = list(range(10, 190, 9))
    grids, lsteps = _grids(offsets)
    clusters = [(START + k * EIGHT_HOURS, [(START + k * EIGHT_HOURS, "BTC")]) for k in offsets]
    members = cluster_members(clusters, START)
    obs, p, null = permutation_p(members, grids, lsteps, np.random.default_rng(1), b=1000)
    assert obs == pytest.approx(0.05 - 0.003) and p < 0.01 and null < 0.01


def test_permutation_is_not_fooled_by_market_drift():
    n = 400
    idx = pd.date_range(START, periods=n * 2 + 12, freq="4h")
    opens = pd.Series(100.0 * np.exp(np.arange(len(idx)) * 0.002), index=idx)     # strong deterministic uptrend
    end = START + EIGHT_HOURS * n + H
    grid, lsteps = return_grid(opens, START, end, H, cost=0.003)
    offsets = list(range(5, 380, 15))                                              # timing unrelated to returns
    clusters = [(START + k * EIGHT_HOURS, [(START + k * EIGHT_HOURS, "BTC")]) for k in offsets]
    obs, p, null = permutation_p(cluster_members(clusters, START), {"BTC": grid}, lsteps, np.random.default_rng(2), b=1000)
    assert obs > 0.005 and abs(obs - null) < 1e-9 and p > 0.3          # positive mean, yet no evidence of timing skill


def test_cluster_returns_average_available_coins():
    grids = {"BTC": np.array([0.02, 0.04, np.nan]), "ETH": np.array([0.06, np.nan, np.nan])}
    members = [[("BTC", 0), ("ETH", 0)], [("BTC", 1), ("ETH", 1)], [("BTC", 2), ("ETH", 2)]]
    vals = cluster_values(members, grids, lsteps=3)
    assert vals.tolist() == pytest.approx([0.04, 0.04])               # the all-missing cluster is skipped


def _synthetic(informative: bool, n_settle=3700):
    idx = pd.date_range("2021-09-01", periods=n_settle, freq="8h", tz="UTC")
    rng = np.random.default_rng(0)
    spikes = list(range(450, n_settle - 40, 90))
    funding = {}
    for coin in ("BTC", "ETH", "SOL"):
        v = 0.0001 + rng.uniform(-1e-6, 1e-6, n_settle)
        for k in spikes:
            v[k] = -0.0011
        funding[coin] = pd.Series(v, index=idx)
    p_idx = pd.date_range("2021-02-01", "2025-02-01", freq="4h", tz="UTC")
    opens = {}
    for coin in funding:
        o = pd.Series(100.0, index=p_idx)
        if informative:
            for k in spikes:
                o.loc[idx[k] + H] = 105.0
        opens[coin] = o
    return funding, opens


@pytest.mark.parametrize("informative,expected", [(True, "MONITORING"), (False, "FAILED GATE (criterion 3)")])
def test_run_r01_end_to_end(monkeypatch, informative, expected):
    monkeypatch.setattr(ev, "DEV_MIN", 10)
    monkeypatch.setattr(ev, "VAL_MIN", 5)
    funding, opens = _synthetic(informative)
    periods = {"dev": (START, pd.Timestamp("2024-01-01", tz="UTC")),
               "validation": (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC"))}
    rows = count_variants(funding, periods, z0s=(2.0,), horizons={"1d": H})
    results = {r["side"]: r for r in run_r01(funding, opens, periods, rows, b=300)}
    low = results["low"]
    assert low["count_verdict"] == "COUNT_OK" and low["tier"] == expected
    assert results["high"]["tier"] == "INSUFFICIENT" and results["high"]["p_dev"] == 1.0
    if informative:
        assert low["mean_dev"] == pytest.approx(0.05 - 0.003) and low["p_dev_holm"] < 0.05 and low["audit_ok"]
