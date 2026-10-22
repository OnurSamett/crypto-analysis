"""OKX'ten mum verisi çekme, sayfalama ve yerel CSV önbelleği."""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from okx_karar.config import BAR_SECONDS

COLUMNS = ["open", "high", "low", "close", "volume"]


def parse_candles(rows: list) -> pd.DataFrame:
    """OKX mum satırlarını DataFrame'e çevirir. Henüz kapanmamış mum (confirm == "0") atılır."""
    rows = [r for r in rows if len(r) < 9 or str(r[8]) == "1"]
    if not rows:
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], tz="UTC", name="ts"), dtype=float)
    df = pd.DataFrame([r[:6] for r in rows], columns=["ts", *COLUMNS])
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    df = df.set_index("ts").astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def _to_ms(ts: pd.Timestamp) -> int:
    return int(ts.value // 1_000_000)


def fetch_history(client, inst_id: str, bar: str, start: pd.Timestamp, end: pd.Timestamp | None = None,
                  pause: float = 0.12) -> pd.DataFrame:
    """[start, end) aralığındaki kapanmış mumları geriye doğru sayfalayarak çeker."""
    start_ms = _to_ms(start)
    after = _to_ms(end) if end is not None else None
    rows: list = []
    while True:
        page = client.get_history_candles(inst_id, bar, after=after, limit=100)
        if not page:
            break
        rows.extend(page)
        oldest = min(int(r[0]) for r in page)
        if oldest <= start_ms or (after is not None and oldest >= after):
            break
        after = oldest
        time.sleep(pause)
    df = parse_candles(rows)
    df = df[df.index >= start]
    if end is not None:
        df = df[df.index < end]
    return df


def fetch_recent(client, inst_id: str, bar: str, limit: int = 300) -> pd.DataFrame:
    """Paper trading için en güncel kapanmış mumlar."""
    return parse_candles(client.get_candles(inst_id, bar, limit=limit))


def _cache_path(cache_dir: Path, inst_id: str, bar: str) -> Path:
    return Path(cache_dir) / f"{inst_id}_{bar}.csv"


def read_cache(cache_dir: Path, inst_id: str, bar: str) -> pd.DataFrame:
    path = _cache_path(cache_dir, inst_id, bar)
    if not path.exists():
        return parse_candles([])
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    return df.set_index("ts")[COLUMNS].astype(float).sort_index()


def write_cache(df: pd.DataFrame, cache_dir: Path, inst_id: str, bar: str) -> None:
    path = _cache_path(cache_dir, inst_id, bar)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out.insert(0, "ts", out.index.asi8 // 1_000_000)
    out.to_csv(path, index=False)


def load_candles(client, inst_id: str, bar: str, start: pd.Timestamp, end: pd.Timestamp | None,
                 cache_dir: Path, offline: bool = False) -> pd.DataFrame:
    cached = read_cache(cache_dir, inst_id, bar)
    if offline:
        if cached.empty:
            raise FileNotFoundError(f"{inst_id} {bar} için önbellekte veri yok; önce `fetch` çalıştırın.")
    else:
        if cached.empty or cached.index[0] > start:
            fresh = fetch_history(client, inst_id, bar, start)
        else:
            fresh = fetch_history(client, inst_id, bar, cached.index[-1])
        cached = pd.concat([cached, fresh])
        cached = cached[~cached.index.duplicated(keep="last")].sort_index()
        write_cache(cached, cache_dir, inst_id, bar)
    df = cached[cached.index >= start]
    if end is not None:
        df = df[df.index < end]
    return df


def count_gaps(df: pd.DataFrame, bar: str) -> int:
    """Beklenen mum aralığından uzun boşlukların toplam eksik bar sayısı."""
    if len(df) < 2:
        return 0
    step = pd.Timedelta(seconds=BAR_SECONDS[bar])
    diffs = df.index.to_series().diff().dropna()
    return int(((diffs / step).round() - 1).clip(lower=0).sum())


def fetch_funding(client, swap_inst_id: str, start: pd.Timestamp, pause: float = 0.12) -> pd.Series:
    """Gerçekleşen funding oranları (fundingTime → oran). Yalnızca swap modunda kullanılır."""
    start_ms = _to_ms(start)
    after = None
    rows: list = []
    while True:
        page = client.get_funding_history(swap_inst_id, after=after, limit=100)
        if not page:
            break
        rows.extend(page)
        oldest = min(int(r["fundingTime"]) for r in page)
        if oldest <= start_ms or (after is not None and oldest >= after):
            break
        after = oldest
        time.sleep(pause)
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([int(r["fundingTime"]) for r in rows], unit="ms", utc=True)
    values = [float(r.get("realizedRate") or r["fundingRate"]) for r in rows]
    s = pd.Series(values, index=idx).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s[s.index >= start]
