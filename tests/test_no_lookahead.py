import numpy as np
import pandas as pd

from okx_karar.backtest import run_backtest
from okx_karar.config import Config, SignalParams
from okx_karar.decision import score_frame, scores_from_callable
from okx_karar.signals import compute_signals, warmup_bars
from tests.conftest import random_walk


def _scramble_future(df, cut, seed=1):
    rng = np.random.default_rng(seed)
    out = df.copy()
    factor = rng.uniform(0.5, 1.5, len(df) - cut - 1)
    for col in ("open", "high", "low", "close", "volume"):
        out.iloc[cut + 1:, out.columns.get_loc(col)] *= factor
    return out


def test_signals_do_not_use_future_bars():
    df = random_walk(600)
    cut = 400
    p = SignalParams()
    a = score_frame(compute_signals(df, p), Config().weights)
    b = score_frame(compute_signals(_scramble_future(df, cut), p), Config().weights)
    assert np.allclose(a.iloc[: cut + 1], b.iloc[: cut + 1], equal_nan=True)
    assert not np.allclose(a.iloc[cut + 1:], b.iloc[cut + 1:], equal_nan=True)


def test_backtest_history_unchanged_by_future():
    cfg = Config(instruments=("AAA-USDT",))
    df = random_walk(900, seed=3)
    cut = 700
    r1 = run_backtest({"AAA-USDT": df}, cfg)
    r2 = run_backtest({"AAA-USDT": _scramble_future(df, cut)}, cfg)
    ts = df.index[cut]
    # Kesim anına kadar dolan işlemler aynı olmalı (cut anındaki karar cut+1'de dolar).
    t1 = [t for t in r1.trades if t.ts <= ts]
    t2 = [t for t in r2.trades if t.ts <= ts]
    assert [(t.ts, t.side, round(t.qty, 9), round(t.price, 9)) for t in t1] == \
           [(t.ts, t.side, round(t.qty, 9), round(t.price, 9)) for t in t2]
    assert np.allclose(r1.equity[:ts], r2.equity[:ts])


def test_scores_from_callable_only_sees_past():
    df = random_walk(300)
    seen = []

    def decide(window: pd.DataFrame) -> float:
        seen.append(window.index[-1])
        return 0.0

    warmup = warmup_bars(SignalParams())
    s = scores_from_callable(df, decide, warmup)
    assert seen == list(df.index[warmup:])
    assert s.iloc[:warmup].isna().all() and (s.iloc[warmup:] == 0).all()
