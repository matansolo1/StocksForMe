import yfinance as yf
import pandas as pd

tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'TSLA', 'AMD']

for t in tickers:
    df = yf.download(t, period='60d', progress=False)
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    
    # Calculate RSI properly
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    close = df['Close'].iloc[-1]
    sma20 = df['SMA_20'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    rsi_prev = df['RSI'].iloc[-2]
    
    print(f'{t}: Close={close:.2f}, SMA20={sma20:.2f}, RSI={rsi:.2f}, RSI_prev={rsi_prev:.2f}, Below_SMA={close < sma20}, RSI_Cross={rsi_prev < 30 and rsi >= 30}')
