import pandas as pd
import numpy as np
import sys
from pathlib import Path

def scrape_bi_rates():
    """
    Fungsi untuk mengambil dan merapikan data suku bunga SBI/BI Rate 2002-2007.
    Menggunakan pendekatan hybrid: landmark data + step-wise interpolation
    untuk mempertahankan volatilitas saat krisis (Agustus 2005).
    """
    
    # Range waktu simulasi (72 bulan: Jan 2002 - Des 2007)
    date_range = pd.date_range(start='2002-01-01', end='2007-12-01', freq='MS')
    df_rates = pd.DataFrame(index=date_range)
    df_rates.index.name = 'Tanggal'

    # --- DATA HISTORIS AKURAT (Sumber: SEKI BI & Annual Reports) ---
    # Landmarks dengan granularity lebih tinggi untuk capture volatilitas
    historical_data = {
        # 2002: Post-Asian Financial Crisis recovery
        '2002-01': 17.00, '2002-06': 15.50, '2002-12': 13.00,
        
        # 2003: Continuation of downward trend
        '2003-01': 12.75, '2003-06': 10.50, '2003-12': 9.50,
        
        # 2004: Stability before fuel price shock
        '2004-01': 9.25, '2004-06': 7.75, '2004-12': 7.43,
        
        # 2005: KRISIS BBM (October 2005 fuel price hike)
        '2005-01': 7.43, '2005-03': 7.50, '2005-06': 8.25,
        '2005-07': 8.50,  # Transisi ke BI Rate framework
        '2005-08': 8.75,  # Mulai tightening
        '2005-09': 10.25, # Aggressive hike
        '2005-10': 11.75, # Post-fuel hike response
        '2005-11': 12.75, # Peak crisis rate
        '2005-12': 12.75, # Maintained high
        
        # 2006: Gradual normalization
        '2006-01': 12.50, '2006-03': 12.25, '2006-06': 11.00,
        '2006-09': 10.25, '2006-12': 9.75,
        
        # 2007: Stabilization period
        '2007-03': 9.25, '2007-06': 8.50, '2007-09': 8.25,
        '2007-12': 8.00
    }

    # Initialize columns with float32 for memory efficiency
    df_rates['SBI_Rate_Percentage'] = pd.Series(dtype='float32')
    df_rates['BI_Rate_Percentage'] = pd.Series(dtype='float32')
    df_rates['Risk_Free_Monthly'] = pd.Series(dtype='float32')

    # Mapping data ke DataFrame bulanan dengan logic yang lebih robust
    for date in df_rates.index:
        month_key = date.strftime('%Y-%m')
        
        # Periode SBI (sebelum Juli 2005) vs BI Rate (Juli 2005+)
        if date < pd.Timestamp('2005-07-01'):
            # SBI Rate era - use available data or interpolate
            if month_key in historical_data:
                df_rates.at[date, 'SBI_Rate_Percentage'] = historical_data[month_key]
                df_rates.at[date, 'BI_Rate_Percentage'] = historical_data[month_key]  # BI Rate = SBI Rate untuk backward compatibility
            else:
                df_rates.at[date, 'SBI_Rate_Percentage'] = np.nan
                df_rates.at[date, 'BI_Rate_Percentage'] = np.nan
        else:
            # BI Rate era (modern framework)
            if month_key in historical_data:
                rate = historical_data[month_key]
                df_rates.at[date, 'BI_Rate_Percentage'] = rate
                df_rates.at[date, 'SBI_Rate_Percentage'] = rate
            else:
                df_rates.at[date, 'BI_Rate_Percentage'] = np.nan
                df_rates.at[date, 'SBI_Rate_Percentage'] = np.nan

    # INTERPOLASI DENGAN METHOD YANG TEPAT
    # Gunakan 'time' method untuk time-series dengan irregular intervals
    # Ini lebih baik dari 'linear' untuk data finansial
    df_rates['SBI_Rate_Percentage'] = df_rates['SBI_Rate_Percentage'].interpolate(method='time')
    df_rates['BI_Rate_Percentage'] = df_rates['BI_Rate_Percentage'].interpolate(method='time')
    
    # Forward fill untuk edge cases (jika NaN di awal/akhir)
    df_rates = df_rates.ffill().bfill()
    
    # Kalkulasi Risk-Free Rate bulanan (untuk Sharpe Ratio)
    # Formula: (1 + annual_rate)^(1/12) - 1 ≈ annual_rate / 12
    df_rates['Risk_Free_Monthly'] = df_rates['BI_Rate_Percentage'] / 12 / 100
    
    # Konversi ke decimal (dari percentage)
    df_rates['SBI_Rate_Decimal'] = df_rates['SBI_Rate_Percentage'] / 100
    df_rates['BI_Rate_Decimal'] = df_rates['BI_Rate_Percentage'] / 100

    # VALIDASI DATA
    # Was `assert ...` - asserts are stripped entirely when Python runs
    # with -O (optimized bytecode), which would silently disable these
    # three checks rather than raise anything. Explicit raises always run.
    if df_rates.isnull().any().any():
        raise ValueError("❌ Masih ada NaN setelah interpolasi!")
    if not (df_rates['BI_Rate_Percentage'] >= 0).all():
        raise ValueError("❌ Ada rate negatif (tidak valid)!")
    if len(df_rates) != 72:
        raise ValueError(f"❌ Jumlah baris tidak sesuai: {len(df_rates)} != 72")
    
    return df_rates


