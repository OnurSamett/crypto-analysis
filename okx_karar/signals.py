"""Analist katmanı: her sinyal −1 (ayı) ile +1 (boğa) arasında bir puandır.

Puanlar kapanmış mumun verisiyle hesaplanır; ısınma (warm-up) süresi dolmadan NaN döner
ve NaN olan bir barda karar verilmez.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from okx_karar.config import SignalParams
from okx_karar.indicators import atr, ema, macd, rsi

SIGNAL_NAMES = ("trend", "macd", "rsi", "volume", "funding", "donchian")

MACD_SCALE = 2.0          # histogram / ATR oranını tanh'a sokmadan önce çarpan
RSI_BAND = 20.0           # RSI 30 → +1, 70 → −1
FUNDING_SCALE = 0.0005    # 8 saatlik %0,05 funding = tam (−1) sinyal


def warmup_bars(p: SignalParams) -> int:
    """EMA'ların başlangıç değerinin etkisi ~%0,3'e insin diye en uzun pencerenin 3 katı."""
    ema_based = 3 * max(p.ema_slow, p.macd_slow + p.macd_signal, p.rsi_period, p.atr_period, p.volume_window)
    return max(ema_based, max(p.donchian_lookbacks) + 1)


def align_funding(index: pd.DatetimeIndex, funding: pd.Series, bar_seconds: int) -> pd.Series:
    """Her bara, o barın KAPANIŞ anında bilinen son funding oranını eşler (geleceğe bakmadan)."""
    funding = funding.sort_index()
    close_times = index + pd.Timedelta(seconds=bar_seconds)
    pos = funding.index.searchsorted(close_times, side="right") - 1
    values = np.where(pos >= 0, funding.to_numpy()[np.clip(pos, 0, None)], np.nan)
    return pd.Series(values, index=index)


def donchian_state(df: pd.DataFrame, lookbacks) -> pd.Series:
    """Donchian kanal trend modelleri topluluğu: her bakış süresi için durum +1 (önceki k barın en yükseğini
    yukarı kıran son kırılım) ya da −1 (en düşüğü aşağı kıran); ortalaması −1…+1 arası skor verir.
    Kanal sınırları bir önceki bardan itibaren hesaplanır (mevcut bar dahil değil)."""
    states = []
    for k in lookbacks:
        upper = df["high"].rolling(k).max().shift(1)
        lower = df["low"].rolling(k).min().shift(1)
        raw = pd.Series(np.where(df["close"] > upper, 1.0, np.where(df["close"] < lower, -1.0, np.nan)), index=df.index)
        states.append(raw.ffill().fillna(0.0))
    return sum(states) / len(states)


def compute_signals(
    df: pd.DataFrame,
    p: SignalParams,
    funding: pd.Series | None = None,
    bar_seconds: int = 3600,
) -> pd.DataFrame:
    close = df["close"]
    a = atr(df, p.atr_period).replace(0.0, np.nan)

    trend = np.tanh((ema(close, p.ema_fast) - ema(close, p.ema_slow)) / a)
    macd_sig = np.tanh(MACD_SCALE * macd(close, p.macd_fast, p.macd_slow, p.macd_signal)["hist"] / a)
    rsi_sig = ((50.0 - rsi(close, p.rsi_period)) / RSI_BAND).clip(-1.0, 1.0)

    vol_ratio = df["volume"] / df["volume"].rolling(p.volume_window).mean()
    volume_sig = np.sign(close - df["open"]) * (vol_ratio - 1.0).clip(0.0, 1.0)

    if funding is not None and len(funding):
        rate = align_funding(df.index, funding, bar_seconds)
        funding_sig = -(rate / FUNDING_SCALE).clip(-1.0, 1.0).fillna(0.0)
    else:
        funding_sig = pd.Series(0.0, index=df.index)

    bars_per_year = 365 * 86400 / bar_seconds
    log_ret = np.log(close).diff()
    ann_vol = log_ret.rolling(p.volume_window).std() * np.sqrt(bars_per_year)

    out = pd.DataFrame(
        {
            "trend": trend,
            "macd": macd_sig,
            "rsi": rsi_sig,
            "volume": volume_sig,
            "funding": funding_sig,
            "donchian": donchian_state(df, p.donchian_lookbacks),
            "atr": a,
            "vol_ratio": vol_ratio,
            "ann_vol": ann_vol,
        },
        index=df.index,
    )
    out.iloc[: warmup_bars(p)] = np.nan
    return out
