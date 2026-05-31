from datetime import datetime
import stock_api
import finance_utils

def update_portfolio_status(trades):
    """
    Updates the prices and statuses of all active trades.
    Inputs: trades (list)
    Output: list (updated trades)
    """
    updated_any = False
    for trade in trades:
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
