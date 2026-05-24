import stock_api
import finance_utils
import trading_logic
import data_manager
import numpy as np
from datetime import datetime, timedelta
import os
import subprocess

# Constants
UNIVERSE = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AMD', 'INTC', 'MU',
    'QCOM', 'AVGO', 'NFLX', 'ADBE', 'ASML', 'CSCO', 'PEP', 'COST', 'TMUS', 'TXN',
    'AMAT', 'ADI', 'NXPI', 'MRVL', 'KLAC', 'LRCX', 'PANW', 'FTNT', 'CRWD', 'DDOG',
    'NET', 'TEAM', 'NOW', 'WDAY', 'SNOW', 'PLTR', 'BABA', 'JD', 'PDD', 'BIDU',
    'MELI', 'SE', 'SHOP', 'SQ', 'PYPL', 'V', 'MA', 'COIN', 'HOOD', 'DIS',
    'SBUX', 'NKE', 'LULU', 'UBER', 'LYFT', 'ABNB', 'DASH', 'ROKU', 'TDOC', 'ZM',
    'DOCU', 'TTD', 'FSLR', 'ENPH', 'SEDG', 'ALB', 'SQM', 'TSMC', 'ARM',
    'SMCI', 'PANW', 'GE', 'CAT', 'CRM', 'ORCL', 'IBM', 'LRCX', 'ETN', 'PH',
    'MSTR', 'MARA', 'RIOT', 'DKNG', 'PINS', 'SNAP', 'AFRM', 'PLTR', 'LCID', 'RIVN',
    'XPEV', 'LI', 'NIO', 'FCX', 'NUE', 'CLF', 'AA', 'X', 'SOFI', 'UPST'
]

def scan_universe():
    """
    Scans the defined universe for trading setups based on RSI and SMA.
    Returns: list of top 3 setups.
    """
    results = []
    print(f"Scanning {len(UNIVERSE)} tickers...")
    
    for ticker in UNIVERSE:
        df = stock_api.get_historical_data(ticker, days=180)
        if df is None or len(df) < 20:
            continue
            
        # Technical Indicators
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['RSI_14'] = finance_utils.calculate_rsi(df['Close'])
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=20).std()
        
        # Current signals
        current_close = float(df['Close'].iloc[-1])
        current_sma = float(df['SMA_20'].iloc[-1])
        current_rsi = float(df['RSI_14'].iloc[-1])
        current_vol = float(df['Volatility'].iloc[-1])
        
        # Strategy Rules
        if not np.isnan(current_sma) and not np.isnan(current_rsi) and \
           current_close < current_sma and current_rsi < 43:
            
            # Earnings Filter (7-day gap protection)
            next_earnings = stock_api.get_next_earnings_date(ticker)
            if next_earnings:
                # Ensure next_earnings is a datetime object (sometimes it's a date)
                if not isinstance(next_earnings, datetime):
                    next_earnings = datetime.combine(next_earnings, datetime.min.time())
                
                days_to_earnings = (next_earnings - datetime.now()).days
                if 0 <= days_to_earnings <= 7:
                    print(f"Skipping {ticker} due to earnings in {days_to_earnings} days ({next_earnings.date()})")
                    continue

            tp = current_sma
            sl = current_close - (2 * current_vol * current_close)
            rr = (tp - current_close) / (current_close - sl) if (current_close - sl) != 0 else 0
            
            # Risk/Reward Filter
            if rr < 1.0:
                continue
            
            dist_pct = (current_sma - current_close) / current_close
            rank_score = dist_pct / current_vol if current_vol > 0 else 0
            
            results.append({
                'Ticker': ticker,
                'Close': current_close,
                'SMA_20': current_sma,
                'RSI_14': current_rsi,
                'Volatility': current_vol,
                'RankScore': rank_score,
                'RiskReward': rr,
                'StopLoss': sl
            })
            
    if not results:
        return []
        
    results.sort(key=lambda x: x['RankScore'], reverse=True)
    return results[:3]

def main():
    """
    Main entry point for the Weekly Scanner.
    """
    print("Step 1: Running Market Scan...")
    top_setups = scan_universe()
    
    print("Step 2: Processing Swaps and New Trades...")
    db = data_manager.load_db()
    trades = db["trades"]
    metadata = db["portfolio_metadata"]
    
    # Calculate position size: 33.3% of (Deposits + Current Profits)
    total_deposits = metadata.get("total_deposits", 0)
    
    # If starting live with $0, we need a deposit first. 
    # The app.py ensures deposit is added before scanner.py runs.
    if total_deposits <= 0:
        print("Warning: No deposits found. Position sizing will be 0.")
        pos_size = 0
    else:
        # Base position sizing on actual deposits
        pos_size = total_deposits / 3.0
    
    # Process Swaps (REVIEW -> CLOSED/ACTIVE)
    trades = trading_logic.process_scanner_swaps(trades, top_setups, position_size_usd=pos_size)
    
    # Add New Trades if space
    trades, added = trading_logic.add_new_trades(trades, top_setups, position_size_usd=pos_size)
    
    # Save back to DB
    data_manager.save_trades(trades)
    
    print("Step 3: Triggering Tracker Update...")
    env = os.environ.copy()
    subprocess.run(["python", "tracker.py"], env=env)

if __name__ == "__main__":
    main()
