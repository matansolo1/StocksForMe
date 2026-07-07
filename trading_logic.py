from datetime import datetime
import stock_api
import finance_utils
import pandas as pd

def check_intraday_stop_loss_take_profit(trades):
    """
    Checks if any active trades hit stop loss or take profit using 5-minute candles.
    This provides more accurate detection than daily candles.
    Inputs: trades (list)
    Output: list (updated trades)
    """
    for trade in trades:
        if trade.get("status") != "ACTIVE":
            continue
            
        ticker = trade["ticker"]
        entry_timestamp = trade.get("timestamp")
        
        if not entry_timestamp:
            continue
            
        try:
            # Parse FULL entry timestamp (including time)
            entry_dt = datetime.strptime(entry_timestamp, "%Y-%m-%d %H:%M:%S")
            days_since_entry = (datetime.now() - entry_dt).days
            
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
            
            # Filter candles to only those AFTER entry time (not just entry date)
            # This ensures we only check SL/TP hits AFTER the trade was entered
            entry_dt_utc = pd.Timestamp(entry_dt).tz_localize('UTC')
            df = df[df.index > entry_dt_utc]
            
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
                    # Add exit commission
                    commission = trade.get("commission_entry", 2.5)
                    trade["commission_exit"] = commission
                    trade["total_commission"] = trade.get("commission_entry", commission) + commission
                    print(f"✅ {ticker} hit Take Profit at {trade['exit_timestamp']}")
                    break
                    
                # Check if stop loss was hit (price went below SL)
                if stop_loss and candle_low <= stop_loss:
                    trade["status"] = "HIT_SL"
                    trade["exit_price"] = stop_loss
                    trade["exit_timestamp"] = idx.strftime("%Y-%m-%d %H:%M:%S")
                    trade["current_price"] = stop_loss
                    trade["pnl_pct"] = finance_utils.calculate_pnl_pct(stop_loss, trade["entry_price"])
                    # Add exit commission
                    commission = trade.get("commission_entry", 2.5)
                    trade["commission_exit"] = commission
                    trade["total_commission"] = trade.get("commission_entry", commission) + commission
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
    Uses fallback methods for weekend/market closed scenarios.
    Inputs: trades (list)
    Output: list (updated trades)
    """
    # First, check intraday candles for precise stop loss / take profit detection
    trades = check_intraday_stop_loss_take_profit(trades)
    
    for trade in trades:
        # Skip trades that were already closed by intraday check
        if trade.get("status") == "ACTIVE":
            ticker = trade["ticker"]
            current_price = None
            price_source = None
            
            # Method 1: Try get_live_data (daily candles)
            df = stock_api.get_live_data(ticker)
            if df is not None and not df.empty and "Close" in df.columns:
                try:
                    current_price = float(df["Close"].iloc[-1])
                    last_date = df.index[-1].strftime("%Y-%m-%d")
                    price_source = f"נכון לסגירת המסחר ב-{last_date}"
                except Exception as e:
                    print(f"Error parsing live data for {ticker}: {e}")
            
            # Method 2: Fallback to get_last_price (works on weekends)
            if current_price is None:
                print(f"📊 {ticker}: משתמש במחיר סגירה אחרון (שוק סגור)")
                current_price, last_date = stock_api.get_last_price(ticker)
                if current_price and last_date:
                    price_source = f"נכון לסגירת המסחר האחרונה ({last_date})"
                elif current_price:
                    price_source = "נכון לסגירת המסחר האחרונה"
            
            # Update trade if we got a price
            if current_price is not None:
                trade["current_price"] = current_price
                trade["pnl_pct"] = finance_utils.calculate_pnl_pct(current_price, trade["entry_price"])
                trade["price_note"] = price_source  # Add note about price freshness
                
                # Check SL/TP conditions
                if current_price >= trade["take_profit"]:
                    trade["status"] = "HIT_TP"
                    trade["exit_price"] = current_price
                    trade["exit_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Add exit commission
                    commission = trade.get("commission_entry", 2.5)
                    trade["commission_exit"] = commission
                    trade["total_commission"] = trade.get("commission_entry", commission) + commission
                elif current_price <= trade["stop_loss"]:
                    trade["status"] = "HIT_SL"
                    trade["exit_price"] = current_price
                    trade["exit_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Add exit commission
                    commission = trade.get("commission_entry", 2.5)
                    trade["commission_exit"] = commission
                    trade["total_commission"] = trade.get("commission_entry", commission) + commission
                # No time-based status changes - positions stay ACTIVE until SL/TP hit
            else:
                print(f"❌ {ticker}: לא ניתן לקבל מחיר - מדלג על עדכון")
                
    return trades


def add_new_trades(trades, new_setups, max_positions=3, position_size_usd=1000.0, commission_per_trade=2.5,
                    cash_available=None):
    """
    Adds new trades from scanner if there's room in the portfolio.
    Only fills empty slots - does not close existing positions.
    Matches backtester logic: simple position filling.

    Position sizing: if cash_available is provided, the position size is
    recalculated based on the ACTUAL number of setups being added this run
    (capped at the number of empty slots, floored at dividing by 2), instead
    of using the flat position_size_usd for every trade. This ensures that
    when fewer opportunities are found than there are empty slots, the
    available cash isn't left mostly idle (e.g. 1 setup found with an empty
    3-slot portfolio -> that setup gets 50% of cash instead of 33%).

    Args:
        trades: List of existing trades
        new_setups: List of new setup dictionaries from scanner
        max_positions: Maximum concurrent positions
        position_size_usd: Fallback/base position size in USD (used if cash_available is None)
        commission_per_trade: Commission per trade in USD (default: $2.5)
        cash_available: Total cash available in USD to split among new setups (optional)
    """
    active_trades = [t for t in trades if t.get("status") == "ACTIVE"]
    active_tickers = [t['ticker'] for t in active_trades]

    slots_available = max_positions - len(active_trades)

    # Setups that will actually be added (not already active, within slot limit)
    fillable_setups = [s for s in new_setups if s['Ticker'] not in active_tickers][:max(0, slots_available)]
    num_setups = len(fillable_setups)

    # Determine position size for this batch
    if cash_available is not None and num_setups > 0 and slots_available > 0:
        if num_setups >= slots_available:
            divisor = slots_available
        else:
            divisor = max(2, num_setups)
        batch_position_size = round(cash_available / divisor, 2) if cash_available > 0 else 0.0
        weight_per_trade = round(100 / divisor, 2) if divisor > 0 else 0
    else:
        batch_position_size = position_size_usd
        weight_per_trade = round(100 / slots_available, 2) if slots_available > 0 else 0

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
                "weight_pct": weight_per_trade,
                "quantity": batch_position_size / entry_price,
                "commission_entry": commission_per_trade,
                "commission_exit": 0,  # Will be set when position closes
                "total_commission": commission_per_trade  # Will be updated on exit
            }
            trades.append(trade)
            active_trades.append(trade)
            active_tickers.append(trade['ticker'])
            added_any = True
            print(f"Added new trade: {trade['ticker']} (Weight: {weight_per_trade}%, Position: ${batch_position_size}, Entry commission: ${commission_per_trade})")
            
    return trades, added_any


