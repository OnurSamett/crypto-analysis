"""Bildirim gönderimi (Telegram, macOS, konsol) ve mesaj biçimi. Hiçbir kanal emir vermez."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime

import pandas as pd
import requests

from okx_karar.advisory import Assessment, CoinView

DISCLAIMER = "Bilgi amaçlıdır, yatırım tavsiyesi değildir. Bot emir vermez; karar sizindir."
BAR_TEXT = {"1Dutc": "günlük", "1D": "günlük", "4H": "4 saatlik", "1H": "saatlik"}
KIND_TEXT = {"ENTRY": "🟢 GİRİŞ SİNYALİ", "EXIT": "🔴 ÇIKIŞ SİNYALİ", "BLOCKED": "🟡 Giriş sinyali filtreye takıldı"}


class NotifyError(RuntimeError):
    pass


def _price(x: float) -> str:
    if x >= 1000:
        return f"{x:,.0f}".replace(",", ".")
    if x >= 10:
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{x:.4f}".replace(".", ",")


def _when(ts: pd.Timestamp) -> str:
    return ts.strftime("%d.%m.%Y %H:%M UTC")


def _days(since, now) -> str:
    if since is None:
        return ""
    d = (now - since).days
    return f" ({d} gündür)" if d >= 1 else ""


def _span(k: int, bar_seconds: int) -> str:
    days = k * bar_seconds / 86400
    return f"{days:g} günlük"


def exit_levels(v: CoinView) -> tuple[float, float] | None:
    """(ilk uyarı, çıkış sinyali) seviyeleri. Pencere k, kapanış alt kanalın (k barlık dip) altına inince short'a döner;
    çıkış için long pencerelerin n_long−1 tanesinin dönmesi gerekir → çıkış seviyesi, long pencerelerin
    alt kanalları içinde (n_long−1). en yüksek olanıdır."""
    longs = sorted((v.lower[k] for k, w in zip(v.windows, v.wstates) if w > 0), reverse=True)
    if not longs:
        return None
    need = max(len(longs) - 1, 1)
    return longs[0], longs[min(need, len(longs)) - 1]


def entry_level(v: CoinView) -> float | None:
    """Girişin ön koşulu: en az iki pencere long. Kısa pencerelerin üst kanalları içinde, eksik sayıyı tamamlayan seviye."""
    shorts = sorted(v.upper[k] for k, w in zip(v.windows, v.wstates) if w <= 0)
    need = max(2 - v.n_long, 0)
    return shorts[need - 1] if 0 < need <= len(shorts) else None


def _levels(v: CoinView, bar_seconds: int) -> list[str]:
    """'Nerede satmalıyım / nerede girmeliyim': tek net seviye + ilk uyarı. Hepsi bir sonraki KAPANIŞ içindir."""
    if v.side == 1:
        lv = exit_levels(v)
        if lv is None:
            return []
        first, exit_ = lv
        if abs(first - exit_) < 1e-12:
            return [f"Çıkış sinyali: kapanış {_price(exit_)} altına inerse"]
        return [f"İlk uyarı: kapanış {_price(first)} altına inerse (bir pencere short'a döner)",
                f"Çıkış sinyali: kapanış {_price(exit_)} altına inerse"]
    lvl = entry_level(v)
    if lvl is None:
        return []
    return [f"Giriş koşulu: kapanış {_price(lvl)} üstüne çıkmalı" + ("" if v.regime_ok else " (ama rejim olumsuz, giriş yok)")]


def format_view(v: CoinView, now: pd.Timestamp, bar_seconds: int = 86400) -> str:
    icon = "🟢" if v.side == 1 else "⚪"
    state = "AKTİF" if v.side == 1 else "nakit"
    head = f"{icon} {v.inst}: {state}{_days(v.since, now) if v.side == 1 else ''} · fiyat {_price(v.price)} · skor {v.score:+.2f}"
    lines = [head]
    if v.side == 1 and v.weight_pct is not None:
        lines.append(f"   önerilen pay: sinyal kovasının ~%{v.weight_pct:.0f}'i")
    lines += ["   " + x for x in _levels(v, bar_seconds)]
    return "\n".join(lines)


def format_message(a: Assessment, title: str, weekly: bool = False) -> str:
    bar = BAR_TEXT.get(a.bar, a.bar)
    out = [f"📊 {title} · {bar} · {_when(a.as_of)}"]
    if a.regime_ok is not None:
        r = "ÜSTÜNDE ✅" if a.regime_ok else "ALTINDA ⛔"
        out.append(f"Rejim: BTC 200 gün ortalamanın {r}{_days(a.regime_since, a.as_of)}")
    if a.snapshot:
        out.append("ℹ️ Başlangıç özeti: mevcut durum geçmişten yeniden kuruldu; eski kırılımlar yeni giriş sayılmaz.")
    if weekly and not a.snapshot and not a.events:
        out.append("🗓 Haftalık özet (olay yok)")
    for e in a.events:
        if e.inst == "REGIME":
            out.append("\n" + ("🌤 Rejim OLUMLUYA döndü: yeni girişler yeniden açıldı"
                               if e.kind == "REGIME_ON" else "🌧 Rejim OLUMSUZA döndü: yeni giriş yok, mevcut sinyaller etkilenmez"))
        else:
            out.append(f"\n{KIND_TEXT.get(e.kind, e.kind)} — {e.inst} ({_when(e.ts)}; {e.detail})")
    out.append("")
    bar_seconds = {"1Dutc": 86400, "1D": 86400, "4H": 14400, "1H": 3600}.get(a.bar, 86400)
    out += [format_view(v, a.as_of, bar_seconds) for v in a.views]
    out += ["", DISCLAIMER]
    return "\n".join(out)


def _split(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit and cur:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    return chunks + [cur] if cur else chunks


class ConsoleSender:
    name = "console"

    def send(self, text: str) -> None:
        print(text, flush=True)


class MacSender:
    """Kısa özetle macOS bildirimi (bilgisayar başındayken). Uzun metin Telegram'a bırakılır."""
    name = "macos"

    def send(self, text: str) -> None:
        first = text.split("\n", 1)[0].replace('"', "'")[:200]
        subprocess.run(["osascript", "-e", f'display notification "{first}" with title "crypto-analysis"'],
                       check=False, capture_output=True, timeout=10)


