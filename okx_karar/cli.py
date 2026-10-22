"""Komut satırı:  python -m okx_karar <komut>

  fetch     geçmiş mumları indirip data/ altına önbelleğe alır
  backtest  kurallı stratejiyi al-tut ile karşılaştırır, results/ altına kaydeder
  paper     her mum kapanışında karar verir (--executor sim | demo)
  status    paper hesabın durumunu gösterir
  evaluate  önceden kaydedilmiş protokolle yapılandırmaları dönem dönem değerlendirir
  events    registry adayları için bağımsız olay sayımı (fiyat/getiri yok)
  collect   kendi veri toplayıcımız: funding, açık pozisyon, derinlik, uzun/kısa oranı → data/collector.db
  notify    sinyal durumu değişince Telegram/macOS/konsol bildirimi (emir vermez)
  dca       E6: düz DCA ve BTC 200g rejim eğimi (dönem dönem)
  audit     sinyaller geleceğe bakıyor mu / geçmiş uzunluğuna bağımlı mı (gerçek veride)
  compare   yıl yıl: kurallı strateji vs grid vs al-tut (önbellekteki veriyle)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import tomllib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from okx_karar.backtest import run_backtest
from okx_karar.config import load_config
from okx_karar.data import count_gaps, fetch_funding, fetch_recent, load_candles
from okx_karar.executors import OKXDemoSpotExecutor, SimExecutor
from okx_karar.grid import GridParams, simulate_grid_portfolio
from okx_karar.metrics import performance, round_trips, summarize
from okx_karar.okx_client import OKXClient, load_env
from okx_karar.paper import PaperState, run_loop
from okx_karar.report import format_summary


def _range(args) -> tuple[pd.Timestamp, pd.Timestamp | None]:
    end = pd.Timestamp(args.end, tz="UTC") if args.end else None
    if args.start:
        start = pd.Timestamp(args.start, tz="UTC")
    else:
        start = (end or pd.Timestamp.now(tz="UTC").floor("h")) - pd.Timedelta(days=args.days)
    return start, end


def _load_data(cfg, client, base: Path, start, end, offline: bool) -> dict[str, pd.DataFrame]:
    data = {}
    for inst in cfg.instruments:
        df = load_candles(client, inst, cfg.bar, start, end, base / "data", offline=offline)
        gaps = count_gaps(df, cfg.bar)
        print(f"{inst}: {len(df)} mum" + (f", {gaps} eksik mum" if gaps else ""))
        data[inst] = df
    return data


def cmd_fetch(cfg, args, base: Path) -> int:
    start, end = _range(args)
    _load_data(cfg, OKXClient(), base, start, end, offline=False)
    return 0


def cmd_backtest(cfg, args, base: Path) -> int:
    start, end = _range(args)
    client = OKXClient()
    data = _load_data(cfg, client, base, start, end, args.offline)
    funding = None
    if cfg.is_swap:
        from okx_karar.futures import swap_inst_id

        funding = {i: fetch_funding(client, swap_inst_id(i), start) for i in cfg.instruments}
    result = run_backtest(data, cfg, funding=funding)
    summary = summarize(result)
    print()
    print(format_summary(summary, cfg.instruments, cfg.mode))

    out_dir = base / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    prefix = out_dir / f"backtest_{stamp}_{cfg.config_hash}"
    Path(f"{prefix}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    pd.DataFrame({"strateji": result.equity, "al_tut": result.benchmark}).to_csv(f"{prefix}_equity.csv")
    with open(f"{prefix}_trades.csv", "w", newline="", encoding="utf-8") as fh:
        rows = [asdict(t) for t in result.trades]
        if rows:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(f"\nSonuçlar: {prefix}.json (+ _equity.csv, _trades.csv)")
    print(f"İşlem başına K/Z: {len(round_trips(result.trades))} tamamlanmış işlem")
    return 0


def _label(args) -> str:
    """Durum dosyaları yapılandırmaya özeldir; böylece E3 ve E4 aynı hesabı paylaşmaz."""
    return Path(args.config).stem if args.config else "default"


def _paper_paths(base: Path, executor_name: str, label: str = "default") -> tuple[Path, Path]:
    return (base / "state" / f"paper_{label}_{executor_name}.json",
            base / "state" / f"trades_{label}_{executor_name}.csv")


def _make_executor(cfg, name: str, base: Path, client: OKXClient, label: str = "default"):
    if name == "sim":
        return SimExecutor(base / "state" / f"sim_account_{label}.json", cfg.initial_equity,
                           cfg.effective_costs(), allow_short=cfg.allow_short)
    if cfg.is_swap:
        from okx_karar.futures import OKXDemoSwapExecutor

        return OKXDemoSwapExecutor(client, cfg)
    return OKXDemoSpotExecutor(client, cfg)


def cmd_paper(cfg, args, base: Path) -> int:
    load_env(base / ".env")
    client = OKXClient.from_env()
    executor = _make_executor(cfg, args.executor, base, client, _label(args))
    state_path, trade_log = _paper_paths(base, args.executor, _label(args))

    if cfg.is_swap:
        from okx_karar.futures import swap_inst_id

        def recent(inst):
            return fetch_recent(client, swap_inst_id(inst), cfg.bar)

        def funding(inst):
            return fetch_funding(client, swap_inst_id(inst), pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=3))
    else:
        def recent(inst):
            return fetch_recent(client, inst, cfg.bar)

        funding = None

    print(f"Paper trading: {args.executor} yürütücü, {cfg.mode}, {', '.join(cfg.instruments)}, {cfg.bar}, "
          f"config_hash={cfg.config_hash}. Durdurmak için Ctrl+C.")
    try:
        run_loop(cfg, executor, recent, state_path, trade_log, fetch_funding=funding, once=args.once)
    except KeyboardInterrupt:
        print("\nDurduruldu.")
    return 0


def cmd_status(cfg, args, base: Path) -> int:
    load_env(base / ".env")
    client = OKXClient.from_env()
    executor = _make_executor(cfg, args.executor, base, client, _label(args))
    state_path, trade_log = _paper_paths(base, args.executor, _label(args))
    state = PaperState.load(state_path)
    prices = {i: float(fetch_recent(client, i, cfg.bar, limit=2)["close"].iloc[-1]) for i in cfg.instruments}
    print(f"Sermaye   : {executor.equity(prices):.2f} (zirve: {state.peak_equity or 0:.2f})")
    for inst, q in executor.positions().items():
        stop = state.stops.get(inst)
        print(f"Pozisyon  : {inst} {q:+.6f} ≈ {q * prices[inst]:.2f}" + (f", stop {stop:.4f}" if stop else ""))
    print(f"Kill switch: {'TETİKLENDİ' if state.killed else 'kapalı'}")
    print(f"İşlem kaydı: {trade_log}")
    return 0


def cmd_compare(cfg, args, base: Path) -> int:
    """Yıl yıl: kurallı strateji vs grid vs al-tut. Tüm parametreler sabit, ayar yapılmaz."""
    rows = []
    for year in (int(y) for y in args.years.split(",")):
        start, end = pd.Timestamp(f"{year}-01-01", tz="UTC"), pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
        data = {i: load_candles(None, i, cfg.bar, start, end, base / "data", offline=True) for i in cfg.instruments}
        if any(len(d) < 500 for d in data.values()):
            print(f"{year}: yeterli veri yok (önce `fetch --start {year - 1}-12-01` çalıştırın)")
            continue
        rule = run_backtest(data, cfg)
        grid = simulate_grid_portfolio(data, cfg.initial_equity, cfg.effective_costs(), GridParams())
        t0 = rule.equity.index[0]
        grid_eq = grid.equity[grid.equity.index >= t0]
        grid_eq = grid_eq / grid_eq.iloc[0] * cfg.initial_equity
        rows.append((year, performance(rule.equity, cfg.bar), performance(grid_eq, cfg.bar),
                     performance(rule.benchmark, cfg.bar), len(rule.trades), grid.fills))

    print(f"\n{'Yıl':<6}{'Strateji':>16}{'Grid':>16}{'Al-tut':>16}   (getiri / max drawdown)")
    for year, a, g, b, n_rule, n_grid in rows:
        cell = lambda m: f"{100 * m['toplam_getiri']:+6.1f}% / {100 * m['max_drawdown']:5.1f}%"
        print(f"{year:<6}{cell(a):>16}{cell(g):>16}{cell(b):>16}   işlem: {n_rule} / {n_grid}")
    if rows:
        def compound(idx):
            out = 1.0
            for r in rows:
                out *= 1 + r[idx]["toplam_getiri"]
            return out - 1
        print(f"{'Bileşik':<6}{100 * compound(1):>15.1f}%{100 * compound(2):>15.1f}%{100 * compound(3):>15.1f}%")
    return 0


def cmd_evaluate(_cfg, args, base: Path) -> int:
    """Önceden kaydedilmiş protokolle birden çok yapılandırmayı dönem dönem değerlendirir."""
    protocol = tomllib.loads((base / "experiments" / "protocol.toml").read_text(encoding="utf-8"))
    periods = [x.strip() for x in args.periods.split(",")]
    test_start = pd.Timestamp(protocol["guard"]["test_start"], tz="UTC")
    in_test_zone = {n: pd.Timestamp(protocol["periods"][n][1], tz="UTC") > test_start for n in periods}
    if any(in_test_zone.values()) and not args.allow_test:
        raise SystemExit("Test bölgesine düşen dönem(ler): " + ", ".join(n for n, z in in_test_zone.items() if z)
                         + ". Yalnızca --allow-test ile ve protokole (experiments/PROTOCOL.md) uygun çalıştırılmalı.")
    context = pd.Timedelta(days=protocol["context_days"])
    print(f"{'yapılandırma':<20}{'dönem':<12}{'getiri':>9}{'Sharpe':>8}{'maxDD':>9}{'işlem':>7}{'maruz.':>8}"
          f"   al-tut: getiri / Sharpe / maxDD")
    out_dir = base / "results" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    for cfg_path in (c.strip() for c in args.configs.split(",")):
        cfg = load_config(base / cfg_path)
        for name in periods:
            start, end = (pd.Timestamp(x, tz="UTC") for x in protocol["periods"][name])
            data = {i: load_candles(None, i, cfg.bar, start - context, end, base / "data", offline=True)
                    for i in cfg.instruments}
            result = run_backtest(data, cfg, eval_start=start)
            summary = summarize(result)
            st, bh = summary["strateji"], summary["al_tut"]
            label = Path(cfg_path).stem
            print(f"{label:<20}{name:<12}{100 * st['toplam_getiri']:>8.1f}%{st['sharpe']:>8.2f}"
                  f"{100 * st['max_drawdown']:>8.1f}%{summary['islemler']['islem_sayisi']:>7}"
                  f"{100 * summary['ortalama_maruziyet']:>7.0f}%   "
                  f"{100 * bh['toplam_getiri']:>6.1f}% / {bh['sharpe']:.2f} / {100 * bh['max_drawdown']:.1f}%")
            record = {"config": cfg_path, "config_hash": cfg.config_hash, "period": name,
                      "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "summary": summary}
            (out_dir / f"{label}_{name}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            if in_test_zone[name]:
                with (base / "experiments" / "test_log.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return 0


def cmd_audit(cfg, args, base: Path) -> int:
    """Sinyaller geleceğe bakıyor mu, ve geçmiş uzunluğuna ne kadar bağlı? (gerçek veride)"""
    from okx_karar.audit import recursion_audit, truncation_audit
    from okx_karar.decision import score_frame
    from okx_karar.signals import compute_signals

    weights = cfg.effective_weights()

    def compute(df):
        sig = compute_signals(df, cfg.signals, None, cfg.bar_seconds)
        sig["score"] = score_frame(sig, weights)
        return sig

    ok = True
    for inst in cfg.instruments:
        df = load_candles(None, inst, cfg.bar, pd.Timestamp("2021-02-01", tz="UTC"), None, base / "data", offline=True)
        t = truncation_audit(df, compute)
        ok &= not t["has_bias"]
        worst = max(v for v in t["max_diff"].values() if v == v) if any(v == v for v in t["max_diff"].values()) else 0.0
        print(f"{inst}: kesme testi {'GEÇTİ' if not t['has_bias'] else 'KALDI ' + ', '.join(t['biased_columns'])}"
              f" ({t['checked_bars']} bar, en büyük fark {worst:.2e})")
        rec = recursion_audit(df, compute, lengths=tuple(int(x) for x in args.lengths.split(",")))
        cols = ["donchian", "trend", "atr", "ann_vol", "score"]
        print(f"  son satırın geçmiş uzunluğuna bağımlılığı (mutlak fark; atr/ann_vol bağıl):")
        print("  " + f"{'son N bar':>10}" + "".join(f"{c:>12}" for c in cols))
        for n, row in rec.items():
            print("  " + f"{n:>10}" + "".join(f"{row[c]:>12.2e}" for c in cols))
    print("\nSONUÇ:", "geleceğe bakma bulunmadı" if ok else "GELECEĞE BAKMA TESPİT EDİLDİ")
    return 0 if ok else 1


def cmd_dca(cfg, args, base: Path) -> int:
    """E6: düz DCA ve BTC 200g rejim eğimi (Protokol Ek 2). Dönemler protokolden, test bölgesi korumalı."""
    from okx_karar.dca import VARIANTS, simulate_dca

    protocol = tomllib.loads((base / "experiments" / "protocol.toml").read_text(encoding="utf-8"))
    periods = [x.strip() for x in args.periods.split(",")]
    test_start = pd.Timestamp(protocol["guard"]["test_start"], tz="UTC")
    zone = {n: pd.Timestamp(protocol["periods"][n][1], tz="UTC") > test_start for n in periods}
    if any(zone.values()) and not args.allow_test:
        raise SystemExit("Test bölgesine düşen dönem(ler): " + ", ".join(n for n, z in zone.items() if z)
                         + ". --allow-test gerekir (bkz. experiments/PROTOCOL.md).")
    context = pd.Timedelta(days=protocol["context_days"])
    print(f"{'dönem':<12}{'varyant':<9}{'yatırılan':>10}{'bitiş':>10}{'getiri':>9}{'IRR':>8}{'maxDD':>8}{'alım':>6}{'atlanan':>8}")
    out_dir = base / "results" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in periods:
        start, end = (pd.Timestamp(x, tz="UTC") for x in protocol["periods"][name])
        data = {i: load_candles(None, i, "1Dutc", start - context, end, base / "data", offline=True) for i in cfg.instruments}
        for v in VARIANTS:
            r = simulate_dca(data, v, cfg.costs, start, end)
            print(f"{name:<12}{v:<9}{r.invested:>10.0f}{r.final_value:>10.0f}{100 * r.return_on_invested:>8.1f}%"
                  f"{100 * r.irr:>7.1f}%{100 * r.max_drawdown:>7.1f}%{r.buys:>6}{r.skipped:>8}")
            record = {"period": name, "variant": v, "invested": r.invested, "final_value": r.final_value,
                      "return_on_invested": r.return_on_invested, "irr": r.irr, "max_drawdown": r.max_drawdown,
                      "buys": r.buys, "skipped": r.skipped, "avg_cost": r.avg_cost,
                      "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            (out_dir / f"dca_{v}_{name}.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
            if zone[name]:
                with (base / "experiments" / "test_log.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"kind": "dca", **record}, default=str) + "\n")
    return 0


def cmd_notify(_cfg, args, base: Path) -> int:
    """Telegram/macOS/konsol bildirimi: sinyal durumu değiştiğinde (ve haftalık) haber verir; emir vermez."""
    from okx_karar.advisory import assess, required_bars
    from okx_karar.notifier import NotifyError, build_senders, find_chat_ids, format_message

    load_env(base / ".env")
    if args.get_chat_id:
        ids = find_chat_ids(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        if not ids:
            print("Henüz mesaj yok. Telegram'da botunuza /start yazıp bu komutu tekrar çalıştırın.")
        for cid, name in ids:
            print(f"TELEGRAM_CHAT_ID={cid}   ({name})")
        return 0
    channels = ["console"] if args.dry_run else [c.strip() for c in args.channels.split(",") if c.strip()]
    try:
        senders = build_senders(channels)
    except NotifyError as exc:
        raise SystemExit(str(exc))
    if args.test:
        for sd in senders:
            sd.send("✅ crypto-analysis bağlantı testi: bildirimler çalışıyor. (Bilgi amaçlıdır, emir vermez.)")
        return 0

    client = OKXClient()
    now = pd.Timestamp.now(tz="UTC")
    state_dir = base / "state"
    state_dir.mkdir(exist_ok=True)
    meta_path = state_dir / "notify_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    failures = 0

    def send_all(text: str) -> None:
        for sd in senders:
            sd.send(text)

    for cfg_path in (c.strip() for c in args.configs.split(",")):
        cfg = load_config(base / cfg_path)
        label = Path(cfg_path).stem
        state_path = state_dir / f"notify_{label}.json"
        state = None if args.force_snapshot or not state_path.exists() else json.loads(state_path.read_text())
        try:
            start = now - pd.Timedelta(seconds=required_bars(cfg) * cfg.bar_seconds)
            frames = {i: load_candles(client, i, cfg.bar, start, None, base / "data") for i in cfg.instruments}
            if state and all(frames[i].index[-1] <= pd.Timestamp(state["last_bar"].get(i, "1970-01-01T00:00:00+00:00"))
                             for i in cfg.instruments):
                print(f"[{label}] yeni kapanmış bar yok")
                continue
            a, new_state = assess(cfg, frames, state, label)
            weekly = (a.as_of.weekday() == 0 and new_state.get("last_weekly") != a.as_of.date().isoformat()
                      and not a.snapshot)
            if a.events or a.snapshot or weekly:
                send_all(format_message(a, label.split("_")[0].upper(), weekly=weekly))
            else:
                print(f"[{label}] olay yok, mesaj gönderilmedi")
            if weekly:
                new_state["last_weekly"] = a.as_of.date().isoformat()
            if not args.dry_run:
                state_path.write_text(json.dumps(new_state, indent=2), encoding="utf-8")
        except Exception as exc:  # tek yapılandırmanın hatası diğerlerini durdurmasın
            failures += 1
            print(f"[{label}] HATA: {type(exc).__name__}: {exc}")
            today = now.date().isoformat()
            if not args.dry_run and meta.get("last_error_notice") != today:
                try:
                    send_all(f"⚠️ crypto-analysis ({label}) hata verdi: {type(exc).__name__}. Ayrıntı günlükte.")
                    meta["last_error_notice"] = today
                except Exception:
                    pass
    if not args.dry_run:
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return 1 if failures else 0


def cmd_collect(_cfg, args, base: Path) -> int:
    """Kendi veri toplayıcımız: bir anlık görüntü alıp data/collector.db'ye yazar (launchd 5 dakikada bir çağırır)."""
    from okx_karar.collector import collect_once, connect, summary

    conn = connect(base / "data" / "collector.db")
    if args.summary:
        for table, v in summary(conn).items():
            span = ""
            if v["rows"]:
                a, b = (pd.to_datetime(v[k], unit="ms", utc=True).strftime("%Y-%m-%d %H:%M") for k in ("first_ms", "last_ms"))
                span = f"  {a} → {b} UTC"
            print(f"{table:<8}{v['rows']:>9} satır{span}")
        return 0
    result = collect_once(OKXClient(), conn, ratio_period=args.ratio_period)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{stamp}] +{result['rows']} satır" + (f"; hata: {', '.join(result['errors'])}" if result["errors"] else ""))
    return 1 if len(result["errors"]) >= 6 else 0


