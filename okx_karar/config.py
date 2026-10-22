"""config.toml dosyasını okur, doğrular ve değişmez (frozen) yapılandırma nesnesi üretir."""
from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

BAR_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1H": 3600, "2H": 7200, "4H": 14400, "6H": 21600, "12H": 43200, "1D": 86400, "1Dutc": 86400,
}


@dataclass(frozen=True)
class SignalParams:
    ema_fast: int = 20
    ema_slow: int = 50
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    rsi_period: int = 14
    atr_period: int = 14
    volume_window: int = 20
    donchian_lookbacks: tuple = (20, 50, 100)


@dataclass(frozen=True)
class Weights:
    trend: float = 0.35
    macd: float = 0.25
    rsi: float = 0.20
    volume: float = 0.20
    funding: float = 0.0
    donchian: float = 0.0


@dataclass(frozen=True)
class DecisionCfg:
    enter_threshold: float = 0.30
    exit_threshold: float = -0.10
    confirm_bars: int = 1          # giriş için skorun üst üste kaç barda eşiği aşması gerektiği
    confirm_volume: float = 0.0    # giriş penceresinde hacim/ortalama hacim en az bu kadar olmalı (0 = kapalı)


@dataclass(frozen=True)
class RiskCfg:
    risk_per_trade: float = 0.01
    stop_atr_multiple: float = 2.0
    max_position_fraction: float = 0.30
    max_drawdown: float = 0.20
    max_atr_pct: float = 0.05
    use_stop: bool = True          # False: stop emri yok, çıkış yalnızca sinyalle
    sizing: str = "atr_stop"       # "atr_stop" | "vol_target"
    target_vol: float = 0.20       # vol_target: enstrüman başına hedef yıllık volatilite
    vol_window: int = 20


@dataclass(frozen=True)
class CostCfg:
    fee_rate: float = 0.001
    slippage: float = 0.0005


@dataclass(frozen=True)
class FuturesCfg:
    enabled: bool = False
    leverage: float = 2
    margin_mode: str = "isolated"
    allow_short: bool = True
    fee_rate: float = 0.0005


@dataclass(frozen=True)
class RegimeCfg:
    enabled: bool = False          # True: referans enstrüman SMA'nın altındayken yeni long girişi yok
    reference: str = "BTC-USDT"
    sma_bars: int = 200


@dataclass(frozen=True)
class Config:
    mode: str = "spot"
    instruments: tuple[str, ...] = ("BTC-USDT", "ETH-USDT", "SOL-USDT")
    bar: str = "1H"
    initial_equity: float = 10_000.0
    signals: SignalParams = field(default_factory=SignalParams)
    weights: Weights = field(default_factory=Weights)
    decision: DecisionCfg = field(default_factory=DecisionCfg)
    risk: RiskCfg = field(default_factory=RiskCfg)
    costs: CostCfg = field(default_factory=CostCfg)
    futures: FuturesCfg = field(default_factory=FuturesCfg)
    regime: RegimeCfg = field(default_factory=RegimeCfg)
    config_hash: str = "kod-içi"

    @property
    def is_swap(self) -> bool:
        return self.mode == "swap"

    @property
    def allow_short(self) -> bool:
        return self.is_swap and self.futures.allow_short

    @property
    def leverage(self) -> float:
        return float(self.futures.leverage) if self.is_swap else 1.0

    @property
    def bar_seconds(self) -> int:
        return BAR_SECONDS[self.bar]

    def effective_costs(self) -> CostCfg:
        if self.is_swap:
            return replace(self.costs, fee_rate=self.futures.fee_rate)
        return self.costs

    def effective_weights(self) -> Weights:
        # Spot piyasada funding yoktur; ağırlığı ne olursa olsun yok sayılır.
        if self.is_swap:
            return self.weights
        return replace(self.weights, funding=0.0)


def _build(cls, section: dict | None, name: str):
    section = section or {}
    known = {f.name for f in fields(cls)}
    unknown = set(section) - known
    if unknown:
        raise ValueError(f"[{name}] bölümünde bilinmeyen anahtar(lar): {', '.join(sorted(unknown))}")
    section = {k: (tuple(v) if isinstance(v, list) else v) for k, v in section.items()}
    return cls(**section)


def validate(cfg: Config) -> Config:
    if cfg.mode not in ("spot", "swap"):
        raise ValueError(f"market.mode 'spot' veya 'swap' olmalı, gelen: {cfg.mode!r}")
    if cfg.bar not in BAR_SECONDS:
        raise ValueError(f"market.bar desteklenmiyor: {cfg.bar!r}. Seçenekler: {', '.join(BAR_SECONDS)}")
    if not cfg.instruments:
        raise ValueError("market.instruments boş olamaz")
    quotes = {inst.split("-")[1] for inst in cfg.instruments}
    if len(quotes) != 1:
        raise ValueError(f"tüm enstrümanlar aynı karşı para birimini kullanmalı, gelen: {quotes}")
    if not cfg.decision.exit_threshold < cfg.decision.enter_threshold:
        raise ValueError("decision.exit_threshold, enter_threshold'dan küçük olmalı")
    if not 0 < cfg.risk.risk_per_trade < 1:
        raise ValueError("risk.risk_per_trade 0 ile 1 arasında olmalı")
    if not 0 < cfg.risk.max_position_fraction <= 1:
        raise ValueError("risk.max_position_fraction 0 ile 1 arasında olmalı")
    if not 0 < cfg.risk.max_drawdown < 1:
        raise ValueError("risk.max_drawdown 0 ile 1 arasında olmalı")
    if cfg.risk.sizing not in ("atr_stop", "vol_target"):
        raise ValueError("risk.sizing 'atr_stop' veya 'vol_target' olmalı")
    if cfg.decision.confirm_bars < 1:
        raise ValueError("decision.confirm_bars en az 1 olmalı")
    if cfg.regime.enabled and cfg.regime.reference not in cfg.instruments:
        raise ValueError("regime.reference, market.instruments içinde olmalı")
    if cfg.futures.margin_mode not in ("isolated", "cross"):
        raise ValueError("futures.margin_mode 'isolated' veya 'cross' olmalı")
    if cfg.is_swap:
        from okx_karar.futures import ensure_enabled

        ensure_enabled(cfg)
    return cfg


def load_config(path: str | Path) -> Config:
    path = Path(path)
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode("utf-8"))
    market = dict(data.get("market", {}))
    if "instruments" in market:
        market["instruments"] = tuple(market["instruments"])
    unknown_sections = set(data) - {"market", "signals", "weights", "decision", "risk", "costs", "futures", "regime"}
    if unknown_sections:
        raise ValueError(f"bilinmeyen bölüm(ler): {', '.join(sorted(unknown_sections))}")
    allowed_market = {"mode", "instruments", "bar", "initial_equity"}
    if set(market) - allowed_market:
        raise ValueError(f"[market] bölümünde bilinmeyen anahtar(lar): {', '.join(sorted(set(market) - allowed_market))}")
    cfg = Config(
        **market,
        signals=_build(SignalParams, data.get("signals"), "signals"),
        weights=_build(Weights, data.get("weights"), "weights"),
        decision=_build(DecisionCfg, data.get("decision"), "decision"),
        risk=_build(RiskCfg, data.get("risk"), "risk"),
        costs=_build(CostCfg, data.get("costs"), "costs"),
        futures=_build(FuturesCfg, data.get("futures"), "futures"),
        regime=_build(RegimeCfg, data.get("regime"), "regime"),
        config_hash=hashlib.sha256(raw).hexdigest()[:12],
    )
    return validate(cfg)

