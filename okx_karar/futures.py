"""Vadeli (USDT-margined perpetual swap) desteği — ŞİMDİLİK DEVRE DIŞI.

Kod hazır ve testli, ancak config.toml içinde `[futures] enabled = true` yapılmadan hiçbir
yerden çağrılamaz. Önce spot sonuçlarını değerlendirmeniz için böyle bırakıldı.

Swap modunda farklı olanlar:
  * short pozisyon açılabilir (allow_short)
  * kaldıraç pozisyon tavanını büyütür (max_position_fraction × leverage)
  * funding ödemeleri backtest'te nakitten düşülür / eklenir
  * funding oranı ayrı bir sinyal olarak oylamaya katılabilir (weights.funding)
"""
from __future__ import annotations

from decimal import Decimal

from okx_karar.executors import Fill, _now, floor_to_step


class FuturesDisabledError(RuntimeError):
    pass


def ensure_enabled(cfg) -> None:
    if not cfg.futures.enabled:
        raise FuturesDisabledError(
            "Vadeli modül devre dışı. Açmak için config.toml → [futures] enabled = true "
            "(önce spot sonuçlarını değerlendirin)."
        )


def swap_inst_id(inst: str) -> str:
    return inst if inst.endswith("-SWAP") else f"{inst}-SWAP"


def to_contracts(qty_base: float, ct_val: str, lot_sz: str, min_sz: str) -> Decimal:
    """Baz miktarı kontrat sayısına çevirir; lot adımına aşağı yuvarlar, minimumun altındaysa 0."""
    contracts = floor_to_step(float(Decimal(str(qty_base)) / Decimal(ct_val)), lot_sz)
    return contracts if contracts >= Decimal(min_sz) else Decimal(0)


class OKXDemoSwapExecutor:
    """OKX demo hesabında swap emirleri. Hesap 'net' pozisyon modunda olmalıdır."""

    def __init__(self, client, cfg):
        ensure_enabled(cfg)
        if not client.has_credentials:
            raise RuntimeError("Demo mod için .env dosyasına OKX demo API anahtarlarını girin.")
        self.client = client
        self.cfg = cfg
        self.quote = cfg.instruments[0].split("-")[1]
        pos_mode = client.get_account_config().get("posMode")
        if pos_mode != "net_mode":
            raise RuntimeError(f"Demo hesabın pozisyon modu 'net' olmalı (şu an: {pos_mode}).")
        self.meta = {inst: client.get_instrument("SWAP", swap_inst_id(inst)) for inst in cfg.instruments}
        for inst in cfg.instruments:
            client.set_leverage(swap_inst_id(inst), cfg.futures.leverage, cfg.futures.margin_mode)

    def positions(self) -> dict[str, float]:
        by_swap = {swap_inst_id(i): i for i in self.cfg.instruments}
        out: dict[str, float] = {}
        for row in self.client.get_positions("SWAP"):
            inst = by_swap.get(row.get("instId"))
            if inst and row.get("pos"):
                out[inst] = out.get(inst, 0.0) + float(row["pos"]) * float(self.meta[inst]["ctVal"])
        return out

    def equity(self, prices: dict[str, float]) -> float:
        details = self.client.get_balance([self.quote]).get("details", [])
        return sum(float(d.get("eq") or 0) for d in details if d.get("ccy") == self.quote)

    def trade(self, inst: str, delta: float, ref_price: float, cl_ord_id: str, reason: str) -> Fill | None:
        meta = self.meta[inst]
        contracts = to_contracts(abs(delta), meta["ctVal"], meta["lotSz"], meta["minSz"])
        if contracts <= 0:
            return None
        current = self.positions().get(inst, 0.0)
        reduce_only = current != 0 and (delta > 0) != (current > 0) and abs(delta) <= abs(current) * 1.0001
        side = "buy" if delta > 0 else "sell"
        swap_id = swap_inst_id(inst)
        result = self.client.place_order(
            swap_id, side, f"{contracts:f}", td_mode=self.cfg.futures.margin_mode, cl_ord_id=cl_ord_id,
            reduceOnly="true" if reduce_only else None,
        )
        order = self.client.wait_for_fill(swap_id, result["ordId"])
        filled = float(order.get("accFillSz") or 0) * float(meta["ctVal"])
        if filled <= 0:
            return None
        return Fill(_now(), inst, side, filled, float(order.get("avgPx") or ref_price),
                    abs(float(order.get("fee") or 0)), reason, cl_ord_id)
