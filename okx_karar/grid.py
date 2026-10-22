"""Spot grid botu (karşılaştırma amaçlı baz çizgisi).

Mantık: fiyatın etrafında [merkez·(1−w), merkez·(1+w)] aralığına N eşit hücre konur.
Fiyat bir seviyenin altına inerken o hücre alır (limit emir), bir üst seviyeye çıkarken satar.
Aralığın üstüne çıkılırsa her şey satılmış, altına inilirse her şey alınmış olur; kapanış
aralığın dışına çıkınca envanter tasfiye edilir ve ızgara yeni fiyatın etrafında yeniden kurulur.

Geleceğe bakmama: ızgara bir mumun KAPANIŞINDA kararlaştırılır, sonraki mumun açılışında kurulur.
Mum içi sıra: yeşil mumda açılış→düşük→yüksek→kapanış, kırmızı mumda açılış→yüksek→düşük→kapanış.
Bir seviyeye sadece "dokunmak" dolum sayılmaz, fiyatın seviyeyi geçmesi gerekir (temkinli varsayım).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from okx_karar.config import CostCfg


@dataclass(frozen=True)
class GridParams:
    width: float = 0.10        # merkezin ±%10'u
    n_grids: int = 20          # hücre sayısı (aralık 20 hücre → hücre başı %1)
    rerange: bool = True       # aralık dışına çıkınca tasfiye + yeniden kur


@dataclass
class GridResult:
    equity: pd.Series
    fills: int
    reranges: int
    fees: float


def simulate_grid(df: pd.DataFrame, capital: float, costs: CostCfg, p: GridParams = GridParams()) -> GridResult:
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    n, N = len(df), p.n_grids
    fee, slip = costs.fee_rate, costs.slippage

    cash = float(capital)
    held = np.zeros(N, dtype=bool)
    q = np.zeros(N)
    lower = step = 0.0
    active = False
    build_next = True
    fills = reranges = 0
    fees_paid = 0.0
    equity = np.empty(n)
    equity[0] = capital

    def level(j: int) -> float:
        return lower + j * step

    def walk(a: float, b: float) -> None:
        nonlocal cash, fills, fees_paid
        if b < a:   # aşağı: seviyeyi yukarıdan aşağı geçerken o hücre alır
            j_hi = min(N - 1, math.ceil((a - lower) / step) - 1)
            j_lo = max(0, math.floor((b - lower) / step) + 1)
            for j in range(j_hi, j_lo - 1, -1):
                lj = level(j)
                if not held[j] and b < lj < a:
                    cost = q[j] * lj * (1 + fee)
                    if cash >= cost:
                        cash -= cost
                        fees_paid += q[j] * lj * fee
                        held[j] = True
                        fills += 1
        elif b > a:  # yukarı: seviyeyi aşağıdan yukarı geçerken alttaki hücre satar
            j_lo = max(1, math.floor((a - lower) / step) + 1)
            j_hi = min(N, math.ceil((b - lower) / step) - 1)
            for j in range(j_lo, j_hi + 1):
                lj = level(j)
                if held[j - 1] and a < lj < b:
                    cash += q[j - 1] * lj * (1 - fee)
                    fees_paid += q[j - 1] * lj * fee
                    held[j - 1] = False
                    fills += 1

    for t in range(n):
        if t == 0:
            continue
        if build_next:
            if active:
                reranges += 1
            if held.any():  # eski ızgarayı açılışta tasfiye et
                sale = float((q * held).sum()) * o[t] * (1 - slip)
                fees_paid += sale * fee
                cash += sale * (1 - fee)
                held[:] = False
            lower, step = o[t] * (1 - p.width), 2 * p.width * o[t] / N
            per_cell = cash / N
            q = np.array([per_cell / level(i) for i in range(N)])
            price = o[t] * (1 + slip)
            for i in range(N):
                if level(i) >= o[t]:   # fiyatın üstündeki hücreler envanterle başlar
                    cost = q[i] * price * (1 + fee)
                    if cash >= cost:
                        cash -= cost
                        fees_paid += q[i] * price * fee
                        held[i] = True
            active, build_next = True, False

        path = (o[t], l[t], h[t], c[t]) if c[t] >= o[t] else (o[t], h[t], l[t], c[t])
        for a, b in zip(path[:-1], path[1:]):
            walk(a, b)
        equity[t] = cash + float((q * held).sum()) * c[t]
        if p.rerange and active and not (lower <= c[t] <= level(N)):
            build_next = True

    equity[0] = capital
    return GridResult(pd.Series(equity, index=df.index, name="grid"), fills, reranges, fees_paid)


def simulate_grid_portfolio(data: dict[str, pd.DataFrame], capital: float, costs: CostCfg,
                            p: GridParams = GridParams()) -> GridResult:
    """Sermaye enstrümanlara eşit bölünür, her biri bağımsız ızgara işletir."""
    index = None
    for df in data.values():
        index = df.index if index is None else index.intersection(df.index)
    parts = [simulate_grid(df.loc[index], capital / len(data), costs, p) for df in data.values()]
    return GridResult(sum(r.equity for r in parts).rename("grid"), sum(r.fills for r in parts),
                      sum(r.reranges for r in parts), sum(r.fees for r in parts))
