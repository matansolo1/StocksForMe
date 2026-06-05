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

def build_diagnostic_message(stats, strategy_mode, is_spy_bullish, target_rsi):
    """Build intelligent diagnostic message based on scan statistics"""
    
    # Base statistics
    msg = f"📊 Scan Statistics:\n"
    msg += f"- Analyzed: {stats['analyzed']}/{stats['total_tickers']} stocks"
    if stats['download_failed'] > 0:
        msg += f" ({stats['download_failed']} download failures)"
    msg += f"\n- RSI crossed {target_rsi}: {stats['rsi_crossed']} stocks\n"
    
    if strategy_mode == "momentum":
        msg += f"- Price above SMA 50: {stats['price_position_ok']} stocks\n"
    else:
        msg += f"- Price below SMA 20: {stats['price_position_ok']} stocks\n"
    
    msg += f"- Both conditions met: {stats['both_conditions']} stocks"
    if stats['both_conditions'] == 0:
        msg += " ❌"
    else:
        msg += " ✅"
    
    if stats['filtered_earnings'] > 0:
        msg += f"\n- Filtered by earnings: {stats['filtered_earnings']} stocks ❌"
    
    msg += f"\n\n💡 Diagnosis: "
    
    # Smart diagnosis
    if stats['final_setups'] > 0:
        msg += f"Found {stats['final_setups']} qualifying setups!"
    elif stats['download_failed'] > 20:
        msg += "High rate of download failures. API rate limiting issue."
        msg += "\n📌 Recommendation: Try again in 1 hour."
    elif stats['filtered_earnings'] > 0 and stats['both_conditions'] > 0:
        msg += "Strong candidates exist but filtered by upcoming earnings."
        msg += "\n📌 Recommendation: Wait 1 week for earnings to pass, then re-scan."
    elif stats['rsi_crossed'] == 0:
        msg += "No RSI crosses detected. Market is in neutral/sideways mode."
        msg += f"\n📌 Recommendation: Wait for more volatility or adjust RSI threshold."
    elif stats['price_position_ok'] == 0:
        if strategy_mode == "momentum":
            msg += "No stocks above SMA 50. Market may be weakening."
            msg += "\n📌 Recommendation: Consider switching to Mean Reversion strategy."
        else:
            msg += "No stocks below SMA 20. Market is very strong."
            msg += "\n📌 Recommendation: Stay in cash or switch to Momentum strategy."
    elif is_spy_bullish and strategy_mode == "mean_reversion":
        msg += "Market is BULLISH. Mean Reversion setups are rare in strong markets."
        msg += "\n📌 Recommendation: Stay in cash or switch to Momentum strategy."
    else:
        msg += "No qualifying trades this week."
        msg += "\n📌 Recommendation: Stay in cash and wait for better setups."
    
    return msg

