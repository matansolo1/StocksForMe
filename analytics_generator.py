"""
Analytics Generator - Trade Analytics & Portfolio State Management
Handles all calculations for trade analytics, portfolio state tracking, and capital management.
"""

import json
from datetime import datetime
import stock_api


def calculate_portfolio_state(trades, total_deposits, commission_per_trade=2.5):
    """
    Calculates the complete portfolio state including equity, cash, and P&L.
    
    Args:
        trades: List of trade dictionaries
        total_deposits: Total amount deposited into the portfolio
        commission_per_trade: Commission per trade in USD (default: $2.5)
    
    Returns:
        Dictionary with portfolio state metrics
    """
    realized_pnl = 0
    unrealized_pnl = 0
    invested_capital = 0
    total_commissions = 0
    
    for trade in trades:
        position_value = trade.get('quantity', 0) * trade.get('entry_price', 0)
        
        if trade.get('status') == 'ACTIVE':
            # Active positions - calculate unrealized P&L (subtract entry commission only)
            current_price = trade.get('current_price', trade.get('entry_price', 0))
            current_value = trade.get('quantity', 0) * current_price
            entry_commission = trade.get('commission_entry', commission_per_trade)
            unrealized_pnl += (current_value - position_value) - entry_commission
            invested_capital += position_value
            total_commissions += entry_commission
        else:
            # Closed positions - calculate realized P&L (subtract both entry and exit commissions)
            exit_price = trade.get('exit_price', trade.get('entry_price', 0))
            exit_value = trade.get('quantity', 0) * exit_price
            entry_commission = trade.get('commission_entry', commission_per_trade)
            exit_commission = trade.get('commission_exit', commission_per_trade)
            total_trade_commission = entry_commission + exit_commission
            realized_pnl += (exit_value - position_value) - total_trade_commission
            total_commissions += total_trade_commission
    
    current_equity = total_deposits + realized_pnl + unrealized_pnl
    cash_available = total_deposits + realized_pnl - invested_capital
    
    return {
        'current_equity': round(current_equity, 2),
        'cash_available': round(cash_available, 2),
        'invested_capital': round(invested_capital, 2),
        'realized_pnl': round(realized_pnl, 2),
        'unrealized_pnl': round(unrealized_pnl, 2),
        'total_deposits': total_deposits,
        'total_commissions': round(total_commissions, 2)
    }


def calculate_position_size(portfolio_state, max_positions=3, active_positions=0):
    """
    Calculates position size based on available cash (Option A - Conservative).
    
    Args:
        portfolio_state: Dictionary from calculate_portfolio_state
        max_positions: Maximum number of concurrent positions
        active_positions: Current number of active positions
    
    Returns:
        Position size in USD
    """
    cash_available = portfolio_state['cash_available']
    slots_available = max(0, max_positions - active_positions)
    
    
    if cash_available > 0 and slots_available > 0:
        position_size = cash_available / slots_available
    else:
        position_size = 0
    

    return round(position_size, 2)

    return round(position_size, 2)


def calculate_simple_cumulative_return(trades):
    """
    Calculates simple cumulative return by summing P&L percentages.
    Each trade is treated equally regardless of position size.
    Groups trades by exit date to show one point per day.
    
    Args:
        trades: List of trade dictionaries
    
    Returns:
        List of dictionaries with date and cumulative return
    """
    # Filter and sort closed trades by exit timestamp (not entry!)
    closed_trades = [t for t in trades if t.get('status') != 'ACTIVE' and t.get('exit_timestamp')]
    closed_trades.sort(key=lambda x: x.get('exit_timestamp', ''))
    
    # Group trades by exit date
    from collections import defaultdict
    trades_by_date = defaultdict(list)
    for trade in closed_trades:
        exit_date = trade.get('exit_timestamp', '').split()[0]
        trades_by_date[exit_date].append(trade)
    
    cumulative = 0
    results = []
    
    # Process each date
    for date in sorted(trades_by_date.keys()):
        daily_pnl = sum(t.get('pnl_pct', 0) for t in trades_by_date[date])
        cumulative += daily_pnl
        results.append({
            'date': date,
            'cumulative_return': round(cumulative, 2),
            'trades_count': len(trades_by_date[date])
        })
    
    return results


def calculate_mwr_cumulative_return(trades, total_deposits):
    """
    Calculates Money-Weighted Return (MWR) cumulative return.
    Takes into account the actual capital invested in each trade.
    Groups trades by exit date to show one point per day.
    
    Args:
        trades: List of trade dictionaries
        total_deposits: Total amount deposited
    
    Returns:
        List of dictionaries with date and MWR return
    """
    closed_trades = [t for t in trades if t.get('status') not in ['ACTIVE', 'REVIEW'] and t.get('exit_timestamp')]
    closed_trades.sort(key=lambda x: x.get('exit_timestamp', ''))
    
    # Group trades by exit date
    from collections import defaultdict
    trades_by_date = defaultdict(list)
    for trade in closed_trades:
        exit_date = trade.get('exit_timestamp', '').split()[0]
        trades_by_date[exit_date].append(trade)
    
    cumulative_usd = 0
    results = []
    
    # Process each date
    for date in sorted(trades_by_date.keys()):
        daily_pnl_usd = 0
        for trade in trades_by_date[date]:
            position_size = trade.get('quantity', 0) * trade.get('entry_price', 0)
            pnl_usd = position_size * (trade.get('pnl_pct', 0) / 100)
            daily_pnl_usd += pnl_usd
        
        cumulative_usd += daily_pnl_usd
        
        if total_deposits > 0:
            mwr_pct = (cumulative_usd / total_deposits) * 100
        else:
            mwr_pct = 0
        
        results.append({
            'date': date,
            'mwr_return': round(mwr_pct, 2),
            'trades_count': len(trades_by_date[date])
        })
    
    return results


