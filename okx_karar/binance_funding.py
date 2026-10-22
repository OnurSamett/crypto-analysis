"""Binance USDT-M public funding-rate history (no API key).

Used only as a long-history proxy for candidate R01 (OKX keeps just ~3 months of funding history).
Prices are never loaded here.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

URL = "https://fapi.binance.com/fapi/v1/fundingRate"
EIGHT_HOURS = pd.Timedelta(hours=8)


def fetch_funding(symbol: str, start: pd.Timestamp, end: pd.Timestamp, session: requests.Session | None = None,
                  pause: float = 0.25) -> pd.Series:
    """Settled funding rates in [start, end), indexed by settlement time (UTC)."""
    sess = session or requests.Session()
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    rows: list = []
    while start_ms < end_ms:
        data = sess.get(URL, params={"symbol": symbol, "startTime": start_ms, "endTime": end_ms, "limit": 1000},
                        timeout=20).json()
        if isinstance(data, dict):
            raise RuntimeError(f"Binance error for {symbol}: {data.get('msg', data)}")
        if not data:
            break
        rows.extend(data)
        if len(data) < 1000:
            break
        start_ms = int(data[-1]["fundingTime"]) + 1
        time.sleep(pause)
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([int(r["fundingTime"]) for r in rows], unit="ms", utc=True)
    series = pd.Series([float(r["fundingRate"]) for r in rows], index=idx).sort_index()
    return series[~series.index.duplicated()]


def load_funding(symbol: str, start: pd.Timestamp, end: pd.Timestamp, cache_dir: Path,
                 session: requests.Session | None = None) -> pd.Series:
    """Cached read; downloads only when the cache does not cover the requested range."""
    path = Path(cache_dir) / f"binance_funding_{symbol}.csv"
    cached = pd.Series(dtype=float)
    if path.exists():
        df = pd.read_csv(path)
        cached = pd.Series(df["rate"].to_numpy(), index=pd.to_datetime(df["ts"], unit="ms", utc=True)).sort_index()
    if cached.empty or cached.index[0] > start + EIGHT_HOURS or cached.index[-1] < end - 2 * EIGHT_HOURS:
        cached = fetch_funding(symbol, start, end, session)
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"ts": cached.index.asi8 // 1_000_000, "rate": cached.to_numpy()}).to_csv(path, index=False)
    return cached[(cached.index >= start) & (cached.index < end)]


def interval_audit(series: pd.Series, tolerance: pd.Timedelta = pd.Timedelta(minutes=1)) -> dict:
    """Coverage and spacing report: how many settlements are not exactly 8 hours after the previous one."""
    if series.empty:
        return {"rows": 0, "first": None, "last": None, "irregular": []}
    diffs = series.index.to_series().diff().dropna()
    bad = diffs[(diffs - EIGHT_HOURS).abs() > tolerance]
    return {"rows": int(len(series)), "first": series.index[0], "last": series.index[-1],
            "irregular": [(series.index[series.index.get_loc(t) - 1], t, d.total_seconds() / 3600) for t, d in bad.items()]}
