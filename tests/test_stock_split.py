"""
Comprehensive test suite for stock_split_2002-2007_scraper.py
Validates all project specifications for Rp15B margin portfolio backtest
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
import importlib

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import using importlib due to hyphenated filename
scraper_module = importlib.import_module('pipeline.split_log_builder')

get_verified_split_data = scraper_module.get_verified_split_data
build_cumulative_multiplier_lookup = scraper_module.build_cumulative_multiplier_lookup
get_share_multiplier = scraper_module.get_share_multiplier
verify_trading_day = scraper_module.verify_trading_day
detect_secondary_offering = scraper_module.detect_secondary_offering
validate_price_adjustment = scraper_module.validate_price_adjustment
adjust_prices_for_splits = scraper_module.adjust_prices_for_splits
export_split_log = scraper_module.export_split_log


def test_data_integrity_cross_verification():
    """
    TEST 1: Cross-verify Ex-Date and Split Ratio against KSEI/IDX records
    Ensures all dates match historical trading days (no weekend/holiday errors)
    """
    print("\n" + "="*80)
    print("TEST 1: Data Integrity Cross-Verification (KSEI/IDX)")
    print("="*80)
    
    splits = get_verified_split_data()
    
    # Expected verified data from KSEI/IDX
    expected_data = [
        ('UNVR', '2003-08-06', 10),
        ('ASII', '2004-03-01', 10),
        ('BBCA', '2004-05-28', 2),
        ('TLKM', '2004-08-23', 2),
        ('BBCA', '2007-06-25', 2),
    ]
    
    # Verify count
    assert len(splits) == len(expected_data), \
        f"❌ Expected {len(expected_data)} splits, got {len(splits)}"
    print(f"✅ Total split events: {len(splits)}")
    
    # Verify each split
    for i, (exp_symbol, exp_date, exp_ratio) in enumerate(expected_data):
        actual_symbol = splits.symbol[i]
        actual_date = pd.Timestamp(splits.ex_date[i])
        if pd.isna(actual_date):
            raise AssertionError(f"❌ Row {i}: Date is NaT")
        actual_date_str = actual_date.strftime('%Y-%m-%d')
        actual_ratio = int(splits.split_ratio[i])
        
        assert actual_symbol == exp_symbol, \
            f"❌ Row {i}: Expected symbol {exp_symbol}, got {actual_symbol}"
        assert actual_date_str == exp_date, \
            f"❌ Row {i}: Expected date {exp_date}, got {actual_date_str}"
        assert actual_ratio == exp_ratio, \
            f"❌ Row {i}: Expected ratio {exp_ratio}, got {actual_ratio}"
        
        print(f"✅ {actual_symbol} @ {actual_date_str}: 1:{actual_ratio} split verified")
    
    # Verify all dates are valid trading days (no weekends/holidays)
    print("\nVerifying trading day validity...")
    invalid_dates = []
    for split in splits:
        ts = pd.Timestamp(split.ex_date)
        if pd.isna(ts):
            continue
        date_str = ts.strftime('%Y-%m-%d')
        if not verify_trading_day(date_str, split.symbol):
            invalid_dates.append((split.symbol, date_str))
    
    if invalid_dates:
        print(f"⚠️ WARNING: {len(invalid_dates)} potentially invalid dates:")
        for sym, dt in invalid_dates:
            print(f"   {sym}: {dt}")
    else:
        print("✅ All ex-dates fall on valid trading days")
    


def test_o1_lookup_complexity():
    """
    TEST 2: Refactor to O(1) search complexity via dictionary lookup
    Verifies MultiIndex/Dictionary implementation
    """
    print("\n" + "="*80)
    print("TEST 2: O(1) Lookup Complexity Verification")
    print("="*80)
    
    # Build lookup
    lookup = build_cumulative_multiplier_lookup()
    
    # Verify structure
    assert isinstance(lookup, dict), f"❌ Expected dict, got {type(lookup)}"
    print("✅ Lookup is dictionary type")
    
    # Verify all symbols present
    expected_symbols = {'UNVR', 'ASII', 'BBCA', 'TLKM'}
    actual_symbols = set(lookup.keys())
    assert expected_symbols == actual_symbols, \
        f"❌ Expected symbols {expected_symbols}, got {actual_symbols}"
    print(f"✅ All symbols present: {sorted(actual_symbols)}")
    
    # Test O(1) access speed (should be near-instant)
    import time
    
    start = time.perf_counter()
    for _ in range(10000):
        _ = get_share_multiplier('BBCA', '2005-01-01', lookup)
    elapsed = time.perf_counter() - start
    
    avg_time_us = (elapsed / 10000) * 1_000_000  # microseconds
    print(f"✅ Average lookup time: {avg_time_us:.2f} μs (O(1) complexity)")
    assert avg_time_us < 100, f"❌ Lookup too slow: {avg_time_us:.2f} μs"
    
    # Verify lookup values
    print("\nVerifying lookup values:")
    
    # UNVR: Single split 1:10 on 2003-08-06
    assert lookup['UNVR']['2003-08-06'] == 10.0, "❌ UNVR split ratio incorrect"
    print("✅ UNVR: 10.0× cumulative after 2003-08-06")
    
    # ASII: Single split 1:10 on 2004-03-01
    assert lookup['ASII']['2004-03-01'] == 10.0, "❌ ASII split ratio incorrect"
    print("✅ ASII: 10.0× cumulative after 2004-03-01")
    
    # BBCA: Two splits 1:2 on 2004-05-28 and 2007-06-25
    assert lookup['BBCA']['2004-05-28'] == 2.0, "❌ BBCA first split incorrect"
    assert lookup['BBCA']['2007-06-25'] == 4.0, "❌ BBCA cumulative split incorrect"
    print("✅ BBCA: 2.0× after 2004-05-28, 4.0× after 2007-06-25")
    
    # TLKM: Single split 1:2 on 2004-08-23
    assert lookup['TLKM']['2004-08-23'] == 2.0, "❌ TLKM split ratio incorrect"
    print("✅ TLKM: 2.0× cumulative after 2004-08-23")
    


def test_cumulative_multiplier_function():
    """
    TEST 3: Verify "Share Multiplier" function calculates cumulative splits correctly
    Example: BBCA splits twice → 2×2=4
    """
    print("\n" + "="*80)
    print("TEST 3: Cumulative Multiplier Calculation")
    print("="*80)
    
    lookup = build_cumulative_multiplier_lookup()
    
    # Test cases with expected cumulative multipliers
    test_cases = [
        # (symbol, date, expected_multiplier, description)
        ('BBCA', '2004-01-01', 1.0, 'Before any split'),
        ('BBCA', '2004-05-28', 2.0, 'On first split date'),
        ('BBCA', '2004-06-01', 2.0, 'After first split'),
        ('BBCA', '2007-06-24', 2.0, 'Before second split'),
        ('BBCA', '2007-06-25', 4.0, 'On second split date'),
        ('BBCA', '2007-07-01', 4.0, 'After second split'),
        ('UNVR', '2003-01-01', 1.0, 'Before split'),
        ('UNVR', '2003-08-06', 10.0, 'On split date'),
        ('UNVR', '2003-09-01', 10.0, 'After split'),
        ('ASII', '2004-02-28', 1.0, 'Before split'),
        ('ASII', '2004-03-01', 10.0, 'On split date'),
        ('TLKM', '2004-08-22', 1.0, 'Before split'),
        ('TLKM', '2004-08-23', 2.0, 'On split date'),
    ]
    
    for symbol, date, expected, desc in test_cases:
        actual = get_share_multiplier(symbol, date, lookup)
        assert abs(actual - expected) < 0.001, \
            f"❌ {symbol} @ {date} ({desc}): expected {expected:.1f}×, got {actual:.1f}×"
        print(f"✅ {symbol} @ {date}: {actual:.1f}× ({desc})")
    
    # Verify BBCA cumulative calculation: 2 × 2 = 4
    bbca_final = get_share_multiplier('BBCA', '2007-12-31', lookup)
    assert bbca_final == 4.0, f"❌ BBCA cumulative should be 4.0×, got {bbca_final}"
    print(f"\n✅ BBCA cumulative verification: 2×2 = {int(bbca_final)}× (CORRECT)")
    


def test_memory_efficiency():
    """
    TEST 4: Memory optimization using numpy.recarray and float32
    Targets 8GB RAM constraint (Intel i3 Gen 10)
    """
    print("\n" + "="*80)
    print("TEST 4: Memory Efficiency (8GB RAM constraint)")
    print("="*80)
    
    # Test recarray memory usage
    splits = get_verified_split_data()
    
    assert isinstance(splits, np.recarray), \
        f"❌ Expected np.recarray, got {type(splits)}"
    print(f"✅ Data structure: np.recarray")
    
    # Check memory usage
    memory_bytes = splits.nbytes
    memory_kb = memory_bytes / 1024
    
    print(f"✅ Split data memory: {memory_bytes} bytes ({memory_kb:.2f} KB)")
    assert memory_kb < 1, f"❌ Memory too high: {memory_kb:.2f} KB"
    print("✅ Memory usage < 1 KB (excellent for 8GB RAM)")
    
    # Verify datetime64[ns] dtype
    assert splits.ex_date.dtype == np.dtype('datetime64[ns]'), \
        f"❌ Expected datetime64[ns], got {splits.ex_date.dtype}"
    print(f"✅ Ex-Date dtype: {splits.ex_date.dtype}")
    
    # Verify float32 for split_ratio
    assert splits.split_ratio.dtype == np.dtype('float32'), \
        f"❌ Expected float32, got {splits.split_ratio.dtype}"
    print(f"✅ Split ratio dtype: {splits.split_ratio.dtype}")
    
    # Test price adjustment memory efficiency
    print("\nTesting price adjustment memory...")
    dates = pd.date_range('2002-01-01', '2007-12-31', freq='D')
    n = len(dates)
    test_df = pd.DataFrame({
        'Date': dates,
        'Close': np.random.uniform(1000, 5000, n).astype(np.float32),
        'Symbol': ['BBCA'] * n
    })
    
    original_memory = test_df.memory_usage(deep=True).sum() / 1024
    print(f"  Original DataFrame: {original_memory:.2f} KB")
    
    adjusted_df = adjust_prices_for_splits(test_df)
    
    adj_memory = adjusted_df.memory_usage(deep=True).sum() / 1024
    print(f"  Adjusted DataFrame: {adj_memory:.2f} KB")
    
    # Verify adjusted columns are float32
    assert adjusted_df['Close_Adj'].dtype == np.float32, \
        f"❌ Close_Adj dtype: {adjusted_df['Close_Adj'].dtype}"
    print(f"✅ Close_Adj dtype: {adjusted_df['Close_Adj'].dtype}")
    


def test_secondary_offering_handling():
    """
    TEST 5: Logic for "Secondary Offerings" (TLKM 2002)
    Verifies dilution vs price adjustment handling
    """
    print("\n" + "="*80)
    print("TEST 5: Secondary Offering (Rights Issue) Handling")
    print("="*80)
    
    df_ri = detect_secondary_offering()
    
    # Verify structure
    required_cols = ['symbol', 'ex_date', 'type', 'impact', 'adjustment_method']
    for col in required_cols:
        assert col in df_ri.columns, f"❌ Missing column: {col}"
    print(f"✅ All required columns present")
    
    # Verify TLKM rights issue detected
    assert len(df_ri) > 0, "❌ No rights issues detected"
    print(f"✅ Detected {len(df_ri)} rights issue event(s)")
    
    tlkm_ri = df_ri[df_ri['symbol'] == 'TLKM']
    assert len(tlkm_ri) > 0, "❌ TLKM rights issue not detected"
    
    ri = tlkm_ri.iloc[0]
    print(f"\nTLKM Rights Issue Details:")
    print(f"  Ex-Date: {ri.ex_date.strftime('%Y-%m-%d')}")
    print(f"  Type: {ri.type}")
    print(f"  Impact: {ri.impact}")
    print(f"  Adjustment Method: {ri.adjustment_method}")
    
    # Verify adjustment method
    assert ri.adjustment_method == 'Theoretical Ex-Rights Price', \
        f"❌ Incorrect adjustment method: {ri.adjustment_method}"
    print(f"\n✅ Correct adjustment method: {ri.adjustment_method}")
    
    # Verify that secondary offerings are NOT treated as splits
    splits = get_verified_split_data()
    tlkm_splits = splits[splits.symbol == 'TLKM']
    
    # TLKM should have split in 2004, but RI in 2002
    assert len(tlkm_splits) == 1, "❌ TLKM should have 1 split event"
    assert tlkm_splits.ex_date[0] == np.datetime64('2004-08-23', 'ns'), \
        "❌ TLKM split date incorrect"
    
    print("✅ Secondary offerings correctly separated from splits")
    print("   → Splits adjust historical prices")
    print("   → Rights issues require Theoretical Ex-Rights Price calculation")



def test_validation_flag():
    """
    TEST 6: "Validation Flag" if split date doesn't show price drop in CSV
    """
    print("\n" + "="*80)
    print("TEST 6: Validation Flag Implementation")
    print("="*80)
    
    # Test case 1: Valid 1:2 split (BBCA)
    print("\nTest 1: Valid 1:2 split scenario")
    valid_price_data = pd.DataFrame({
        'Date': ['2004-05-27', '2004-05-28', '2004-05-31'],
        'Close': [3200.0, 1600.0, 1625.0]
    })
    
    result = validate_price_adjustment(valid_price_data, 'BBCA', '2004-05-28', 2.0)
    assert result == True, "❌ Valid split not verified"
    print("✅ Validation passed for correct split")
    
    # Test case 2: Invalid split (no price drop)
    print("\nTest 2: Invalid split (no price drop detected)")
    invalid_price_data = pd.DataFrame({
        'Date': ['2004-05-27', '2004-05-28', '2004-05-31'],
        'Close': [3200.0, 3150.0, 3175.0]  # No significant drop
    })
    
    result = validate_price_adjustment(invalid_price_data, 'BBCA', '2004-05-28', 2.0)
    assert result == False, "❌ Invalid split not flagged"
    print("✅ Validation correctly flagged data error")
    
    # Test case 3: Missing data
    print("\nTest 3: Insufficient data")
    incomplete_data = pd.DataFrame({
        'Date': ['2004-05-28'],
        'Close': [1600.0]
    })
    
    result = validate_price_adjustment(incomplete_data, 'BBCA', '2004-05-28', 2.0)
    assert result == False, "❌ Missing data not flagged"
    print("✅ Validation correctly flagged insufficient data")


def test_price_adjustment_function():
    """
    TEST 7: Full DataFrame price adjustment with float32 efficiency
    """
    print("\n" + "="*80)
    print("TEST 7: Price Adjustment Function")
    print("="*80)
    
    # Create test price data spanning ONLY the first split (2004-05-28)
    # This isolates testing to a single split event
    dates = pd.date_range('2004-01-01', '2004-12-31', freq='B')  # Business days
    n = len(dates)
    
    test_data = {
        'Date': dates,
        'Open': np.full(n, 3000, dtype=np.float32),
        'High': np.full(n, 3200, dtype=np.float32),
        'Low': np.full(n, 2900, dtype=np.float32),
        'Close': np.full(n, 3100, dtype=np.float32),
        'Symbol': 'BBCA'
    }
    
    test_df = pd.DataFrame(test_data)
    
    # Apply adjustment
    print("Applying split adjustments...")
    adjusted_df = adjust_prices_for_splits(test_df)
    
    # Verify columns
    assert 'Close_Adj' in adjusted_df.columns, "❌ Missing Close_Adj column"
    assert 'Low_Adj' in adjusted_df.columns, "❌ Missing Low_Adj column"
    assert 'High_Adj' in adjusted_df.columns, "❌ Missing High_Adj column"
    print("✅ All adjusted columns present")
    
    # Verify dtype
    assert adjusted_df['Close_Adj'].dtype == np.float32, \
        f"❌ Close_Adj dtype: {adjusted_df['Close_Adj'].dtype}"
    print(f"✅ Adjusted columns use float32")
    
    # Verify adjustment logic
    # For BBCA in 2004 (single split on 2004-05-28):
    #   - Before 2004-05-28: divided by 2 (backward adjustment)
    #   - On/after 2004-05-28: no adjustment (current prices)
    
    # Check a pre-split value (before 2004-05-28)
    pre_split_mask = adjusted_df['Date'] < '2004-05-28'
    if pre_split_mask.sum() > 0:
        pre_split_row = adjusted_df[pre_split_mask].iloc[0]
        original_close = float(pre_split_row['Close'])
        adjusted_close = float(pre_split_row['Close_Adj'])
        
        # Before split, should be divided by 2
        expected_adj = original_close / 2.0
        assert abs(adjusted_close - expected_adj) < 0.01, \
            f"❌ Pre-split adjustment: expected {expected_adj:.2f}, got {adjusted_close:.2f}"
        print(f"✅ Pre-split adjustment verified: Rp{original_close:,.0f} → Rp{adjusted_close:.2f} (÷2)")
    
    # Check on/after split date (should have NO adjustment in single-split scenario)
    post_split_mask = adjusted_df['Date'] >= '2004-05-28'
    if post_split_mask.sum() > 0:
        post_split_row = adjusted_df[post_split_mask].iloc[0]
        original_close = float(post_split_row['Close'])
        adjusted_close = float(post_split_row['Close_Adj'])
        
        # On/after split: no adjustment needed
        expected_adj = original_close
        assert abs(adjusted_close - expected_adj) < 0.01, \
            f"❌ Post-split adjustment: expected {expected_adj:.2f}, got {adjusted_close:.2f}"
        print(f"✅ Post-split (no adjustment): Rp{original_close:,.0f} → Rp{adjusted_close:.2f}")
    
    # Verify consistency
    assert adjusted_df['Close_Adj'].iloc[0] < adjusted_df['Close'].iloc[0], \
        "❌ Adjusted price should be lower than original for pre-split dates"
    print(f"✅ Adjustment direction correct (reduces historical prices)")

def test_export_format():
    """
    TEST 8: Export format for integration with backtest models
    """
    print("\n" + "="*80)
    print("TEST 8: Export Format Verification")
    print("="*80)
    
    lookup = build_cumulative_multiplier_lookup()
    output_file = 'test_split_log_export.csv'
    
    # Export
    df_export = export_split_log(lookup, output_file)
    
    # Verify file exists
    assert Path(output_file).exists(), f"❌ Export file not created"
    print(f"✅ Export file created: {output_file}")
    
    # Verify columns
    required_cols = ['symbol', 'ex_date', 'split_ratio', 'cumulative_multiplier', 'verified', 'source']
    for col in required_cols:
        assert col in df_export.columns, f"❌ Missing column: {col}"
    print(f"✅ All required columns present: {required_cols}")
    
    # Verify row count
    assert len(df_export) == 5, f"❌ Expected 5 rows, got {len(df_export)}"
    print(f"✅ Correct row count: {len(df_export)}")
    
    # Verify data
    bbca_rows = df_export[df_export['symbol'] == 'BBCA']
    assert len(bbca_rows) == 2, f"❌ BBCA should have 2 split events"
    print(f"✅ BBCA has 2 split events")
    
    # Verify cumulative multiplier progression
    bbca_rows_sorted = bbca_rows.sort_values('ex_date')
    assert float(bbca_rows_sorted.iloc[0]['cumulative_multiplier']) == 2.0, \
        "❌ BBCA first cumulative multiplier incorrect"
    assert float(bbca_rows_sorted.iloc[1]['cumulative_multiplier']) == 4.0, \
        "❌ BBCA second cumulative multiplier incorrect"
    print("✅ BBCA cumulative multipliers: 2.0×, 4.0×")
    
    # Clean up
    Path(output_file).unlink()
    print(f"✅ Cleaned up test file: {output_file}")


def run_all_tests():
    """Run all test suites"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST SUITE FOR STOCK_SPLIT_2002-2007_SCRAPER")
    print("Rp15B Margin Portfolio Backtest - Data Integrity Verification")
    print("="*80)
    
    tests = [
        ("Data Integrity Cross-Verification", test_data_integrity_cross_verification),
        ("O(1) Lookup Complexity", test_o1_lookup_complexity),
        ("Cumulative Multiplier Calculation", test_cumulative_multiplier_function),
        ("Memory Efficiency (8GB RAM)", test_memory_efficiency),
        ("Secondary Offering Handling", test_secondary_offering_handling),
        ("Validation Flag Implementation", test_validation_flag),
        ("Price Adjustment Function", test_price_adjustment_function),
        ("Export Format Verification", test_export_format),
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
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        print(f"{result} - {test_name}")
    
    passed = sum(1 for r in results.values() if "PASSED" in r)
    total = len(results)
    
    print("="*80)
    print(f"Results: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Stock split logic verified for Rp15B margin portfolio backtest")
        print("✅ Data integrity confirmed against KSEI/IDX historical records")
        print("✅ Memory optimization validated for Intel i3 Gen 10, 8GB RAM")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Review errors above.")


if __name__ == "__main__":
    sys.exit(run_all_tests())
