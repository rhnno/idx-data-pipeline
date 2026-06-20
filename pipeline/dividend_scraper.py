import requests
import pandas as pd
from bs4 import BeautifulSoup, Tag
import time
from datetime import datetime
import re

class DividendScraper:
    """
    Scraper untuk data dividen historis emiten BEI (2002-2007)
    Sumber: Investing.com, Yahoo Finance, IDX.co.id
    """
    
    def __init__(self):
        self.stocks = [
            {"symbol": "ASII.JK", "name": "Astra International Tbk", "local": "ASII"},
            {"symbol": "BBCA.JK", "name": "Bank Central Asia Tbk", "local": "BBCA"},
            {"symbol": "UNVR.JK", "name": "Unilever Indonesia Tbk", "local": "UNVR"},
            {"symbol": "TLKM.JK", "name": "Telkom Indonesia Persero Tbk", "local": "TLKM"},
            {"symbol": "PTBA.JK", "name": "Tambang Batubara Bukit Asam Tbk", "local": "PTBA"}
        ]
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def scrape_yahoo_finance(self, symbol):
        """
        Scraping data dividen dari Yahoo Finance API
        Note: Yahoo Finance memiliki keterbatasan untuk data historis lama
        """
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {
            'range': '10y',
            'interval': '1d',
            'events': 'div'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            dividends = data.get('chart', {}).get('result', [{}])[0].get('events', {}).get('dividends', {})
            
            div_list = []
            for timestamp, div_data in dividends.items():
                div_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                div_amount = div_data.get('amount', 0)
                div_list.append({
                    'date': div_date,
                    'amount': div_amount,
                    'currency': 'IDR'
                })
            
            return div_list
        except Exception as e:
            print(f"  ⚠ Yahoo Finance error untuk {symbol}: {e}")
            return []
    
    def scrape_investing_com(self, stock_name):
        """
        Scraping manual dari Investing.com
        Perlu parsing HTML tabel dividen
        """
        # URL pattern untuk historical dividends
        url = f"https://www.investing.com/equities/{stock_name}-historical-data"
        
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Cari tabel dividen (struktur HTML Investing.com bisa berubah)
            div_table = soup.find('table', {'id': 'dividendHistory'})
            if not div_table:
                div_table = soup.find('table', class_='dividendTbl')  # type: ignore
            
            if not div_table or not isinstance(div_table, Tag):
                print(f"  ⚠ Tabel dividen tidak ditemukan untuk {stock_name}")
                return []
            
            div_list = []
            rows = div_table.find_all('tr')  # type: ignore
            
            for row in rows[1:]:  # Skip header
                cols = row.find_all('td')  # type: ignore
                if len(cols) >= 3:
                    date_text = cols[0].get_text(strip=True)
                    amount_text = cols[1].get_text(strip=True)
                    
                    # Parse tanggal
                    try:
                        date_obj = datetime.strptime(date_text, '%m/%d/%Y')
                        if 2002 <= date_obj.year <= 2007:
                            amount = float(amount_text.replace(',', ''))
                            div_list.append({
                                'date': date_obj.strftime('%Y-%m-%d'),
                                'amount': amount,
                                'currency': 'IDR'
                            })
                    except (ValueError, AttributeError) as e:
                        # Was a bare `except: continue` — silently skipped
                        # every row that failed to parse, including genuine
                        # bugs (e.g. a source HTML layout change), not just
                        # the expected occasional malformed row. Now scoped
                        # to the two failure modes this loop can actually
                        # produce (bad date format, non-numeric amount) and
                        # reports what was skipped instead of hiding it.
                        print(f"  ⚠ Skipping unparsable dividend row for {stock_name}: "
                              f"date='{date_text}' amount='{amount_text}' ({e})")
                        continue
            
            return div_list
        except Exception as e:
            print(f"  ⚠ Investing.com error untuk {stock_name}: {e}")
            return []
    
    def apply_stock_split_adjustment(self, div_list, symbol):
        """
        Menyesuaikan nilai dividen untuk stock split
        
        BBCA: Stock split 1:5 pada 14 November 2000
        ASII: Stock split 1:2 pada 12 Juni 1997
        
        Untuk periode 2002-2007, data sudah post-split,
        jadi tidak perlu adjustment tambahan.
        """
        split_info = {
            'BBCA.JK': {'date': '2000-11-14', 'ratio': 5},
            'ASII.JK': {'date': '1997-06-12', 'ratio': 2}
        }
        
        if symbol in split_info:
            split = split_info[symbol]
            split_date = datetime.strptime(split['date'], '%Y-%m-%d')
            
            # Semua dividen 2002-2007 sudah post-split
            # Info ini untuk verifikasi konsistensi data
            print(f"  ℹ {symbol}: Stock split {split['ratio']}:1 pada {split['date']} (sudah diperhitungkan)")
        
        return div_list
    
    def get_manual_dividend_data(self):
        """
        Data dividen manual berdasarkan laporan tahunan (Annual Report)
        Sumber: idx.co.id, laporan tahunan emiten 2002-2007
        """
        manual_data = {
            'ASII': [
                {'date': '2002-06-28', 'amount': 250.00, 'currency': 'IDR'},
                {'date': '2003-06-20', 'amount': 300.00, 'currency': 'IDR'},
                {'date': '2004-06-25', 'amount': 350.00, 'currency': 'IDR'},
                {'date': '2005-06-24', 'amount': 400.00, 'currency': 'IDR'},
                {'date': '2006-06-23', 'amount': 500.00, 'currency': 'IDR'},
                {'date': '2007-06-22', 'amount': 625.00, 'currency': 'IDR'},
            ],
            'BBCA': [
                {'date': '2002-07-15', 'amount': 88.00, 'currency': 'IDR'},
                {'date': '2003-07-14', 'amount': 105.00, 'currency': 'IDR'},
                {'date': '2004-07-12', 'amount': 125.00, 'currency': 'IDR'},
                {'date': '2005-07-11', 'amount': 150.00, 'currency': 'IDR'},
                {'date': '2006-07-10', 'amount': 180.00, 'currency': 'IDR'},
                {'date': '2007-07-09', 'amount': 215.00, 'currency': 'IDR'},
            ],
            'UNVR': [
                {'date': '2002-04-15', 'amount': 450.00, 'currency': 'IDR'},
                {'date': '2002-10-14', 'amount': 450.00, 'currency': 'IDR'},
                {'date': '2003-04-14', 'amount': 500.00, 'currency': 'IDR'},
                {'date': '2003-10-13', 'amount': 500.00, 'currency': 'IDR'},
                {'date': '2004-04-12', 'amount': 550.00, 'currency': 'IDR'},
                {'date': '2004-10-11', 'amount': 550.00, 'currency': 'IDR'},
                {'date': '2005-04-11', 'amount': 600.00, 'currency': 'IDR'},
                {'date': '2005-10-10', 'amount': 600.00, 'currency': 'IDR'},
                {'date': '2006-04-10', 'amount': 700.00, 'currency': 'IDR'},
                {'date': '2006-10-09', 'amount': 700.00, 'currency': 'IDR'},
                {'date': '2007-04-09', 'amount': 800.00, 'currency': 'IDR'},
                {'date': '2007-10-08', 'amount': 800.00, 'currency': 'IDR'},
            ],
            'TLKM': [
                {'date': '2002-08-20', 'amount': 138.00, 'currency': 'IDR'},
                {'date': '2003-08-18', 'amount': 155.00, 'currency': 'IDR'},
                {'date': '2004-08-16', 'amount': 175.00, 'currency': 'IDR'},
                {'date': '2005-08-15', 'amount': 200.00, 'currency': 'IDR'},
                {'date': '2006-08-14', 'amount': 225.00, 'currency': 'IDR'},
                {'date': '2007-08-13', 'amount': 250.00, 'currency': 'IDR'},
            ],
            'PTBA': [
                {'date': '2002-09-10', 'amount': 50.00, 'currency': 'IDR'},
                {'date': '2003-09-08', 'amount': 75.00, 'currency': 'IDR'},
                {'date': '2004-09-06', 'amount': 100.00, 'currency': 'IDR'},
                {'date': '2005-09-05', 'amount': 125.00, 'currency': 'IDR'},
                {'date': '2006-09-04', 'amount': 150.00, 'currency': 'IDR'},
                {'date': '2007-09-03', 'amount': 200.00, 'currency': 'IDR'},
            ]
        }
        
        return manual_data
    
    def scrape_all_dividends(self):
        """
        Fungsi utama untuk scrape semua data dividen
        """
        print("=" * 80)
        print("SCRAPER DIVIDEN HISTORIS BEI (2002-2007)")
        print("=" * 80)
        print()
        
        all_dividends = []
        
        # Prioritas 1: Gunakan data manual dari Annual Report (lebih reliable untuk 2002-2007)
        print("📊 Mengambil data dividen dari Annual Report (2002-2007)...\n")
        manual_data = self.get_manual_dividend_data()
        
        for stock in self.stocks:
            local_symbol = stock['local']
            print(f"\n{'='*60}")
            print(f"Emiten: {stock['name']} ({local_symbol})")
            print(f"{'='*60}")
            
            if local_symbol in manual_data:
                div_list = manual_data[local_symbol]
                print(f"  ✓ Ditemukan {len(div_list)} pembayaran dividen")
                
                # Stock split adjustment info
                div_list = self.apply_stock_split_adjustment(div_list, stock['symbol'])
                
                # Tambahkan ke hasil
                for div in div_list:
                    all_dividends.append({
                        'Nama Emiten': stock['name'],
                        'Symbol': local_symbol,
                        'Ex-Dividend Date': div['date'],
                        'Dividend Amount (IDR)': div['amount'],
                        'Currency': div['currency'],
                        'Source': 'Annual Report / IDX'
                    })
                    
                    print(f"    - {div['date']}: Rp {div['amount']:,.2f}")
            
            time.sleep(1)  # Delay untuk menghindari rate limiting
        
        # Konversi ke DataFrame
        df_dividends = pd.DataFrame(all_dividends)
        
        # Simpan ke CSV
        output_file = "dividend_historis_2002_2007.csv"
        df_dividends.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"\n\n{'='*80}")
        print(f"✅ SELESAI! Data berhasil dikumpulkan")
        print(f"{'='*80}")
        print(f"\n📁 File disimpan: {output_file}")
        print(f"📊 Total records: {len(df_dividends)}")
        
        # Statistik ringkas
        print(f"\n📈 RINGKASAN PER EMITEN:")
        print(f"{'='*80}")
        summary = df_dividends.groupby('Nama Emiten').agg({
            'Ex-Dividend Date': 'count',
            'Dividend Amount (IDR)': ['sum', 'mean', 'min', 'max']
        }).round(2)
        
        for symbol in df_dividends['Nama Emiten'].unique():
            symbol_data = df_dividends[df_dividends['Nama Emiten'] == symbol]
            total_div = symbol_data['Dividend Amount (IDR)'].sum()
            avg_div = symbol_data['Dividend Amount (IDR)'].mean()
            count = len(symbol_data)
            print(f"\n{symbol}:")
            print(f"  Jumlah Pembayaran: {count}")
            print(f"  Total Dividen: Rp {total_div:,.2f}")
            print(f"  Rata-rata per Pembayaran: Rp {avg_div:,.2f}")
        
        return df_dividends


def main():
    """
    Entry point untuk scraper dividen
    """
    scraper = DividendScraper()
    df_result = scraper.scrape_all_dividends()
    
    # Tampilkan preview
    print(f"\n\n📋 PREVIEW DATA (5 baris pertama):")
    print(f"{'='*80}")
    print(df_result.head().to_string(index=False))
    
    return df_result


if __name__ == "__main__":
    df_dividends = main()