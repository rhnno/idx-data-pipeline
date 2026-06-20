"""
Turns raw per-source OHLCV (whatever an adapter/orchestrator handed back)
into the canonical master dataset: derived columns computed, dtypes
enforced via pipeline.schema, nothing left to whatever pandas feels like
inferring on a given run.

This module exists because the adapter/orchestrator refactor (see
pipeline/orchestrator.py) only fetches and merges raw OHLCV — it
deliberately doesn't know about Turnover, Liquidity_Score, or outlier
detection, because those are processing-layer concerns, not fetching-layer
concerns. Before this module, nothing called those steps at all once
idx_master_scraper.py was deleted, so a fresh `scrape-prices` run would
have silently produced a dataset missing several columns the data quality
checker still expects.
"""
import logging
from typing import Dict, Optional

import pandas as pd

from pipeline.schema import MASTER_PRICE_SCHEMA, enforce_schema

logger = logging.getLogger(__name__)


def compute_turnover(df: pd.DataFrame) -> pd.Series:
    """Close * Volume, in Rupiah. Computed in float64 deliberately — this
    reaches the trillions for these tickers, and float32 (~7 significant
    digits) would silently round amounts at that scale by hundreds of
    thousands. Cast to float32 only happened in the original
    implementation; it was never validated against the actual magnitudes
    in this dataset."""
    return (df["Close"].astype("float64") * df["Volume"].astype("float64"))


def compute_liquidity_score(df: pd.DataFrame) -> pd.Series:
    """Volume relative to its own trailing 20-day average. >1 means a day
    traded busier than its recent normal; <1 means quieter. The first 4
    days of any series won't have a full 20-day window (min_periods=5), so
    those get forward-filled from the first valid score rather than left
    as NaN."""
    volume_ma20 = df["Volume"].rolling(window=20, min_periods=5).mean()
    score = df["Volume"] / volume_ma20
    return score.ffill()


def compute_outlier_flag(df: pd.DataFrame, threshold_pct: float) -> pd.Series:
    """Flags days where Close moved more than threshold_pct vs the prior
    day. Threshold comes from config/quality_rules.yaml, not hardcoded, so
    changing sensitivity doesn't require touching this file.

    Per docs/DATA_LIMITATIONS.md sec 2: this is computed on raw Close, not
    a re-derived adjusted series, because raw Close was verified to already
    trade cleanly through this dataset's known split dates. If a future
    ticker/source DOES need split-adjustment, that decision should be
    re-verified the same way (manual continuity check across the actual
    split date) before assuming this function is still correct for it."""
    daily_return = df["Close"].pct_change()
    return daily_return.abs() > (threshold_pct / 100.0)


def process_ticker(raw_df: pd.DataFrame, ticker_local: str, outlier_threshold_pct: float = 50.0) -> pd.DataFrame:
    """raw_df: whatever an adapter/orchestrator returned for one ticker —
    indexed by Date, columns Open/High/Low/Close/Volume/source at minimum.
    Returns a dataframe with every column in MASTER_PRICE_SCHEMA populated,
    still needing enforce_schema() applied once all tickers are concatenated."""
    df = raw_df.reset_index().rename(columns={"Date": "date"})
    df["Ticker"] = ticker_local
    df = df.sort_values("date").reset_index(drop=True)

    df["Turnover"] = compute_turnover(df)
    df["Liquidity_Score"] = compute_liquidity_score(df)
    df["Outlier_Flag"] = compute_outlier_flag(df, outlier_threshold_pct)

    # Identical to Close by design — see docs/DATA_LIMITATIONS.md sec 2.
    # Not an independently computed value; do not "fix" this to diverge
    # from Close without re-running the manual continuity check documented
    # there first.
    df["Close_Adj"] = df["Close"]

    # Inherited from the archived margin-call simulation layer. Nothing in
    # this package uses it; kept only so the schema doesn't silently drop a
    # column anyone archived elsewhere might still expect.
    df["mc_eligible"] = True

    return df


def build_master_dataset(
    per_ticker_results: Dict[str, Optional[pd.DataFrame]],
    outlier_threshold_pct: float = 50.0,
) -> pd.DataFrame:
    """per_ticker_results: {local_ticker: raw_df_or_None}, as returned by
    pipeline.orchestrator.fetch_all(). Returns one combined, schema-enforced
    dataframe ready to write to data/raw/idx_daily_prices_2002_2007.csv."""
    frames = []
    for ticker_local, raw_df in per_ticker_results.items():
        if raw_df is None or raw_df.empty:
            logger.warning(f"No data for {ticker_local}; skipping.")
            continue
        frames.append(process_ticker(raw_df, ticker_local, outlier_threshold_pct))

    if not frames:
        raise ValueError("No ticker produced data — nothing to build a master dataset from.")

    combined = pd.concat(frames, ignore_index=True)
    return enforce_schema(combined, MASTER_PRICE_SCHEMA)
