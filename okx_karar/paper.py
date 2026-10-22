"""Paper trading döngüsü: her mum kapanışında karar ver, yürütücüye ilet.

Backtest ile aynı karar ve risk kodunu kullanır. Farklar:
  * Emir, kapanıştan hemen sonra o anki fiyattan verilir (backtest: sonraki açılış).
  * Stop bot tarafından mum kapanışlarında kontrol edilir; borsada bekleyen stop emri yoktur.
    Bu yüzden mum içinde stop'un çok altına inen bir hareket yakalanamaz.
"""
from __future__ import annotations

import csv
import json
import math
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from okx_karar.config import Config
from okx_karar.decision import next_target, score_frame
from okx_karar.executors import MIN_NOTIONAL, Fill
from okx_karar.risk import DrawdownGuard, entry_veto, position_size, stop_price
from okx_karar.signals import compute_signals


@dataclass
class PaperState:
    last_bar: dict[str, str] = field(default_factory=dict)
    stops: dict[str, float] = field(default_factory=dict)
    blocked: dict[str, int] = field(default_factory=dict)
    peak_equity: float | None = None
    killed: bool = False

    @classmethod
    def load(cls, path: Path) -> "PaperState":
        path = Path(path)
        if not path.exists():
            return cls()
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def cl_ord_id(inst: str, bar_ts: pd.Timestamp, tag: str) -> str:
    """OKX clOrdId: harf/rakam, en fazla 32 karakter. Aynı mum + aynı işlem → aynı kimlik."""
    ms = str(int(bar_ts.value // 1_000_000))
    return f"ok{inst.replace('-', '')[:15]}{ms}{tag}"[:32]


def _log_fills(fills: list[Fill], path: Path | None) -> None:
    if not fills or path is None:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(fills[0])))
        if new_file:
            writer.writeheader()
        for f in fills:
            writer.writerow(asdict(f))


