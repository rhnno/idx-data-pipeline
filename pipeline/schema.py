"""
Single source of truth for column dtypes across the pipeline.

Why this exists: before this module, dtype enforcement was scattered and
silently broken in three places —

1. pipeline/data_quality.py's read_csv() had `dtype={'ticker': 'str', ...}`
   with a lowercase 'ticker' key against a column actually named 'Ticker'.
   pandas does not error on an unmatched dtype key; it just never applies
   it. So `Ticker` was never actually controlled, it fell through to
   pandas' default string/object inference.
2. The same file's dtype *validation* check compared dtypes with exact
   string equality against a single hardcoded label (`'datetime64[ns]'`),
   which breaks across pandas versions that default to `datetime64[us]` —
   a real column that IS a datetime would still fail this check for having
   the "wrong" resolution label, which isn't actually a data problem.
3. `Volume` was being cast to float32 in the Yahoo adapter and in the
   quality checker's read_csv. float32 has ~7 significant digits of exact
   integer precision (~16.7M); real Volume values in this dataset reach
   2.38 billion shares, so float32 silently rounds about 16% of rows
   (946 / 5780) by up to 64 shares. Share counts are integers; this caused
   needless precision loss for no benefit.

This module fixes all three: one schema dict, one loader, one validator
that checks dtype *family* (is this a datetime? is this numeric?) rather
than an exact version-dependent string label.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

import numpy as np
import pandas as pd


def _is_category_dtype(series: pd.Series) -> bool:
    """pandas.api.types.is_categorical_dtype is deprecated; this is the
    replacement pandas itself recommends. Needed because is_object_dtype
    (used for plain string columns) returns False for category dtype —
    using the wrong checker here previously made Ticker/source fail
    validation even when their dtype was exactly the expected 'category'."""
    return isinstance(series.dtype, pd.CategoricalDtype)


@dataclass(frozen=True)
class ColumnSpec:
    dtype: str               # target dtype used when writing/casting
    checker: Callable        # pandas.api.types.is_*_dtype function used when validating
    description: str


# Volume is a share count: integers, not floats. Six rows in the source
# data carry fractional values (e.g. 33.33, 6460033.50) — a known Yahoo
# Finance quirk where Volume gets split-adjusted independently of the
# price `auto_adjust` flag, observed right around ASII's and UNVR's real
# split dates. These are rounded to the nearest whole share before casting
# rather than truncated, so a .50 doesn't always round down.
MASTER_PRICE_SCHEMA: Dict[str, ColumnSpec] = {
    "date":             ColumnSpec("datetime64[ns]", pd.api.types.is_datetime64_any_dtype,
                                    "trading date"),
    "Ticker":           ColumnSpec("category",        _is_category_dtype,
                                    "ticker symbol, small fixed set"),
    "Open":             ColumnSpec("float32",          pd.api.types.is_float_dtype, "opening price"),
    "High":             ColumnSpec("float32",          pd.api.types.is_float_dtype, "high price"),
    "Low":              ColumnSpec("float32",          pd.api.types.is_float_dtype, "low price"),
    "Close":            ColumnSpec("float32",          pd.api.types.is_float_dtype, "close price"),
    "Close_Adj":        ColumnSpec("float32",          pd.api.types.is_float_dtype,
                                    "see docs/DATA_LIMITATIONS.md sec 2 - identical to Close by design"),
    "Volume":           ColumnSpec("int64",            pd.api.types.is_integer_dtype,
                                    "share count - must be a whole number"),
    "Turnover":         ColumnSpec("float64",          pd.api.types.is_float_dtype,
                                    "Rupiah value, can reach the trillions - float32 loses precision here"),
    "Liquidity_Score":  ColumnSpec("float32",          pd.api.types.is_float_dtype, "normalized score"),
    "Outlier_Flag":     ColumnSpec("bool",              pd.api.types.is_bool_dtype, "outlier flag"),
    "source":           ColumnSpec("category",          _is_category_dtype,
                                    "data source name, small fixed set"),
    "mc_eligible":      ColumnSpec("bool",              pd.api.types.is_bool_dtype,
                                    "leftover from the archived margin-call simulation layer; "
                                    "kept for backward compatibility, not used by anything in this package"),
}


class SchemaValidationError(Exception):
    """Raised when a dataframe genuinely doesn't match its expected schema family."""


def enforce_schema(df: pd.DataFrame, schema: Dict[str, ColumnSpec] = MASTER_PRICE_SCHEMA) -> pd.DataFrame:
    """Cast a dataframe to the canonical dtypes. Call this once, right before
    writing a CSV — not scattered ad hoc casts in every script that touches
    the data."""
    df = df.copy()

    for col, spec in schema.items():
        if col not in df.columns:
            continue

        if col == "Volume":
            # round (not truncate) before casting to int — see module docstring.
            df[col] = df[col].round(0).astype("int64")
        elif spec.dtype == "datetime64[ns]":
            df[col] = pd.to_datetime(df[col])
        elif spec.dtype == "category":
            df[col] = df[col].astype("category")
        else:
            df[col] = df[col].astype(spec.dtype)

    return df


def validate_schema(df: pd.DataFrame, schema: Dict[str, ColumnSpec] = MASTER_PRICE_SCHEMA) -> Dict[str, dict]:
    """Check dtype *family* (datetime? numeric? bool?) rather than an exact
    version-dependent dtype string. Returns one result row per column found
    in both the dataframe and the schema, for the data quality report to
    render however it wants."""
    results = {}
    for col, spec in schema.items():
        if col not in df.columns:
            continue
        actual_dtype = df[col].dtype
        passed = bool(spec.checker(df[col]))
        results[col] = {
            "expected_family": spec.dtype,
            "actual_dtype": str(actual_dtype),
            "passed": passed,
        }
    return results


def read_master_csv(path: str, schema: Dict[str, ColumnSpec] = MASTER_PRICE_SCHEMA) -> pd.DataFrame:
    """The one place that should ever call pd.read_csv() on the master
    price file. Loads then enforces the canonical schema, so every caller
    gets identical dtypes regardless of what pandas would have inferred on
    its own from the CSV text."""
    df = pd.read_csv(path)
    return enforce_schema(df, schema)
