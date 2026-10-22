"""Sinyal denetimi (Freqtrade'in `lookahead-analysis` ve `recursive-analysis` fikirlerinin gerçek veriye uyarlaması).

* Kesme testi: göstergeler tüm veriyle bir kez, ve her kontrol noktasında yalnızca o noktaya kadarki veriyle hesaplanır;
  son satırlar eşit olmalıdır. Fark varsa gösterge o bara geleceğe ait bilgi taşıyordur.
* Özyineleme testi: aynı son satır, geçmişin yalnızca son N barıyla hesaplanır. EMA/ATR gibi özyineli göstergeler
  geçmiş uzunluğuna bağlıdır; paper trading yalnızca son ~300 mumu çeker, backtest ise çok daha uzun geçmişle çalışır.
  Pencere tabanlı göstergeler (Donchian, SMA, yuvarlanan oynaklık) yeterli uzunlukta tam olarak aynı çıkmalıdır.

Sınır (Freqtrade'inkiyle aynı): yalnızca denetlenen barlardaki sinyalleri doğrular.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

Compute = Callable[[pd.DataFrame], pd.DataFrame]
RELATIVE = {"atr", "ann_vol"}  # ölçeksiz olmayan sütunlar bağıl farkla ölçülür


def _diff(a: float, b: float, column: str) -> float:
    if np.isnan(a) and np.isnan(b):
        return 0.0
    if np.isnan(a) or np.isnan(b):
        return float("nan")
    d = abs(a - b)
    return d / max(abs(a), 1e-12) if column in RELATIVE else d


def truncation_audit(df: pd.DataFrame, compute: Compute, step: int = 20, tail: int = 400, tol: float = 1e-9) -> dict:
    full = compute(df)
    positions = list(range(max(len(df) - tail, 1), len(df), step))
    worst = {c: 0.0 for c in full.columns}
    for t in positions:
        row = compute(df.iloc[: t + 1]).iloc[-1]
        for c in full.columns:
            d = _diff(full[c].iloc[t], row[c], c)
            worst[c] = float("nan") if np.isnan(d) else max(worst[c], d)
    bad = [c for c, d in worst.items() if np.isnan(d) or d > tol]
    return {"checked_bars": len(positions), "max_diff": worst, "biased_columns": bad, "has_bias": bool(bad)}


def recursion_audit(df: pd.DataFrame, compute: Compute, lengths=(150, 300, 600, 1200)) -> dict:
    full_row = compute(df).iloc[-1]
    table = {}
    for n in lengths:
        if n >= len(df):
            continue
        row = compute(df.iloc[-n:]).iloc[-1]
        table[n] = {c: _diff(full_row[c], row[c], c) for c in full_row.index}
    return table
