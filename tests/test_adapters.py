"""
These tests mock yfinance entirely — this sandbox's network egress doesn't
allow finance.yahoo.com (confirmed: HTTP 403 'Host not in allowlist'), so
this validates the adapter's parsing/normalization logic, not a live fetch.
Run a real end-to-end fetch from an unrestricted machine before relying on
this in production: `python main.py scrape-prices`.
"""
import sys
import types
from unittest.mock import MagicMock
import pandas as pd
import pytest

from pipeline.adapters.yahoo import YahooAdapter
from pipeline.config import TickerConfig


def _fake_yfinance_module(history_df):
    fake_yf = types.ModuleType("yfinance")
    fake_ticker_instance = MagicMock()
    fake_ticker_instance.history.return_value = history_df
    fake_yf.Ticker = MagicMock(return_value=fake_ticker_instance)
    return fake_yf


def test_yahoo_adapter_normalizes_columns(monkeypatch):
    raw = pd.DataFrame({
        "Open": [100.0, 101.0],
        "High": [105.0, 106.0],
        "Low": [99.0, 100.0],
        "Close": [104.0, 105.0],
        "Volume": [1000, 1100],
        "Dividends": [0.0, 0.0],
        "Stock Splits": [0.0, 0.0],
    }, index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
    raw.index.name = "Date"

    monkeypatch.setitem(sys.modules, "yfinance", _fake_yfinance_module(raw))

    adapter = YahooAdapter()
    ticker = TickerConfig(local="TEST", yahoo_symbol="TEST.JK")
    result = adapter.fetch(ticker, "2024-01-01", "2024-01-10")

    assert result is not None
    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert result["Close"].dtype == "float32"
    assert len(result) == 2


def test_yahoo_adapter_returns_none_on_empty_response(monkeypatch):
    empty = pd.DataFrame()
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yfinance_module(empty))

    adapter = YahooAdapter()
    ticker = TickerConfig(local="TEST", yahoo_symbol="TEST.JK")
    result = adapter.fetch(ticker, "2024-01-01", "2024-01-10")

    assert result is None


def test_yahoo_adapter_returns_none_without_symbol():
    adapter = YahooAdapter()
    ticker = TickerConfig(local="TEST", yahoo_symbol=None)
    result = adapter.fetch(ticker, "2024-01-01", "2024-01-10")
    assert result is None


def test_yahoo_adapter_handles_exception_gracefully(monkeypatch):
    fake_yf = types.ModuleType("yfinance")
    broken_ticker = MagicMock()
    broken_ticker.history.side_effect = RuntimeError("network blocked")
    fake_yf.Ticker = MagicMock(return_value=broken_ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    adapter = YahooAdapter()
    ticker = TickerConfig(local="TEST", yahoo_symbol="TEST.JK")
    result = adapter.fetch(ticker, "2024-01-01", "2024-01-10")
    assert result is None
