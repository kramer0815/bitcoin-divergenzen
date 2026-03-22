import requests
import pandas as pd
import time
import logging
from dataclasses import dataclass, asdict
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# --- Konfiguration ---
SYMBOL_PAIR = 'BTCUSDT'
TIMEFRAMES = ['15m', '1h', '4h', '1d']
RSI_LENGTH = 14
LOOKBACK = 5
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SIGNAL_FRESHNESS = 15  # candles


@dataclass
class AnalysisResult:
    timeframe: str
    price: float
    signal: str          # "BULLISH_DIV" | "BEARISH_DIV" | "NEUTRAL"
    macd_conf: str       # "YES_RISING" | "YES_FALLING" | "NO" | "-"
    details: str
    rsi: float
    macd_hist: float
    trend: str           # "UP" | "DOWN" | "SIDEWAYS"
    volume_24h: Optional[float] = None

    def to_dict(self):
        return asdict(self)


def fetch_data(symbol: str, interval: str, limit: int = 150) -> pd.DataFrame:
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        df = pd.DataFrame(resp.json(), columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        logger.warning(f"Fetch error [{interval}]: {e}")
        return pd.DataFrame()


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # RSI (Wilder's smoothing via EWM)
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / RSI_LENGTH, min_periods=RSI_LENGTH, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_LENGTH, min_periods=RSI_LENGTH, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    df['rsi'] = 100 - (100 / (1 + rs))

    # MACD
    exp1 = df['close'].ewm(span=MACD_FAST, adjust=False).mean()
    exp2 = df['close'].ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    df['macd_hist'] = macd_line - signal_line
    df['macd_line'] = macd_line
    df['signal_line'] = signal_line

    # Simple trend via 20-period SMA
    df['sma20'] = df['close'].rolling(20).mean()
    df['trend'] = 'SIDEWAYS'
    df.loc[df['close'] > df['sma20'] * 1.005, 'trend'] = 'UP'
    df.loc[df['close'] < df['sma20'] * 0.995, 'trend'] = 'DOWN'

    return df


def find_extremes(series: pd.Series, lookback: int):
    """Returns (peaks, valleys) as index lists."""
    peaks, valleys = [], []
    n = len(series)
    for i in range(lookback, n - lookback):
        window_before = series.iloc[i - lookback:i]
        window_after = series.iloc[i + 1:i + lookback + 1]
        val = series.iloc[i]
        if val > window_before.max() and val > window_after.max():
            peaks.append(i)
        if val < window_before.min() and val < window_after.min():
            valleys.append(i)
    return peaks, valleys


def analyze_timeframe(symbol: str, tf: str) -> Optional[AnalysisResult]:
    df = fetch_data(symbol, tf)
    if df.empty or len(df) <= MACD_SLOW + RSI_LENGTH:
        return None

    df = calculate_indicators(df)

    curr_rsi = round(df['rsi'].iloc[-1], 2)
    curr_hist = df['macd_hist'].iloc[-1]
    prev_hist = df['macd_hist'].iloc[-2]
    trend = df['trend'].iloc[-1]
    price = df['close'].iloc[-1]

    signal = "NEUTRAL"
    macd_conf = "-"
    details = "-"

    price_peaks, price_valleys = find_extremes(df['low'], LOOKBACK)
    _, high_peaks = find_extremes(df['high'], LOOKBACK)

    # Bullish divergence (on lows)
    if len(price_valleys) >= 2:
        last, prev = price_valleys[-1], price_valleys[-2]
        if len(df) - last < SIGNAL_FRESHNESS:
            p_last, p_prev = df['low'].iloc[last], df['low'].iloc[prev]
            r_last, r_prev = df['rsi'].iloc[last], df['rsi'].iloc[prev]
            if p_last < p_prev and r_last > r_prev:
                signal = "BULLISH_DIV"
                details = f"Low {p_prev:.0f}→{p_last:.0f} | RSI {r_prev:.0f}→{r_last:.0f}"
                macd_conf = "YES_RISING" if curr_hist > prev_hist else "NO"

    # Bearish divergence (on highs)
    if len(high_peaks) >= 2:
        last, prev = high_peaks[-1], high_peaks[-2]
        if len(df) - last < SIGNAL_FRESHNESS:
            p_last, p_prev = df['high'].iloc[last], df['high'].iloc[prev]
            r_last, r_prev = df['rsi'].iloc[last], df['rsi'].iloc[prev]
            if p_last > p_prev and r_last < r_prev:
                signal = "BEARISH_DIV"
                details = f"High {p_prev:.0f}→{p_last:.0f} | RSI {r_prev:.0f}→{r_last:.0f}"
                macd_conf = "YES_FALLING" if curr_hist < prev_hist else "NO"

    return AnalysisResult(
        timeframe=tf,
        price=round(price, 2),
        signal=signal,
        macd_conf=macd_conf,
        details=details,
        rsi=curr_rsi,
        macd_hist=round(curr_hist, 4),
        trend=trend,
    )


def run_scan(symbol: str = SYMBOL_PAIR) -> list[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(analyze_timeframe, symbol, tf): tf for tf in TIMEFRAMES}
        for future in as_completed(futures):
            tf = futures[future]
            try:
                result = future.result()
                if result:
                    results.append(result.to_dict())
            except Exception as e:
                logger.error(f"Error analyzing {tf}: {e}")

    # Sort by timeframe order
    order = {tf: i for i, tf in enumerate(TIMEFRAMES)}
    results.sort(key=lambda r: order.get(r['timeframe'], 99))
    return results


if __name__ == "__main__":
    data = run_scan()
    for row in data:
        print(row)