def run_once(
    cfg: Config,
    executor,
    fetch_recent: Callable[[str], pd.DataFrame],
    state: PaperState,
    trade_log: Path | None = None,
    fetch_funding: Callable[[str], pd.Series] | None = None,
) -> list[str]:
    insts = list(cfg.instruments)
    frames = {i: fetch_recent(i) for i in insts}
    for i, df in frames.items():
        if df.empty:
            raise RuntimeError(f"{i} için mum verisi gelmedi")
    prices = {i: float(frames[i]["close"].iloc[-1]) for i in insts}
    latest = {i: frames[i].index[-1] for i in insts}
    new = [i for i in insts if i not in state.last_bar or pd.Timestamp(state.last_bar[i]) < latest[i]]
    if not new:
        return ["yeni kapanmış mum yok"]

    events: list[str] = []
    fills: list[Fill] = []
    positions = executor.positions()

    def side_of(i: str) -> int:
        q = positions.get(i, 0.0)
        return 0 if abs(q * prices[i]) < MIN_NOTIONAL else (1 if q > 0 else -1)

    def do_trade(i: str, delta: float, tag: str, reason: str) -> Fill | None:
        fill = executor.trade(i, delta, prices[i], cl_ord_id(i, latest[i], tag), reason)
        if fill:
            fills.append(fill)
            events.append(f"{i}: {fill.side} {fill.qty:.6f} @ {fill.price:.4f} ({reason})")
        return fill

    # 1) Son işlenen mumdan bu yana stop'a değildi mi?
    for i in new:
        s, stop = side_of(i), state.stops.get(i)
        if s == 0 or stop is None:
            continue
        df = frames[i]
        if i in state.last_bar:
            df = df[df.index > pd.Timestamp(state.last_bar[i])]
        hit = (df["low"] <= stop).any() if s > 0 else (df["high"] >= stop).any()
        if hit:
            do_trade(i, -positions[i], "s", "stop")
            state.stops.pop(i, None)
            state.blocked[i] = s
    positions = executor.positions()

    # 2) Kill switch.
    equity = executor.equity(prices)
    guard = DrawdownGuard(cfg.risk.max_drawdown, state.peak_equity, state.killed)
    already = guard.tripped
    guard.update(equity)
    state.peak_equity = guard.peak
    if guard.tripped:
        if not already:
            events.append(f"KILL SWITCH: sermaye {equity:.2f}, zirve {guard.peak:.2f}. Tüm pozisyonlar kapanıyor.")
        state.killed = True
        for i in insts:
            if side_of(i) != 0:
                do_trade(i, -positions[i], "k", "kill_switch")
                state.stops.pop(i, None)
        for i in new:
            state.last_bar[i] = latest[i].isoformat()
        _log_fills(fills, trade_log)
        return events

    # 3) Kararlar.
    weights = cfg.effective_weights()
    plans = []
    for i in new:
        funding = fetch_funding(i) if (cfg.is_swap and weights.funding and fetch_funding) else None
        sig = compute_signals(frames[i], cfg.signals, funding, cfg.bar_seconds)
        score = float(score_frame(sig, weights).iloc[-1])
        atr_value = float(sig["atr"].iloc[-1])
        cur = side_of(i)
        blocked = state.blocked.get(i, 0)
        if blocked == 1 and score < cfg.decision.exit_threshold:
            state.blocked.pop(i, None)
            blocked = 0
        elif blocked == -1 and score > -cfg.decision.exit_threshold:
            state.blocked.pop(i, None)
            blocked = 0
        tgt = next_target(score, cur, cfg.decision.enter_threshold, cfg.decision.exit_threshold, cfg.allow_short)
        if tgt != 0 and tgt == blocked:
            tgt = 0
        if math.isnan(score):
            events.append(f"{i}: yeterli veri yok, karar verilmedi")
        if tgt == cur:
            events.append(f"{i}: skor {score:+.2f}, değişiklik yok (yön {cur:+d})")
            continue
        if tgt != 0:
            veto = entry_veto(prices[i], atr_value, cfg.risk)
            if veto:
                events.append(f"{i}: skor {score:+.2f}, giriş veto edildi: {veto}")
                if cur == 0:
                    continue
                tgt = 0
        events.append(f"{i}: skor {score:+.2f}, yön {cur:+d} → {tgt:+d}")
        plans.append((i, cur, tgt, atr_value))

    # 4) Önce kapat, sonra aç (nakit serbest kalsın).
    for i, cur, tgt, _ in plans:
        if cur != 0:
            do_trade(i, -positions.get(i, 0.0), "c", "sinyal")
            state.stops.pop(i, None)
    for i, cur, tgt, atr_value in plans:
        if tgt == 0:
            continue
        equity = executor.equity(prices)
        qty = tgt * position_size(equity, prices[i], atr_value, cfg.risk, cfg.leverage)
        fill = do_trade(i, qty, "o", "sinyal") if qty else None
        if fill:
            state.stops[i] = stop_price(fill.price, atr_value, cfg.risk, tgt)

    for i in new:
        state.last_bar[i] = latest[i].isoformat()
    _log_fills(fills, trade_log)
    return events


def seconds_until_next_close(bar_seconds: int, now: float | None = None) -> float:
    now = time.time() if now is None else now
    return bar_seconds - (now % bar_seconds)


def run_loop(cfg: Config, executor, fetch_recent, state_path: Path, trade_log: Path,
             fetch_funding=None, once: bool = False, settle_seconds: float = 15.0) -> None:
    """Her mum kapanışından `settle_seconds` sonra bir tur çalışır. Ctrl+C ile durur."""
    while True:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        try:
            state = PaperState.load(state_path)
            events = run_once(cfg, executor, fetch_recent, state, trade_log, fetch_funding)
            state.save(state_path)
            for e in events:
                print(f"[{stamp}] {e}", flush=True)
        except Exception:  # döngü tek bir hatada ölmesin; hata yazdırılır, sonraki turda tekrar denenir
            print(f"[{stamp}] HATA:\n{traceback.format_exc()}", flush=True)
            if once:
                raise
        if once:
            return
        time.sleep(seconds_until_next_close(cfg.bar_seconds) + settle_seconds)
