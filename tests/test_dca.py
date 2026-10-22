import numpy as np
import pandas as pd
import pytest

from okx_karar.config import CostCfg
from okx_karar.dca import _irr, simulate_dca
from tests.conftest import make_ohlc

NO_COST = CostCfg(fee_rate=0.0, slippage=0.0)
START = pd.Timestamp("2025-01-01", tz="UTC")   # çarşamba


def _frames(closes):
    df = make_ohlc(closes, opens=closes, freq="1D", start="2024-01-01")
    return {"BTC-USDT": df, "ETH-USDT": df.copy()}


def test_flat_price_no_costs_returns_zero_and_counts_mondays():
    n = 500
    data = _frames(np.full(n, 100.0))
    end = pd.Timestamp("2025-04-01", tz="UTC")
    r = simulate_dca(data, "D0", NO_COST, START, end)
    mondays = sum(1 for t in pd.date_range(START, end, freq="D", inclusive="left") if t.weekday() == 0)
    assert r.buys == mondays and r.invested == pytest.approx(100.0 * mondays)
    assert r.return_on_invested == pytest.approx(0.0, abs=1e-9) and r.max_drawdown == pytest.approx(0.0, abs=1e-9)


def test_costs_reduce_return():
    data = _frames(np.full(500, 100.0))
    r = simulate_dca(data, "D0", CostCfg(fee_rate=0.001, slippage=0.0005), START, pd.Timestamp("2025-04-01", tz="UTC"))
    assert r.return_on_invested == pytest.approx(-(1 - 1 / (1.001 * 1.0005)), rel=1e-6)


def test_regime_variants_skip_or_double_below_sma_and_use_previous_close():
    closes = np.r_[np.linspace(100, 300, 400), np.linspace(300, 50, 100)]    # yükseliş sonra düşüş: rejim kapanır
    data = _frames(closes)
    end = pd.Timestamp("2025-05-10", tz="UTC")
    d0, d1, d2 = (simulate_dca(data, v, NO_COST, START, end) for v in ("D0", "D1", "D2"))
    assert d1.skipped > 0 and d1.invested < d0.invested
    assert d2.invested > d0.invested and d2.invested == pytest.approx(d0.invested + 100.0 * d1.skipped)
    assert d0.skipped == 0


def test_irr_single_year_doubling():
    t0 = pd.Timestamp("2025-01-01", tz="UTC")
    assert _irr([(t0, -100.0), (t0 + pd.Timedelta(days=365), 110.0)]) == pytest.approx(0.10, abs=1e-6)
