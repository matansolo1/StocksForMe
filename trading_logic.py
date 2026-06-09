from datetime import datetime
import stock_api
import finance_utils

def check_intraday_stop_loss_take_profit(trades):
    """
    Checks if any active trades hit stop loss or take profit using 5-minute candles.
    This provides more accurate detection than daily candles.
    Inputs: trades (list)
    Output: list (updated trades)
    """
    for trade in trades:
        if trade.get("status") not in ["ACTIVE", "REVIEW"]:
            continue
            
        ticker = trade["ticker"]
        entry_timestamp = trade.get("timestamp")
        
        if not entry_timestamp:
            continue
            
        try:
            # Parse entry date (use date only, not time)
            entry_date = datetime.strptime(entry_timestamp.split()[0], "%Y-%m-%d")
            days_since_entry = (datetime.now() - entry_date).days
            
            # yfinance provides 5-minute data for up to 60 days
            # If trade is older, skip intraday check (will be checked by daily candles)
            if days_since_entry > 60:
                continue
                
            # Download 5-minute candles - get extra days to ensure we have data
            # Use at least 5 days to ensure we capture the entry day and subsequent days
            period = f"{max(5, min(days_since_entry + 2, 60))}d"
            df = stock_api.get_intraday_data(ticker, period=period, interval="5m")
            
            if df is None or df.empty or "High" not in df.columns or "Low" not in df.columns:
                continue
            
            # Filter candles to only those on or after entry date (not strict time comparison)
            # This ensures we catch any intraday movements on the entry day itself
            df = df[df.index.date >= entry_date.date()]
            
            if df.empty:
                continue
            
            stop_loss = trade.get("stop_loss")
            take_profit = trade.get("take_profit")
            
            # Check each candle for stop loss or take profit hit
            for idx, row in df.iterrows():
                candle_high = float(row["High"])
                candle_low = float(row["Low"])
                
                # Check if take profit was hit (price went above TP)
                if take_profit and candle_high >= take_profit:
                    trade["status"] = "HIT_TP"
                    trade["exit_price"] = take_profit
                    trade["exit_timestamp"] = idx.strftime("%Y-%m-%d %H:%M:%S")
                    trade["current_price"] = take_profit
                    trade["pnl_pct"] = finance_utils.calculate_pnl_pct(take_profit, trade["entry_price"])
                    print(f"✅ {ticker} hit Take Profit at {trade['exit_timestamp']}")
                    break
                    
                # Check if stop loss was hit (price went below SL)
                if stop_loss and candle_low <= stop_loss:
                    trade["status"] = "HIT_SL"
                    trade["exit_price"] = stop_loss
                    trade["exit_timestamp"] = idx.strftime("%Y-%m-%d %H:%M:%S")
                    trade["current_price"] = stop_loss
                    trade["pnl_pct"] = finance_utils.calculate_pnl_pct(stop_loss, trade["entry_price"])
                    print(f"🛑 {ticker} hit Stop Loss at {trade['exit_timestamp']}")
                    break
                    
        except Exception as e:
            print(f"Error checking intraday data for {ticker}: {e}")
            continue
            
    return trades

def update_portfolio_status(trades):
    """
    Updates the prices and statuses of all active trades.
    First checks intraday 5-minute candles for precise SL/TP detection,
    then updates current prices with daily data.
    Inputs: trades (list)
    Output: list (updated trades)
    """
    # First, check intraday candles for precise stop loss / take profit detection
    trades = check_intraday_stop_loss_take_profit(trades)
    
    updated_any = False
    for trade in trades:
        # Skip trades that were already closed by intraday check
        if trade.get("status") in ["ACTIVE", "REVIEW"]:
            ticker = trade["ticker"]
            df = stock_api.get_live_data(ticker)
            if df is not None and not df.empty and "Close" in df.columns:
                try:
                    current_price = float(df["Close"].iloc[-1])
                    trade["current_price"] = current_price
                    trade["pnl_pct"] = finance_utils.calculate_pnl_pct(current_price, trade["entry_price"])
                    
                    if current_price >= trade["take_profit"]:
                        trade["status"] = "HIT_TP"
                        trade["exit_price"] = current_price
                        trade["exit_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    elif current_price <= trade["stop_loss"]:
                        trade["status"] = "HIT_SL"
                        trade["exit_price"] = current_price
                        trade["exit_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    elif trade.get("status") == "ACTIVE":
                        ts_str = trade.get("timestamp")
                        if ts_str:
                            entry_date = datetime.strptime(ts_str.split()[0], "%Y-%m-%d")
                            if (datetime.now() - entry_date).days >= 7:
                                trade["status"] = "REVIEW"
                except Exception as e:
                    print(f"Error updating trade {ticker}: {e}")
                    continue
    return trades

def process_scanner_swaps(trades, new_setups, position_size_usd=None):
    """
    Handles swapping REVIEW trades with new scanner setups.
    Inputs: trades (list), new_setups (list)
    Output: list (updated trades)
    """
    active_trades = [t for t in trades if t.get("status") in ["ACTIVE", "REVIEW"]]
    review_trades = [t for t in trades if t.get("status") == "REVIEW"]
    
    if review_trades:
        active_tickers = [t['ticker'] for t in active_trades]
        available_setups = [s for s in new_setups if s['Ticker'] not in active_tickers]
        
        for rt in review_trades:
            if available_setups:
                new_s = available_setups.pop(0)
                print(f"Swapping {rt['ticker']} (REVIEW) with {new_s['Ticker']} (NEW)")
                rt["status"] = "CLOSED_BY_SCANNER"
                rt["exit_price"] = rt.get("current_price", rt["entry_price"])
                rt["exit_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                entry_price = new_s['Close']
                # If position_size_usd is not provided, we should ideally use 33.3% of portfolio
                # For now, let's stick to the previous weight logic but allow quantity
                notion = position_size_usd if position_size_usd else 1000.0 
                
                new_trade = {
                    "ticker": new_s['Ticker'],
                    "entry_price": entry_price,
                    "take_profit": new_s.get('TakeProfit', new_s['SMA_20']),
                    "stop_loss": new_s['StopLoss'],
                    "risk_reward": new_s['RiskReward'],
                    "rsi": new_s['RSI_14'],
                    "status": "ACTIVE",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "weight_pct": rt.get("weight_pct", 33.33),
                    "quantity": notion / entry_price
                }
                trades.append(new_trade)
            else:
                print(f"No new setups for {rt['ticker']}. Reverting to ACTIVE.")
                rt["status"] = "ACTIVE"
    
    return trades

def add_new_trades(trades, new_setups, max_positions=3, position_size_usd=1000.0):
    """
    Adds new trades from scanner if there's room in the portfolio.
    """
    active_trades = [t for t in trades if t.get("status") in ["ACTIVE", "REVIEW"]]
    active_tickers = [t['ticker'] for t in active_trades]
    
    added_any = False
    for s in new_setups:
        if len(active_trades) >= max_positions:
            break
            
        if s['Ticker'] not in active_tickers:
            entry_price = s['Close']
            trade = {
                "ticker": s['Ticker'],
                "entry_price": entry_price,
                "take_profit": s.get('TakeProfit', s['SMA_20']),
                "stop_loss": s['StopLoss'],
                "risk_reward": s['RiskReward'],
                "rsi": s['RSI_14'],
                "status": "ACTIVE",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "weight_pct": 33.33,
                "quantity": position_size_usd / entry_price
            }
            trades.append(trade)
            active_trades.append(trade)
            active_tickers.append(trade['ticker'])
            added_any = True
            print(f"Added new trade: {trade['ticker']}")
            
    return trades, added_any
