import numpy as np
import pandas as pd

from okx_karar.indicators import atr, ema, macd, rsi
from tests.conftest import make_ohlc


def test_rsi_extremes():
    up = pd.Series(np.arange(1, 101, dtype=float))
    down = up[::-1].reset_index(drop=True)
    flat = pd.Series(np.full(100, 5.0))
    assert rsi(up).iloc[-1] == 100.0
    assert rsi(down).iloc[-1] == 0.0
    assert rsi(flat).iloc[-1] == 50.0
    assert rsi(up).iloc[:14].isna().all()  # min_periods dolmadan değer yok


def test_ema_matches_recursion():
    s = pd.Series([1.0, 2.0, 4.0, 3.0, 5.0])
    alpha = 2 / (3 + 1)
    expected = [1.0]
    for x in s.iloc[1:]:
        expected.append(alpha * x + (1 - alpha) * expected[-1])
    assert np.allclose(ema(s, 3), expected)


def test_atr_constant_range():
    df = make_ohlc(np.full(100, 100.0), lows=np.full(100, 99.0), highs=np.full(100, 101.0))
    assert np.isclose(atr(df, 14).iloc[-1], 2.0)


def test_macd_zero_on_flat():
    out = macd(pd.Series(np.full(100, 7.0)))
    assert np.allclose(out[["macd", "signal", "hist"]].to_numpy(), 0.0)
