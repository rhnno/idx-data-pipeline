import pytest
from pipeline.config import load_sources_config, load_quality_rules, ConfigError


def test_sources_config_loads():
    cfg = load_sources_config("config/sources.yaml")
    assert len(cfg.tickers) == 5
    assert cfg.merge_strategy == "per_date_gap_fill"
    assert cfg.date_start == "2002-01-01"


def test_only_yahoo_is_enabled():
    cfg = load_sources_config("config/sources.yaml")
    enabled_names = [s.name for s in cfg.enabled_sources()]
    assert enabled_names == ["yahoo"]


def test_disabled_sources_carry_a_reason():
    cfg = load_sources_config("config/sources.yaml")
    disabled = [s for s in cfg.sources if not s.enabled]
    assert len(disabled) == 2
    for s in disabled:
        assert s.disabled_reason, f"{s.name} is disabled but has no disabled_reason"


def test_tickers_have_local_code():
    cfg = load_sources_config("config/sources.yaml")
    locals_ = {t.local for t in cfg.tickers}
    assert locals_ == {"BBCA", "UNVR", "TLKM", "PTBA", "ASII"}


def test_missing_required_field_raises_config_error(tmp_path):
    bad_yaml = tmp_path / "bad_sources.yaml"
    bad_yaml.write_text("sources: []\ntickers: []\nmerge_strategy: per_date_gap_fill\n")
    with pytest.raises(ConfigError):
        load_sources_config(str(bad_yaml))  # missing date_range


def test_quality_rules_config_loads():
    rules = load_quality_rules("config/quality_rules.yaml")
    assert rules.apply_split_adjustment is False
    assert rules.expected_trading_days["ASII"] == 1564
    assert rules.outlier_threshold_pct == 50
