"""Trader katmanının yürütücüleri.

* SimExecutor: tamamen yerel paper trading defteri (anahtar gerekmez).
* OKXDemoSpotExecutor: OKX demo trading hesabında spot piyasa emri (demo API anahtarı gerekir).

Ortak arayüz:
    positions() -> {enstrüman: işaretli baz miktar}
    equity(prices) -> karşı para birimi cinsinden toplam sermaye
    trade(inst, delta, ref_price, cl_ord_id, reason) -> Fill | None
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from okx_karar.config import Config, CostCfg

MIN_NOTIONAL = 5.0  # bu değerin altındaki bakiye "toz" sayılır, pozisyon kabul edilmez


@dataclass
class Fill:
    ts: str
    inst: str
    side: str
    qty: float
    price: float
    fee: float
    reason: str
    cl_ord_id: str


def floor_to_step(value: float, step: str) -> Decimal:
    step_d = Decimal(step)
    return (Decimal(str(value)) / step_d).to_integral_value(rounding=ROUND_DOWN) * step_d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SimExecutor:
    """Yerel defter: backtest ile aynı maliyet modeli (komisyon + kayma)."""

    def __init__(self, state_path: str | Path, initial_cash: float, costs: CostCfg, allow_short: bool = False):
        self.path = Path(state_path)
        self.costs = costs
        self.allow_short = allow_short
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.state = {"cash": float(initial_cash), "positions": {}}
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    @property
    def cash(self) -> float:
        return float(self.state["cash"])

    def positions(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.state["positions"].items()}

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(q * prices[i] for i, q in self.positions().items() if q)

    def trade(self, inst: str, delta: float, ref_price: float, cl_ord_id: str, reason: str) -> Fill | None:
        fee_rate, slip = self.costs.fee_rate, self.costs.slippage
        price = ref_price * (1 + slip) if delta > 0 else ref_price * (1 - slip)
        current = self.positions().get(inst, 0.0)
        if delta > 0 and not self.allow_short:
            delta = min(delta, self.cash / (price * (1 + fee_rate)))
        if delta < 0 and not self.allow_short:
            delta = max(delta, -current)
        if abs(delta) * price < 1e-9:
            return None
        fee = abs(delta) * price * fee_rate
        self.state["cash"] = self.cash - delta * price - fee
        new_qty = current + delta
        if abs(new_qty) < 1e-12:
            self.state["positions"].pop(inst, None)
        else:
            self.state["positions"][inst] = new_qty
        self._save()
        return Fill(_now(), inst, "buy" if delta > 0 else "sell", abs(delta), price, fee, reason, cl_ord_id)


class OKXDemoSpotExecutor:
    """OKX demo trading hesabında spot piyasa emirleri (tdMode=cash, miktar baz para biriminde)."""

    def __init__(self, client, cfg: Config):
        if not client.has_credentials:
            raise RuntimeError("Demo mod için .env dosyasına OKX demo API anahtarlarını girin.")
        self.client = client
        self.cfg = cfg
        self.quote = cfg.instruments[0].split("-")[1]
        self.base = {inst: inst.split("-")[0] for inst in cfg.instruments}
        self.meta = {inst: client.get_instrument("SPOT", inst) for inst in cfg.instruments}

    def _balances(self) -> dict[str, float]:
        ccys = [self.quote, *self.base.values()]
        details = self.client.get_balance(ccys).get("details", [])
        return {d["ccy"]: float(d.get("availBal") or 0) for d in details}

    def positions(self) -> dict[str, float]:
        bal = self._balances()
        return {inst: bal.get(base, 0.0) for inst, base in self.base.items() if bal.get(base, 0.0) > 0}

    def equity(self, prices: dict[str, float]) -> float:
        bal = self._balances()
        return bal.get(self.quote, 0.0) + sum(bal.get(b, 0.0) * prices[i] for i, b in self.base.items())

    def trade(self, inst: str, delta: float, ref_price: float, cl_ord_id: str, reason: str) -> Fill | None:
        meta = self.meta[inst]
        qty = abs(delta)
        bal = self._balances()
        if delta > 0:
            # Komisyon ve kayma payı bırakarak kullanılabilir USDT ile sınırla.
            qty = min(qty, bal.get(self.quote, 0.0) / (ref_price * 1.005))
        else:
            qty = min(qty, bal.get(self.base[inst], 0.0))
        sz = floor_to_step(qty, meta["lotSz"])
        if sz <= 0 or sz < Decimal(meta["minSz"]):
            return None
        side = "buy" if delta > 0 else "sell"
        result = self.client.place_order(inst, side, f"{sz:f}", td_mode="cash", cl_ord_id=cl_ord_id, tgtCcy="base_ccy")
        order = self.client.wait_for_fill(inst, result["ordId"])
        filled = float(order.get("accFillSz") or 0)
        if filled <= 0:
            return None
        price = float(order.get("avgPx") or ref_price)
        fee = abs(float(order.get("fee") or 0))
        if order.get("feeCcy") == self.base[inst]:
            fee *= price  # alışta komisyon baz paradan kesilir; karşı paraya çevir
        return Fill(_now(), inst, side, filled, price, fee, reason, cl_ord_id)


def fill_to_row(fill: Fill) -> dict:
    return asdict(fill)
