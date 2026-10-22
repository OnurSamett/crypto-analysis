"""E6: düzenli alım (DCA) simülatörü ve BTC 200g rejim eğimi (Protokol Ek 2).

Kurallar (sabit, önceden kayıtlı):
  * Her pazartesi günlük mumun AÇILIŞINDA 100 USDT, enstrümanlar arasında eşit bölünür.
  * Rejim kararı bir önceki günün KAPANIŞINDAKİ bilgiyle verilir: BTC kapanışı, kendi 200 günlük ortalamasının üstünde mi?
  * D0 düz DCA. D1: rejim olumsuzken alım yok (harcanmayan tutar yatırılmış sayılmaz). D2: rejim olumsuzken alım iki katı.
  * Maliyet: kayma + komisyon, alışta.

Metrikler: yatırılan tutar, bitiş değeri, yatırılan tutara göre getiri, parayla ağırlıklı yıllık getiri (IRR),
ortalama maliyet ve zaman ağırlıklı endeksin maksimum düşüşü. Zaman ağırlıklı getiri, bir günün alımını
önceki kapanış değerine ekleyerek hesaplanır (kripto mumları ardışık olduğundan açılış ≈ önceki kapanış).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from okx_karar.config import CostCfg

VARIANTS = ("D0", "D1", "D2")


@dataclass
class DcaResult:
    variant: str
    invested: float
    final_value: float
    return_on_invested: float
    irr: float
    max_drawdown: float
    buys: int
    skipped: int
    avg_cost: dict
    value: pd.Series


def _irr(flows: list[tuple[pd.Timestamp, float]]) -> float:
    """Parayla ağırlıklı yıllık getiri: Σ cf_i · (1+r)^(−t_i) = 0 (çıkışlar negatif, bitiş değeri pozitif), ikili arama."""
    t0 = flows[0][0]
    ts = np.array([(t - t0).days / 365.0 for t, _ in flows])
    cf = np.array([c for _, c in flows])

    def npv(r: float) -> float:
        return float(np.sum(cf / (1 + r) ** ts))

    lo, hi = -0.99, 50.0
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def simulate_dca(data: dict[str, pd.DataFrame], variant: str, costs: CostCfg, start: pd.Timestamp,
                 end: pd.Timestamp, weekly_amount: float = 100.0, reference: str = "BTC-USDT",
                 sma_bars: int = 200) -> DcaResult:
    if variant not in VARIANTS:
        raise ValueError(f"bilinmeyen varyant: {variant}")
    insts = list(data)
    index = data[insts[0]].index
    for i in insts[1:]:
        index = index.intersection(data[i].index)
    index = index.sort_values()
    ref = data[reference]["close"].reindex(index)
    above = (ref > ref.rolling(sma_bars).mean())          # NaN → False
    open_ = {i: data[i]["open"].reindex(index) for i in insts}
    close = {i: data[i]["close"].reindex(index) for i in insts}

    units = {i: 0.0 for i in insts}
    spent_base = {i: 0.0 for i in insts}
    flows: list[tuple[pd.Timestamp, float]] = []
    invested = 0.0
    buys = skipped = 0
    values, twr = [], [1.0]
    prev_value = 0.0

    days = [t for t in index if start <= t < end]
    for k, t in enumerate(days):
        pos = index.get_loc(t)
        buy_today = 0.0
        if t.weekday() == 0:  # pazartesi
            regime_ok = bool(above.iloc[pos - 1]) if pos > 0 else False   # önceki kapanış
            amount = weekly_amount
            if variant == "D1" and not regime_ok:
                amount = 0.0
            elif variant == "D2" and not regime_ok:
                amount = 2 * weekly_amount
            if amount > 0:
                per = amount / len(insts)
                for i in insts:
                    price = open_[i].iloc[pos] * (1 + costs.slippage)
                    q = per / (1 + costs.fee_rate) / price
                    units[i] += q
                    spent_base[i] += per
                invested += amount
                buy_today = amount
                flows.append((t, -amount))
                buys += 1
            else:
                skipped += 1
        value = sum(units[i] * close[i].iloc[pos] for i in insts)
        values.append(value)
        if k > 0 and (prev_value + buy_today) > 0:
            twr.append(twr[-1] * value / (prev_value + buy_today))
        elif k > 0:
            twr.append(twr[-1])
        prev_value = value

    value_series = pd.Series(values, index=days)
    final = float(value_series.iloc[-1])
    flows.append((days[-1], final))
    twr_s = pd.Series(twr, index=days)
    dd = float((twr_s / twr_s.cummax() - 1).min())
    avg_cost = {i: (spent_base[i] / units[i] if units[i] else float("nan")) for i in insts}
    return DcaResult(variant, invested, final, final / invested - 1 if invested else float("nan"),
                     _irr(flows) if invested else float("nan"), dd, buys, skipped, avg_cost, value_series)
