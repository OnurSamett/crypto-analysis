import numpy as np
import pandas as pd
import pytest

from okx_karar.backtest import run_backtest
from okx_karar.config import Config, FuturesCfg, RiskCfg
from okx_karar.futures import FuturesDisabledError
from okx_karar.signals import compute_signals
from tests.conftest import make_ohlc, scores_with

INST = "AAA-USDT"


def _flat(n=220, price=100.0):
    return make_ohlc(np.full(n, price))


def test_decision_at_close_fills_at_next_open(cfg_one):
    # Fiyat 171. mumda 100 → 100.5 seviyesine geçiyor; açılış = kapanış olduğundan
    # dolum fiyatı karar anındaki kapanıştan (100) değil, sonraki açılıştan (100.5) gelmeli.
    closes = np.r_[np.full(171, 100.0), np.full(49, 100.5)]
    df = make_ohlc(closes, opens=closes)
    scores = {INST: scores_with(df.index, {slice(170, 190): 1.0, 190: -1.0})}
    r = run_backtest({INST: df}, cfg_one, scores=scores)
    buy, sell = r.trades[0], r.trades[1]
    assert buy.ts == df.index[171] and buy.side == "buy"
    assert buy.price == pytest.approx(100.5 * 1.0005)
    assert buy.fee == pytest.approx(buy.qty * buy.price * 0.001)
    assert sell.ts == df.index[191] and sell.side == "sell" and sell.reason == "sinyal"
    assert sell.qty == pytest.approx(buy.qty)
    # Tavan karar anındaki fiyatla uygulanır: miktar × karar kapanışı ≤ sermayenin %30'u.
    # (Açılış farklıysa dolan değer biraz sapabilir; canlıda da miktar emirden önce belirlenir.)
    assert buy.qty * 100.0 == pytest.approx(0.30 * cfg_one.initial_equity)
    assert r.decisions[0].ts == df.index[170]


def test_stop_and_no_reentry_until_rearmed(cfg_one):
    lows = np.full(220, 99.9)
    lows[180] = 90.0
    df = make_ohlc(np.full(220, 100.0), lows=lows)
    # Skor 1'de kalıyor: stop sonrası aynı yöne yeniden giriş OLMAMALI; skor exit altına inince tekrar silahlanır.
    scores = {INST: scores_with(df.index, {slice(170, 200): 1.0, 200: -0.5, slice(201, 220): 1.0})}
    r = run_backtest({INST: df}, cfg_one, scores=scores)
    stop_trade = r.trades[1]
    assert stop_trade.reason == "stop" and stop_trade.ts == df.index[180]
    buys = [t for t in r.trades if t.side == "buy"]
    assert buys[0].ts == df.index[171]
    assert buys[1].ts == df.index[202]  # yeniden giriş ancak 200'deki −0.5'ten sonra
    atr_at_decision = compute_signals(df, cfg_one.signals)["atr"].iloc[170]
    expected_stop = buys[0].price - 2.0 * atr_at_decision
    assert stop_trade.price == pytest.approx(min(100.0, expected_stop) * (1 - 0.0005))


def test_gap_below_stop_fills_at_open(cfg_one):
    closes = np.full(220, 100.0)
    opens = np.r_[closes[0], closes[:-1]]
    opens[180] = 80.0
    lows = np.minimum(opens, closes) * 0.999
    df = make_ohlc(closes, opens=opens, lows=lows)
    scores = {INST: scores_with(df.index, {slice(170, 220): 1.0})}
    r = run_backtest({INST: df}, cfg_one, scores=scores)
    stop_trade = next(t for t in r.trades if t.reason == "stop")
    assert stop_trade.price == pytest.approx(80.0 * (1 - 0.0005))


def test_spot_never_shorts_and_cash_never_negative(cfg_one):
    df = _flat()
    scores = {INST: scores_with(df.index, {slice(160, 220): -1.0})}
    r = run_backtest({INST: df}, cfg_one, scores=scores)
    assert r.trades == []
    assert r.equity.iloc[-1] == pytest.approx(cfg_one.initial_equity)


def test_kill_switch_closes_and_stops_trading():
    # Stop uzak (400 × ATR) ki önce kill switch tetiklensin; risk sınırı tavanı bağlamasın.
    cfg = Config(instruments=(INST,), risk=RiskCfg(max_drawdown=0.05, stop_atr_multiple=400,
                                                   risk_per_trade=0.5, max_atr_pct=1.0))
    closes = np.full(240, 100.0)
    closes[180:] = 50.0
    df = make_ohlc(closes)
    scores = {INST: scores_with(df.index, {slice(170, 240): 1.0})}
    r = run_backtest({INST: df}, cfg, scores=scores)
    assert r.killed_at == df.index[180]
    assert [t.reason for t in r.trades] == ["sinyal", "kill_switch"]
    assert r.final_positions == {}


def test_benchmark_is_equal_weight_buy_and_hold():
    cfg = Config(instruments=("AAA-USDT", "BBB-USDT"))
    a = make_ohlc(np.linspace(100, 200, 220))
    b = make_ohlc(np.full(220, 50.0))
    scores = {k: scores_with(a.index, {}) for k in cfg.instruments}
    r = run_backtest({"AAA-USDT": a, "BBB-USDT": b}, cfg, scores=scores)
    start = a.index.get_loc(r.equity.index[0])
    cost = (1 + 0.0005) * (1 + 0.001)
    qa = 5000 / (a["open"].iloc[start + 1] * cost)
    qb = 5000 / (b["open"].iloc[start + 1] * cost)
    assert r.benchmark.iloc[0] == 10_000
    assert r.benchmark.iloc[-1] == pytest.approx(qa * 200 + qb * 50)


def test_swap_mode_requires_futures_enabled():
    cfg = Config(mode="swap", instruments=(INST,))
    with pytest.raises(FuturesDisabledError):
        run_backtest({INST: _flat()}, cfg)


def test_swap_short_profits_and_receives_positive_funding():
    cfg = Config(mode="swap", instruments=(INST,), futures=FuturesCfg(enabled=True, leverage=2),
                 risk=RiskCfg(stop_atr_multiple=400, risk_per_trade=0.5, max_atr_pct=1.0))
    closes = np.r_[np.full(171, 100.0), np.linspace(100, 90, 49)]
    df = make_ohlc(closes)
    scores = {INST: scores_with(df.index, {slice(170, 220): -1.0})}
    funding = {INST: pd.Series([0.001], index=[df.index[200] + pd.Timedelta(minutes=30)])}
    r = run_backtest({INST: df}, cfg, scores=scores, funding=funding)
    assert r.trades[0].side == "sell" and r.trades[0].ts == df.index[171]
    # Kaldıraçla tavan: 10000 × 0.30 × 2 = 6000 USDT
    assert r.trades[0].qty * r.trades[0].price == pytest.approx(6000, rel=0.01)
    assert r.funding_paid < 0                      # short, pozitif funding'de para ALIR
    assert r.equity.iloc[-1] > cfg.initial_equity  # fiyat düştü → short kârda
