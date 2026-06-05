import stock_api
import finance_utils

# Test a few stocks to see their current conditions
tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'TSLA', 'AMD']

print("Testing Mean Reversion Setup Conditions (target_rsi=30):")
print("=" * 80)

for ticker in tickers:
    df = stock_api.get_historical_data(ticker, days=60)
    if df is None or len(df) < 20:
        print(f"{ticker}: Failed to download data")
        continue
    
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['RSI_14'] = finance_utils.calculate_rsi(df['Close'])
    
    current_close = float(df['Close'].iloc[-1])
    current_sma = float(df['SMA_20'].iloc[-1])
    current_rsi = float(df['RSI_14'].iloc[-1])
    rsi_prev = float(df['RSI_14'].iloc[-2]) if len(df) >= 2 else current_rsi
    
    # Check mean reversion conditions
    below_sma = current_close < current_sma
    rsi_crossed = rsi_prev < 30.0 and current_rsi >= 30.0
    
    print(f"{ticker}:")
    print(f"  Close: ${current_close:.2f}, SMA20: ${current_sma:.2f}")
    print(f"  RSI: {current_rsi:.2f}, RSI_prev: {rsi_prev:.2f}")
    print(f"  Below SMA: {below_sma}, RSI Crossed 30: {rsi_crossed}")
    print(f"  SETUP: {'YES' if (below_sma and rsi_crossed) else 'NO'}")
    print()
