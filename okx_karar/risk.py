"""Risk katmanı: pozisyon büyüklüğü, stop seviyesi, giriş vetosu ve drawdown kill switch."""
from __future__ import annotations

import math

from okx_karar.config import RiskCfg


def entry_veto(price: float, atr_value: float, cfg: RiskCfg) -> str | None:
    """Yeni girişi engelleyen bir durum varsa nedenini döner, yoksa None."""
    if price is None or atr_value is None or math.isnan(price) or math.isnan(atr_value) or price <= 0:
        return "veri eksik"
    if atr_value / price > cfg.max_atr_pct:
        return f"volatilite çok yüksek (ATR/fiyat %{100 * atr_value / price:.2f})"
    return None


def position_size(equity: float, price: float, atr_value: float, cfg: RiskCfg, leverage: float = 1.0) -> float:
    """Baz para birimi cinsinden miktar.

    İki sınırın küçüğü alınır:
      * risk sınırı: stop'a gelinirse kayıp = sermaye × risk_per_trade
      * tavan: pozisyon değeri ≤ sermaye × max_position_fraction × kaldıraç
    """
    stop_distance = cfg.stop_atr_multiple * atr_value
    if equity <= 0 or price <= 0 or not stop_distance > 0:
        return 0.0
    by_risk = equity * cfg.risk_per_trade / stop_distance
    by_cap = equity * cfg.max_position_fraction * leverage / price
    return max(0.0, min(by_risk, by_cap))


def vol_target_size(equity: float, price: float, ann_vol: float, cfg: RiskCfg, leverage: float = 1.0) -> float:
    """Hedef volatiliteye göre miktar: pozisyon değeri = sermaye × hedef_vol / gerçekleşen_vol,
    en fazla sermaye × max_position_fraction × kaldıraç."""
    if equity <= 0 or price <= 0 or ann_vol is None or math.isnan(ann_vol) or ann_vol <= 0:
        return 0.0
    fraction = min(cfg.target_vol / ann_vol, cfg.max_position_fraction * leverage)
    return max(0.0, equity * fraction / price)


def stop_price(entry: float, atr_value: float, cfg: RiskCfg, side: int) -> float:
    return entry - side * cfg.stop_atr_multiple * atr_value


class DrawdownGuard:
    """Sermaye zirveden max_drawdown kadar düşerse tetiklenir ve tetiklenmiş kalır."""

    def __init__(self, max_drawdown: float, peak: float | None = None, tripped: bool = False):
        self.max_drawdown = max_drawdown
        self.peak = peak
        self.tripped = tripped

    def update(self, equity: float) -> bool:
        if self.peak is None or equity > self.peak:
            self.peak = equity
        if equity <= self.peak * (1 - self.max_drawdown):
            self.tripped = True
        return self.tripped
