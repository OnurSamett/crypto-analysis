import pandas as pd
import pytest

from okx_karar.data import count_gaps, fetch_history, load_candles, parse_candles, read_cache

HOUR_MS = 3_600_000
T0 = 1_735_689_600_000  # 2025-01-01 00:00 UTC


def _row(ts, price=100.0, confirm="1"):
    return [str(ts), str(price), str(price + 1), str(price - 1), str(price), "10", "0", "0", confirm]


class FakeClient:
    """history-candles davranışı: `after`dan daha eski en fazla `limit` mum, yeniden eskiye."""

    def __init__(self, n=1000):
        self.rows = [_row(T0 + k * HOUR_MS, 100 + k) for k in range(n)]
        self.rows.append(_row(T0 + n * HOUR_MS, 0, confirm="0"))  # henüz kapanmamış mum
        self.calls = 0

    def get_history_candles(self, inst_id, bar, after=None, limit=100):
        self.calls += 1
        older = [r for r in self.rows if after is None or int(r[0]) < after]
        return sorted(older, key=lambda r: -int(r[0]))[:limit]


def test_parse_drops_unconfirmed_and_sorts():
    df = parse_candles([_row(T0 + HOUR_MS), _row(T0), _row(T0 + 2 * HOUR_MS, confirm="0")])
    assert list(df.index.asi8 // 1_000_000) == [T0, T0 + HOUR_MS]
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_fetch_history_paginates_to_start(monkeypatch):
    monkeypatch.setattr("okx_karar.data.time.sleep", lambda s: None)
    client = FakeClient(1000)
    start = pd.Timestamp(T0 + 250 * HOUR_MS, unit="ms", tz="UTC")
    df = fetch_history(client, "X", "1H", start)
    assert len(df) == 750
    assert df.index[0] == start and df.index.is_monotonic_increasing and df.index.is_unique
    assert client.calls == 8  # 750 mum / sayfa başına 100


def test_load_candles_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("okx_karar.data.time.sleep", lambda s: None)
    client = FakeClient(300)
    start = pd.Timestamp(T0, unit="ms", tz="UTC")
    first = load_candles(client, "X", "1H", start, None, tmp_path)
    assert len(first) == 300 and len(read_cache(tmp_path, "X", "1H")) == 300
    offline = load_candles(None, "X", "1H", start, None, tmp_path, offline=True)
    pd.testing.assert_frame_equal(first, offline, check_freq=False)
    with pytest.raises(FileNotFoundError):
        load_candles(None, "Y", "1H", start, None, tmp_path, offline=True)


def test_count_gaps():
    df = parse_candles([_row(T0), _row(T0 + HOUR_MS), _row(T0 + 4 * HOUR_MS)])
    assert count_gaps(df, "1H") == 2
