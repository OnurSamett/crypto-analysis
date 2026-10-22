"""Komut satırı:  python -m okx_karar <komut>

  fetch     geçmiş mumları indirip data/ altına önbelleğe alır
  backtest  kurallı stratejiyi al-tut ile karşılaştırır, results/ altına kaydeder
  paper     her mum kapanışında karar verir (--executor sim | demo)
  status    paper hesabın durumunu gösterir
  evaluate  önceden kaydedilmiş protokolle yapılandırmaları dönem dönem değerlendirir
  compare   yıl yıl: kurallı strateji vs grid vs al-tut (önbellekteki veriyle)
"""
from __future__ import annotations

import argparse
import csv
import json
import tomllib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from okx_karar.backtest import run_backtest
from okx_karar.config import load_config, paper_unsupported
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


def _paper_paths(base: Path, executor_name: str) -> tuple[Path, Path]:
    return base / "state" / f"paper_{executor_name}.json", base / "state" / f"trades_{executor_name}.csv"


def _make_executor(cfg, name: str, base: Path, client: OKXClient):
    if name == "sim":
        return SimExecutor(base / "state" / "sim_account.json", cfg.initial_equity,
                           cfg.effective_costs(), allow_short=cfg.allow_short)
    if cfg.is_swap:
        from okx_karar.futures import OKXDemoSwapExecutor

        return OKXDemoSwapExecutor(client, cfg)
    return OKXDemoSpotExecutor(client, cfg)


def _refuse_research_features(cfg) -> None:
    extra = paper_unsupported(cfg)
    if extra:
        raise SystemExit("Bu yapılandırma yalnızca araştırma backtest'inde desteklenen özellikler içeriyor: "
                         + ", ".join(extra) + ". Paper/demo'da henüz yok (backtest ile farklı davranırdı).")


def cmd_paper(cfg, args, base: Path) -> int:
    _refuse_research_features(cfg)
    load_env(base / ".env")
    client = OKXClient.from_env()
    executor = _make_executor(cfg, args.executor, base, client)
    state_path, trade_log = _paper_paths(base, args.executor)

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
    _refuse_research_features(cfg)
    load_env(base / ".env")
    client = OKXClient.from_env()
    executor = _make_executor(cfg, args.executor, base, client)
    state_path, trade_log = _paper_paths(base, args.executor)
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
    if "test" in periods and not args.allow_test:
        raise SystemExit("test dönemi yalnızca son adımda, --allow-test ile ve bir kez çalıştırılmalı "
                         "(bkz. experiments/PROTOCOL.md).")
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
            if name == "test":
                with (base / "experiments" / "test_log.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
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

    p = sub.add_parser("status")
    p.add_argument("--executor", choices=("sim", "demo"), default="sim")

    args = parser.parse_args(argv)
    base = Path(__file__).resolve().parent.parent
    cfg = load_config(args.config or base / "config.toml")
    handlers = {"fetch": cmd_fetch, "backtest": cmd_backtest, "paper": cmd_paper, "status": cmd_status,
                "compare": cmd_compare, "evaluate": cmd_evaluate}
    return handlers[args.cmd](cfg, args, base)
