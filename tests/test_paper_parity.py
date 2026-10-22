"""Paper döngüsü ile backtest aynı kararları veriyor mu? (E3/E4 özellikleriyle)

Aynı sentetik veride backtest çalıştırılır; paper döngüsü aynı barlara tek tek beslenir. Yön değişimlerinin
(zaman, enstrüman, yeni yön) birebir aynı olması beklenir. Dolum fiyatları farklıdır (backtest: sonraki açılış,
paper: kapanış), bu yüzden miktar değil karar karşılaştırılır.
"""
import numpy as np
import pandas as pd
import pytest

from okx_karar.backtest import run_backtest
from okx_karar.config import Config, DecisionCfg, RegimeCfg, RiskCfg, SignalParams, Weights
from okx_karar.executors import SimExecutor
from okx_karar.paper import PaperState, run_once
from tests.conftest import make_ohlc

INSTS = ("AAA-USDT", "BBB-USDT")


def _trending_frames(n=700, seed=11):
    rng = np.random.default_rng(seed)
    frames = {}
    for k, inst in enumerate(INSTS):
        drift = np.r_[np.full(200, 0.004), np.full(150, -0.006), np.full(200, 0.005), np.full(150, -0.004)]
        closes = 100 * np.exp(np.cumsum(drift + rng.normal(0, 0.012, n)))
        df = make_ohlc(closes, freq="1D")
        df["volume"] = rng.uniform(0.5, 2.0, n)
        frames[inst] = df
    return frames


def _side_changes_paper(cfg, frames, start_pos, tmp_path):
    n = len(frames[INSTS[0]])
    ex = SimExecutor(tmp_path / "acct.json", cfg.initial_equity, cfg.costs)
    state = PaperState()
    prev = {i: 0 for i in INSTS}
    out = []
    for t in range(start_pos, n - 1):  # backtest son barın kararını dolduramaz
        view = {i: frames[i].iloc[: t + 1] for i in INSTS}
        run_once(cfg, ex, lambda inst, v=view: v[inst], state)
        pos = ex.positions()
        for i in INSTS:
            side = 1 if pos.get(i, 0.0) * view[i]["close"].iloc[-1] > 5 else 0
            if side != prev[i]:
                out.append((frames[i].index[t], i, side))
                prev[i] = side
    return out


@pytest.mark.parametrize("variant", ["e3", "e4"])
def test_paper_matches_backtest_decisions(variant, tmp_path):
    frames = _trending_frames()
    decision = DecisionCfg(confirm_bars=2, confirm_volume=1.0) if variant == "e4" else DecisionCfg()
    cfg = Config(
        instruments=INSTS, bar="1D", initial_equity=10_000.0,
        signals=SignalParams(),
        weights=Weights(trend=0, macd=0, rsi=0, volume=0, funding=0, donchian=1.0),
        decision=decision,
        risk=RiskCfg(max_drawdown=0.99, max_atr_pct=0.5, use_stop=False, sizing="vol_target", target_vol=0.2),
        regime=RegimeCfg(enabled=True, reference=INSTS[0], sma_bars=100),
    )
    bt = run_backtest(frames, cfg)
    start_pos = frames[INSTS[0]].index.get_loc(bt.equity.index[0])
    expected = [(d.ts, d.inst, d.to_side) for d in bt.decisions if not d.note.startswith("veto") and d.to_side != d.from_side]
    got = _side_changes_paper(cfg, frames, start_pos, tmp_path)
    assert len(expected) >= 4, "test verisi yeterince işlem üretmedi"
    assert got == expected
