import numpy as np
import pandas as pd

from okx_karar.audit import recursion_audit, truncation_audit
from tests.conftest import random_walk


def causal(df):
    return pd.DataFrame({
        "sma": df["close"].rolling(20).mean(),
        "ema": df["close"].ewm(span=20, adjust=False).mean(),
    })


def leaky(df):
    out = causal(df)
    out["future"] = df["close"].shift(-1)          # bir sonraki barın kapanışı: geleceğe bakıyor
    return out


def test_truncation_audit_passes_causal_and_flags_leak():
    df = random_walk(700, seed=4)
    ok = truncation_audit(df, causal)
    assert not ok["has_bias"] and ok["checked_bars"] > 10
    bad = truncation_audit(df, leaky)
    assert bad["has_bias"] and bad["biased_columns"] == ["future"]


def test_recursion_audit_separates_window_from_recursive_indicators():
    df = random_walk(1500, seed=2)
    rec = recursion_audit(df, causal, lengths=(25, 300, 1000))
    assert rec[25]["sma"] == 0.0 or rec[25]["sma"] != rec[25]["sma"] or rec[25]["sma"] < 1e-12  # SMA(20) 25 barla yeter
    assert rec[300]["sma"] == 0.0                                                              # pencere tabanlı: tam eşit
    assert rec[25]["ema"] > 0 and rec[1000]["ema"] < rec[25]["ema"]                            # EMA geçmişe bağlı, azalır
