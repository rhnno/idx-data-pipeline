"""
Config loader for the scraping and data-quality layers.

Both config/sources.yaml and config/quality_rules.yaml are loaded through
this module so there's exactly one place that knows what shape those files
are supposed to have, and fails loudly (not silently with a KeyError three
calls deep) if a required field is missing.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


class ConfigError(Exception):
    """Raised when a config file is missing required fields."""


@dataclass
class RetryConfig:
    max_attempts: int = 1
    backoff_seconds: float = 1.0


@dataclass
class SourceConfig:
    name: str
    enabled: bool
    priority: int
    adapter: str
    rate_limit_seconds: float = 0.0
    retry: RetryConfig = field(default_factory=RetryConfig)
    disabled_reason: Optional[str] = None


@dataclass
class TickerConfig:
    local: str
    yahoo_symbol: Optional[str] = None
    wsj_symbol: Optional[str] = None
    investing_symbol: Optional[str] = None


@dataclass
class SourcesConfig:
    sources: List[SourceConfig]
    tickers: List[TickerConfig]
    merge_strategy: str
    date_start: str
    date_end: str

    def enabled_sources(self) -> List[SourceConfig]:
        return sorted(
            (s for s in self.sources if s.enabled),
            key=lambda s: s.priority,
        )


@dataclass
class QualityRulesConfig:
    outlier_threshold_pct: float
    flag_gap_days_above: int
    split_log_path: str
    apply_split_adjustment: bool
    expected_trading_days: Dict[str, int]
    min_close: float
    max_close: float
    require_close_within_low_high: bool


def _require(d: Dict[str, Any], key: str, context: str) -> Any:
    if key not in d:
        raise ConfigError(f"Missing required field '{key}' in {context}")
    return d[key]


def load_sources_config(path: str = "config/sources.yaml") -> SourcesConfig:
    raw = yaml.safe_load(Path(path).read_text())

    sources = []
    for s in _require(raw, "sources", path):
        retry_raw = s.get("retry", {})
        sources.append(SourceConfig(
            name=_require(s, "name", f"sources entry in {path}"),
            enabled=_require(s, "enabled", f"sources entry in {path}"),
            priority=_require(s, "priority", f"sources entry in {path}"),
            adapter=_require(s, "adapter", f"sources entry in {path}"),
            rate_limit_seconds=s.get("rate_limit_seconds", 0.0),
            retry=RetryConfig(
                max_attempts=retry_raw.get("max_attempts", 1),
                backoff_seconds=retry_raw.get("backoff_seconds", 1.0),
            ),
            disabled_reason=s.get("disabled_reason"),
        ))

    tickers = []
    for t in _require(raw, "tickers", path):
        tickers.append(TickerConfig(
            local=_require(t, "local", f"tickers entry in {path}"),
            yahoo_symbol=t.get("yahoo_symbol"),
            wsj_symbol=t.get("wsj_symbol"),
            investing_symbol=t.get("investing_symbol"),
        ))

    date_range = _require(raw, "date_range", path)

    return SourcesConfig(
        sources=sources,
        tickers=tickers,
        merge_strategy=_require(raw, "merge_strategy", path),
        date_start=_require(date_range, "start", f"date_range in {path}"),
        date_end=_require(date_range, "end", f"date_range in {path}"),
    )


def load_quality_rules(path: str = "config/quality_rules.yaml") -> QualityRulesConfig:
    raw = yaml.safe_load(Path(path).read_text())
    gap = raw.get("gap_detection", {})
    sanity = raw.get("price_sanity", {})

    return QualityRulesConfig(
        outlier_threshold_pct=_require(raw, "outlier_threshold_pct", path),
        flag_gap_days_above=gap.get("flag_gap_days_above", 10),
        split_log_path=_require(raw, "split_log_path", path),
        apply_split_adjustment=raw.get("apply_split_adjustment", False),
        expected_trading_days=_require(raw, "expected_trading_days", path),
        min_close=sanity.get("min_close", 0),
        max_close=sanity.get("max_close", float("inf")),
        require_close_within_low_high=sanity.get("require_close_within_low_high", True),
    )
