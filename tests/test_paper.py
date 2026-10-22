import numpy as np
import pandas as pd
import pytest

from okx_karar.config import Config, RiskCfg
from okx_karar.executors import SimExecutor
from okx_karar.paper import PaperState, cl_ord_id, run_once
from tests.conftest import make_ohlc

INST = "AAA-USDT"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    cfg = Config(instruments=(INST,))
    df = make_ohlc(np.full(300, 100.0))
    box = {"df": df, "score": 0.9}
    monkeypatch.setattr("okx_karar.paper.score_frame",
                        lambda sig, w: pd.Series(box["score"], index=sig.index))
    ex = SimExecutor(tmp_path / "acct.json", cfg.initial_equity, cfg.costs)
    return cfg, ex, box, tmp_path


def test_buy_then_idempotent_on_same_bar(setup):
    cfg, ex, box, tmp = setup
    state = PaperState()
    events = run_once(cfg, ex, lambda i: box["df"], state, tmp / "t.csv")
    assert any("buy" in e for e in events)
    qty = ex.positions()[INST]
    assert qty * 100 == pytest.approx(0.30 * 10_000, rel=0.01)
    assert INST in state.stops and state.stops[INST] < 100
    # Aynı mum ikinci kez işlenmez, ikinci emir gitmez.
    assert run_once(cfg, ex, lambda i: box["df"], state) == ["yeni kapanmış mum yok"]
    assert ex.positions()[INST] == qty
    assert len((tmp / "t.csv").read_text().strip().splitlines()) == 2  # başlık + 1 işlem


def test_stop_then_blocked(setup):
    cfg, ex, box, tmp = setup
    state = PaperState()
    run_once(cfg, ex, lambda i: box["df"], state)
    nxt = make_ohlc(np.full(301, 100.0))
    nxt.iloc[-1, nxt.columns.get_loc("low")] = 50.0
    events = run_once(cfg, ex, lambda i: nxt, state)
    assert any("(stop)" in e for e in events)
    assert ex.positions() == {}
    assert state.blocked[INST] == 1  # skor hâlâ 0.9 ama aynı yöne yeniden girilmez


def test_kill_switch_closes_everything(setup):
    cfg, ex, box, tmp = setup
    state = PaperState()
    run_once(cfg, ex, lambda i: box["df"], state)
    state.peak_equity = 20_000  # sermaye zirvenin %50 altında görünsün
    nxt = make_ohlc(np.full(301, 100.0))
    events = run_once(cfg, ex, lambda i: nxt, state)
    assert any("KILL SWITCH" in e for e in events)
    assert state.killed and ex.positions() == {}


def test_exit_on_low_score(setup):
    cfg, ex, box, tmp = setup
    state = PaperState()
    run_once(cfg, ex, lambda i: box["df"], state)
    box["score"] = -0.5
    events = run_once(cfg, ex, lambda i: make_ohlc(np.full(301, 100.0)), state)
    assert any("sell" in e and "(sinyal)" in e for e in events)
    assert ex.positions() == {} and INST not in state.stops


def test_cl_ord_id_is_okx_compatible():
    cid = cl_ord_id("BTC-USDT", pd.Timestamp("2025-01-01", tz="UTC"), "o")
    assert cid.isalnum() and len(cid) <= 32
