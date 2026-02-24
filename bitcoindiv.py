import requests
import pandas as pd
from tabulate import tabulate
import time
import sys

# --- Konfiguration ---
SYMBOL_PAIR = 'BTCUSDT'
TIMEFRAMES = ['15m', '1h', '4h', '1d']
RSI_LENGTH = 14
LOOKBACK = 5

# MACD Einstellungen (Standard)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

def fetch_data_requests(symbol, interval, limit=100):
    """Holt Daten direkt von der Binance API."""
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
    except Exception as e:
        print(f"\nFehler bei {interval}: {e}")
        return pd.DataFrame()

def calculate_indicators(df):
    """Berechnet RSI und MACD manuell."""
    # 1. RSI Berechnung
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(alpha=1/RSI_LENGTH, min_periods=RSI_LENGTH, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/RSI_LENGTH, min_periods=RSI_LENGTH, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 2. MACD Berechnung
    exp1 = df['close'].ewm(span=MACD_FAST, adjust=False).mean()
    exp2 = df['close'].ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    
    # Das Histogramm zeigt die Distanz zwischen MACD und Signallinie
    df['macd_hist'] = macd_line - signal_line
    
    return df

def find_peaks_valleys(series, lookback=2):
    """Findet lokale Hoch- und Tiefpunkte."""
    peaks = []
    valleys = []
    
    if len(series) < lookback * 2:
        return [], []

    for i in range(lookback, len(series) - lookback):
        current = series[i]
        if all(current > series[i-j] for j in range(1, lookback+1)) and \
           all(current > series[i+j] for j in range(1, lookback+1)):
            peaks.append(i)   
        if all(current < series[i-j] for j in range(1, lookback+1)) and \
           all(current < series[i+j] for j in range(1, lookback+1)):
            valleys.append(i)
    return peaks, valleys

def analyze_market(df):
    """Prüft auf Divergenzen und MACD Bestätigung."""
    df = calculate_indicators(df)
    
    price_valleys_idx, _ = find_peaks_valleys(df['low'], LOOKBACK)
    _, price_peaks_idx = find_peaks_valleys(df['high'], LOOKBACK)

    signal = "Neutral"
    details = "-"
    macd_conf = "-" # Bestätigungsstatus

    # Aktuelle MACD Werte für Bestätigung
    curr_hist = df['macd_hist'].iloc[-1]
    prev_hist = df['macd_hist'].iloc[-2]

    # --- Bullish Check ---
    if len(price_valleys_idx) >= 2:
        last_idx = price_valleys_idx[-1]
        prev_idx = price_valleys_idx[-2]
        
        if len(df) - last_idx < 15: # Signal muss frisch sein
            p_last = df['low'][last_idx]
            p_prev = df['low'][prev_idx]
            r_last = df['rsi'][last_idx]
            r_prev = df['rsi'][prev_idx]

            # Preis tiefer, RSI höher
            if p_last < p_prev and r_last > r_prev:
                signal = "\033[92mBULLISH DIV\033[0m" # Grün
                details = f"P:{p_prev:.0f}->{p_last:.0f} RSI:{r_prev:.0f}->{r_last:.0f}"
                
                # MACD Bestätigung: Histogramm steigt an
                if curr_hist > prev_hist:
                    macd_conf = "✅ JA (Steigend)"
                else:
                    macd_conf = "❌ NEIN"

    # --- Bearish Check ---
    if len(price_peaks_idx) >= 2:
        last_idx = price_peaks_idx[-1]
        prev_idx = price_peaks_idx[-2]
        
        if len(df) - last_idx < 15:
            p_last = df['high'][last_idx]
            p_prev = df['high'][prev_idx]
            r_last = df['rsi'][last_idx]
            r_prev = df['rsi'][prev_idx]

            # Preis höher, RSI tiefer
            if p_last > p_prev and r_last < r_prev:
                signal = "\033[91mBEARISH DIV\033[0m" # Rot
                details = f"P:{p_prev:.0f}->{p_last:.0f} RSI:{r_prev:.0f}->{r_last:.0f}"
                
                # MACD Bestätigung: Histogramm fällt
                if curr_hist < prev_hist:
                    macd_conf = "✅ JA (Fallend)"
                else:
                    macd_conf = "❌ NEIN"

    return df['close'].iloc[-1], signal, details, macd_conf

def main():
    print(f"Starte Scanner (RSI Divergenz + MACD Bestätigung)...\n")
    results = []
    
    for tf in TIMEFRAMES:
        sys.stdout.write(f"\rAnalysiere {tf}...")
        sys.stdout.flush()
        
        df = fetch_data_requests(SYMBOL_PAIR, tf)
        
        if not df.empty and len(df) > MACD_SLOW:
            price, signal, info, macd = analyze_market(df)
            results.append([tf, f"${price:.2f}", signal, macd, info])
        
        time.sleep(0.25)

    print("\n\n" + "="*75)
    print(f"BITCOIN ANALYSE REPORT ({SYMBOL_PAIR})")
    print("="*75)
    
    headers = ["Timeframe", "Preis", "Signal", "MACD Conf.", "Details"]
    print(tabulate(results, headers=headers, tablefmt="simple_grid"))
    print("\n")

if __name__ == "__main__":
    main()