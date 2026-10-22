"""Danışma modu: emir vermez, sinyal durumunu ve olayları hesaplar (bildirim botunun çekirdeği).

Karar mantığı backtest/paper ile aynıdır (Donchian topluluğu, rejim filtresi, giriş onayı, volatilite vetosu,
histerezisli eşikler); uyum tests/test_advisory.py ile doğrulanır. Spot, yalnızca long.

Durum (state) dosyası bir yapılandırma için son işlenen barı ve her enstrümanın yönünü tutar; böylece bir bar
iki kez bildirilmez. İlk çalıştırmada durum, geçmişin yeniden oynatılmasıyla (replay) kurulur ve yalnızca bir
"mevcut durum" özeti üretilir, eski kırılımlar yeni giriş olarak bildirilmez.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from okx_karar.config import Config
from okx_karar.decision import entry_gate, next_target, score_frame
from okx_karar.risk import entry_veto
from okx_karar.signals import compute_signals, donchian_window_states, warmup_bars


@dataclass
class Event:
    ts: pd.Timestamp          # olayı doğuran barın KAPANIŞ zamanı
    inst: str                 # enstrüman ya da "REGIME"
    kind: str                 # ENTRY | EXIT | BLOCKED | REGIME_ON | REGIME_OFF
    detail: str = ""


@dataclass
class CoinView:
    inst: str
    price: float
    score: float
    side: int
    n_long: int
    windows: tuple
    wstates: tuple            # pencere başına son durum (+1 long, −1 short)
    regime_ok: bool
    gate_ok: bool
    weight_pct: float | None
    upper: dict               # bakış → bir sonraki kapanışta aşılması gereken üst kanal
    lower: dict               # bakış → bir sonraki kapanışta altına inilmemesi gereken alt kanal
    since: pd.Timestamp | None


@dataclass
class Assessment:
    label: str
    bar: str
    as_of: pd.Timestamp                 # son kapanmış barın kapanış zamanı
    regime_ok: bool | None
    regime_since: pd.Timestamp | None
    views: list = field(default_factory=list)
    events: list = field(default_factory=list)
    snapshot: bool = False


def required_bars(cfg: Config, replay: int = 250) -> int:
    need = max(cfg.signals.volume_window, max(cfg.signals.donchian_lookbacks), warmup_bars(cfg.signals))
    if cfg.regime.enabled:
        need = max(need, cfg.regime.sma_bars)
    return need + replay


def _iso(ts) -> str | None:
    return None if ts is None else pd.Timestamp(ts).isoformat()


def _ts(v):
    return None if v is None else pd.Timestamp(v)


def assess(cfg: Config, frames: dict, state: dict | None, label: str) -> tuple[Assessment, dict]:
    insts = list(cfg.instruments)
    index = frames[insts[0]].index
    for i in insts[1:]:
        index = index.intersection(frames[i].index)
    index = index.sort_values()
    fr = {i: frames[i].loc[index] for i in insts}
    step = pd.Timedelta(seconds=cfg.bar_seconds)

    weights = cfg.effective_weights()
    dcfg = cfg.decision
    sig = {i: compute_signals(fr[i], cfg.signals, None, cfg.bar_seconds) for i in insts}
    score = {i: score_frame(sig[i], weights) for i in insts}
    use_gate = dcfg.confirm_bars > 1 or dcfg.confirm_volume > 0
    gate = {i: (entry_gate(score[i], sig[i]["vol_ratio"], dcfg.enter_threshold, dcfg.confirm_bars,
                           dcfg.confirm_volume, side=1).to_numpy() if use_gate else np.ones(len(index), dtype=bool))
            for i in insts}
    if cfg.regime.enabled:
        ref = fr[cfg.regime.reference]["close"]
        ma = ref.rolling(cfg.regime.sma_bars).mean()
        reg_ok = (ref > ma).to_numpy()
        reg_valid = ma.notna().to_numpy()
    else:
        reg_ok = np.ones(len(index), dtype=bool)
        reg_valid = np.ones(len(index), dtype=bool)

    first_run = state is None
    st = {"last_bar": {}, "side": {}, "blocked": {}, "since": {}, "regime_ok": None, "regime_since": None,
          "last_weekly": None, "last_error_notice": None} if first_run else dict(state)
    events: list[Event] = []

    # --- rejim olayları (referans enstrüman üzerinden, ortak bar akışı) ---
    prev_reg = st.get("regime_ok")
    reg_since = _ts(st.get("regime_since"))
    reg_start = 0
    if not first_run and st.get("last_bar"):
        lb = min(pd.Timestamp(v) for v in st["last_bar"].values())
        reg_start = int(index.searchsorted(lb, side="right"))
    if cfg.regime.enabled:
        for t in range(reg_start if not first_run else 0, len(index)):
            if not reg_valid[t]:
                continue
            cur_reg = bool(reg_ok[t])
            if prev_reg is None or cur_reg != prev_reg:
                if prev_reg is not None and not first_run:
                    events.append(Event(index[t] + step, "REGIME", "REGIME_ON" if cur_reg else "REGIME_OFF"))
                reg_since = index[t] + step
            prev_reg = cur_reg
        st["regime_ok"] = prev_reg
        st["regime_since"] = _iso(reg_since)

    views = []
    for i in insts:
        sc = score[i].to_numpy()
        atr = sig[i]["atr"].to_numpy()
        close = fr[i]["close"].to_numpy()
        ready = ~np.isnan(sc) & ~np.isnan(atr) & reg_valid
        if first_run:
            t0 = int(np.argmax(ready)) if ready.any() else len(index)
            cur, blocked, since = 0, False, None
            emit = False
        else:
            t0 = int(index.searchsorted(pd.Timestamp(st["last_bar"][i]), side="right")) if i in st["last_bar"] else len(index)
            cur, blocked, since = int(st["side"].get(i, 0)), bool(st["blocked"].get(i, False)), _ts(st["since"].get(i))
            emit = True
        for t in range(t0, len(index)):
            if not ready[t]:
                continue
            tgt = next_target(float(sc[t]), cur, dcfg.enter_threshold, dcfg.exit_threshold, False)
            would_enter = cur == 0 and tgt == 1
            if would_enter:
                veto = entry_veto(float(close[t]), float(atr[t]), cfg.risk)
                if veto or not (gate[i][t] and reg_ok[t]):
                    tgt = 0
                    if not blocked and emit:
                        why = veto or ("rejim olumsuz" if not reg_ok[t] else "giriş onayı yok")
                        events.append(Event(index[t] + step, i, "BLOCKED", why))
                    blocked = True
                else:
                    blocked = False
            elif tgt == 0 and cur == 0:
                blocked = False
            if tgt != cur:
                since = index[t] + step
                if emit:
                    events.append(Event(index[t] + step, i, "ENTRY" if tgt == 1 else "EXIT",
                                        f"skor {float(sc[t]):+.2f}"))
                blocked = False if tgt == 1 else blocked
            cur = tgt
        st["side"][i] = cur
        st["blocked"][i] = blocked
        st["since"][i] = _iso(since)
        st["last_bar"][i] = _iso(index[-1])

        # --- bir sonraki kapanış için seviyeler ---
        lbs = cfg.signals.donchian_lookbacks
        wstates = [float(s.iloc[-1]) for s in donchian_window_states(fr[i], lbs)]
        upper = {k: float(fr[i]["high"].iloc[-k:].max()) for k in lbs}
        lower = {k: float(fr[i]["low"].iloc[-k:].min()) for k in lbs}
        ann_vol = float(sig[i]["ann_vol"].iloc[-1])
        weight = None
        if cfg.risk.sizing == "vol_target" and ann_vol > 0 and not math.isnan(ann_vol):
            weight = 100 * min(cfg.risk.target_vol / ann_vol, cfg.risk.max_position_fraction)
        views.append(CoinView(
            inst=i, price=float(close[-1]), score=float(sc[-1]) if not math.isnan(sc[-1]) else float("nan"),
            side=cur, n_long=sum(1 for w in wstates if w > 0), windows=tuple(lbs), wstates=tuple(wstates),
            regime_ok=bool(reg_ok[-1]), gate_ok=bool(gate[i][-1]), weight_pct=weight, upper=upper, lower=lower,
            since=since))

    events.sort(key=lambda e: (e.ts, e.inst))
    a = Assessment(label=label, bar=cfg.bar, as_of=index[-1] + step, regime_ok=st.get("regime_ok"),
                   regime_since=_ts(st.get("regime_since")), views=views, events=events, snapshot=first_run)
    return a, st
