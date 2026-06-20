"""
This is the test that matters most: the old fetch_with_redundancy() picked
one source's full output and discarded everything else, so two sources
that each covered different date ranges for the same ticker never actually
combined coverage. These tests prove the replacement (per_date_gap_fill)
does combine them.
"""
import pandas as pd
import pytest

from pipeline import orchestrator
from pipeline.config import SourcesConfig, SourceConfig, TickerConfig, RetryConfig


class _FakeAdapter:
    def __init__(self, df):
        self._df = df

    def fetch(self, ticker, start_date, end_date):
        return self._df


def _cfg_with_sources(sources):
    return SourcesConfig(
        sources=sources,
        tickers=[TickerConfig(local="TEST")],
        merge_strategy="per_date_gap_fill",
        date_start="2002-01-01",
        date_end="2002-01-10",
    )


def _df(dates, closes):
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": [100] * len(dates)},
        index=pd.to_datetime(dates),
    )


def test_lower_priority_fills_dates_higher_priority_is_missing(monkeypatch):
    primary_df = _df(["2002-01-01", "2002-01-02"], [10.0, 11.0])      # only 2 days
    fallback_df = _df(["2002-01-01", "2002-01-02", "2002-01-03", "2002-01-04"], [99, 99, 30.0, 31.0])

    sources = [
        SourceConfig(name="primary", enabled=True, priority=1, adapter="x.Primary"),
        SourceConfig(name="fallback", enabled=True, priority=2, adapter="x.Fallback"),
    ]
    cfg = _cfg_with_sources(sources)

    adapters = {"primary": _FakeAdapter(primary_df), "fallback": _FakeAdapter(fallback_df)}
    monkeypatch.setattr(orchestrator, "_load_adapter", lambda source: adapters[source.name])

    result = orchestrator.fetch_ticker(cfg.tickers[0], cfg, sleep=False)

    assert len(result) == 4  # 2 from primary + 2 gap-filled from fallback
    assert result.loc["2002-01-01", "Close"] == 10.0  # primary wins where both have data
    assert result.loc["2002-01-03", "Close"] == 30.0  # fallback fills the gap
    assert set(result["source"]) == {"primary", "fallback"}


def test_disabled_source_is_never_called(monkeypatch):
    primary_df = _df(["2002-01-01"], [10.0])
    sources = [
        SourceConfig(name="primary", enabled=True, priority=1, adapter="x.Primary"),
        SourceConfig(name="off", enabled=False, priority=2, adapter="x.Off"),
    ]
    cfg = _cfg_with_sources(sources)

    def fail_if_called(source):
        if source.name == "off":
            raise AssertionError("disabled source should never be loaded")
        return _FakeAdapter(primary_df)

    monkeypatch.setattr(orchestrator, "_load_adapter", fail_if_called)
    result = orchestrator.fetch_ticker(cfg.tickers[0], cfg, sleep=False)
    assert len(result) == 1


def test_returns_none_when_all_sources_return_none(monkeypatch):
    sources = [SourceConfig(name="primary", enabled=True, priority=1, adapter="x.Primary")]
    cfg = _cfg_with_sources(sources)
    monkeypatch.setattr(orchestrator, "_load_adapter", lambda source: _FakeAdapter(None))
    result = orchestrator.fetch_ticker(cfg.tickers[0], cfg, sleep=False)
    assert result is None


def test_retry_gives_up_after_max_attempts(monkeypatch):
    calls = {"n": 0}

    class FlakyAdapter:
        def fetch(self, ticker, start_date, end_date):
            calls["n"] += 1
            raise ConnectionError("simulated failure")

    sources = [SourceConfig(
        name="primary", enabled=True, priority=1, adapter="x.Primary",
        retry=RetryConfig(max_attempts=3, backoff_seconds=0),
    )]
    cfg = _cfg_with_sources(sources)
    monkeypatch.setattr(orchestrator, "_load_adapter", lambda source: FlakyAdapter())

    result = orchestrator.fetch_ticker(cfg.tickers[0], cfg, sleep=False)
    assert result is None
    assert calls["n"] == 3
