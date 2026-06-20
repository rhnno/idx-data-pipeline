# IDX Historical Data Pipeline (2002-2007)

A data engineering project: acquiring, cleaning, and validating daily OHLC
price history, dividend events, and reference rate data for five Indonesian
blue-chip stocks (ASII, BBCA, PTBA, TLKM, UNVR) across a period where
public data sources for Indonesian equities are fragmented, inconsistent in
format, and — as this project found out the hard way — not as complete as
they initially appear.

## Why this exists

I got curious about why investors like Munger and Buffett are so wary of
leverage, and wanted to explore the question myself with real historical
data instead of taking it on faith. That meant building a usable daily
price history for Indonesian stocks going back to 2002, which turned out to
be a much harder data acquisition and validation problem than the
analysis question itself. This repo is that data layer: the acquisition,
cleaning, and validation work, on its own, documented honestly.

The leverage-vs-no-leverage analysis itself isn't included here — it's a
separate, unfinished piece of work with its own unresolved issues, kept out
of this package on purpose. See `docs/DATA_LIMITATIONS.md` §6.

## What's actually in here

- **`config/sources.yaml`** — declares which price sources are enabled, per-ticker symbol mappings, retry/rate-limit behavior, and how multiple sources get merged. Add a ticker or source here, not in code.
- **`config/quality_rules.yaml`** — thresholds and expectations for the validation layer (expected trading days per ticker, outlier threshold, whether split-adjustment is applied).
- **`pipeline/adapters/`** — one file per price source, implementing a shared interface (`base.py`). `yahoo.py` is the only working one right now (see below). WSJ and Investing.com are registered in config as disabled, with the reason on record, rather than silently deleted.
- **`pipeline/orchestrator.py`** — fetches each ticker across all enabled sources and merges them **per date** (a lower-priority source fills in dates the higher-priority source is missing, instead of one source's full output winning and the rest being discarded — this was a real bug in the previous version).
- **`pipeline/dividend_scraper.py`**, **`pipeline/rate_scraper.py`**, **`pipeline/split_log_builder.py`** — dividend events, BI/SBI reference rates, and the corporate-action split log respectively.
- **`pipeline/data_quality.py`** — validation suite (row count integrity, price sanity, outlier audit, corporate-action boundary checks, time-series gap detection), thresholds loaded from `config/quality_rules.yaml`.

### Why WSJ and Investing.com are disabled, not "coming soon"

WSJ's historical-prices download endpoint has been retired and reliably
returns nothing — confirmed, not assumed. Investing.com's historical data
table is JavaScript-rendered and addressed by a descriptive URL slug
(`bank-central-asia`, not `bbca`), so the static-HTML scraping approach used
elsewhere in this pipeline can't reach it without a different approach
entirely. Both are left in `config/sources.yaml` with `enabled: false` and a
`disabled_reason`, specifically so the next person (or future me) doesn't
waste time re-discovering this. The dataset shipped here is 100%
Yahoo-sourced.

### A known limitation of this sandbox-built version

The adapter and merge logic are unit-tested with mocked responses, not a
live fetch — this environment's network egress doesn't allow
`finance.yahoo.com`. Run `python main.py scrape-prices` on a machine without
that restriction before trusting a fresh pull end-to-end.

## The actual finding

The original problem statement was "some of these stocks only have data
from 2002 onward, handle the gap." The real problem was bigger: BBCA and
TLKM have **no real daily trading data at all for 2002-2003**, with BBCA's
real coverage only starting June 2004 and TLKM's in September 2004 — almost
two and a half years later than the other three tickers. An earlier version
of this pipeline papered over the 2002 gap with synthetically generated
placeholder values and didn't flag them as synthetic in its own
documentation. That's been removed. The real gap is now documented and
checked automatically by `pipeline/data_quality.py` instead of hidden.

Full detail, including why split-adjustment was deliberately *not* applied
to the shipped price series (it was actively making the data wrong, not
fixing it), is in `docs/DATA_LIMITATIONS.md`. Read that before using this
data for anything.

## Validation

`docs/VALIDATION_REPORT.md` is the record of every test and check actually
run before this was packaged: 31/31 unit tests passing (including config
loading, adapter parsing, and the per-date merge logic), 26/31 automated
data quality checks passing (with the 5 failures explained, not hidden),
and a manual price-continuity check that justifies the split-adjustment
decision above. Reproduce it yourself:

```bash
pip install -r requirements.txt
pytest tests/
python main.py validate
```

## Usage

```bash
python main.py validate          # run data quality checks (no network needed)
python main.py scrape-prices      # re-run the price scraper
python main.py scrape-dividends   # re-run the dividend scraper
python main.py scrape-rates       # re-run the BI/SBI rate scraper
python main.py build-split-log    # rebuild the corporate action split log
```

## CI/CD

Every push runs three GitHub Actions jobs (`.github/workflows/ci.yml`):
`lint-and-security` (flake8 + bandit + pip-audit), `test` (pytest + data
validation), and `docker` (build the image and test it for real - non-root
check, test suite run inside the container, network-isolated failure-mode
check). The `docker` job only runs after the first two pass.

**Disclosure:** this repo's dev environment never had a Docker daemon
available, so locally this Dockerfile was only validated by simulating its
dependency install in an isolated venv (`tests/test_dockerfile_sim.sh`) -
that catches missing/undeclared dependencies (it's what caught a missing
`tabulate` package) but can't catch a broken Dockerfile instruction, a
COPY path error, or a permissions bug. The GitHub Actions `docker` job is
the first place this Dockerfile is actually built and run. Check the
Actions tab for current build status before assuming the container works.

Dependabot (`.github/dependabot.yml`) opens weekly PRs for pip and Docker
base image updates.

## Container

```bash
docker build -t idx-data-pipeline .
docker run --rm idx-data-pipeline                      # runs `validate` by default
docker run --rm idx-data-pipeline python main.py scrape-prices
```

See `tests/docker_build_test.txt` for the manual verification commands
(non-root check, in-container test run) the CI `docker` job automates.

## Project structure

```
.github/workflows/ci.yml   lint, security scan, tests, container build/test
.github/dependabot.yml     automated dependency update PRs
pipeline/    scraper, processing, and validation modules
data/raw/    daily OHLC price data
data/processed/  dividend events, rate data, ticker coverage summary
data/reference/   corporate action (split) log
tests/       unit tests (31/31 passing) + Dockerfile validation
docs/        DATA_LIMITATIONS.md, VALIDATION_REPORT.md
Dockerfile   container build, multi-stage, non-root
main.py      entry point
```
