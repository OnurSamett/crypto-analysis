import math

import numpy as np
import pandas as pd
import pytest

from okx_karar.config import RiskCfg, Weights
from okx_karar.decision import next_target, score_frame
from okx_karar.risk import DrawdownGuard, entry_veto, position_size, stop_price


def test_next_target_hysteresis_spot():
    assert next_target(0.5, 0, 0.3, -0.1, False) == 1
    assert next_target(0.1, 1, 0.3, -0.1, False) == 1     # eşikler arası: pozisyon korunur
    assert next_target(-0.2, 1, 0.3, -0.1, False) == 0
    assert next_target(-0.9, 0, 0.3, -0.1, False) == 0    # spotta short yok
    assert next_target(math.nan, 1, 0.3, -0.1, False) == 1


def test_next_target_short_when_allowed():
    assert next_target(-0.5, 0, 0.3, -0.1, True) == -1
    assert next_target(-0.5, 1, 0.3, -0.1, True) == -1    # doğrudan yön değişimi
    assert next_target(0.05, -1, 0.3, -0.1, True) == -1   # short çıkış eşiği −exit = +0.1
    assert next_target(0.2, -1, 0.3, -0.1, True) == 0


def test_score_is_weighted_mean_and_nan_propagates():
    sig = pd.DataFrame({"trend": [1.0, np.nan], "macd": [-1.0, 0.0], "rsi": [0.0, 0.0],
                        "volume": [0.0, 0.0], "funding": [0.0, 0.0]})
    s = score_frame(sig, Weights(trend=0.5, macd=0.5, rsi=0, volume=0, funding=0))
    assert s.iloc[0] == 0.0
    assert math.isnan(s.iloc[1])
    with pytest.raises(ValueError):
        score_frame(sig, Weights(0, 0, 0, 0, 0))


def test_position_size_takes_smaller_limit():
    cfg = RiskCfg(risk_per_trade=0.01, stop_atr_multiple=2.0, max_position_fraction=0.3)
    # stop mesafesi 2 × 1 = 2 → risk sınırı 10000 × 0.01 / 2 = 50 adet; tavan 3000/100 = 30 adet
    assert position_size(10_000, 100, 1.0, cfg) == pytest.approx(30)
    # stop mesafesi 2 × 10 = 20 → risk sınırı 5 adet
    assert position_size(10_000, 100, 10.0, cfg) == pytest.approx(5)
    assert position_size(10_000, 100, 1.0, cfg, leverage=2) == pytest.approx(50)
    assert position_size(0, 100, 1.0, cfg) == 0
    assert stop_price(100, 1.0, cfg, 1) == 98 and stop_price(100, 1.0, cfg, -1) == 102


def test_entry_veto():
    cfg = RiskCfg(max_atr_pct=0.05)
    assert entry_veto(100, 1, cfg) is None
    assert "volatilite" in entry_veto(100, 6, cfg)
    assert entry_veto(100, math.nan, cfg) == "veri eksik"


def test_drawdown_guard_latches():
    g = DrawdownGuard(0.2)
    assert not g.update(100)
    assert not g.update(120)
    assert g.update(95)           # 120 × 0.8 = 96 altı
    assert g.update(200)          # tetiklendikten sonra kalıcı
