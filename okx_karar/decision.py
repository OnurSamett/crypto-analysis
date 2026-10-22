"""Tartışma katmanı: sinyalleri ağırlıklı oylamayla tek bir skora indirger, skordan hedef yön üretir."""
from __future__ import annotations

import math
from typing import Callable

import numpy as np
import pandas as pd

from okx_karar.config import Weights
from okx_karar.signals import SIGNAL_NAMES


def score_frame(signals: pd.DataFrame, weights: Weights) -> pd.Series:
    """Skor = Σ ağırlık × sinyal / Σ |ağırlık|; sonuç −1 ile +1 arasındadır.

    Kullanılan sinyallerden biri NaN ise skor da NaN olur (o barda karar verilmez).
    """
    active = {name: getattr(weights, name) for name in SIGNAL_NAMES if getattr(weights, name) != 0}
    total = sum(abs(w) for w in active.values())
    if total == 0:
        raise ValueError("en az bir sinyalin ağırlığı sıfırdan farklı olmalı")
    score = pd.Series(0.0, index=signals.index)
    for name, w in active.items():
        score = score + w * signals[name]
    return score / total


def scores_from_callable(df: pd.DataFrame, decide: Callable[[pd.DataFrame], float], warmup: int) -> pd.Series:
    """Bar bar karar veren bir stratejiden (ör. ileride bir LLM ajanı) skor serisi üretir.

    `decide` fonksiyonuna her adımda YALNIZCA o ana kadarki mumlar verilir; geleceğe ait
    veri yapısal olarak görünmez. Backtest motoru bu seriyi kurallı skorla aynı şekilde kullanır.
    """
    values = np.full(len(df), np.nan)
    for i in range(warmup, len(df)):
        values[i] = float(decide(df.iloc[: i + 1]))
    return pd.Series(values, index=df.index)


def next_target(score: float, current: int, enter: float, exit_: float, allow_short: bool) -> int:
    """Histerezisli hedef yön: +1 long, −1 short, 0 nakit.

    Giriş eşiği çıkış eşiğinden yüksek olduğu için skor eşik çevresinde dalgalanınca
    sürekli al-sat yapılmaz.
    """
    if score is None or math.isnan(score):
        return current
    if current == 1:
        if allow_short and score < -enter:
            return -1
        return 0 if score < exit_ else 1
    if current == -1:
        if score > enter:
            return 1
        return 0 if score > -exit_ else -1
    if score > enter:
        return 1
    if allow_short and score < -enter:
        return -1
    return 0


def entry_gate(score: pd.Series, vol_ratio: pd.Series, enter: float, confirm_bars: int, confirm_volume: float,
               side: int = 1) -> pd.Series:
    """Yeni giriş için onay: skor son `confirm_bars` barın hepsinde eşiği aşmış olmalı ve (istenirse)
    aynı pencerede en az bir barda hacim ortalamanın `confirm_volume` katını geçmiş olmalı.
    Yalnızca geçmiş ve mevcut barı kullanır."""
    beyond = (score > enter) if side > 0 else (score < -enter)
    ok = beyond.astype(float).rolling(confirm_bars).min().fillna(0.0) == 1.0
    if confirm_volume > 0:
        ok = ok & (vol_ratio.rolling(confirm_bars).max() >= confirm_volume)
    return ok
