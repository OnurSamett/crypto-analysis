import json

import pandas as pd
import pytest
import requests

from okx_karar.advisory import assess
from okx_karar.backtest import run_backtest
from okx_karar.config import Config, DecisionCfg, RegimeCfg, RiskCfg, SignalParams, Weights
from okx_karar.notifier import DISCLAIMER, NotifyError, TelegramSender, find_chat_ids, format_message
from tests.test_paper_parity import INSTS, _trending_frames


def _cfg(variant="e3"):
    return Config(
        instruments=INSTS, bar="1D", initial_equity=10_000.0, signals=SignalParams(),
        weights=Weights(trend=0, macd=0, rsi=0, volume=0, funding=0, donchian=1.0),
        decision=DecisionCfg(confirm_bars=2, confirm_volume=1.0) if variant == "e4" else DecisionCfg(),
        risk=RiskCfg(max_drawdown=0.99, max_atr_pct=0.5, use_stop=False, sizing="vol_target", target_vol=0.2),
        regime=RegimeCfg(enabled=True, reference=INSTS[0], sma_bars=100))


@pytest.mark.parametrize("variant", ["e3", "e4"])
def test_advisory_events_match_backtest_decisions(variant):
    frames = _trending_frames()
    cfg = _cfg(variant)
    step = pd.Timedelta(days=1)
    bt = run_backtest(frames, cfg)
    n = len(frames[INSTS[0]])
    t0 = frames[INSTS[0]].index.get_loc(bt.equity.index[0]) + 40
    view = {i: frames[i].iloc[: t0 + 1] for i in INSTS}
    first, state = assess(cfg, view, None, "x")
    assert first.snapshot and first.events == []
    got = []
    for t in range(t0 + 1, n - 1):
        view = {i: frames[i].iloc[: t + 1] for i in INSTS}
        a, state = assess(cfg, view, state, "x")
        got += [(e.ts, e.inst, e.kind) for e in a.events if e.kind in ("ENTRY", "EXIT")]
    expected = [(d.ts + step, d.inst, "ENTRY" if d.to_side == 1 else "EXIT") for d in bt.decisions
                if not d.note.startswith("veto") and d.to_side != d.from_side and d.ts > frames[INSTS[0]].index[t0]]
    assert len(expected) >= 3
    assert got == expected


def test_advisory_idempotent_and_levels():
    frames = _trending_frames()
    cfg = _cfg()
    view = {i: frames[i].iloc[:420] for i in INSTS}
    a1, st = assess(cfg, view, None, "x")
    a2, st2 = assess(cfg, view, st, "x")
    assert a2.events == [] and not a2.snapshot and st2["side"] == st["side"]
    for v in a1.views:
        assert all(v.upper[k] >= v.lower[k] for k in v.windows)
        assert v.upper[v.windows[0]] <= v.upper[v.windows[-1]] + 1e-9   # daha uzun pencere daha yüksek/eşit tepe


def test_message_has_disclaimer_and_levels():
    frames = _trending_frames()
    cfg = _cfg()
    view = {i: frames[i].iloc[:420] for i in INSTS}
    a, _ = assess(cfg, view, None, "e3_regime")
    text = format_message(a, "E3", weekly=False)
    assert DISCLAIMER in text and "Başlangıç özeti" in text and "AAA-USDT" in text and "Rejim" in text
    assert len(text) < 4000


class FakeResp:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload=None, exc=None):
        self.payload, self.exc, self.calls = payload or {"ok": True, "result": []}, exc, []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        if self.exc:
            raise self.exc
        return FakeResp(self.payload)

    get = post


def test_telegram_sender_splits_and_hides_token():
    sess = FakeSession()
    TelegramSender("TOKEN123", "42", sess).send("x\n" * 3000)
    assert len(sess.calls) >= 2 and all(c[1]["chat_id"] == "42" for c in sess.calls)
    assert all("/botTOKEN123/sendMessage" in c[0] for c in sess.calls)
    with pytest.raises(NotifyError) as e:
        TelegramSender("TOKEN123", "42", FakeSession(exc=requests.ConnectionError("https://api.telegram.org/botTOKEN123/x"))).send("a")
    assert "TOKEN123" not in str(e.value)
    with pytest.raises(NotifyError, match="Unauthorized"):
        TelegramSender("t", "1", FakeSession({"ok": False, "description": "Unauthorized"})).send("a")
    with pytest.raises(NotifyError):
        TelegramSender("", "1")


def test_find_chat_ids():
    sess = FakeSession({"ok": True, "result": [{"message": {"chat": {"id": 123, "first_name": "Onur"}}},
                                               {"message": {"chat": {"id": 123, "first_name": "Onur"}}}]})
    assert find_chat_ids("t", sess) == [("123", "Onur")]


def test_exit_and_entry_levels_logic():
    from okx_karar.advisory import CoinView
    from okx_karar.notifier import entry_level, exit_levels
    base = dict(inst="X", price=100.0, score=1.0, regime_ok=True, gate_ok=True, weight_pct=30.0, since=None, windows=(20, 50, 100),
                upper={20: 105.0, 50: 110.0, 100: 120.0})
    # üç pencere long → çıkış için ikisi dönmeli: en yüksek iki alt kanaldan ikincisi
    v = CoinView(side=1, n_long=3, wstates=(1, 1, 1), lower={20: 95.0, 50: 90.0, 100: 80.0}, **base)
    assert exit_levels(v) == (95.0, 90.0)
    # tek long kalmışsa çıkış çok yakın (aynı seviye)
    v = CoinView(side=1, n_long=2, wstates=(1, 1, -1), lower={20: 95.0, 50: 90.0, 100: 80.0}, **base)
    assert exit_levels(v) == (95.0, 95.0)
    # nakit, bir pencere long → bir pencere daha lazım: kısa pencerelerin en düşük üst kanalı
    v = CoinView(side=0, n_long=1, wstates=(-1, -1, 1), lower={20: 95.0, 50: 90.0, 100: 80.0}, **base)
    assert entry_level(v) == 105.0
    v = CoinView(side=0, n_long=0, wstates=(-1, -1, -1), lower={20: 95.0, 50: 90.0, 100: 80.0}, **base)
    assert entry_level(v) == 110.0   # iki pencerenin dönmesi: ikinci en düşük üst kanal
