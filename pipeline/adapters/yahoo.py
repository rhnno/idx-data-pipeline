"""
Yahoo Finance adapter via the yfinance package. This is the only source
that has actually produced data for this pipeline (see
docs/DATA_LIMITATIONS.md) — WSJ and Investing.com are registered in
config/sources.yaml but disabled, not implemented here, because neither
has a working adapter yet.
"""
import logging
from typing import Optional
import pandas as pd

from pipeline.adapters.base import SourceAdapter

logger = logging.getLogger(__name__)


class YahooAdapter(SourceAdapter):
    name = "yahoo"

    def fetch(self, ticker, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        symbol = ticker.yahoo_symbol
        if not symbol:
            logger.warning(f"No yahoo_symbol configured for ticker {ticker.local}")
            return None

        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed; skipping Yahoo source.")
            return None

        try:
            raw = yf.Ticker(symbol).history(start=start_date, end=end_date, auto_adjust=False)
        except Exception as e:
            logger.error(f"Yahoo fetch failed for {symbol}: {e}")
            return None

        if raw is None or raw.empty:
            return None

        df = raw[["Open", "High", "Low", "Close", "Volume"]].astype({
            "Open": "float32", "High": "float32", "Low": "float32",
            "Close": "float32", "Volume": "float32",
        })
        df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
        df.index.name = "Date"

        self.validate_schema(df)
        logger.info(f"Yahoo: {symbol} - {len(df)} daily records")
        return df
