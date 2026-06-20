"""
Replaces the old fetch_with_redundancy() "whichever source returns
non-empty wins entirely" logic. This orchestrator merges sources at the
row level: the highest-priority enabled source provides the baseline, and
each lower-priority source only fills in dates the baseline is missing —
nobody's full output gets thrown away just because a higher-priority
source partially covers the same ticker.
"""
import importlib
import logging
import time
from typing import List, Optional

import pandas as pd

from pipeline.config import SourcesConfig, SourceConfig, TickerConfig

logger = logging.getLogger(__name__)


def _load_adapter(source: SourceConfig):
    module_path, class_name = source.adapter.rsplit(".", 1)
    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    return adapter_cls()


def fetch_ticker(ticker: TickerConfig, cfg: SourcesConfig, sleep: bool = True) -> Optional[pd.DataFrame]:
    """Fetch one ticker across all enabled sources, merged per-date."""
    enabled = cfg.enabled_sources()
    if not enabled:
        logger.error("No enabled sources in config — nothing to fetch.")
        return None

    if cfg.merge_strategy != "per_date_gap_fill":
        raise NotImplementedError(f"Unknown merge_strategy: {cfg.merge_strategy}")

    merged: Optional[pd.DataFrame] = None

    for source in enabled:
        adapter = _load_adapter(source)
        df = _fetch_with_retry(adapter, ticker, cfg.date_start, cfg.date_end, source)

        if df is None or df.empty:
            continue

        df = df.copy()
        df["source"] = source.name

        if merged is None:
            merged = df
        else:
            missing_dates = df.index.difference(merged.index)
            if len(missing_dates) > 0:
                gap_fill = df.loc[missing_dates]
                logger.info(
                    f"{ticker.local}: {source.name} filled {len(gap_fill)} "
                    f"date(s) missing from higher-priority source(s)."
                )
                merged = pd.concat([merged, gap_fill]).sort_index()

        if sleep and source.rate_limit_seconds:
            time.sleep(source.rate_limit_seconds)

    return merged


def _fetch_with_retry(adapter, ticker, start_date, end_date, source: SourceConfig) -> Optional[pd.DataFrame]:
    last_error = None
    for attempt in range(1, source.retry.max_attempts + 1):
        try:
            result = adapter.fetch(ticker, start_date, end_date)
            if result is not None:
                return result
        except Exception as e:
            last_error = e
            logger.warning(f"{source.name} attempt {attempt}/{source.retry.max_attempts} for {ticker.local} failed: {e}")
        if attempt < source.retry.max_attempts:
            time.sleep(source.retry.backoff_seconds)
    if last_error:
        logger.error(f"{source.name} exhausted retries for {ticker.local}: {last_error}")
    return None


def fetch_all(cfg: SourcesConfig, sleep: bool = True) -> dict:
    """Fetch every configured ticker. Returns {local_ticker: DataFrame|None}."""
    results = {}
    for ticker in cfg.tickers:
        logger.info(f"Fetching {ticker.local} ({cfg.date_start} to {cfg.date_end})")
        results[ticker.local] = fetch_ticker(ticker, cfg, sleep=sleep)
    return results
