"""Backtest özetini okunur metne çevirir."""
from __future__ import annotations

import math


def _pct(x: float) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"%{100 * x:+.2f}"


def format_summary(s: dict, instruments, mode: str) -> str:
    st, bh, tr = s["strateji"], s["al_tut"], s["islemler"]
    lines = [
        f"Dönem         : {s['baslangic'][:16]} → {s['bitis'][:16]}  ({mode}, {', '.join(instruments)})",
        f"config_hash   : {s['config_hash']}",
        "",
        f"{'':22}{'Strateji':>12}{'Al-tut':>12}",
        f"{'Toplam getiri':22}{_pct(st['toplam_getiri']):>12}{_pct(bh['toplam_getiri']):>12}",
        f"{'Yıllık getiri':22}{_pct(st['yillik_getiri']):>12}{_pct(bh['yillik_getiri']):>12}",
        f"{'Sharpe':22}{st['sharpe']:>12.2f}{bh['sharpe']:>12.2f}",
        f"{'Max drawdown':22}{_pct(st['max_drawdown']):>12}{_pct(bh['max_drawdown']):>12}",
        "",
        f"İşlem sayısı  : {tr['islem_sayisi']}  (stop ile kapanan: {tr['stop_ile_kapanan']})",
        f"Kazanma oranı : {_pct(tr['kazanma_orani'])}",
        f"Ort. maruziyet: {_pct(s['ortalama_maruziyet'])} (sermayenin piyasada olan kısmı)",
        f"Komisyon      : {s['odenen_komisyon']:.2f} USDT   Veto: {s['veto_sayisi']}",
    ]
    if s["odenen_funding"]:
        lines.append(f"Funding       : {s['odenen_funding']:.2f} USDT")
    if s["kill_switch"]:
        lines.append(f"KILL SWITCH   : {s['kill_switch']} tarihinde tetiklendi, işlem durdu")
    lines += ["", "Karar başına ileri getiri (karar yönüyle işaretli):",
              f"{'':10}{'giriş ort.':>12}{'isabet':>9}{'çıkış ort.':>12}{'isabet':>9}"]
    for h, v in s["ileri_getiri"].items():
        g, c = v["giris"], v["cikis"]
        lines.append(f"{h:>3} mum   {_pct(g['ortalama']):>12}{_pct(g['isabet']):>9}"
                     f"{_pct(c['ortalama']):>12}{_pct(c['isabet']):>9}")
    return "\n".join(lines)