def scan_universe_generator(strategy_mode="mean_reversion", target_rsi=30.0, stop_loss_pct=3.0, take_profit_pct=6.0):
    """
    Generator that scans the defined universe for trading setups.
    Yields: dict with progress and message, and finally the top setups.
    """
    results = []
    total = len(UNIVERSE)
    
    # Initialize diagnostic statistics
    stats = {
        "total_tickers": len(UNIVERSE),
        "analyzed": 0,
        "download_failed": 0,
        "rsi_crossed": 0,
        "price_position_ok": 0,
        "both_conditions": 0,
        "filtered_earnings": 0,
        "final_setups": 0
    }
    
    yield {"progress": 0, "message": "Checking Global Market Trend (SPY SMA 200)..."}
    
    # Global Trend Filter: SPY above its SMA 200
    is_spy_bullish = True
    try:
        spy_df = stock_api.get_historical_data("SPY", days=300)
        if spy_df is not None and len(spy_df) >= 200:
            spy_df['SMA_200'] = spy_df['Close'].rolling(window=200).mean()
            spy_close = float(spy_df['Close'].iloc[-1])
            spy_sma200 = float(spy_df['SMA_200'].iloc[-1])
            is_spy_bullish = spy_close > spy_sma200
            if is_spy_bullish:
                yield {"progress": 0, "message": f"Market Trend: BULLISH (SPY {spy_close:.2f} > SMA 200 {spy_sma200:.2f}). Scanning universe..."}
            else:
                yield {"progress": 0, "message": f"Market Trend: BEARISH (SPY {spy_close:.2f} <= SMA 200 {spy_sma200:.2f}). Skipping scans / entries for safety."}
                yield {"progress": 100, "message": "Scan complete! Bearish market filter active: No active setups allowed.", "complete": True, "top_setups": []}
                return
        else:
            yield {"progress": 0, "message": "Could not download SPY trend data. Proceeding with scan anyway."}
    except Exception as e:
        yield {"progress": 0, "message": f"Error checking SPY trend: {str(e)}. Proceeding anyway."}

    for index, ticker in enumerate(UNIVERSE):
        progress = (index + 1) / total * 100
        
        try:
            # We download 365 days of history to compute the 52-week high accurately for momentum
            df = stock_api.get_historical_data(ticker, days=365)
            if df is None or len(df) < 20:
                stats["download_failed"] += 1
                yield {"progress": progress, "message": f"Failed to download {ticker}: Rate Limited"}
                continue
        except Exception as e:
            stats["download_failed"] += 1
            yield {"progress": progress, "message": f"Failed to download {ticker}: {str(e)}"}
            continue
        
        stats["analyzed"] += 1
            
        # Technical Indicators
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['RSI_14'] = finance_utils.calculate_rsi(df['Close'])
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=20).std()
        df['High_52w'] = df['High'].rolling(window=252, min_periods=1).max()
        
        # Current signals
        current_close = float(df['Close'].iloc[-1])
        current_sma = float(df['SMA_20'].iloc[-1])
        current_sma50 = float(df['SMA_50'].iloc[-1])
        current_rsi = float(df['RSI_14'].iloc[-1])
        rsi_prev = float(df['RSI_14'].iloc[-2]) if len(df) >= 2 else current_rsi
        current_vol = float(df['Volatility'].iloc[-1])
        high52w = float(df['High_52w'].iloc[-1]) if 'High_52w' in df.columns else current_close
        
        passed_rules = False
        rank_score = 0.0
        tp = current_close * (1.0 + (take_profit_pct / 100.0))
        sl = current_close * (1.0 - (stop_loss_pct / 100.0))
        rr = take_profit_pct / stop_loss_pct if stop_loss_pct > 0 else 0.0
        
        # Track conditions separately for diagnostics
        rsi_crossed = False
        price_position_ok = False
        
        if strategy_mode == "momentum":
            # Condition: RSI crosses above target_rsi (default 60) and Close > SMA 50
            if not np.isnan(current_sma50) and not np.isnan(current_rsi) and not np.isnan(rsi_prev):
                rsi_crossed = (rsi_prev < target_rsi and current_rsi >= target_rsi)
                price_position_ok = (current_close > current_sma50)
                
                if rsi_crossed:
                    stats["rsi_crossed"] += 1
                if price_position_ok:
                    stats["price_position_ok"] += 1
                if rsi_crossed and price_position_ok:
                    stats["both_conditions"] += 1
                    passed_rules = True
                    rank_score = current_close / high52w if high52w > 0 else 0.0
        else: # mean_reversion
            # Smart Reversal Trigger: RSI was below target yesterday, and crossed above it today
            if not np.isnan(current_sma) and not np.isnan(current_rsi) and not np.isnan(rsi_prev):
                rsi_crossed = (rsi_prev < target_rsi and current_rsi >= target_rsi)
                price_position_ok = (current_close < current_sma)
                
                if rsi_crossed:
                    stats["rsi_crossed"] += 1
                if price_position_ok:
                    stats["price_position_ok"] += 1
                if rsi_crossed and price_position_ok:
                    stats["both_conditions"] += 1
                    passed_rules = True
                    dist_pct = (current_sma - current_close) / current_close
                    rank_score = dist_pct / current_vol if current_vol > 0 else 0.0
                
        if passed_rules:
            # Earnings Filter (7-day gap protection)
            next_earnings = stock_api.get_next_earnings_date(ticker)
            if next_earnings:
                # Ensure next_earnings is a datetime object (sometimes it's a date)
                if not isinstance(next_earnings, datetime):
                    next_earnings = datetime.combine(next_earnings, datetime.min.time())
                
                days_to_earnings = (next_earnings - datetime.now()).days
                if 0 <= days_to_earnings <= 7:
                    stats["filtered_earnings"] += 1
                    if 0 <= days_to_earnings <= 2:
                        yield {"progress": progress, "message": f"Skipped {ticker}: Upcoming earnings"}
                    else:
                        yield {"progress": progress, "message": f"Skipping {ticker} due to earnings in {days_to_earnings} days"}
                    continue
            
            # Passed all filters!
            stats["final_setups"] += 1
            results.append({
                'Ticker': ticker,
                'Close': current_close,
                'SMA_20': current_sma,
                'RSI_14': current_rsi,
                'Volatility': current_vol,
                'RankScore': rank_score,
                'RiskReward': rr,
                'StopLoss': sl,
                'TakeProfit': tp
            })
            yield {"progress": progress, "message": f"Found setup for {ticker}! RSI: {current_rsi:.1f}, R/R: {rr:.2f}"}
        else:
            yield {"progress": progress, "message": f"Analyzed {ticker}: No setup"}
            
    results.sort(key=lambda x: x['RankScore'], reverse=True)
    top_setups = results[:3]
    
    # Use smart diagnostic message when no setups found
    if len(results) == 0:
        diagnostic_msg = build_diagnostic_message(stats, strategy_mode, is_spy_bullish, target_rsi)
        yield {"progress": 100, "message": f"Scan complete! Found 0 setups.\n\n{diagnostic_msg}", "complete": True, "top_setups": []}
    else:
        yield {"progress": 100, "message": f"Scan complete! Found {len(results)} setups. Top 3: {', '.join([x['Ticker'] for x in top_setups])}", "complete": True, "top_setups": top_setups}

