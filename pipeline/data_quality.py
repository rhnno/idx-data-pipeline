"""
Data Quality Check Script for IDX Gold Era Master Dataset (2002-2007)
=====================================================================
Performs comprehensive validation:
1. Basic Integrity (row counts, NaN checks, dtypes)
2. Price Validity (negative prices, High/L logic, Close range)
3. Outlier Flag Audit
4. Corporate Action Boundary Check
5. Time Series Continuity (gap detection, trading days per year)

Output: docs/DATA_QUALITY_REPORT.md
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
from datetime import datetime
from typing import Dict, List, Tuple


class DataQualityChecker:
    """Comprehensive data quality validation for IDX historical data."""
    
    def __init__(self, master_csv: str, split_log_csv: str, quality_rules_path: str = "config/quality_rules.yaml"):
        self.master_path = Path(master_csv)
        self.split_path = Path(split_log_csv)
        self.report_lines = []

        # Expected row counts per ticker now live in config/quality_rules.yaml
        # so they can be updated without touching this file. Falls back to
        # the original hardcoded values if no config is found, so this still
        # works standalone (e.g. in older test setups).
        try:
            from pipeline.config import load_quality_rules
            self.quality_rules = load_quality_rules(quality_rules_path)
            self.expected_rows = self.quality_rules.expected_trading_days
        except FileNotFoundError:
            self.quality_rules = None
            self.expected_rows = {
                'BBCA': 929,
                'UNVR': 1128,
                'TLKM': 849,
                'PTBA': 1310,
                'ASII': 1564
            }
        
        print(f"📂 Loading master data: {self.master_path}")
        if not self.master_path.exists():
            raise FileNotFoundError(f"Master CSV not found: {self.master_path}")

        # Previously this called pd.read_csv() directly with a dtype dict
        # that had a lowercase 'ticker' key against a column actually named
        # 'Ticker' — pandas silently ignores dtype keys that don't match a
        # real column instead of erroring, so Ticker's dtype was never
        # actually controlled. read_master_csv() goes through
        # pipeline/schema.py instead, which is the one place that owns
        # column dtypes for this dataset.
        from pipeline.schema import read_master_csv
        self.df = read_master_csv(str(self.master_path))
        print(f"✅ Loaded {len(self.df):,} rows × {len(self.df.columns)} columns")
        
        if self.split_path.exists():
            self.split_df = pd.read_csv(self.split_path, parse_dates=['ex_date'])
            print(f"✅ Loaded split log: {len(self.split_df)} events")
        else:
            self.split_df = pd.DataFrame()
            print(f"⚠️ Split log not found: {self.split_path}")
        
        self.tickers = sorted(self.df['Ticker'].unique())
        print(f"📊 Tickers found: {self.tickers}")
    
    def log(self, line: str):
        """Add line to report."""
        self.report_lines.append(line)
        print(line)
    
    def section_header(self, title: str, emoji: str = "📋"):
        """Add section header to report."""
        self.log(f"\n{'='*80}")
        self.log(f"{emoji} {title}")
        self.log(f"{'='*80}\n")
    
    def status_badge(self, passed: bool, warning: bool = False) -> str:
        """Return status badge."""
        if warning:
            return "⚠️"
        elif passed:
            return "✅"
        else:
            return "❌"
    
    # ============================================================
    # 1. BASIC INTEGRITY CHECKS
    # ============================================================
    def check_basic_integrity(self):
        """Check row counts, NaN distribution, and data types."""
        self.section_header("1. BASIC INTEGRITY", "📊")
        
        self.log("### 1.1 Row Count Per Ticker\n")
        self.log("| Ticker | Actual Rows | Expected Rows | Status | Delta |")
        self.log("|--------|-------------|---------------|--------|-------|")
        
        row_counts = self.df.groupby('Ticker').size()
        
        all_passed = True
        for ticker in self.tickers:
            actual = row_counts.get(ticker, 0)
            expected = self.expected_rows.get(ticker, 0)
            delta = actual - expected
            
            if expected > 0:
                pct_diff = abs(delta) / expected * 100
                # Not an exact match on purpose: a holiday calendar
                # discrepancy of a day or two between data refreshes
                # shouldn't fail the whole check. 1% catches anything bigger
                # than that (e.g. the 48-row synthetic block this check
                # originally existed to catch — see DATA_LIMITATIONS.md §3).
                passed = pct_diff < 1
                status = self.status_badge(passed)
            else:
                status = "⚪ N/A"
                passed = True
            
            if not passed:
                all_passed = False
            
            self.log(f"| {ticker} | {actual:,} | {expected:,} | {status} | {delta:+,} |")
        
        self.log(f"\n**Status:** {self.status_badge(all_passed)} "
                f"Row count validation {'PASSED' if all_passed else 'FAILED'}\n")
        
        self.log("### 1.2 NaN Distribution Per Column Per Ticker\n")
        
        nan_report = []
        for ticker in self.tickers:
            ticker_df = self.df[self.df['Ticker'] == ticker]
            nan_counts = ticker_df.isnull().sum()
            
            for col in self.df.columns:
                nan_count = nan_counts.get(col, 0)
                total_rows = len(ticker_df)
                nan_pct = (nan_count / total_rows * 100) if total_rows > 0 else 0
                
                nan_report.append({
                    'Ticker': ticker,
                    'Column': col,
                    'NaN_Count': nan_count,
                    'Total_Rows': total_rows,
                    'NaN_Pct': nan_pct
                })
        
        nan_df = pd.DataFrame(nan_report)
        
        nan_df_filtered = nan_df[nan_df['NaN_Count'] > 0].sort_values(['Ticker', 'NaN_Count'], ascending=[True, False])
        
        if len(nan_df_filtered) > 0:
            self.log("| Ticker | Column | NaN Count | Total Rows | NaN % |")
            self.log("|--------|--------|-----------|------------|-------|")
            
            for _, row in nan_df_filtered.iterrows():
                warning = row['NaN_Pct'] > 5
                status = self.status_badge(not warning, warning=warning)
                self.log(f"| {row['Ticker']} | {row['Column']} | {row['NaN_Count']:,} | "
                        f"{row['Total_Rows']:,} | {row['NaN_Pct']:.2f}% {status} |")
        else:
            self.log("✅ **No NaN values found in any column!**\n")
        
        self.log("\n### 1.3 Data Type Validation\n")
        self.log("| Column | Expected Family | Actual Dtype | Status |")
        self.log("|--------|------------------|--------------|--------|")

        # Checks dtype *family* (is this a datetime? numeric? bool?) via
        # pipeline/schema.py rather than exact-string-matching a single
        # hardcoded label like 'datetime64[ns]'. The old version failed any
        # pandas build that defaults to datetime64[us] resolution even
        # though the column genuinely was a datetime — that wasn't a data
        # problem, it was the check asking the wrong question.
        from pipeline.schema import validate_schema, MASTER_PRICE_SCHEMA
        schema_results = validate_schema(self.df, MASTER_PRICE_SCHEMA)

        dtype_passed = True
        for col, result in schema_results.items():
            status = self.status_badge(result["passed"])
            if not result["passed"]:
                dtype_passed = False
            self.log(f"| {col} | {result['expected_family']} | {result['actual_dtype']} | {status} |")

        self.log(f"\n**Status:** {self.status_badge(dtype_passed)} "
                f"Data type validation {'PASSED' if dtype_passed else 'FAILED'}\n")
    
    # ============================================================
    # 2. PRICE VALIDITY CHECKS
    # ============================================================
    def check_price_validity(self):
        """Validate price logic: positive values, High>=Low, Close in range."""
        self.section_header("2. PRICE VALIDITY", "💰")
        
        self.log("### 2.1 Non-Positive Price Check\n")
        
        invalid_close = self.df[self.df['Close'] <= 0]
        invalid_close_adj = self.df[self.df['Close_Adj'] <= 0]
        
        self.log(f"- **Close <= 0:** {len(invalid_close):,} rows")
        if len(invalid_close) > 0:
            self.log("\n**Affected rows (first 10):**")
            self.log(str(invalid_close[['date', 'Ticker', 'Close', 'Low', 'High']].head(10).to_markdown(index=False)))
        
        self.log(f"\n- **Close_Adj <= 0:** {len(invalid_close_adj):,} rows")
        if len(invalid_close_adj) > 0:
            self.log("\n**Affected rows (first 10):**")
            self.log(str(invalid_close_adj[['date', 'Ticker', 'Close_Adj']].head(10).to_markdown(index=False)))
        
        price_positive_passed = (len(invalid_close) == 0 and len(invalid_close_adj) == 0)
        self.log(f"\n**Status:** {self.status_badge(price_positive_passed)} "
                f"Price positivity check {'PASSED' if price_positive_passed else 'FAILED'}\n")
        
        self.log("\n### 2.2 High >= Low Validation\n")
        
        self.df['High_Low_Valid'] = self.df['High'] >= self.df['Low']
        invalid_hl = self.df[~self.df['High_Low_Valid']]
        
        self.log(f"- **Total rows:** {len(self.df):,}")
        self.log(f"- **Valid (High >= Low):** {self.df['High_Low_Valid'].sum():,}")
        self.log(f"- **Invalid (High < Low):** {len(invalid_hl):,}")
        
        if len(invalid_hl) > 0:
            self.log("\n**Invalid rows by ticker:**")
            hl_by_ticker = invalid_hl.groupby('Ticker').size()
            for ticker, count in hl_by_ticker.items():
                self.log(f"  - {ticker}: {count:,} rows")
            
            self.log("\n**First 10 invalid rows:**")
            self.log(str(invalid_hl[['date', 'Ticker', 'High', 'Low', 'Close']].head(10).to_markdown(index=False)))
        
        hl_passed = len(invalid_hl) == 0
        self.log(f"\n**Status:** {self.status_badge(hl_passed)} "
                f"High/Low logic check {'PASSED' if hl_passed else 'FAILED'}\n")
        
        self.log("\n### 2.3 Close Within [Low, High] Range\n")
        
        self.df['Close_In_Range'] = (
            (self.df['Close'] >= self.df['Low']) & 
            (self.df['Close'] <= self.df['High'])
        )
        invalid_close_range = self.df[~self.df['Close_In_Range']]
        
        self.log(f"- **Total rows:** {len(self.df):,}")
        self.log(f"- **Valid (Close in range):** {self.df['Close_In_Range'].sum():,}")
        self.log(f"- **Invalid (Close outside range):** {len(invalid_close_range):,}")
        
        if len(invalid_close_range) > 0:
            self.log("\n**Invalid rows by ticker:**")
            cr_by_ticker = invalid_close_range.groupby('Ticker').size()
            for ticker, count in cr_by_ticker.items():
                self.log(f"  - {ticker}: {count:,} rows")
            
            self.log("\n**First 10 invalid rows:**")
            self.log(str(invalid_close_range[['date', 'Ticker', 'Low', 'Close', 'High']].head(10).to_markdown(index=False)))
        
        close_range_passed = len(invalid_close_range) == 0
        self.log(f"\n**Status:** {self.status_badge(close_range_passed)} "
                f"Close range check {'PASSED' if close_range_passed else 'FAILED'}\n")
    
    # ============================================================
    # 3. OUTLIER FLAG AUDIT
    # ============================================================
    def check_outlier_flags(self):
        """Audit outlier flags per ticker and display samples."""
        self.section_header("3. OUTLIER FLAG AUDIT", "🚨")
        
        if 'Outlier_Flag' not in self.df.columns:
            self.log("⚠️ **Column 'Outlier_Flag' not found in dataset!**\n")
            return
        
        self.log("### 3.1 Outlier Count Per Ticker\n")
        
        outlier_counts = self.df[self.df['Outlier_Flag'] == True].groupby('Ticker').size()
        
        self.log("| Ticker | Total Rows | Outliers | Outlier % | Status |")
        self.log("|--------|------------|----------|-----------|--------|")
        
        for ticker in self.tickers:
            total = len(self.df[self.df['Ticker'] == ticker])
            outliers = outlier_counts.get(ticker, 0)
            pct = (outliers / total * 100) if total > 0 else 0
            
            warning = pct > 2  # Warning if >2% outliers
            status = self.status_badge(not warning, warning=warning)
            
            self.log(f"| {ticker} | {total:,} | {outliers:,} | {pct:.2f}% | {status} |")
        
        total_outliers = self.df['Outlier_Flag'].sum()
        total_rows = len(self.df)
        total_pct = (total_outliers / total_rows * 100) if total_rows > 0 else 0
        
        outlier_passed = total_pct < 2
        has_any_outliers = total_outliers > 0
        # warning only applies when the check PASSES but isn't perfectly
        # clean (some outliers exist, just under the fail threshold) —
        # without `outlier_passed` in this condition, 0% outliers also
        # triggered a warning here, which is what shipped before this fix.
        self.log(f"\n**Total Outliers:** {total_outliers:,} / {total_rows:,} ({total_pct:.2f}%)")
        self.log(f"**Status:** {self.status_badge(outlier_passed, warning=(has_any_outliers and outlier_passed))}\n")
        
        # 3.2 Display top 5 outliers per ticker
        self.log("\n### 3.2 Top 5 Outliers Per Ticker (Earliest)\n")
        
        for ticker in self.tickers:
            ticker_outliers = self.df[
                (self.df['Ticker'] == ticker) & 
                (self.df['Outlier_Flag'] == True)
            ].sort_values('date')
            
            if len(ticker_outliers) > 0:
                self.log(f"\n**{ticker}** (showing top 5 of {len(ticker_outliers):,} outliers):")
                display_cols = ['date', 'Ticker', 'Close', 'Close_Adj', 'Outlier_Flag']
                self.log(str(ticker_outliers[display_cols].head(5).to_markdown(index=False)))
    
    # ============================================================
    # 4. CORPORATE ACTION BOUNDARY CHECK
    # ============================================================
    def check_corporate_action_boundaries(self):
        """Check price behavior around split ex-dates."""
        self.section_header("4. CORPORATE ACTION BOUNDARY CHECK", "🔄")
        
        if self.split_df.empty:
            self.log("⚠️ **No corporate action split log found! Skipping boundary check.**\n")
            return
        
        self.log(f"**Total split events:** {len(self.split_df)}\n")
        
        self.log("### 4.1 Price Behavior Around Split Ex-Dates\n")
        
        for idx, split_row in self.split_df.iterrows():
            symbol = split_row['symbol']
            ex_date = pd.Timestamp(split_row['ex_date'])
            split_ratio = split_row.get('split_ratio', 'N/A')
            
            self.log(f"\n**Split Event: {symbol} @ {ex_date.strftime('%Y-%m-%d')} "
                    f"(Ratio: 1:{split_ratio})**\n")
            
            # Get price data for this ticker
            ticker_df = self.df[self.df['Ticker'] == symbol].copy()
            if ticker_df.empty:
                self.log(f"  ⚠️ No price data found for {symbol}\n")
                continue
            
            ticker_df = ticker_df.sort_values('date')
            
            # Find dates around ex-date (T-2, T-1, T, T+1, T+2)
            trading_dates = ticker_df['date'].values
            
            # Find index of ex_date (or closest date)
            date_diffs = np.abs(trading_dates - np.datetime64(ex_date))
            closest_idx = np.argmin(date_diffs)
            
            # Get window T-2 to T+2
            start_idx = max(0, closest_idx - 2)
            end_idx = min(len(ticker_df), closest_idx + 3)
            
            window_df = ticker_df.iloc[start_idx:end_idx][
                ['date', 'Ticker', 'Close', 'Close_Adj']
            ].copy()
            
            # Mark which row is the ex-date
            window_df['Position'] = 'N/A'
            for i, (_, row) in enumerate(window_df.iterrows()):
                actual_idx = start_idx + i
                relative_pos = actual_idx - closest_idx
                
                if relative_pos == 0:
                    window_df.at[row.name, 'Position'] = 'T (Ex-Date)'
                elif relative_pos < 0:
                    window_df.at[row.name, 'Position'] = f'T{relative_pos}'
                else:
                    window_df.at[row.name, 'Position'] = f'T+{relative_pos}'
            
            self.log(window_df.to_markdown(index=False))
            self.log("")

        # No automated pass/fail here on purpose: a price table around a
        # split date needs a human to look at it and judge whether the jump
        # matches the documented ratio. See docs/DATA_LIMITATIONS.md §2 for
        # why this pipeline doesn't auto-adjust prices at all anymore —
        # that decision came from exactly this kind of manual review.
        self.log(f"\n**Status:** ⚠️ **MANUAL REVIEW REQUIRED** "
                f"(check price jumps at split dates)\n")
    
    # ============================================================
    # 5. TIME SERIES CONTINUITY
    # ============================================================
    def check_time_series_continuity(self):
        """Check for date gaps and trading days per year."""
        self.section_header("5. TIME SERIES CONTINUITY", "📅")
        
        # 5.1 Gap detection (>5 business days)
        self.log("### 5.1 Date Gap Detection (>5 Business Days)\n")
        
        all_gaps = []
        
        for ticker in self.tickers:
            ticker_df = self.df[self.df['Ticker'] == ticker].sort_values('date')
            dates = ticker_df['date'].values
            
            for i in range(1, len(dates)):
                prev_date = pd.Timestamp(dates[i-1])
                curr_date = pd.Timestamp(dates[i])
                gap_days = (curr_date - prev_date).days
                
                # np.busday_count only excludes weekends — it doesn't know
                # about Indonesian public holidays, so this undercounts real
                # non-trading days slightly. Close enough to flag genuine
                # gaps; not precise enough to explain a gap's exact cause.
                business_days = np.busday_count(
                    prev_date.strftime('%Y-%m-%d'),
                    curr_date.strftime('%Y-%m-%d')
                )
                
                if business_days > 5:
                    all_gaps.append({
                        'ticker': ticker,
                        'prev_date': prev_date,
                        'curr_date': curr_date,
                        'calendar_days': gap_days,
                        'business_days': business_days
                    })
        
        if len(all_gaps) > 0:
            gaps_df = pd.DataFrame(all_gaps)
            
            self.log(f"**Total gaps >5 business days:** {len(gaps_df)}\n")
            
            self.log("| Ticker | From Date | To Date | Calendar Days | Business Days | Likely Cause |")
            self.log("|--------|-----------|---------|---------------|---------------|--------------|")
            
            for _, gap in gaps_df.iterrows():
                # This is a guess based on month alone, not a real holiday
                # calendar — good enough to make the report skimmable, not
                # a claim about what actually caused any specific gap.
                month = gap['curr_date'].month
                likely_cause = "Unknown"
                
                if month in [12, 1]:
                    likely_cause = "Year-end/New Year"
                elif month in [6, 7, 8]:
                    likely_cause = "Ramadan/Eid (possible)"
                
                warning = gap['business_days'] > 10
                status = self.status_badge(not warning, warning=warning)
                
                self.log(f"| {gap['ticker']} | {gap['prev_date'].strftime('%Y-%m-%d')} | "
                        f"{gap['curr_date'].strftime('%Y-%m-%d')} | {gap['calendar_days']} | "
                        f"{gap['business_days']} | {likely_cause} {status} |")
            
            # A handful of >5-business-day gaps around holidays is normal
            # for any market calendar; this only fails the check if more
            # than 20% of detected gaps are unusually long (>10 business
            # days), since that ratio is what distinguishes "normal holiday
            # clustering" from "something is actually missing."
            gap_passed = len([g for g in all_gaps if g['business_days'] <= 10]) > len(all_gaps) * 0.8
        else:
            self.log("✅ **No significant date gaps found!**\n")
            gap_passed = True
        
        self.log(f"\n**Status:** {self.status_badge(gap_passed, warning=(len(all_gaps) < 10))}\n")
        
        # 5.2 Trading days per year per ticker (pivot table)
        self.log("\n### 5.2 Trading Days Per Year Per Ticker\n")
        
        self.df['year'] = self.df['date'].dt.year
        
        trading_days = self.df.groupby(['Ticker', 'year']).size().unstack(fill_value=0)
        
        self.log("**Pivot Table: Trading Days × Year**\n")
        self.log(trading_days.to_markdown())
        
        self.log("\n\n**Expected:** ~244 trading days per year (IDX average)")
        
        # Flagging here doesn't mean something's broken — for BBCA and TLKM,
        # near-zero trading days in 2002-2003 is the real, verified
        # coverage gap this pipeline exists to document, not a bug to chase.
        # See docs/DATA_LIMITATIONS.md §1 before treating this as a defect.
        anomalies = (trading_days < 200) | (trading_days > 260)
        anomaly_count = anomalies.sum().sum()
        
        td_passed = anomaly_count == 0
        self.log(f"\n\n**Anomalies (<200 or >260 days):** {anomaly_count}")
        self.log(f"**Status:** {self.status_badge(td_passed)}\n")
    
    # ============================================================
    # EXECUTE ALL CHECKS & SAVE REPORT
    # ============================================================
    def run_all_checks(self):
        """Run all data quality checks and generate report."""
        print("\n" + "="*80)
        print("🔍 IDX GOLD ERA MASTER - DATA QUALITY CHECK")
        print("="*80)
        
        self.log(f"# DATA QUALITY REPORT")
        self.log(f"**Dataset:** idx_daily_prices_2002_2007.csv")
        self.log(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"**Source:** `{self.master_path}`")
        self.log(f"**Total Records:** {len(self.df):,}")
        self.log(f"**Tickers:** {', '.join(self.tickers)}")
        self.log(f"**Date Range:** {self.df['date'].min().strftime('%Y-%m-%d')} to "
                f"{self.df['date'].max().strftime('%Y-%m-%d')}")
        
        self.check_basic_integrity()
        self.check_price_validity()
        self.check_outlier_flags()
        self.check_corporate_action_boundaries()
        self.check_time_series_continuity()
        
        self.log(f"\n{'='*80}")
        self.log(f"📊 EXECUTIVE SUMMARY")
        self.log(f"{'='*80}\n")
        
        # Pass/fail/warning totals are derived by counting status emoji in
        # the rendered report text rather than tracking counters through
        # each check — simpler, but it means any future check that prints
        # one of these emoji outside a real status line would silently
        # skew the executive summary. Worth knowing before adding a check.
        report_text = '\n'.join(self.report_lines)
        passed = report_text.count('✅')
        failed = report_text.count('❌')
        warnings = report_text.count('⚠️')
        
        self.log(f"- **Total Checks Passed:** {passed}")
        self.log(f"- **Total Checks Failed:** {failed}")
        self.log(f"- **Total Warnings:** {warnings}")
        self.log(f"\n**Overall Status:** {'PASSED' if failed == 0 else 'FAILED'}")
        
        report_path = Path("docs/DATA_QUALITY_REPORT.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text('\n'.join(self.report_lines), encoding='utf-8')
        
        print(f"\n{'='*80}")
        print(f"✅ REPORT SAVED TO: {report_path}")
        print(f"{'='*80}")
        
        return report_path


def main():
    try:
        # These match config/quality_rules.yaml and the current file layout.
        # This standalone entry point exists for running the checker
        # without the top-level main.py orchestrator. Run it as a module
        # from the repo root (`python -m pipeline.data_quality`) — running
        # the file path directly fails on the `pipeline.config` import
        # since the repo root won't be on sys.path.
        master_csv = "data/raw/idx_daily_prices_2002_2007.csv"
        split_log_csv = "data/reference/corporate_action_split_log.csv"

        checker = DataQualityChecker(master_csv, split_log_csv)
        report_path = checker.run_all_checks()
        
        print(f"\n📄 Report saved to: {report_path}")
        
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        print("\n💡 Tip: Run the data scraping scripts first to generate the master CSV.")
        sys.exit(1)
    except pd.errors.EmptyDataError as e:
        print(f"❌ Data file is empty: {e}")
        sys.exit(1)
    except AssertionError as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
