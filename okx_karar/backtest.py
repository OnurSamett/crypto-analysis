"""Portföy düzeyinde olay tabanlı backtest.

Zamanlama kuralı (geleceğe bakmayı engeller):
  * Karar, t mumunun KAPANIŞINDA o ana kadarki veriyle verilir.
  * Emir t+1 mumunun AÇILIŞ fiyatından (kayma + komisyonla) dolar.
  * Stop, mum içinde düşük/yüksek fiyatla kontrol edilir; fiyat stop'un altında açılırsa
    (boşluk) açılış fiyatından dolar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from okx_karar.config import Config
from okx_karar.decision import entry_gate, next_target, score_frame
from okx_karar.risk import DrawdownGuard, entry_veto, position_size, stop_price, vol_target_size
from okx_karar.signals import compute_signals


@dataclass
class Trade:
    ts: pd.Timestamp
    inst: str
    side: str
    qty: float
    price: float
    fee: float
    reason: str


@dataclass
class DecisionRecord:
    ts: pd.Timestamp
    inst: str
    from_side: int
    to_side: int
    score: float
    close: float
    note: str = ""


@dataclass
class _Order:
    target_qty: float
    atr: float
    reason: str


@dataclass
class BacktestResult:
    equity: pd.Series
    benchmark: pd.Series
    exposure: pd.Series
    trades: list[Trade]
    decisions: list[DecisionRecord]
    closes: dict[str, pd.Series]
    bar: str
    config_hash: str
    vetoes: int = 0
    killed_at: pd.Timestamp | None = None
    funding_paid: float = 0.0
    fees_paid: float = 0.0
    final_positions: dict[str, float] = field(default_factory=dict)


def _sign(x: float) -> int:
    return 0 if x == 0 else (1 if x > 0 else -1)


def run_backtest(
    data: dict[str, pd.DataFrame],
    cfg: Config,
    funding: dict[str, pd.Series] | None = None,
    scores: dict[str, pd.Series] | None = None,
    eval_start: pd.Timestamp | None = None,
) -> BacktestResult:
    """`eval_start`: göstergeler öncesindeki tüm veriyle ısınır, ama işlem ve değerleme bu tarihten başlar."""
    if cfg.is_swap:
        from okx_karar.futures import ensure_enabled

        ensure_enabled(cfg)
    funding = funding or {}
    insts = list(cfg.instruments)
    missing = [i for i in insts if i not in data]
    if missing:
        raise ValueError(f"veri eksik: {', '.join(missing)}")

    signals = {
        i: compute_signals(data[i], cfg.signals, funding.get(i) if cfg.is_swap else None, cfg.bar_seconds)
        for i in insts
    }
    if scores is None:
        weights = cfg.effective_weights()
        scores = {i: score_frame(signals[i], weights) for i in insts}

    index = data[insts[0]].index
    for i in insts[1:]:
        index = index.intersection(data[i].index)
    index = index.sort_values()
    n = len(index)

    opens = {i: data[i]["open"].reindex(index).to_numpy() for i in insts}
    highs = {i: data[i]["high"].reindex(index).to_numpy() for i in insts}
    lows = {i: data[i]["low"].reindex(index).to_numpy() for i in insts}
    closes = {i: data[i]["close"].reindex(index).to_numpy() for i in insts}
    score_arr = {i: scores[i].reindex(index).to_numpy() for i in insts}
    atr_arr = {i: signals[i]["atr"].reindex(index).to_numpy() for i in insts}
    vol_arr = {i: signals[i]["ann_vol"].reindex(index).to_numpy() for i in insts}
    dcfg = cfg.decision
    gate_arr = {}
    for i in insts:
        if dcfg.confirm_bars > 1 or dcfg.confirm_volume > 0:
            g = entry_gate(scores[i].reindex(index), signals[i]["vol_ratio"].reindex(index),
                           dcfg.enter_threshold, dcfg.confirm_bars, dcfg.confirm_volume, side=1)
            gate_arr[i] = g.to_numpy()
        else:
            gate_arr[i] = np.ones(n, dtype=bool)
    if cfg.regime.enabled:
        ref_close = data[cfg.regime.reference]["close"].reindex(index)
        regime_ok = (ref_close > ref_close.rolling(cfg.regime.sma_bars).mean()).to_numpy()  # NaN ısınmada False
    else:
        regime_ok = np.ones(n, dtype=bool)

    ready = np.all([~np.isnan(score_arr[i]) & ~np.isnan(atr_arr[i]) for i in insts], axis=0)
    if cfg.risk.sizing == "vol_target":
        ready &= np.all([~np.isnan(vol_arr[i]) for i in insts], axis=0)
    if eval_start is not None:
        ready &= np.asarray(index >= eval_start)
    if not ready.any():
        raise ValueError("yeterli veri yok: göstergelerin ısınma süresi dolmadı")
    start = int(np.argmax(ready))
    if n - start < 2:
        raise ValueError("ısınma sonrası en az 2 mum gerekli")

    costs = cfg.effective_costs()
    fee_rate, slip = costs.fee_rate, costs.slippage
    enter, exit_ = cfg.decision.enter_threshold, cfg.decision.exit_threshold
    bar_delta = pd.Timedelta(seconds=cfg.bar_seconds)

    cash = float(cfg.initial_equity)
    qty = {i: 0.0 for i in insts}
    stops: dict[str, float | None] = {i: None for i in insts}
    blocked = {i: 0 for i in insts}   # stop sonrası aynı yöne yeniden girişi engeller
    pending: dict[str, _Order] = {}
    guard = DrawdownGuard(cfg.risk.max_drawdown)
    trades: list[Trade] = []
    decisions: list[DecisionRecord] = []
    equity_vals, exposure_vals = [], []
    vetoes = 0
    killed_at = None
    funding_paid = 0.0

    def execute(i: str, t: int, delta: float, ref_price: float, reason: str) -> float | None:
        nonlocal cash
        price = ref_price * (1 + slip) if delta > 0 else ref_price * (1 - slip)
        if delta > 0 and not cfg.is_swap:
            delta = min(delta, cash / (price * (1 + fee_rate)))
        if abs(delta) * price < 1e-9:
            return None
        fee = abs(delta) * price * fee_rate
        cash -= delta * price + fee
        qty[i] += delta
        if abs(qty[i]) < 1e-12:
            qty[i] = 0.0
        trades.append(Trade(index[t], i, "buy" if delta > 0 else "sell", abs(delta), price, fee, reason))
        return price

    for t in range(start, n):
        # 1) Önceki kapanışta verilen emirler bu mumun açılışında dolar (önce azaltanlar).
        if pending:
            for i, order in sorted(pending.items(), key=lambda kv: abs(kv[1].target_qty) - abs(qty[kv[0]])):
                o = opens[i][t]
                if qty[i] != 0 and (order.target_qty == 0 or _sign(order.target_qty) != _sign(qty[i])):
                    execute(i, t, -qty[i], o, order.reason)
                    stops[i] = None
                if order.target_qty != 0:
                    fill = execute(i, t, order.target_qty - qty[i], o, order.reason)
                    if fill is not None and qty[i] != 0 and cfg.risk.use_stop:
                        stops[i] = stop_price(fill, order.atr, cfg.risk, _sign(qty[i]))
            pending = {}

        # 2) Mum içi stop kontrolü.
        for i in insts:
            if qty[i] == 0 or stops[i] is None:
                continue
            side, stop = _sign(qty[i]), stops[i]
            if side > 0 and lows[i][t] <= stop:
                execute(i, t, -qty[i], min(opens[i][t], stop), "stop")
            elif side < 0 and highs[i][t] >= stop:
                execute(i, t, -qty[i], max(opens[i][t], stop), "stop")
            else:
                continue
            stops[i] = None
            blocked[i] = side

        # 3) Funding ödemeleri (yalnızca swap): bu mum içinde gerçekleşen funding anları.
        if cfg.is_swap:
            for i in insts:
                f = funding.get(i)
                if f is None or qty[i] == 0 or f.empty:
                    continue
                window = f[(f.index > index[t]) & (f.index <= index[t] + bar_delta)]
                for rate in window:
                    paid = qty[i] * closes[i][t] * float(rate)   # long pozitif funding'de öder
                    cash -= paid
                    funding_paid += paid

        # 4) Kapanışta değerleme ve kill switch.
        equity = cash + sum(qty[i] * closes[i][t] for i in insts)
        gross = sum(abs(qty[i] * closes[i][t]) for i in insts)
        equity_vals.append(equity)
        exposure_vals.append(gross / equity if equity > 0 else 0.0)

        if guard.tripped:
            continue
        if guard.update(equity):
            killed_at = index[t]
            for i in insts:
                if qty[i] != 0:
                    pending[i] = _Order(0.0, math.nan, "kill_switch")
            continue
        if t == n - 1:
            continue  # son mumun kararı dolamaz

        # 5) Kararlar (dolum bir sonraki açılışta).
        for i in insts:
            s, a, c = score_arr[i][t], atr_arr[i][t], closes[i][t]
            cur = _sign(qty[i])
            if blocked[i] == 1 and s < exit_:
                blocked[i] = 0
            elif blocked[i] == -1 and s > -exit_:
                blocked[i] = 0
            tgt = next_target(s, cur, enter, exit_, cfg.allow_short)
            if tgt != 0 and tgt == blocked[i]:
                tgt = 0
            if cur == 0 and tgt == 1 and not (gate_arr[i][t] and regime_ok[t]):
                continue  # onay/rejim filtresi yalnızca yeni long girişini engeller
            if tgt == cur:
                continue
            target_qty = 0.0
            note = ""
            if tgt != 0:
                veto = entry_veto(c, a, cfg.risk)
                if veto:
                    vetoes += 1
                    if cur == 0:
                        decisions.append(DecisionRecord(index[t], i, cur, cur, s, c, f"veto: {veto}"))
                        continue
                    tgt, note = 0, f"yön değişimi veto edildi: {veto}"
                else:
                    if cfg.risk.sizing == "vol_target":
                        size = vol_target_size(equity, c, vol_arr[i][t], cfg.risk, cfg.leverage)
                    else:
                        size = position_size(equity, c, a, cfg.risk, cfg.leverage)
                    target_qty = tgt * size
                    if target_qty == 0:
                        continue
            pending[i] = _Order(target_qty, a, "sinyal")
            decisions.append(DecisionRecord(index[t], i, cur, tgt, s, c, note))

    # Al-tut karşılaştırması: eşit ağırlık, aynı başlangıç ve aynı maliyetlerle.
    alloc = cfg.initial_equity / len(insts)
    bench_qty = {i: alloc / (opens[i][start + 1] * (1 + slip) * (1 + fee_rate)) for i in insts}
    bench = [cfg.initial_equity] + [
        sum(bench_qty[i] * closes[i][t] for i in insts) for t in range(start + 1, n)
    ]

    eq_index = index[start:]
    return BacktestResult(
        equity=pd.Series(equity_vals, index=eq_index, name="strateji"),
        benchmark=pd.Series(bench, index=eq_index, name="al_tut"),
        exposure=pd.Series(exposure_vals, index=eq_index, name="maruziyet"),
        trades=trades,
        decisions=decisions,
        closes={i: pd.Series(closes[i], index=index) for i in insts},
        bar=cfg.bar,
        config_hash=cfg.config_hash,
        vetoes=vetoes,
        killed_at=killed_at,
        funding_paid=funding_paid,
        fees_paid=sum(tr.fee for tr in trades),
        final_positions={i: q for i, q in qty.items() if q},
    )
