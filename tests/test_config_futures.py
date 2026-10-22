from decimal import Decimal
from pathlib import Path

import pytest

from okx_karar.config import Config, load_config
from okx_karar.futures import FuturesDisabledError, OKXDemoSwapExecutor, swap_inst_id, to_contracts

ROOT = Path(__file__).resolve().parent.parent


def test_repo_config_loads_as_spot_with_futures_disabled():
    cfg = load_config(ROOT / "config.toml")
    assert cfg.mode == "spot" and not cfg.futures.enabled
    assert cfg.instruments == ("BTC-USDT", "ETH-USDT", "SOL-USDT")
    assert len(cfg.config_hash) == 12
    assert cfg.effective_weights().funding == 0.0 and not cfg.allow_short and cfg.leverage == 1.0


def _write(tmp_path, text):
    p = tmp_path / "c.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_config_rejects_typos_and_bad_thresholds(tmp_path):
    with pytest.raises(ValueError, match="bilinmeyen"):
        load_config(_write(tmp_path, "[risk]\nrisk_per_trd = 0.01\n"))
    with pytest.raises(ValueError, match="exit_threshold"):
        load_config(_write(tmp_path, "[decision]\nenter_threshold = 0.1\nexit_threshold = 0.2\n"))


def test_config_hash_changes_with_content(tmp_path):
    a = load_config(_write(tmp_path, "[decision]\nenter_threshold = 0.3\n")).config_hash
    b = load_config(_write(tmp_path, "[decision]\nenter_threshold = 0.31\n")).config_hash
    assert a != b


def test_swap_mode_blocked_while_futures_disabled(tmp_path):
    with pytest.raises(FuturesDisabledError):
        load_config(_write(tmp_path, '[market]\nmode = "swap"\n'))
    cfg = load_config(_write(tmp_path, '[market]\nmode = "swap"\n[futures]\nenabled = true\n'))
    assert cfg.allow_short and cfg.leverage == 2 and cfg.effective_costs().fee_rate == 0.0005


def test_swap_executor_refuses_when_disabled():
    with pytest.raises(FuturesDisabledError):
        OKXDemoSwapExecutor(client=None, cfg=Config())


def test_contract_conversion():
    assert swap_inst_id("BTC-USDT") == "BTC-USDT-SWAP"
    assert swap_inst_id("BTC-USDT-SWAP") == "BTC-USDT-SWAP"
    # 0.0537 BTC / 0.01 BTC = 5.37 kontrat → lot 0.01 → 5.37
    assert to_contracts(0.0537, "0.01", "0.01", "0.01") == Decimal("5.37")
    assert to_contracts(0.05379, "0.01", "0.1", "0.1") == Decimal("5.3")
    assert to_contracts(0.00001, "0.01", "0.01", "0.01") == 0