def get_spy_benchmark(start_date, end_date):
    """
    Downloads SPY data and calculates cumulative return for benchmark comparison.
    
    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
    
    Returns:
        List of dictionaries with date and SPY cumulative return
    """
    try:
        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days + 30  # Add buffer
        
        # Download SPY data
        df = stock_api.get_historical_data('SPY', days=days)
        
        if df is None or df.empty:
            return []
        
        # Filter to date range
        df = df[df.index >= start_dt]
        df = df[df.index <= end_dt]
        
        if df.empty:
            return []
        
        # Calculate cumulative return
        initial_price = df['Close'].iloc[0]
        results = []
        
        for idx, row in df.iterrows():
            current_price = row['Close']
            cumulative_return = ((current_price - initial_price) / initial_price) * 100
            results.append({
                'date': idx.strftime('%Y-%m-%d'),
                'spy_return': round(cumulative_return, 2)
            })
        
        return results
    except Exception as e:
        print(f"Error fetching SPY benchmark: {e}")
        return []


def calculate_trade_duration(trade):
    """
    Calculates the duration of a trade in days.
    
    Args:
        trade: Trade dictionary
    
    Returns:
        Duration in days (float)
    """
    try:
        entry_time = datetime.strptime(trade.get('timestamp', ''), "%Y-%m-%d %H:%M:%S")
        
        if trade.get('status') == 'ACTIVE':
            exit_time = datetime.now()
        else:
            exit_time = datetime.strptime(trade.get('exit_timestamp', ''), "%Y-%m-%d %H:%M:%S")
        
        duration = (exit_time - entry_time).total_seconds() / 86400  # Convert to days
        return round(duration, 2)
    except:
        return 0


def calculate_performance_metrics(trades):
    """
    Calculates key performance metrics for the portfolio.
    
    Args:
        trades: List of trade dictionaries
    
    Returns:
        Dictionary with performance metrics
    """
    closed_trades = [t for t in trades if t.get('status') != 'ACTIVE']
    
    if not closed_trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'avg_duration': 0
        }
    
    total_trades = len(closed_trades)
    winning_trades = [t for t in closed_trades if t.get('pnl_pct', 0) > 0]
    losing_trades = [t for t in closed_trades if t.get('pnl_pct', 0) < 0]
    
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    
    avg_win = sum(t.get('pnl_pct', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t.get('pnl_pct', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0
    
    total_wins = sum(t.get('pnl_pct', 0) for t in winning_trades)
    total_losses = abs(sum(t.get('pnl_pct', 0) for t in losing_trades))
    profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
    
    durations = [calculate_trade_duration(t) for t in closed_trades]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    return {
        'total_trades': total_trades,
        'win_rate': round(win_rate, 1),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2),
        'avg_duration': round(avg_duration, 1)
    }


def prepare_analytics_data(trades, total_deposits):
    """
    Prepares all data needed for the analytics page.
    
    Args:
        trades: List of trade dictionaries
        total_deposits: Total deposits
    
    Returns:
        Dictionary with all analytics data
    """
    # Calculate portfolio state
    portfolio_state = calculate_portfolio_state(trades, total_deposits)
    
    # Calculate returns
    simple_returns = calculate_simple_cumulative_return(trades)
    mwr_returns = calculate_mwr_cumulative_return(trades, total_deposits)
    
    # Get date range for SPY benchmark
    if simple_returns:
        start_date = simple_returns[0]['date']
        end_date = simple_returns[-1]['date']
        spy_returns = get_spy_benchmark(start_date, end_date)
    else:
        spy_returns = []
    
    # Calculate performance metrics
    metrics = calculate_performance_metrics(trades)
    
    # Calculate alpha (strategy return - SPY return)
    if simple_returns and spy_returns:
        strategy_return = simple_returns[-1]['cumulative_return']
        spy_final_return = spy_returns[-1]['spy_return'] if spy_returns else 0
        alpha = strategy_return - spy_final_return
    else:
        alpha = 0
    
    return {
        'portfolio_state': portfolio_state,
        'simple_returns': simple_returns,
        'mwr_returns': mwr_returns,
        'spy_returns': spy_returns,
        'metrics': metrics,
        'alpha': round(alpha, 2),
        'trades': trades
    }
