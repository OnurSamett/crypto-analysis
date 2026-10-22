import time

from okx_karar.collector import collect_once, connect, summary


class FakeClient:
    def __init__(self, fail=()):
        self.fail, self.calls = set(fail), []

    def public_get(self, path, params=None):
        self.calls.append(path)
        if any(f in path for f in self.fail):
            raise RuntimeError("boom")
        now = str(int(time.time() * 1000))
        if path.endswith("/market/ticker"):
            return [{"ts": now, "last": "100", "bidPx": "99.9", "askPx": "100.1", "bidSz": "1", "askSz": "2", "volCcy24h": "5"}]
        if path.endswith("/market/books"):
            return [{"ts": now, "bids": [["99.9", "2", "0", "1"], ["99.8", "1", "0", "1"]],
                     "asks": [["100.1", "1", "0", "1"], ["100.2", "1", "0", "1"]]}]
        if path.endswith("/funding-rate"):
            return [{"fundingRate": "0.0001", "premium": "0.0002", "fundingTime": "1700000000000"}]
        if path.endswith("/open-interest"):
            return [{"ts": now, "oiCcy": "10", "oiUsd": "1000"}]
        if path.endswith("long-short-account-ratio"):
            return [["1700000000000", "1.5"], ["1700003600000", "1.6"]]
        if path.endswith("taker-volume"):
            return [["1700000000000", "3", "4"]]
        raise AssertionError(path)


def test_collect_once_writes_all_tables_and_dedupes(tmp_path):
    conn = connect(tmp_path / "c.db")
    r1 = collect_once(FakeClient(), conn, instruments=("BTC-USDT",))
    assert r1["errors"] == [] and r1["rows"] >= 7
    s = summary(conn)
    assert all(s[t]["rows"] >= 1 for t in s)
    assert s["ratio"]["rows"] == 2 and s["taker"]["rows"] == 1
    r2 = collect_once(FakeClient(), conn, instruments=("BTC-USDT",))   # aynı geçmiş satırlar tekrar eklenmez
    assert summary(conn)["ratio"]["rows"] == 2 and summary(conn)["taker"]["rows"] == 1 and r2["rows"] < r1["rows"] + 1


def test_book_metrics_are_computed(tmp_path):
    conn = connect(tmp_path / "c.db")
    collect_once(FakeClient(), conn, instruments=("BTC-USDT",))
    spread, bid_d, ask_d, imb = conn.execute("SELECT spread_bps, bid_depth, ask_depth, imbalance FROM book").fetchone()
    assert abs(spread - 1e4 * 0.2 / 100.0) < 1e-6
    assert bid_d > ask_d and 0 < imb < 1


def test_one_failing_endpoint_does_not_stop_the_rest(tmp_path):
    conn = connect(tmp_path / "c.db")
    r = collect_once(FakeClient(fail=["open-interest"]), conn, instruments=("BTC-USDT", "ETH-USDT"))
    assert len(r["errors"]) == 2 and all("oi" in e for e in r["errors"])
    assert summary(conn)["ticker"]["rows"] >= 2 and summary(conn)["oi"]["rows"] == 0
