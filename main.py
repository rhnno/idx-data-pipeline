"""
IDX Historical Data Pipeline — entry point.

This pipeline scrapes, validates, and ships daily OHLC price data, dividend
events, BI/SBI reference rates, and corporate action (stock split) records
for five Indonesian blue-chip tickers (ASII, BBCA, PTBA, TLKM, UNVR),
2002-2007.

Usage
-----
    python main.py validate      # run data quality checks against the
                                  # shipped dataset (no network required,
                                  # always works, recommended first step)
    python main.py scrape-prices # re-run the price scraper (requires
                                  # network access; see docs/DATA_LIMITATIONS.md
                                  # for known source reliability caveats)
    python main.py scrape-dividends
    python main.py scrape-rates
    python main.py build-split-log

Read docs/DATA_LIMITATIONS.md before using this dataset for analysis — it
documents real coverage gaps per ticker and decisions made about price
adjustment that affect how the data should be interpreted.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_REFERENCE = ROOT / "data" / "reference"


def run_validate():
    from pipeline.data_quality import DataQualityChecker
    checker = DataQualityChecker(
        str(DATA_RAW / "idx_daily_prices_2002_2007.csv"),
        str(DATA_REFERENCE / "corporate_action_split_log.csv"),
    )
    checker.run_all_checks()


def run_scrape_prices():
    from pipeline.config import load_sources_config, load_quality_rules
    from pipeline.orchestrator import fetch_all
    from pipeline.sanitize import build_master_dataset

    cfg = load_sources_config()
    results = fetch_all(cfg)

    try:
        rules = load_quality_rules()
        outlier_threshold_pct = rules.outlier_threshold_pct
    except FileNotFoundError:
        outlier_threshold_pct = 50.0

    combined = build_master_dataset(results, outlier_threshold_pct=outlier_threshold_pct)
    out = DATA_RAW / "idx_daily_prices_2002_2007.csv"
    combined.to_csv(out, index=False)
    print(f"Saved {len(combined)} rows across {combined['Ticker'].nunique()} tickers to {out}")


def run_scrape_dividends():
    from pipeline.dividend_scraper import main as scrape_main
    scrape_main()


def run_scrape_rates():
    from pipeline.rate_scraper import scrape_bi_rates
    df = scrape_bi_rates()
    out = DATA_PROCESSED / "bi_sbi_rates_2002_2007.csv"
    df.to_csv(out)
    print(f"Saved {len(df)} rows to {out}")


def run_build_split_log():
    from pipeline.split_log_builder import build_cumulative_multiplier_lookup, export_split_log
    lookup = build_cumulative_multiplier_lookup()
    out = DATA_REFERENCE / "corporate_action_split_log.csv"
    export_split_log(lookup, str(out))
    print(f"Split log written to {out}")


COMMANDS = {
    "validate": run_validate,
    "scrape-prices": run_scrape_prices,
    "scrape-dividends": run_scrape_dividends,
    "scrape-rates": run_scrape_rates,
    "build-split-log": run_build_split_log,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=COMMANDS.keys())
    args = parser.parse_args()
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()