def cmd_events(_cfg, args, base: Path) -> int:
    """R01 olay sayımı (yalnızca sayım; fiyat/getiri yok). Plan: experiments/registry/R01_count_plan.md"""
    from okx_karar.binance_funding import interval_audit, load_funding
    from okx_karar.events import count_variants, render_markdown

    if args.candidate != "R01":
        raise SystemExit("Şimdilik yalnızca R01 destekleniyor.")
    protocol = tomllib.loads((base / "experiments" / "protocol.toml").read_text(encoding="utf-8"))
    periods = {n: tuple(pd.Timestamp(x, tz="UTC") for x in protocol["periods"][n]) for n in ("dev", "validation")}
    symbols = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
    start, end = pd.Timestamp("2021-09-01", tz="UTC"), periods["validation"][1]
    funding, coverage = {}, {}
    for coin, symbol in symbols.items():
        funding[coin] = load_funding(symbol, start, end, base / "data")
        coverage[coin] = interval_audit(funding[coin])
        a = coverage[coin]
        print(f"{coin}: {a['rows']} settlement, {a['first']:%Y-%m-%d} → {a['last']:%Y-%m-%d}, düzensiz adım: {len(a['irregular'])}")
    rows = count_variants(funding, periods)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out_dir = base / "experiments" / "registry"
    (out_dir / "R01_counts.md").write_text(render_markdown(rows, coverage, stamp), encoding="utf-8")
    (out_dir / "R01_counts.json").write_text(json.dumps({"generated_at": stamp, "rows": rows}, indent=2, default=str), encoding="utf-8")
    print(f"\n{'varyant':<28}{'dev':>5}{'val':>5}  karar")
    for r in rows:
        print(f"{r['variant']:<28}{r['n_dev']:>5}{r['n_validation']:>5}  {r['verdict']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="okx_karar", description="OKX kurallı karar sistemi")
    parser.add_argument("--config", default=None, help="yapılandırma dosyası (varsayılan: proje içindeki config.toml)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("fetch", "backtest"):
        p = sub.add_parser(name)
        p.add_argument("--days", type=int, default=365, help="kaç günlük veri (varsayılan 365)")
        p.add_argument("--start", help="başlangıç tarihi, ör. 2025-01-01 (UTC)")
        p.add_argument("--end", help="bitiş tarihi (hariç), ör. 2026-01-01 (UTC)")
        if name == "backtest":
            p.add_argument("--offline", action="store_true", help="yalnızca önbellekteki veriyi kullan")

    p = sub.add_parser("paper")
    p.add_argument("--executor", choices=("sim", "demo"), default="sim")
    p.add_argument("--once", action="store_true", help="tek tur çalış ve çık")

    p = sub.add_parser("compare")
    p.add_argument("--years", default="2022,2023,2024,2025", help="virgülle ayrılmış yıllar")

    p = sub.add_parser("evaluate")
    p.add_argument("--configs", required=True, help="virgülle ayrılmış yapılandırma yolları (proje köküne göre)")
    p.add_argument("--periods", default="dev,validation", help="protocol.toml'daki dönem adları")
    p.add_argument("--allow-test", action="store_true", help="test dönemini aç (yalnızca son adımda)")

    p = sub.add_parser("audit")
    p.add_argument("--lengths", default="150,300,600,1200", help="özyineleme testinde kullanılacak son-N bar değerleri")

    p = sub.add_parser("dca")
    p.add_argument("--periods", default="dev,validation", help="protocol.toml'daki dönem adları")
    p.add_argument("--allow-test", action="store_true", help="test bölgesini aç (kayıt altına alınır)")

    p = sub.add_parser("notify")
    p.add_argument("--configs", default="experiments/e3_regime.toml,experiments/e5_fast4h.toml",
                   help="virgülle ayrılmış yapılandırmalar")
    p.add_argument("--channels", default="telegram", help="telegram,macos,console")
    p.add_argument("--dry-run", action="store_true", help="yalnızca konsola yaz, durumu kaydetme")
    p.add_argument("--test", action="store_true", help="kanallara bağlantı testi mesajı gönder")
    p.add_argument("--get-chat-id", action="store_true", help="bota /start yazdıktan sonra sohbet kimliğini göster")
    p.add_argument("--force-snapshot", action="store_true", help="durumu sıfırdan kur ve özet gönder")

    p = sub.add_parser("collect")
    p.add_argument("--summary", action="store_true", help="birikmiş verinin özetini göster")
    p.add_argument("--ratio-period", default="1H", help="rubik istatistik periyodu (5m, 1H, 1D)")

    p = sub.add_parser("events")
    p.add_argument("--candidate", default="R01", help="registry adayı (şimdilik yalnızca R01)")

    p = sub.add_parser("status")
    p.add_argument("--executor", choices=("sim", "demo"), default="sim")

    args = parser.parse_args(argv)
    base = Path(__file__).resolve().parent.parent
    cfg = load_config(args.config or base / "config.toml")
    handlers = {"fetch": cmd_fetch, "backtest": cmd_backtest, "paper": cmd_paper, "status": cmd_status,
                "compare": cmd_compare, "evaluate": cmd_evaluate, "audit": cmd_audit, "dca": cmd_dca, "notify": cmd_notify, "collect": cmd_collect, "events": cmd_events}
    return handlers[args.cmd](cfg, args, base)
