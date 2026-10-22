import numpy as np
import pytest

from okx_karar.config import CostCfg
from okx_karar.grid import GridParams, simulate_grid
from tests.conftest import make_ohlc

NO_COST = CostCfg(fee_rate=0.0, slippage=0.0)


def test_flat_price_makes_no_trades():
    df = make_ohlc(np.full(50, 100.0), highs=np.full(50, 100.0), lows=np.full(50, 100.0), opens=np.full(50, 100.0))
    r = simulate_grid(df, 10_000, NO_COST)
    assert r.fills == 0 and r.equity.iloc[-1] == pytest.approx(10_000)


def test_oscillation_earns_roughly_spacing_per_round_trip():
    # 100 ↔ 103: hücre 1 (=%1) → her gidiş-dönüşte birden fazla hücre çalışır.
    closes = np.tile([100.0, 103.0, 100.0, 97.0], 30)
    df = make_ohlc(closes, opens=np.r_[100.0, closes[:-1]], highs=closes + 0.0, lows=closes + 0.0)
    free = simulate_grid(df, 10_000, NO_COST, GridParams(rerange=False))
    paid = simulate_grid(df, 10_000, CostCfg(fee_rate=0.001, slippage=0.0), GridParams(rerange=False))
    assert free.fills > 20 and free.equity.iloc[-1] > 10_000 * 1.01
    assert paid.equity.iloc[-1] < free.equity.iloc[-1] and paid.fees > 0


def test_one_way_crash_holds_inventory_without_rerange():
    closes = np.r_[np.full(5, 100.0), np.linspace(100, 70, 45)]
    df = make_ohlc(closes, opens=np.r_[100.0, closes[:-1]])
    r = simulate_grid(df, 10_000, NO_COST, GridParams(rerange=False))
    assert r.reranges == 0 and r.equity.iloc[-1] < 10_000 * 0.97


def test_rerange_liquidates_when_price_leaves_range():
    closes = np.r_[np.full(5, 100.0), np.linspace(100, 130, 40)]
    df = make_ohlc(closes, opens=np.r_[100.0, closes[:-1]])
    r = simulate_grid(df, 10_000, NO_COST, GridParams(rerange=True))
    assert r.reranges >= 1 and r.equity.iloc[-1] > 10_000
    assert np.isfinite(r.equity).all()
