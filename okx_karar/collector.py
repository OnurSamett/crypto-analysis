"""Kendi verimizi toplamak: OKX'in anahtar gerektirmeyen uç noktalarından zaman damgalı anlık görüntüler.

Amaç, geriye dönük alınamayan ya da kısa saklanan verileri (emir defteri derinliği, funding, açık pozisyon,
uzun/kısa hesap oranı, alıcı/satıcı hacmi) kendi disk kayıtlarımızda, olay anındaki haliyle biriktirmektir.
Böylece sonradan yapılacak araştırma "o an bilinen" veriyle çalışır (point-in-time) ve ileride hiçbir
satıcıya ya da değişen bir API'ye bağlı kalmayız.

Tek çalıştırma = bir anlık görüntü (launchd her 5 dakikada çağırır). Yinelenen kayıtlar birincil anahtarla elenir.
Hiçbir uç nokta başarısız olsa diğerleri devam eder; hatalar sayılır ve raporlanır.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticker(inst TEXT, ts INTEGER, last REAL, bid REAL, ask REAL, bid_sz REAL, ask_sz REAL,
    vol24h_quote REAL, PRIMARY KEY(inst, ts));
CREATE TABLE IF NOT EXISTS book(inst TEXT, ts INTEGER, spread_bps REAL, bid_depth REAL, ask_depth REAL, imbalance REAL,
    PRIMARY KEY(inst, ts));
CREATE TABLE IF NOT EXISTS funding(inst TEXT, ts INTEGER, rate REAL, premium REAL, funding_time INTEGER,
    PRIMARY KEY(inst, ts));
CREATE TABLE IF NOT EXISTS oi(inst TEXT, ts INTEGER, oi_ccy REAL, oi_usd REAL, PRIMARY KEY(inst, ts));
CREATE TABLE IF NOT EXISTS ratio(ccy TEXT, period TEXT, ts INTEGER, value REAL, PRIMARY KEY(ccy, period, ts));
CREATE TABLE IF NOT EXISTS taker(ccy TEXT, period TEXT, ts INTEGER, sell_vol REAL, buy_vol REAL,
    PRIMARY KEY(ccy, period, ts));
"""
TABLES = ("ticker", "book", "funding", "oi", "ratio", "taker")


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def _f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _book_metrics(book: dict) -> tuple[float, float, float, float] | None:
    bids, asks = book.get("bids") or [], book.get("asks") or []
    if not bids or not asks:
        return None
    bid1, ask1 = float(bids[0][0]), float(asks[0][0])
    mid = (bid1 + ask1) / 2
    bid_d = sum(float(px) * float(sz) for px, sz, *_ in bids)
    ask_d = sum(float(px) * float(sz) for px, sz, *_ in asks)
    total = bid_d + ask_d
    return 1e4 * (ask1 - bid1) / mid, bid_d, ask_d, (bid_d - ask_d) / total if total else 0.0


def collect_once(client, conn: sqlite3.Connection, instruments=("BTC-USDT", "ETH-USDT", "SOL-USDT"),
                 ratio_period: str = "1H") -> dict:
    """Bir anlık görüntü alıp yazar. Dönüş: {'rows': eklenen satır sayısı, 'errors': [hata açıklamaları]}."""
    rows, errors = 0, []
    cur = conn.cursor()
    now_ms = int(time.time() * 1000)

    def run(name, fn):
        nonlocal rows
        try:
            before = conn.total_changes
            fn()
            rows += conn.total_changes - before
        except Exception as exc:  # bir uç nokta tüm turu bozmasın
            errors.append(f"{name}: {type(exc).__name__}")

    for spot in instruments:
        swap = f"{spot}-SWAP"
        ccy = spot.split("-")[0]

        def ticker(inst=spot):
            for d in client.public_get("/api/v5/market/ticker", {"instId": inst}):
                cur.execute("INSERT OR IGNORE INTO ticker VALUES (?,?,?,?,?,?,?,?)",
                            (inst, int(d["ts"]), _f(d["last"]), _f(d["bidPx"]), _f(d["askPx"]), _f(d["bidSz"]),
                             _f(d["askSz"]), _f(d.get("volCcy24h"))))

        def book(inst=spot):
            for d in client.public_get("/api/v5/market/books", {"instId": inst, "sz": 5}):
                m = _book_metrics(d)
                if m:
                    cur.execute("INSERT OR IGNORE INTO book VALUES (?,?,?,?,?,?)", (inst, int(d["ts"]), *m))

        def funding(inst=swap):
            for d in client.public_get("/api/v5/public/funding-rate", {"instId": inst}):
                cur.execute("INSERT OR IGNORE INTO funding VALUES (?,?,?,?,?)",
                            (inst, now_ms, _f(d["fundingRate"]), _f(d.get("premium")), int(d["fundingTime"])))

        def oi(inst=swap):
            for d in client.public_get("/api/v5/public/open-interest", {"instType": "SWAP", "instId": inst}):
                cur.execute("INSERT OR IGNORE INTO oi VALUES (?,?,?,?)", (inst, int(d["ts"]), _f(d["oiCcy"]), _f(d["oiUsd"])))

        def ratio(c=ccy):
            for ts, v in client.public_get("/api/v5/rubik/stat/contracts/long-short-account-ratio",
                                           {"ccy": c, "period": ratio_period}):
                cur.execute("INSERT OR IGNORE INTO ratio VALUES (?,?,?,?)", (c, ratio_period, int(ts), _f(v)))

        def taker(c=ccy):
            for ts, sell, buy in client.public_get("/api/v5/rubik/stat/taker-volume",
                                                   {"ccy": c, "instType": "SPOT", "period": ratio_period}):
                cur.execute("INSERT OR IGNORE INTO taker VALUES (?,?,?,?,?)", (c, ratio_period, int(ts), _f(sell), _f(buy)))

        for name, fn in ((f"ticker {spot}", ticker), (f"book {spot}", book), (f"funding {swap}", funding),
                         (f"oi {swap}", oi), (f"ratio {ccy}", ratio), (f"taker {ccy}", taker)):
            run(name, fn)
    conn.commit()
    return {"rows": rows, "errors": errors}


def summary(conn: sqlite3.Connection) -> dict:
    out = {}
    for t in TABLES:
        n, lo, hi = conn.execute(f"SELECT COUNT(*), MIN(ts), MAX(ts) FROM {t}").fetchone()
        out[t] = {"rows": n, "first_ms": lo, "last_ms": hi}
    return out
