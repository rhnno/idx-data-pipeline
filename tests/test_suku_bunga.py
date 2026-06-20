"""
Comprehensive test suite for suku_bunga_BI_scraper.py
Validates all project specifications and requirements
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rate_scraper import scrape_bi_rates, validate_financial_accuracy

def test_memory_efficiency():
    """Test: Code must use float32 instead of float64 for numeric columns"""
    print("\n" + "="*60)
    print("TEST 1: Memory Efficiency (float32 requirement)")
    print("="*60)
    
    df = scrape_bi_rates()
    
    float32_columns = ['SBI_Rate_Percentage', 'BI_Rate_Percentage', 'Risk_Free_Monthly']
    
    for col in float32_columns:
        dtype = str(df[col].dtype)
        assert dtype == 'float32', f"❌ {col} is {dtype}, expected float32"
        print(f"✅ {col}: {dtype}")
    
    # Check total memory usage (should be minimal for 8GB RAM constraint)
    memory_kb = df.memory_usage(deep=True).sum() / 1024
    print(f"\n✅ Total memory usage: {memory_kb:.2f} KB")
    assert memory_kb < 10, f"Memory usage too high: {memory_kb:.2f} KB"
    print("✅ Memory usage within acceptable range (< 10 KB)")
    
    return True

def test_historical_rate_validation():
    """Test: All hardcoded historical rates must be validated with tolerance-based assertions"""
    print("\n" + "="*60)
    print("TEST 2: Historical Rate Validation (SEKI BI data)")
    print("="*60)
    
    df = scrape_bi_rates()
    
    # Critical historical rates from SEKI BI
    critical_rates = {
        '2002-01': 17.00,  # Start of period
        '2005-11': 12.75,  # Peak crisis rate (BI Rate)
        '2005-08': 8.75,   # Crisis start
        '2005-09': 10.25,  # Aggressive hike
        '2005-10': 11.75,  # Post-fuel hike
    }
    
    tolerance = 0.1  # Strict tolerance for exact matches
    
    for date_str, expected_rate in critical_rates.items():
        # date_str is month-level ('YYYY-MM'); partial DatetimeIndex matching
        # returns every row in that month, not a single value, so take the
        # first available reading for the month instead of forcing to float.
        matched = df.loc[date_str, 'BI_Rate_Percentage']
        actual_rate = float(matched.iloc[0]) if hasattr(matched, 'iloc') else float(matched)
        diff = abs(actual_rate - expected_rate)
        
        assert diff <= tolerance, f"❌ {date_str}: {actual_rate:.2f}% vs expected {expected_rate:.2f}%"
        print(f"✅ {date_str}: {actual_rate:.2f}% (expected: {expected_rate:.2f}%)")
    
    print("\n✅ All critical historical rates validated")
    return True

def test_crisis_period_interpolation():
    """Test: Use 'time'-based interpolation for financial crisis periods"""
    print("\n" + "="*60)
    print("TEST 3: Crisis Period Interpolation (Aug-Nov 2005)")
    print("="*60)
    
    df = scrape_bi_rates()
    
    # Check that crisis period shows volatility, not artificial smoothing
    crisis_period = df.loc['2005-08':'2005-11', 'BI_Rate_Percentage']
    
    # Rate should increase significantly during crisis
    aug_rate = float(crisis_period.loc['2005-08-01'])
    nov_rate = float(crisis_period.loc['2005-11-01'])
    
    print(f"August 2005: {aug_rate:.2f}%")
    print(f"November 2005: {nov_rate:.2f}%")
    print(f"Increase: {nov_rate - aug_rate:.2f}%")
    
    assert nov_rate > aug_rate, "❌ Crisis period should show rate increase"
    assert (nov_rate - aug_rate) > 3.0, f"❌ Crisis volatility too smooth: only {nov_rate - aug_rate:.2f}% increase"
    
    print("✅ Crisis period shows appropriate volatility")
    
    # Check that interpolation method preserves abrupt changes
    # The jump from Aug (8.75) to Sep (10.25) should be visible
    sep_rate = float(df.loc['2005-09-01', 'BI_Rate_Percentage'])
    assert sep_rate > aug_rate, "❌ September should show rate hike"
    print(f"✅ September 2005: {sep_rate:.2f}% (shows tightening)")
    
    return True

def test_dataframe_structure():
    """Test: DataFrame must include specific columns for Sharpe Ratio calculation"""
    print("\n" + "="*60)
    print("TEST 4: DataFrame Structure (Sharpe Ratio requirements)")
    print("="*60)
    
    df = scrape_bi_rates()
    
    required_columns = [
        'Risk_Free_Monthly',
        'BI_Rate_Decimal',
        'SBI_Rate_Decimal',
        'BI_Rate_Percentage',
        'SBI_Rate_Percentage'
    ]
    
    for col in required_columns:
        assert col in df.columns, f"❌ Missing column: {col}"
        print(f"✅ Column present: {col}")
    
    # Verify decimal format (not percentage)
    bi_rate_dec = float(df.loc['2005-11-01', 'BI_Rate_Decimal'])
    bi_rate_pct = float(df.loc['2005-11-01', 'BI_Rate_Percentage'])
    
    expected_decimal = bi_rate_pct / 100
    assert abs(bi_rate_dec - expected_decimal) < 0.0001, \
        f"❌ Decimal format incorrect: {bi_rate_dec} vs {expected_decimal}"
    
    print(f"\n✅ Decimal format verified: {bi_rate_pct:.2f}% = {bi_rate_dec:.4f}")
    
    # Verify Risk_Free_Monthly calculation (BI Rate / 12 / 100)
    risk_free = float(df.loc['2005-11-01', 'Risk_Free_Monthly'])
    expected_risk_free = bi_rate_pct / 12 / 100
    
    assert abs(risk_free - expected_risk_free) < 0.000001, \
        f"❌ Risk_Free_Monthly incorrect: {risk_free} vs {expected_risk_free}"
    
    print(f"✅ Risk_Free_Monthly verified: {risk_free:.6f}")
    
    return True

def test_data_completeness():
    """Test: Complete 72-month period from Jan 2002 to Dec 2007"""
    print("\n" + "="*60)
    print("TEST 5: Data Completeness (72 months)")
    print("="*60)
    
    df = scrape_bi_rates()
    
    assert len(df) == 72, f"❌ Expected 72 rows, got {len(df)}"
    print(f"✅ Total rows: {len(df)}")
    
    # Check date range
    assert df.index[0] == pd.Timestamp('2002-01-01'), \
        f"❌ Start date incorrect: {df.index[0]}"
    assert df.index[-1] == pd.Timestamp('2007-12-01'), \
        f"❌ End date incorrect: {df.index[-1]}"
    
    print(f"✅ Date range: {df.index[0].strftime('%Y-%m')} to {df.index[-1].strftime('%Y-%m')}")
    
    # Check for NaN values
    assert not df.isnull().any().any(), "❌ Contains NaN values"
    print("✅ No NaN values in dataset")
    
    # Check for negative rates
    assert (df['BI_Rate_Percentage'] >= 0).all(), "❌ Contains negative rates"
    assert (df['SBI_Rate_Percentage'] >= 0).all(), "❌ Contains negative rates"
    print("✅ All rates are non-negative")
    
    return True

def test_error_handling():
    """Test: Error handling uses specific exception types"""
    print("\n" + "="*60)
    print("TEST 6: Error Handling (specific exceptions)")
    print("="*60)
    
    # Import the module and check exception types
    from pipeline import rate_scraper as suku_bunga_BI_scraper
    import inspect
    
    # Get the main execution block
    source = inspect.getsource(suku_bunga_BI_scraper)
    
    required_exceptions = [
        'pd.errors.EmptyDataError',
        'pd.errors.ParserError',
        'PermissionError',
        'AssertionError'
    ]
    
    for exc_type in required_exceptions:
        assert exc_type in source, f"❌ Missing exception handler: {exc_type}"
        print(f"✅ Exception handler present: {exc_type}")
    
    print("\n✅ All required exception types are handled")
    return True

def test_sharpe_ratio_export():
    """Test: Export format supports Sharpe Ratio calculation"""
    print("\n" + "="*60)
    print("TEST 7: Sharpe Ratio Export Format")
    print("="*60)
    
    from pipeline.rate_scraper import scrape_bi_rates, export_for_sharpe_calculation
    
    df = scrape_bi_rates()
    output_file = export_for_sharpe_calculation(df, 'test_sharpe_export.csv')
    
    # Verify file exists
    assert Path(output_file).exists(), f"❌ Export file not created: {output_file}"
    print(f"✅ Export file created: {output_file}")
    
    # Read and validate format
    export_df = pd.read_csv(output_file)
    
    required_cols = ['Date', 'BI_Rate_Annual_Pct', 'BI_Rate_Monthly_Dec', 'SBI_Rate_Annual_Pct']
    for col in required_cols:
        assert col in export_df.columns, f"❌ Missing column in export: {col}"
        print(f"✅ Export column present: {col}")
    
    assert len(export_df) == 72, f"❌ Export has {len(export_df)} rows, expected 72"
    print(f"✅ Export has correct row count: {len(export_df)}")
    
    # Clean up test file
    Path(output_file).unlink()
    print(f"✅ Cleaned up test file: {output_file}")
    
    return True

def run_all_tests():
    """Run all test suites"""
    print("\n" + "="*60)
    print("COMPREHENSIVE TEST SUITE FOR SUKU_BUNGA_BI_SCRAPER")
    print("="*60)
    
    tests = [
        ("Memory Efficiency", test_memory_efficiency),
        ("Historical Rate Validation", test_historical_rate_validation),
        ("Crisis Period Interpolation", test_crisis_period_interpolation),
        ("DataFrame Structure", test_dataframe_structure),
        ("Data Completeness", test_data_completeness),
        ("Error Handling", test_error_handling),
        ("Sharpe Ratio Export", test_sharpe_ratio_export),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = "✅ PASSED"
        except Exception as e:
            results[test_name] = f"❌ FAILED: {str(e)}"
            print(f"\n❌ Test '{test_name}' failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, result in results.items():
        print(f"{result} - {test_name}")
    
    passed = sum(1 for r in results.values() if "PASSED" in r)
    total = len(results)
    
    print("="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Code meets all project specifications.")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
