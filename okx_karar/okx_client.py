"""OKX v5 REST istemcisi.

* Public uç noktalar (mumlar, enstrüman bilgisi, funding) anahtar gerektirmez.
* Özel uç noktalar (bakiye, emir) YALNIZCA demo trading modunda çalışır: her özel isteğe
  `x-simulated-trading: 1` başlığı eklenir. Canlı hesapla işlem bu sürümde kapalıdır;
  açmak bilinçli bir kod değişikliği gerektirir.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

BASE_URL = "https://www.okx.com"
RATE_LIMIT_CODES = {"50011", "50061"}


class OKXError(RuntimeError):
    def __init__(self, code: str, msg: str, path: str):
        super().__init__(f"OKX hatası {code} ({path}): {msg}")
        self.code = code
        self.msg = msg
        self.path = path


class LiveTradingDisabled(RuntimeError):
    pass


def sign(timestamp: str, method: str, request_path: str, body: str, secret: str) -> str:
    """OKX imzası: base64(HMAC-SHA256(secret, timestamp + METHOD + requestPath + body))."""
    message = f"{timestamp}{method.upper()}{request_path}{body}"
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_env(path: str | Path) -> None:
    """Basit .env okuyucu: KEY=VALUE satırlarını ortamda yoksa ekler."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class OKXClient:
    def __init__(
        self,
        api_key: str | None = None,
        secret: str | None = None,
        passphrase: str | None = None,
        demo: bool = True,
        session: requests.Session | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        if not demo:
            raise LiveTradingDisabled(
                "Canlı hesapla işlem bu sürümde kapalı. Yalnızca OKX demo trading desteklenir."
            )
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.demo = True
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries

    @classmethod
    def from_env(cls) -> "OKXClient":
        return cls(
            api_key=os.environ.get("OKX_API_KEY") or None,
            secret=os.environ.get("OKX_API_SECRET") or None,
            passphrase=os.environ.get("OKX_API_PASSPHRASE") or None,
        )

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.secret and self.passphrase)

    # ------------------------------------------------------------------ çekirdek
    def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None,
                 private: bool = False) -> list:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        request_path = path + (f"?{urlencode(params)}" if params else "")
        body_str = json.dumps(body, separators=(",", ":")) if body is not None else ""
        headers = {"Content-Type": "application/json"}
        if private:
            if not self.has_credentials:
                raise RuntimeError(
                    "Özel uç nokta için OKX demo API anahtarı gerekli (.env: OKX_API_KEY, "
                    "OKX_API_SECRET, OKX_API_PASSPHRASE)."
                )

        # Emir gibi POST istekleri tekrar denenmez: ağ hatasında emir iki kez gidebilir.
        attempts = self.max_retries if method == "GET" else 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            if private:
                ts = _timestamp()
                headers.update({
                    "OK-ACCESS-KEY": self.api_key,
                    "OK-ACCESS-SIGN": sign(ts, method, request_path, body_str, self.secret),
                    "OK-ACCESS-TIMESTAMP": ts,
                    "OK-ACCESS-PASSPHRASE": self.passphrase,
                    "x-simulated-trading": "1",
                })
            try:
                resp = self.session.request(
                    method, BASE_URL + request_path, data=body_str or None, headers=headers, timeout=self.timeout
                )
                payload = resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                time.sleep(0.5 * (2 ** attempt))
                continue
            code = str(payload.get("code", ""))
            if code == "0":
                return payload.get("data", [])
            if code in RATE_LIMIT_CODES and attempt + 1 < attempts:
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise OKXError(code, payload.get("msg", ""), path)
        raise RuntimeError(f"OKX isteği başarısız ({path}): {last_exc}")

    # ------------------------------------------------------------------ public
    def get_candles(self, inst_id: str, bar: str, limit: int = 300) -> list:
        """En yeni mumlar (en fazla 300). Satırlar yeniden eskiye sıralıdır."""
        return self._request("GET", "/api/v5/market/candles", {"instId": inst_id, "bar": bar, "limit": limit})

    def get_history_candles(self, inst_id: str, bar: str, after: int | None = None, limit: int = 100) -> list:
        """`after` zaman damgasından (ms) daha ESKİ mumlar (en fazla 100)."""
        return self._request(
            "GET", "/api/v5/market/history-candles",
            {"instId": inst_id, "bar": bar, "after": after, "limit": limit},
        )

    def get_instrument(self, inst_type: str, inst_id: str) -> dict:
        data = self._request("GET", "/api/v5/public/instruments", {"instType": inst_type, "instId": inst_id})
        if not data:
            raise OKXError("-", f"enstrüman bulunamadı: {inst_id}", "/api/v5/public/instruments")
        return data[0]

    def get_ticker(self, inst_id: str) -> dict:
        return self._request("GET", "/api/v5/market/ticker", {"instId": inst_id})[0]

    def get_funding_history(self, inst_id: str, after: int | None = None, limit: int = 100) -> list:
        return self._request(
            "GET", "/api/v5/public/funding-rate-history", {"instId": inst_id, "after": after, "limit": limit}
        )

    # ------------------------------------------------------------------ özel (demo)
    def get_balance(self, ccys: list[str] | None = None) -> dict:
        data = self._request("GET", "/api/v5/account/balance",
                             {"ccy": ",".join(ccys) if ccys else None}, private=True)
        return data[0] if data else {}

    def get_account_config(self) -> dict:
        return self._request("GET", "/api/v5/account/config", private=True)[0]

    def get_positions(self, inst_type: str = "SWAP") -> list:
        return self._request("GET", "/api/v5/account/positions", {"instType": inst_type}, private=True)

    def set_leverage(self, inst_id: str, lever: float, mgn_mode: str) -> list:
        return self._request("POST", "/api/v5/account/set-leverage",
                             body={"instId": inst_id, "lever": str(lever), "mgnMode": mgn_mode}, private=True)

    def place_order(self, inst_id: str, side: str, sz: str, td_mode: str, ord_type: str = "market",
                    cl_ord_id: str | None = None, **extra) -> dict:
        body = {"instId": inst_id, "tdMode": td_mode, "side": side, "ordType": ord_type, "sz": sz}
        if cl_ord_id:
            body["clOrdId"] = cl_ord_id
        body.update({k: v for k, v in extra.items() if v is not None})
        data = self._request("POST", "/api/v5/trade/order", body=body, private=True)
        result = data[0] if data else {}
        if str(result.get("sCode", "0")) != "0":
            raise OKXError(str(result.get("sCode")), result.get("sMsg", ""), "/api/v5/trade/order")
        return result

    def get_order(self, inst_id: str, ord_id: str) -> dict:
        return self._request("GET", "/api/v5/trade/order", {"instId": inst_id, "ordId": ord_id}, private=True)[0]

    def wait_for_fill(self, inst_id: str, ord_id: str, attempts: int = 10, delay: float = 0.5) -> dict:
        order: dict = {}
        for _ in range(attempts):
            order = self.get_order(inst_id, ord_id)
            if order.get("state") in ("filled", "canceled", "mmp_canceled"):
                return order
            time.sleep(delay)
        return order