import sys

def scan_universe(strategy_mode="mean_reversion", target_rsi=30.0, stop_loss_pct=3.0, take_profit_pct=6.0):
    top_setups = []
    for event in scan_universe_generator(strategy_mode, target_rsi, stop_loss_pct, take_profit_pct):
        print(event["message"])
        if "top_setups" in event:
            top_setups = event["top_setups"]
    return top_setups

def main():
    strategy_mode = sys.argv[1] if len(sys.argv) > 1 else "mean_reversion"
    target_rsi = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    stop_loss_pct = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    take_profit_pct = float(sys.argv[4]) if len(sys.argv) > 4 else 6.0

    print(f"Step 1: Running Market Scan in {strategy_mode} mode...")
    top_setups = scan_universe(strategy_mode, target_rsi, stop_loss_pct, take_profit_pct)
    
    print("Step 2: Processing Swaps and New Trades...")
    db = data_manager.load_db()
    trades = db["trades"]
    metadata = db["portfolio_metadata"]
    
    total_deposits = metadata.get("total_deposits", 0)
    if total_deposits <= 0:
        print("Warning: No deposits found. Position sizing will be 0.")
        pos_size = 0
    else:
        pos_size = total_deposits / 3.0
    
    trades = trading_logic.process_scanner_swaps(trades, top_setups, position_size_usd=pos_size)
    trades, added = trading_logic.add_new_trades(trades, top_setups, position_size_usd=pos_size)
    data_manager.save_trades(trades)
    
    print("Step 3: Triggering Tracker Update...")
    env = os.environ.copy()
    subprocess.run(["python", "tracker.py"], env=env)

if __name__ == "__main__":
    main()
