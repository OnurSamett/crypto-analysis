from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from okx_karar.backtest import run_backtest
from okx_karar.config import Config, DecisionCfg, RegimeCfg, RiskCfg, Weights, load_config
from okx_karar.decision import entry_gate
from okx_karar.risk import vol_target_size
from okx_karar.signals import donchian_state
from tests.conftest import make_ohlc, scores_with

ROOT = Path(__file__).resolve().parent.parent
INST = "AAA-USDT"


def test_donchian_state_breakouts_and_no_lookahead():
    closes = np.r_[np.full(10, 100.0), 110.0, 110.0, 110.0, 90.0, 90.0]
    df = make_ohlc(closes, opens=closes, highs=closes, lows=closes)
    st = donchian_state(df, (5,))
    assert st.iloc[9] == 0.0           # henüz kırılım yok
    assert st.iloc[10] == 1.0          # 110 > önceki 5 barın en yükseği (100)
    assert st.iloc[12] == 1.0          # durum korunur
    assert st.iloc[13] == -1.0         # 90 < önceki 5 barın en düşüğü (100)
    # Geleceği değiştirmek geçmişi değiştirmez
    df2 = df.copy()
    df2.iloc[11:, df2.columns.get_loc("close")] = 1.0
    assert (donchian_state(df2, (5,)).iloc[:11] == st.iloc[:11]).all()


def test_donchian_ensemble_is_mean_of_lookbacks():
    closes = np.r_[np.full(30, 100.0), 105.0, 105.0]
    df = make_ohlc(closes, opens=closes, highs=closes, lows=closes)
    assert donchian_state(df, (5, 10, 20)).iloc[-1] == 1.0
    # k=5 son barda 118 > önceki 5 barın en yükseği (115) → +1; k=20 pencerede 120'yi geçemedi → 0; ortalama 0.5
    mixed = np.r_[np.full(10, 100.0), 120.0, np.full(15, 115.0), 118.0]
    d = make_ohlc(mixed, opens=mixed, highs=mixed, lows=mixed)
    assert donchian_state(d, (5, 20)).iloc[-1] == pytest.approx(0.5)


def test_entry_gate_requires_consecutive_bars_and_volume():
    idx = pd.date_range("2025-01-01", periods=6, freq="D", tz="UTC")
    score = pd.Series([0.0, 0.5, 0.5, 0.2, 0.5, 0.5], index=idx)
    vol = pd.Series([1.0, 0.5, 1.5, 1.0, 0.4, 0.6], index=idx)
    g = entry_gate(score, vol, 0.3, confirm_bars=2, confirm_volume=1.0)
    assert list(g) == [False, False, True, False, False, False]   # 5. barda hacim yetersiz
    assert list(entry_gate(score, vol, 0.3, 2, 0.0)) == [False, False, True, False, False, True]
    assert list(entry_gate(score, vol, 0.3, 1, 0.0)) == [False, True, True, False, True, True]


def test_vol_target_size_caps_and_scales():
    cfg = RiskCfg(target_vol=0.20, max_position_fraction=0.30)
    assert vol_target_size(10_000, 100, 0.80, cfg) == pytest.approx(10_000 * 0.25 / 100)   # 0.20/0.80
    assert vol_target_size(10_000, 100, 0.20, cfg) == pytest.approx(10_000 * 0.30 / 100)   # tavan
    assert vol_target_size(10_000, 100, float("nan"), cfg) == 0.0
    assert vol_target_size(10_000, 100, 0.0, cfg) == 0.0


def test_experiment_configs_load():
    e1, e2, e3, e4 = (load_config(ROOT / "experiments" / f"{n}.toml")
                      for n in ("e1_donchian", "e2_voltarget", "e3_regime", "e4_confirm"))
    for name in ("e0_daily_baseline", "e1_donchian", "e2_voltarget", "e3_regime", "e4_confirm"):
        cfg = load_config(ROOT / "experiments" / f"{name}.toml")
        assert cfg.bar == "1Dutc" and cfg.risk.max_drawdown == 0.99
    assert e1.signals.donchian_lookbacks == (20, 50, 100) and e1.weights.donchian == 1.0 and not e1.risk.use_stop
    assert e2.risk.sizing == "vol_target" and e3.regime.enabled and e4.decision.confirm_bars == 2


def test_regime_blocks_new_entries_only_when_reference_below_sma():
    n = 260
    closes = np.r_[np.linspace(200, 100, 200), np.full(60, 100.0)]    # düşüş: fiyat 200 SMA'nın altında
    df = make_ohlc(closes, opens=closes)
    on = Config(instruments=(INST,), regime=RegimeCfg(enabled=True, reference=INST, sma_bars=50))
    off = Config(instruments=(INST,))
    scores = {INST: scores_with(df.index, {slice(210, 260): 1.0}, start_valid=160)}
    assert [t for t in run_backtest({INST: df}, on, scores=scores).trades] == []
    assert len(run_backtest({INST: df}, off, scores=scores).trades) >= 1


def test_no_stop_mode_never_stops_out():
    lows = np.full(240, 99.9)
    lows[180] = 10.0
    df = make_ohlc(np.full(240, 100.0), lows=lows)
    scores = {INST: scores_with(df.index, {slice(170, 240): 1.0})}
    with_stop = run_backtest({INST: df}, Config(instruments=(INST,)), scores=scores)
    without = run_backtest({INST: df}, Config(instruments=(INST,), risk=RiskCfg(use_stop=False)), scores=scores)
    assert any(t.reason == "stop" for t in with_stop.trades)
    assert all(t.reason != "stop" for t in without.trades)


def test_eval_start_trades_only_from_that_date():
    from tests.conftest import random_walk
    df = random_walk(900, seed=5)
    cfg = Config(instruments=(INST,))
    start = df.index[600]
    r = run_backtest({INST: df}, cfg, eval_start=start)
    assert r.equity.index[0] >= start
    assert all(t.ts >= start for t in r.trades)
