# DATA QUALITY REPORT
**Dataset:** idx_daily_prices_2002_2007.csv
**Generated:** 2026-06-20 14:23:37
**Source:** `/home/claude/build/idx-data-pipeline/data/raw/idx_daily_prices_2002_2007.csv`
**Total Records:** 5,780
**Tickers:** ASII, BBCA, PTBA, TLKM, UNVR
**Date Range:** 2002-01-01 to 2007-12-28

================================================================================
📊 1. BASIC INTEGRITY
================================================================================

### 1.1 Row Count Per Ticker

| Ticker | Actual Rows | Expected Rows | Status | Delta |
|--------|-------------|---------------|--------|-------|
| ASII | 1,564 | 1,564 | ✅ | +0 |
| BBCA | 929 | 929 | ✅ | +0 |
| PTBA | 1,310 | 1,310 | ✅ | +0 |
| TLKM | 849 | 849 | ✅ | +0 |
| UNVR | 1,128 | 1,128 | ✅ | +0 |

**Status:** ✅ Row count validation PASSED

### 1.2 NaN Distribution Per Column Per Ticker

| Ticker | Column | NaN Count | Total Rows | NaN % |
|--------|--------|-----------|------------|-------|
| ASII | Liquidity_Score | 4 | 1,564 | 0.26% ✅ |
| BBCA | Liquidity_Score | 4 | 929 | 0.43% ✅ |
| PTBA | Liquidity_Score | 4 | 1,310 | 0.31% ✅ |
| TLKM | Liquidity_Score | 4 | 849 | 0.47% ✅ |
| UNVR | Liquidity_Score | 4 | 1,128 | 0.35% ✅ |

### 1.3 Data Type Validation

| Column | Expected Family | Actual Dtype | Status |
|--------|------------------|--------------|--------|
| date | datetime64[ns] | datetime64[us] | ✅ |
| Ticker | category | category | ✅ |
| Open | float32 | float32 | ✅ |
| High | float32 | float32 | ✅ |
| Low | float32 | float32 | ✅ |
| Close | float32 | float32 | ✅ |
| Close_Adj | float32 | float32 | ✅ |
| Volume | int64 | int64 | ✅ |
| Turnover | float64 | float64 | ✅ |
| Liquidity_Score | float32 | float32 | ✅ |
| Outlier_Flag | bool | bool | ✅ |
| source | category | category | ✅ |
| mc_eligible | bool | bool | ✅ |

**Status:** ✅ Data type validation PASSED


================================================================================
💰 2. PRICE VALIDITY
================================================================================

### 2.1 Non-Positive Price Check

- **Close <= 0:** 0 rows

- **Close_Adj <= 0:** 0 rows

**Status:** ✅ Price positivity check PASSED


### 2.2 High >= Low Validation

- **Total rows:** 5,780
- **Valid (High >= Low):** 5,780
- **Invalid (High < Low):** 0

**Status:** ✅ High/Low logic check PASSED


### 2.3 Close Within [Low, High] Range

- **Total rows:** 5,780
- **Valid (Close in range):** 5,778
- **Invalid (Close outside range):** 2

**Invalid rows by ticker:**
  - PTBA: 1 rows
  - TLKM: 1 rows

**First 10 invalid rows:**
| date                | Ticker   |   Low |   Close |   High |
|:--------------------|:---------|------:|--------:|-------:|
| 2007-02-02 00:00:00 | PTBA     |   630 |     625 |    630 |
| 2007-02-02 00:00:00 | TLKM     |  1920 |    1910 |   1940 |

**Status:** ❌ Close range check FAILED


================================================================================
🚨 3. OUTLIER FLAG AUDIT
================================================================================

### 3.1 Outlier Count Per Ticker

| Ticker | Total Rows | Outliers | Outlier % | Status |
|--------|------------|----------|-----------|--------|
| ASII | 1,564 | 0 | 0.00% | ✅ |
| BBCA | 929 | 0 | 0.00% | ✅ |
| PTBA | 1,310 | 0 | 0.00% | ✅ |
| TLKM | 849 | 0 | 0.00% | ✅ |
| UNVR | 1,128 | 0 | 0.00% | ✅ |

**Total Outliers:** 0 / 5,780 (0.00%)
**Status:** ✅


### 3.2 Top 5 Outliers Per Ticker (Earliest)


