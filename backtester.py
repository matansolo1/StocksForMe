import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from scanner import UNIVERSE
import finance_utils
import monte_carlo_backtester

CACHE_RECENT = "backtest_data_cache_recent.pkl"
CACHE_CALM = "backtest_data_cache_calm.pkl"

def get_backtest_data(period="recent"):
    """
    Downloads historical '1d' data for all stocks in UNIVERSE + SPY in a single batch
    and saves to a local pickle cache based on the selected period.
    """
    if period == "recent":
        cache_file = CACHE_RECENT
        start_date = datetime(2021, 1, 1)
        end_date = datetime.now()
    else:
        cache_file = CACHE_CALM
        start_date = datetime(2010, 1, 1)
        end_date = datetime(2020, 12, 31)
        
    if os.path.exists(cache_file):
        print(f"Loading {period} historical data from local cache...")
        try:
            df = pd.read_pickle(cache_file)
            cached_tickers = df.columns.get_level_values(0).unique() if isinstance(df.columns, pd.MultiIndex) else []
            if "SPY" in cached_tickers and len(cached_tickers) >= len(UNIVERSE) * 0.9:
                return df
            print(f"Cache {period} incomplete. Re-downloading...")
        except Exception as e:
            print(f"Error reading cache: {e}. Re-downloading...")

    print(f"Downloading {period} historical data ({start_date.year} to {end_date.year}) for {len(UNIVERSE)} tickers + SPY...")
    try:
        tickers_to_download = list(UNIVERSE) + ["SPY"]
        df = yf.download(tickers_to_download, start=start_date, end=end_date, interval="1d", group_by="ticker", progress=False)
        df.to_pickle(cache_file)
        print(f"Historical data for {period} cached successfully.")
        return df
    except Exception as e:
        print(f"Error downloading data for {period}: {e}")
        return None

