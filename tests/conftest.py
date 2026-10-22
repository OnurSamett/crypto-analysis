import numpy as np
import pandas as pd
import pytest

from okx_karar.config import Config, CostCfg, DecisionCfg, RiskCfg


def make_ohlc(closes, opens=None, lows=None, highs=None, start="2025-01-01", freq="1h", volume=1.0):
    closes = np.asarray(closes, dtype=float)
    index = pd.date_range(start, periods=len(closes), freq=freq, tz="UTC", name="ts")
    o = np.r_[closes[0], closes[:-1]] if opens is None else np.asarray(opens, dtype=float)
    hi = np.maximum(o, closes) * 1.001 if highs is None else np.asarray(highs, dtype=float)
    lo = np.minimum(o, closes) * 0.999 if lows is None else np.asarray(lows, dtype=float)
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": closes,
                         "volume": np.full(len(closes), volume)}, index=index)


def random_walk(n=600, seed=0, start_price=100.0):
    rng = np.random.default_rng(seed)
    closes = start_price * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    df = make_ohlc(closes)
    df["volume"] = rng.uniform(0.5, 2.0, n)
    return df


@pytest.fixture
def cfg_one():
    """Tek enstrümanlı, maliyetleri bilinen spot yapılandırma."""
    return Config(
        instruments=("AAA-USDT",),
        costs=CostCfg(fee_rate=0.001, slippage=0.0005),
        decision=DecisionCfg(enter_threshold=0.3, exit_threshold=-0.1),
        risk=RiskCfg(),
    )


def scores_with(index, values: dict, start_valid=160, default=0.0):
    """start_valid öncesi NaN, sonrası `default`, verilen pozisyonlarda verilen skor."""
    s = pd.Series(np.nan, index=index)
    s.iloc[start_valid:] = default
    for pos, v in values.items():
        if isinstance(pos, slice):
            s.iloc[pos] = v
        else:
            s.iloc[pos] = v
    return s
