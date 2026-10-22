"""Performans ölçütleri: getiri, Sharpe, drawdown, işlem istatistikleri ve karar başına ileri getiri."""
from __future__ import annotations

import math
from collections import defaultdict

import pandas as pd

from okx_karar.config import BAR_SECONDS

HORIZONS = (1, 4, 24)


def bars_per_year(bar: str) -> float:
    return 365 * 86400 / BAR_SECONDS[bar]


def performance(equity: pd.Series, bar: str) -> dict:
    rets = equity.pct_change().dropna()
    total = equity.iloc[-1] / equity.iloc[0] - 1
    years = (len(equity) - 1) / bars_per_year(bar)
    annual = (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else math.nan
    std = rets.std()
    sharpe = rets.mean() / std * math.sqrt(bars_per_year(bar)) if std and std > 0 else 0.0
    drawdown = equity / equity.cummax() - 1
    return {
        "toplam_getiri": float(total),
        "yillik_getiri": float(annual),
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
    }


def round_trips(trades) -> list[dict]:
    """Pozisyon sıfırdan açılıp tekrar sıfıra dönene kadarki nakit akışlarından işlem başına K/Z."""
    pos: dict[str, float] = defaultdict(float)
    flows: dict[str, float] = defaultdict(float)
    opened: dict[str, pd.Timestamp] = {}
    out = []
    for tr in trades:
        signed = tr.qty if tr.side == "buy" else -tr.qty
        if pos[tr.inst] == 0:
            opened[tr.inst] = tr.ts
            flows[tr.inst] = 0.0
        flows[tr.inst] += -signed * tr.price - tr.fee
        pos[tr.inst] += signed
        if abs(pos[tr.inst]) < 1e-12:
            pos[tr.inst] = 0.0
            out.append({"inst": tr.inst, "acilis": opened[tr.inst], "kapanis": tr.ts,
                        "kz": flows[tr.inst], "cikis_nedeni": tr.reason})
    return out


def trade_stats(trades) -> dict:
    trips = round_trips(trades)
    wins = [t for t in trips if t["kz"] > 0]
    return {
        "islem_sayisi": len(trips),
        "kazanma_orani": len(wins) / len(trips) if trips else math.nan,
        "ortalama_kz": sum(t["kz"] for t in trips) / len(trips) if trips else math.nan,
        "stop_ile_kapanan": sum(1 for t in trips if t["cikis_nedeni"] == "stop"),
    }


def forward_returns(decisions, closes: dict[str, pd.Series], horizons=HORIZONS) -> dict:
    """Her kararın h mum sonraki getirisi, kararın yönüyle işaretlenmiş.

    Giriş kararı doğruysa fiyat girilen yönde gider; çıkış kararı doğruysa fiyat çıkılan
    pozisyonun aleyhine gider. Hepsi karar anındaki kapanış fiyatına göre ölçülür.
    """
    result = {}
    for h in horizons:
        buckets = {"giris": [], "cikis": []}
        for d in decisions:
            if d.note.startswith("veto"):
                continue
            series = closes[d.inst]
            pos = series.index.get_loc(d.ts)
            if pos + h >= len(series):
                continue
            r = series.iloc[pos + h] / d.close - 1
            if d.to_side != 0:
                buckets["giris"].append(r * d.to_side)
            else:
                buckets["cikis"].append(-r * d.from_side)
        result[h] = {
            k: {
                "adet": len(v),
                "ortalama": sum(v) / len(v) if v else math.nan,
                "isabet": sum(1 for x in v if x > 0) / len(v) if v else math.nan,
            }
            for k, v in buckets.items()
        }
    return result


def summarize(result) -> dict:
    return {
        "config_hash": result.config_hash,
        "baslangic": str(result.equity.index[0]),
        "bitis": str(result.equity.index[-1]),
        "strateji": performance(result.equity, result.bar),
        "al_tut": performance(result.benchmark, result.bar),
        "islemler": trade_stats(result.trades),
        "ortalama_maruziyet": float(result.exposure.mean()),
        "odenen_komisyon": float(result.fees_paid),
        "odenen_funding": float(result.funding_paid),
        "veto_sayisi": result.vetoes,
        "kill_switch": str(result.killed_at) if result.killed_at is not None else None,
        "ileri_getiri": forward_returns(result.decisions, result.closes),
    }