def run_backtest_for_period(period="recent", initial_capital=10000.0, target_rsi=30.0, stop_loss_pct=3.0, take_profit_pct=6.0, strategy_mode="mean_reversion", use_monte_carlo=True):
    """
    Runs a stateful, week-by-week backtest for a specific period (recent or calm).
    
    Args:
        period: "recent" (2021-2026) or "calm" (2010-2020)
        initial_capital: Starting capital in USD
        target_rsi: RSI threshold for entry signals
        stop_loss_pct: Stop loss percentage
        take_profit_pct: Take profit percentage
        strategy_mode: "mean_reversion" or "momentum"
        use_monte_carlo: If True, uses Monte Carlo simulation for intraday SL/TP detection
    """
    df = get_backtest_data(period=period)
    if df is None or df.empty:
        return {"error": f"Failed to retrieve {period} historical data."}

    tickers = [t for t in UNIVERSE if t in df.columns.get_level_values(0)]
    
    # Pre-calculate SPY indicators for the global trend filter
    spy_df = df["SPY"].copy().dropna(subset=['Close'])
    spy_df['SMA_200'] = spy_df['Close'].rolling(window=200).mean()
    
    # Pre-calculate indicators for each ticker
    ticker_data = {}
    print(f"Pre-calculating technical indicators for {period} (mode: {strategy_mode})...")
    for ticker in tickers:
        try:
            ticker_df = df[ticker].copy()
            ticker_df = ticker_df.dropna(subset=['Close'])
            if len(ticker_df) < 30:
                continue
            
            ticker_df['SMA_20'] = ticker_df['Close'].rolling(window=20).mean()
            ticker_df['SMA_50'] = ticker_df['Close'].rolling(window=50).mean()
            ticker_df['RSI_14'] = finance_utils.calculate_rsi(ticker_df['Close'])
            ticker_df['Returns'] = ticker_df['Close'].pct_change()
            ticker_df['Volatility'] = ticker_df['Returns'].rolling(window=20).std()
            ticker_df['High_52w'] = ticker_df['High'].rolling(window=252, min_periods=1).max()
            
            ticker_data[ticker] = ticker_df
        except Exception as e:
            continue

    # Get unique trading dates
    all_dates = pd.DatetimeIndex([])
    for ticker, t_df in ticker_data.items():
        all_dates = all_dates.union(t_df.index)
    
    all_dates = sorted(all_dates.unique())
    if not all_dates:
        return {"error": f"No trading dates found in {period} dataset."}

    # Group dates by week
    weeks = {}
    for d in all_dates:
        iso_yr, iso_wk, _ = d.isocalendar()
        week_key = (iso_yr, iso_wk)
        if week_key not in weeks:
            weeks[week_key] = []
        weeks[week_key].append(d)
    
    sorted_week_keys = sorted(weeks.keys())
    
    # Portfolio Tracking State
    cash = initial_capital
    active_trades = []
    trades_log = []
    equity_curve = []
    
    # Record starting equity point
    first_week_dates = weeks[sorted_week_keys[0]]
    start_date_str = first_week_dates[0].strftime("%Y-%m-%d")
    equity_curve.append({
        "date": start_date_str,
        "equity": round(initial_capital, 2)
    })

    commission_pct = 0.0005 # 0.05% commission
    
    print(f"Starting {period} backtest simulation over {len(sorted_week_keys)} weeks...")
    
    for i in range(1, len(sorted_week_keys)):
        prev_week_key = sorted_week_keys[i-1]
        curr_week_key = sorted_week_keys[i]
        
        prev_week_dates = weeks[prev_week_key]
        curr_week_dates = weeks[curr_week_key]
        
        scan_cutoff_date = prev_week_dates[-1]
        
        # 1. CHECK GLOBAL SPY TREND FILTER AS OF PREVIOUS WEEK END
        spy_hist = spy_df.loc[:scan_cutoff_date]
        is_spy_bullish = True
        if len(spy_hist) >= 200:
            spy_close = float(spy_hist.iloc[-1]['Close'])
            spy_sma200 = float(spy_hist.iloc[-1]['SMA_200'])
            is_spy_bullish = spy_close > spy_sma200

        # Calculate current total portfolio equity
        current_equity = cash
        for trade in active_trades:
            ticker = trade["ticker"]
            t_df = ticker_data[ticker]
            last_known_data = t_df.loc[:scan_cutoff_date]
            if not last_known_data.empty:
                last_price = float(last_known_data.iloc[-1]['Close'])
                current_equity += trade["quantity"] * last_price
                
        # Day-by-day simulation
        for day_idx, current_day in enumerate(curr_week_dates):
            current_day_str = current_day.strftime("%Y-%m-%d")
            
            # A. ENTRY ON MONDAY MORNING
            if day_idx == 0 and len(active_trades) < 3 and is_spy_bullish:
                open_slots = 3 - len(active_trades)
                
                setups = []
                for ticker, t_df in ticker_data.items():
                    if any(t["ticker"] == ticker for t in active_trades):
                        continue
                        
                    hist_slice = t_df.loc[:scan_cutoff_date]
                    if len(hist_slice) < 20:
                        continue
                    
                    if strategy_mode == "momentum":
                        if len(hist_slice) < 2:
                            continue
                        row = hist_slice.iloc[-1]
                        row_prev = hist_slice.iloc[-2]
                        close = float(row['Close'])
                        sma50 = float(row['SMA_50']) if 'SMA_50' in row else float(row['Close'])
                        rsi = float(row['RSI_14'])
                        rsi_prev = float(row_prev['RSI_14'])
                        high52w = float(row['High_52w']) if 'High_52w' in row else float(row['High'])
                        
                        if np.isnan(sma50) or np.isnan(rsi) or np.isnan(rsi_prev) or np.isnan(high52w):
                            continue
                            
                        # Condition: RSI crosses above target_rsi and Price > SMA 50
                        if rsi_prev < target_rsi and rsi >= target_rsi and close > sma50:
                            # Rank score is proximity to 52w high (close / high52w) - higher is closer
                            rank_score = close / high52w if high52w > 0 else 0
                            setups.append({
                                "ticker": ticker,
                                "rank_score": rank_score
                            })
                    else:  # mean_reversion
                        row = hist_slice.iloc[-1]
                        close = float(row['Close'])
                        sma = float(row['SMA_20'])
                        rsi = float(row['RSI_14'])
                        vol = float(row['Volatility'])
                        
                        if np.isnan(sma) or np.isnan(rsi) or np.isnan(vol):
                            continue
                            
                        if close < sma and rsi < target_rsi:
                            dist_pct = (sma - close) / close
                            rank_score = dist_pct / vol if vol > 0 else 0
                            setups.append({
                                "ticker": ticker,
                                "rank_score": rank_score
                            })
                
                setups.sort(key=lambda x: x['rank_score'], reverse=True)
                selected_setups = setups[:open_slots]
                
                for s in selected_setups:
                    ticker = s["ticker"]
                    t_df = ticker_data[ticker]
                    
                    if current_day in t_df.index:
                        entry_price = float(t_df.loc[current_day, 'Open'])
                        if entry_price > 0:
                            position_size = min(cash, current_equity / 3.0)
                            if position_size > 50:
                                net_pos_start = position_size * (1 - commission_pct)
                                qty = net_pos_start / entry_price
                                cash -= position_size
                                
                                active_trades.append({
                                    "ticker": ticker,
                                    "entry_price": entry_price,
                                    "sl": entry_price * (1.0 - (stop_loss_pct / 100.0)),
                                    "tp": entry_price * (1.0 + (take_profit_pct / 100.0)),
                                    "quantity": qty,
                                    "entry_date": current_day_str
                                })

            # B. DAILY SL/TP CHECKS
            trades_to_keep = []
            for trade in active_trades:
                ticker = trade["ticker"]
                t_df = ticker_data[ticker]
                
                if current_day in t_df.index:
                    row = t_df.loc[current_day]
                    day_open = float(row['Open'])
                    day_high = float(row['High'])
                    day_low = float(row['Low'])
                    day_close = float(row['Close'])
                    
                    # Get volatility for Monte Carlo simulation
                    hist_slice = t_df.loc[:current_day]
                    if len(hist_slice) >= 20 and 'Volatility' in hist_slice.columns:
                        current_vol = float(hist_slice.iloc[-1]['Volatility'])
                    else:
                        current_vol = 0.02  # Default 2% daily volatility
                    
                    # Use Monte Carlo simulation if enabled
                    if use_monte_carlo:
                        mc_result = monte_carlo_backtester.simulate_intraday_path(
                            open_price=day_open,
                            high=day_high,
                            low=day_low,
                            close=day_close,
                            stop_loss=trade["sl"],
                            take_profit=trade["tp"],
                            volatility=current_vol,
                            num_simulations=100
                        )
                        
                        exit_reason = mc_result["exit_reason"]
                        
                        if exit_reason == "HIT_SL":
                            exit_price = trade["sl"]
                            net_exit_val = (trade["quantity"] * exit_price) * (1 - commission_pct)
                            cash += net_exit_val
                            
                            trade_return = (exit_price - trade["entry_price"]) / trade["entry_price"] - (2 * commission_pct)
                            trades_log.append({
                                "ticker": ticker,
                                "entry_price": trade["entry_price"],
                                "exit_price": exit_price,
                                "exit_reason": "HIT_SL",
                                "entry_date": trade["entry_date"],
                                "exit_date": current_day_str,
                                "return_pct": round(trade_return * 100, 2),
                                "pnl_usd": round(net_exit_val - (trade["quantity"] * trade["entry_price"] / (1 - commission_pct)), 2)
                            })
                        elif exit_reason == "HIT_TP":
                            exit_price = trade["tp"]
                            net_exit_val = (trade["quantity"] * exit_price) * (1 - commission_pct)
                            cash += net_exit_val
                            
                            trade_return = (exit_price - trade["entry_price"]) / trade["entry_price"] - (2 * commission_pct)
                            trades_log.append({
                                "ticker": ticker,
                                "entry_price": trade["entry_price"],
                                "exit_price": exit_price,
                                "exit_reason": "HIT_TP",
                                "entry_date": trade["entry_date"],
                                "exit_date": current_day_str,
                                "return_pct": round(trade_return * 100, 2),
                                "pnl_usd": round(net_exit_val - (trade["quantity"] * trade["entry_price"] / (1 - commission_pct)), 2)
                            })
                        else:
                            trades_to_keep.append(trade)
                    else:
                        # Original simple logic (fallback)
                        if day_low <= trade["sl"]:
                            exit_price = min(day_open, trade["sl"])
                            net_exit_val = (trade["quantity"] * exit_price) * (1 - commission_pct)
                            cash += net_exit_val
                            
                            trade_return = (exit_price - trade["entry_price"]) / trade["entry_price"] - (2 * commission_pct)
                            trades_log.append({
                                "ticker": ticker,
                                "entry_price": trade["entry_price"],
                                "exit_price": exit_price,
                                "exit_reason": "HIT_SL",
                                "entry_date": trade["entry_date"],
                                "exit_date": current_day_str,
                                "return_pct": round(trade_return * 100, 2),
                                "pnl_usd": round(net_exit_val - (trade["quantity"] * trade["entry_price"] / (1 - commission_pct)), 2)
                            })
                        elif day_high >= trade["tp"]:
                            exit_price = max(day_open, trade["tp"])
                            net_exit_val = (trade["quantity"] * exit_price) * (1 - commission_pct)
                            cash += net_exit_val
                            
                            trade_return = (exit_price - trade["entry_price"]) / trade["entry_price"] - (2 * commission_pct)
                            trades_log.append({
                                "ticker": ticker,
                                "entry_price": trade["entry_price"],
                                "exit_price": exit_price,
                                "exit_reason": "HIT_TP",
                                "entry_date": trade["entry_date"],
                                "exit_date": current_day_str,
                                "return_pct": round(trade_return * 100, 2),
                                "pnl_usd": round(net_exit_val - (trade["quantity"] * trade["entry_price"] / (1 - commission_pct)), 2)
                            })
                        else:
                            trades_to_keep.append(trade)
                else:
                    trades_to_keep.append(trade)
                    
            active_trades = trades_to_keep

        # Calculate portfolio liquidation value
        end_of_week_date = curr_week_dates[-1]
        week_end_equity = cash
        for trade in active_trades:
            ticker = trade["ticker"]
            t_df = ticker_data[ticker]
            if end_of_week_date in t_df.index:
                current_price = float(t_df.loc[end_of_week_date, 'Close'])
            else:
                current_price = float(t_df.loc[:end_of_week_date].iloc[-1]['Close'])
            week_end_equity += trade["quantity"] * current_price
            
        equity_curve.append({
            "date": end_of_week_date.strftime("%Y-%m-%d"),
            "equity": round(week_end_equity, 2)
        })

    # Stats Calculation
    total_trades = len(trades_log)
    winning_trades = len([t for t in trades_log if t["return_pct"] > 0])
    win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    final_equity = equity_curve[-1]["equity"]
    total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100
    
    equity_series = pd.Series([point["equity"] for point in equity_curve])
    running_max = equity_series.cummax()
    drawdowns = (equity_series - running_max) / running_max * 100
    max_drawdown_pct = drawdowns.min() if not drawdowns.empty else 0.0

    stats = {
        "total_return_pct": float(round(total_return_pct, 2)),
        "win_rate_pct": float(round(win_rate_pct, 2)),
        "total_trades": int(total_trades),
        "max_drawdown_pct": float(round(abs(max_drawdown_pct), 2)),
        "final_equity": float(round(final_equity, 2))
    }

    return {
        "stats": stats,
        "equity_curve": equity_curve
    }

def run_backtest(initial_capital=10000.0, target_rsi=30.0, stop_loss_pct=3.0, take_profit_pct=6.0, strategy_mode="mean_reversion", use_monte_carlo=True):
    """
    Runs the backtest simulation for both Calm (2010-2020) and Recent (2021-2026) periods.
    
    Args:
        use_monte_carlo: If True, uses Monte Carlo simulation for more accurate SL/TP detection
    """
    recent_res = run_backtest_for_period("recent", initial_capital, target_rsi, stop_loss_pct, take_profit_pct, strategy_mode, use_monte_carlo)
    calm_res = run_backtest_for_period("calm", initial_capital, target_rsi, stop_loss_pct, take_profit_pct, strategy_mode, use_monte_carlo)
    return {
        "recent": recent_res,
        "calm": calm_res
    }

if __name__ == "__main__":
    print("Testing dual backtester...")
    results = run_backtest(initial_capital=10000.0)
    print("Recent stats:", results["recent"]["stats"])
    print("Calm stats:", results["calm"]["stats"])