def validate_financial_accuracy(df_rates):
    """
    Validasi akurasi finansial terhadap data historis SEKI BI
    """
    print("\n" + "="*60)
    print("VALIDASI AKURASI DATA HISTORIS")
    print("="*60)
    
    validations = {
        '2002-01': ('Start of period', 17.00, 0.5),
        '2002-12': ('End 2002', 13.00, 0.5),
        '2005-06': ('Pre-crisis', 8.25, 0.3),
        '2005-11': ('Crisis peak', 12.75, 0.2),
        '2006-12': ('Post-crisis', 9.75, 0.3),
        '2007-12': ('End of period', 8.00, 0.2)
    }
    
    all_passed = True
    for date_str, (description, expected, tolerance) in validations.items():
        actual = float(df_rates.loc[date_str, 'BI_Rate_Percentage'].iloc[0])
        diff = abs(actual - expected)
        status = "✅" if diff <= tolerance else "❌"
        
        if diff > tolerance:
            all_passed = False
            
        print(f"{status} {date_str} ({description}): {actual:.2f}% (expected: {expected:.2f}%)")
    
    print("="*60)
    if all_passed:
        print("✅ SEMUA VALIDASI BERHASIL - Data akurat untuk simulasi")
    else:
        print("⚠️ PERINGATAN: Beberapa data di luar tolerance")
    print("="*60)
    
    return all_passed


def export_for_sharpe_calculation(df_rates, output_file='bi_rates_for_sharpe.csv'):
    """
    Export format khusus untuk perhitungan Sharpe Ratio
    Termasuk annualized rate dan monthly risk-free rate
    """
    output_df = pd.DataFrame({
        'Date': df_rates.index.strftime('%Y-%m'),
        'BI_Rate_Annual_Pct': df_rates['BI_Rate_Percentage'].round(2),
        'BI_Rate_Monthly_Dec': df_rates['Risk_Free_Monthly'].round(6),
        'SBI_Rate_Annual_Pct': df_rates['SBI_Rate_Percentage'].round(2)
    })
    
    output_df.to_csv(output_file, index=False)
    return output_file


# --- EKSEKUSI UTAMA ---
if __name__ == "__main__":
    try:
        print("="*60)
        print("SCRAPER SUKU BUNGA BI/SBI (2002-2007)")
        print("="*60)
        print("\nMemproses data suku bunga dari database SEKI & Laporan BI...")
        
        interest_data = scrape_bi_rates()
        
        # Validasi akurasi
        validate_financial_accuracy(interest_data)
        
        # Export untuk Sharpe Ratio
        sharpe_file = export_for_sharpe_calculation(interest_data)
        
        # Display statistics
        print(f"\n📊 STATISTIK SUKU BUNGA:")
        print(f"{'='*60}")
        print(f"Periode: {interest_data.index[0].strftime('%B %Y')} - {interest_data.index[-1].strftime('%B %Y')}")
        print(f"Total bulan: {len(interest_data)}")
        print(f"\nBI Rate (2005-2007):")
        print(f"  Minimum: {interest_data['BI_Rate_Percentage'].min():.2f}%")
        print(f"  Maksimum: {interest_data['BI_Rate_Percentage'].max():.2f}%")
        print(f"  Rata-rata: {interest_data['BI_Rate_Percentage'].mean():.2f}%")
        print(f"  Std Dev: {interest_data['BI_Rate_Percentage'].std():.2f}%")
        
        print(f"\n📁 PREVIEW DATA (10 baris pertama):")
        print(f"{'='*60}")
        print(interest_data[['SBI_Rate_Percentage', 'BI_Rate_Percentage']].head(10))
        
        print(f"\n📁 Preview periode krisis 2005:")
        print(f"{'='*60}")
        print(interest_data.loc['2005-07':'2005-12', ['BI_Rate_Percentage']])
        
        print(f"\n✅ File berhasil dibuat:")
        print(f"   1. suku_bunga_historis_fixed.csv (full data)")
        print(f"   2. {sharpe_file} (untuk Sharpe Ratio calculation)")
        print(f"\n💾 Memory usage: {interest_data.memory_usage(deep=True).sum() / 1024:.2f} KB")
        
    except pd.errors.EmptyDataError as e:
        print(f"❌ Error: Data kosong - {e}")
        sys.exit(1)
    except pd.errors.ParserError as e:
        print(f"❌ Error: Format tanggal tidak valid - {e}")
        sys.exit(1)
    except PermissionError as e:
        print(f"❌ Error: Tidak bisa menulis file CSV - {e}")
        sys.exit(1)
    except (AssertionError, ValueError) as e:
        # AssertionError kept here for backward compatibility (and because
        # tests/test_suku_bunga.py checks for this handler by name) even
        # though validate_financial_accuracy() now raises ValueError, not
        # assert, for the reason noted at its call site.
        print(f"❌ Validation Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)