class TelegramSender:
    name = "telegram"

    def __init__(self, token: str, chat_id: str, session: requests.Session | None = None):
        if not token or not chat_id:
            raise NotifyError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env dosyasında tanımlı olmalı.")
        self._token, self._chat_id = token, str(chat_id)
        self.session = session or requests.Session()

    def _call(self, method: str, **kw) -> dict:
        try:  # istisna mesajı URL'yi (dolayısıyla token'ı) içerir; yutup temiz hata veriyoruz
            resp = self.session.post(f"https://api.telegram.org/bot{self._token}/{method}", json=kw, timeout=20)
            data = resp.json()
        except (requests.RequestException, ValueError):
            raise NotifyError(f"Telegram {method} çağrısı ağ/yanıt hatası verdi") from None
        if not data.get("ok"):
            raise NotifyError(f"Telegram hatası: {data.get('description', 'bilinmiyor')}")
        return data

    def send(self, text: str) -> None:
        for chunk in _split(text):
            self._call("sendMessage", chat_id=self._chat_id, text=chunk, disable_web_page_preview=True)


def find_chat_ids(token: str, session: requests.Session | None = None) -> list[tuple[str, str]]:
    """Bota yazdıktan sonra sohbet kimliğini bulur (getUpdates)."""
    s = session or requests.Session()
    try:
        data = s.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
    except (requests.RequestException, ValueError):
        raise NotifyError("Telegram getUpdates ağ/yanıt hatası verdi") from None
    if not data.get("ok"):
        raise NotifyError(f"Telegram hatası: {data.get('description', 'bilinmiyor')}")
    seen = {}
    for u in data.get("result", []):
        chat = (u.get("message") or u.get("channel_post") or {}).get("chat")
        if chat:
            seen[str(chat["id"])] = chat.get("username") or chat.get("first_name") or chat.get("title") or ""
    return list(seen.items())


def build_senders(names: list[str]) -> list:
    out = []
    for n in names:
        if n == "console":
            out.append(ConsoleSender())
        elif n == "macos":
            out.append(MacSender())
        elif n == "telegram":
            out.append(TelegramSender(os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")))
        else:
            raise NotifyError(f"bilinmeyen kanal: {n}")
    return out
