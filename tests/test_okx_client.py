import base64
import hashlib
import hmac
import json

import pytest
import requests

from okx_karar.okx_client import LiveTradingDisabled, OKXClient, OKXError, sign


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, data=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "data": data, "headers": dict(headers)})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)


OK = {"code": "0", "msg": "", "data": [{"ok": 1}]}


def _client(session):
    return OKXClient("key", "secret", "pass", session=session)


def test_live_trading_is_disabled():
    with pytest.raises(LiveTradingDisabled):
        OKXClient(demo=False)


def test_sign_matches_okx_formula():
    ts, path, body = "2020-12-08T09:08:57.715Z", "/api/v5/account/balance?ccy=BTC", ""
    expected = base64.b64encode(
        hmac.new(b"secret", f"{ts}GET{path}{body}".encode(), hashlib.sha256).digest()
    ).decode()
    assert sign(ts, "get", path, body, "secret") == expected


def test_private_request_is_signed_and_simulated(monkeypatch):
    session = FakeSession([{"code": "0", "data": [{"details": []}]}])
    monkeypatch.setattr("okx_karar.okx_client._timestamp", lambda: "2020-12-08T09:08:57.715Z")
    _client(session).get_balance(["BTC", "USDT"])
    call = session.calls[0]
    assert call["url"] == "https://www.okx.com/api/v5/account/balance?ccy=BTC%2CUSDT"
    h = call["headers"]
    assert h["x-simulated-trading"] == "1"
    assert h["OK-ACCESS-SIGN"] == sign("2020-12-08T09:08:57.715Z", "GET",
                                       "/api/v5/account/balance?ccy=BTC%2CUSDT", "", "secret")


def test_public_request_has_no_auth_headers():
    session = FakeSession([OK])
    OKXClient(session=session).get_candles("BTC-USDT", "1H", limit=5)
    assert "OK-ACCESS-KEY" not in session.calls[0]["headers"]
    assert session.calls[0]["url"].endswith("/api/v5/market/candles?instId=BTC-USDT&bar=1H&limit=5")


def test_private_request_without_credentials_fails():
    with pytest.raises(RuntimeError, match="API anahtarı"):
        OKXClient(session=FakeSession([])).get_balance()


def test_get_is_retried_but_order_post_is_not(monkeypatch):
    monkeypatch.setattr("okx_karar.okx_client.time.sleep", lambda s: None)
    session = FakeSession([requests.ConnectionError("x"), OK])
    assert OKXClient(session=session).get_ticker("BTC-USDT") == {"ok": 1}
    assert len(session.calls) == 2

    session = FakeSession([requests.ConnectionError("x"), OK])
    with pytest.raises(RuntimeError):
        _client(session).place_order("BTC-USDT", "buy", "0.01", "cash")
    assert len(session.calls) == 1  # emir asla tekrar gönderilmez


def test_errors_raise():
    with pytest.raises(OKXError) as exc:
        OKXClient(session=FakeSession([{"code": "51001", "msg": "yok", "data": []}])).get_ticker("X")
    assert exc.value.code == "51001"
    session = FakeSession([{"code": "0", "data": [{"sCode": "51008", "sMsg": "bakiye yetersiz"}]}])
    with pytest.raises(OKXError, match="bakiye yetersiz"):
        _client(session).place_order("BTC-USDT", "buy", "1", "cash", cl_ord_id="abc", tgtCcy="base_ccy")
    body = json.loads(session.calls[0]["data"])
    assert body == {"instId": "BTC-USDT", "tdMode": "cash", "side": "buy", "ordType": "market",
                    "sz": "1", "clOrdId": "abc", "tgtCcy": "base_ccy"}