================================================================================
🔄 4. CORPORATE ACTION BOUNDARY CHECK
================================================================================

**Total split events:** 5

### 4.1 Price Behavior Around Split Ex-Dates


**Split Event: ASII @ 2004-03-01 (Ratio: 1:10.0)**

| date                | Ticker   |   Close |   Close_Adj | Position    |
|:--------------------|:---------|--------:|------------:|:------------|
| 2004-02-26 00:00:00 | ASII     |     555 |         555 | T-2         |
| 2004-02-27 00:00:00 | ASII     |     540 |         540 | T-1         |
| 2004-03-01 00:00:00 | ASII     |     535 |         535 | T (Ex-Date) |
| 2004-03-02 00:00:00 | ASII     |     570 |         570 | T+1         |
| 2004-03-03 00:00:00 | ASII     |     570 |         570 | T+2         |


**Split Event: BBCA @ 2004-05-28 (Ratio: 1:2.0)**

| date                | Ticker   |   Close |   Close_Adj | Position    |
|:--------------------|:---------|--------:|------------:|:------------|
| 2004-06-08 00:00:00 | BBCA     |   177.5 |       177.5 | T (Ex-Date) |
| 2004-06-09 00:00:00 | BBCA     |   180   |       180   | T+1         |
| 2004-06-10 00:00:00 | BBCA     |   180   |       180   | T+2         |


**Split Event: BBCA @ 2007-06-25 (Ratio: 1:2.0)**

| date                | Ticker   |   Close |   Close_Adj | Position    |
|:--------------------|:---------|--------:|------------:|:------------|
| 2007-06-21 00:00:00 | BBCA     |     535 |         535 | T-2         |
| 2007-06-22 00:00:00 | BBCA     |     535 |         535 | T-1         |
| 2007-06-25 00:00:00 | BBCA     |     535 |         535 | T (Ex-Date) |
| 2007-06-26 00:00:00 | BBCA     |     535 |         535 | T+1         |
| 2007-06-27 00:00:00 | BBCA     |     535 |         535 | T+2         |


**Split Event: TLKM @ 2004-08-23 (Ratio: 1:2.0)**

| date                | Ticker   |   Close |   Close_Adj | Position    |
|:--------------------|:---------|--------:|------------:|:------------|
| 2004-09-28 00:00:00 | TLKM     |     825 |         825 | T (Ex-Date) |
| 2004-09-29 00:00:00 | TLKM     |     825 |         825 | T+1         |
| 2004-09-30 00:00:00 | TLKM     |     830 |         830 | T+2         |


**Split Event: UNVR @ 2003-08-06 (Ratio: 1:10.0)**

| date                | Ticker   |   Close |   Close_Adj | Position    |
|:--------------------|:---------|--------:|------------:|:------------|
| 2003-09-03 00:00:00 | UNVR     |     675 |         675 | T (Ex-Date) |
| 2003-09-04 00:00:00 | UNVR     |     685 |         685 | T+1         |
| 2003-09-05 00:00:00 | UNVR     |     690 |         690 | T+2         |


**Status:** ⚠️ **MANUAL REVIEW REQUIRED** (check price jumps at split dates)


================================================================================
📅 5. TIME SERIES CONTINUITY
================================================================================

### 5.1 Date Gap Detection (>5 Business Days)

✅ **No significant date gaps found!**


**Status:** ⚠️


### 5.2 Trading Days Per Year Per Ticker

**Pivot Table: Trading Days × Year**

| Ticker   |   2002 |   2003 |   2004 |   2005 |   2006 |   2007 |
|:---------|-------:|-------:|-------:|-------:|-------:|-------:|
| ASII     |    261 |    261 |    262 |    260 |    260 |    260 |
| BBCA     |      0 |      0 |    149 |    260 |    260 |    260 |
| PTBA     |      7 |    261 |    262 |    260 |    260 |    260 |
| TLKM     |      0 |      0 |     69 |    260 |    260 |    260 |
| UNVR     |      0 |     86 |    262 |    260 |    260 |    260 |


**Expected:** ~244 trading days per year (IDX average)


**Anomalies (<200 or >260 days):** 15
**Status:** ❌


================================================================================
📊 EXECUTIVE SUMMARY
================================================================================

- **Total Checks Passed:** 34
- **Total Checks Failed:** 2
- **Total Warnings:** 2

**Overall Status:** FAILED