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


def calculate_position_size(portfolio_state, max_positions=3, active_positions=0, num_setups_found=None):
    """
    Calculates position size based on available cash.

    The divisor used to split available cash is the number of empty slots,
    UNLESS fewer setups were actually found this week - in that case we
    divide by the number of setups found (so found capital isn't left idle),
    but we never divide by less than 2. This means:
      - Empty portfolio (3 slots) + 1 setup found -> 50% of cash goes to it
      - Empty portfolio (3 slots) + 2 setups found -> 50/50 split
      - Empty portfolio (3 slots) + 3 setups found -> 33/33/33 split
      - 1 active position (2 slots) + 1 setup found -> 50% of remaining cash

    Args:
        portfolio_state: Dictionary from calculate_portfolio_state
        max_positions: Maximum number of concurrent positions
        active_positions: Current number of active positions
        num_setups_found: Number of setups actually found by the scanner this run
                           (None = unknown yet, fall back to slots_available only)

    Returns:
        Position size in USD
    """
    cash_available = portfolio_state['cash_available']
    slots_available = max(0, max_positions - active_positions)

    if slots_available <= 0 or cash_available <= 0:
        return 0.0

    if num_setups_found is not None and num_setups_found > 0:
        # Never divide by less than 2, and never by more than the empty slots
        divisor = max(2, min(slots_available, num_setups_found))
        # If there are enough setups to fill ALL empty slots, use the normal
        # even split across all slots instead of the min-2 floor.
        if num_setups_found >= slots_available:
            divisor = slots_available
    else:
        divisor = slots_available

    position_size = cash_available / divisor

    return round(position_size, 2)


def _dedupe_signals(trades):
    """
    Collapses duplicate trades that represent the SAME underlying strategy
    signal but were recorded once per owner (e.g. both 'matan' and 'horim'
    bought the same ticker because they each run their own independent slot
    allocation). For the purposes of simulating "what would a single $X
    account have done if it followed every signal the strategy produced",
    these must be counted ONCE.

    Two trades are considered the same signal if they share the same
    ticker, entry_price and exit_price (both rounded to cents). This is
    deliberately timestamp-independent: each owner's automation executes at
    a slightly different moment (sometimes minutes apart), but an identical
    entry+exit price pair on the same ticker is conclusive proof it's the
    same underlying scanner signal, not two separate trading decisions.

    Args:
        trades: List of trade dictionaries (all owners combined)

    Returns:
        List of deduplicated trade dictionaries, sorted by entry timestamp.
    """
    seen = {}
    for t in trades:
        key = (
            t.get('ticker'),
            round(t.get('entry_price', 0), 2),
            round(t.get('exit_price', 0) or 0, 2)
        )
        if key not in seen:
            seen[key] = t
    deduped = list(seen.values())
    deduped.sort(key=lambda t: t.get('timestamp', ''))
    return deduped


def simulate_strategy_growth(trades, initial_capital=10000.0, max_slots=3, commission_per_trade=2.5):
    """
    Simulates "what if a single account of `initial_capital` had followed
    every signal this strategy produced from day one, using the exact
    slot-allocation rule: whenever a slot frees up, the position size for
    the NEXT trade taken is (current cash) / (number of currently free
    slots) - i.e. an even split of available cash across empty slots at
    the moment of entry.

    This deliberately ignores everything about what ACTUALLY happened with
    real money (multiple owners, staggered deposits, uneven real position
    sizing) and instead answers: "if I had started with $X and mechanically
    followed the strategy's signals with disciplined position sizing, what
    would I have today?"

    Rules (confirmed with user):
      - Only CLOSED trades are simulated (ACTIVE/REVIEW positions are
        skipped entirely - they never open a slot in the simulation).
      - Duplicate signals (same ticker/entry_price/exit_price recorded once
        per owner) are collapsed into a single trade via _dedupe_signals().
      - A trade only "opens" if a slot is free at its entry time (slots
        free up strictly when an earlier trade's exit_timestamp has passed).
      - Position size at entry = cash_available / free_slots_at_that_moment.
      - Commission (entry+exit) is deducted in dollar terms, scaled to the
        simulated position size (not the real historical position size).
      - If, at a given entry moment, there are more signals than free
        slots, only the first `free_slots` (in chronological order) are
        taken; the rest are recorded as "skipped".

    Args:
        trades: List of trade dictionaries (all owners combined)
        initial_capital: Starting capital for the simulation (default $10,000
                          to keep commission drag proportionally realistic)
        max_slots: Number of concurrent position slots (default 3)
        commission_per_trade: Commission in USD per entry/exit leg

    Returns:
        Dictionary:
            {
                'final_equity': float,
                'total_return_pct': float,
                'initial_capital': float,
                'signals_taken': int,
                'signals_skipped': int,
                'start_date': str,
                'end_date': str,
                'trades_log': [ {ticker, entry_date, exit_date, position_size,
                                  pnl_pct, pnl_usd, commission_usd}, ... ]
            }
    """
    closed_trades = [t for t in trades if t.get('status') not in ['ACTIVE', 'REVIEW'] and t.get('exit_timestamp')]
    signals = _dedupe_signals(closed_trades)

    cash = float(initial_capital)
    # open_positions: list of dicts with exit_timestamp (str) and invested (float)
    open_positions = []
    trades_log = []
    signals_skipped = 0

    for signal in signals:
        entry_ts = signal.get('timestamp', '')
        exit_ts = signal.get('exit_timestamp', '')

        # Free up any slots whose exit time is at or before this entry time
        still_open = []
        for pos in open_positions:
            if pos['exit_timestamp'] <= entry_ts:
                # Settle this position: return invested capital + P&L - exit commission
                proceeds = pos['invested'] * (1 + pos['pnl_pct'] / 100)
                cash += proceeds - commission_per_trade  # exit commission leg
            else:
                still_open.append(pos)
        open_positions = still_open

        free_slots = max_slots - len(open_positions)

        if free_slots <= 0:
            signals_skipped += 1
            continue

        position_size = cash / free_slots

        # Entry commission leg
        cash -= position_size
        cash -= commission_per_trade

        open_positions.append({
            'exit_timestamp': exit_ts,
            'invested': position_size,
            'pnl_pct': signal.get('pnl_pct', 0)
        })

        trades_log.append({
            'ticker': signal.get('ticker'),
            'entry_date': entry_ts,
            'exit_date': exit_ts,
            'position_size': round(position_size, 2),
            'pnl_pct': round(signal.get('pnl_pct', 0), 2)
        })

    # Settle any positions still open at the end of history (all real
    # data given to this function is closed trades, so this normally
    # closes everything that was ever opened).
    for pos in open_positions:
        proceeds = pos['invested'] * (1 + pos['pnl_pct'] / 100)
        cash += proceeds - commission_per_trade

    final_equity = cash
    total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100 if initial_capital else 0

    # Backfill pnl_usd/commission_usd into the log for transparency
    for entry in trades_log:
        entry['pnl_usd'] = round(entry['position_size'] * (entry['pnl_pct'] / 100), 2)
        entry['commission_usd'] = round(commission_per_trade * 2, 2)

    start_date = signals[0]['timestamp'].split()[0] if signals else None
    end_date = signals[-1]['exit_timestamp'].split()[0] if signals else None

    return {
        'final_equity': round(final_equity, 2),
        'total_return_pct': round(total_return_pct, 2),
        'initial_capital': initial_capital,
        'signals_taken': len(trades_log),
        'signals_skipped': signals_skipped,
        'start_date': start_date,
        'end_date': end_date,
        'trades_log': trades_log
    }


def calculate_simulation_cumulative_return(simulation):
    """
    Builds a day-by-day (per-exit-date) cumulative return series (%) for the
    strategy simulation, so it can be plotted on the same chart as the MWR
    and SPY benchmark lines.

    Uses the `trades_log` produced by simulate_strategy_growth(), which
    already contains each simulated trade's position_size and pnl_usd at
    the time it exited. We reconstruct running equity by adding each
    trade's pnl_usd (in chronological exit order) to the initial capital,
    then express it as cumulative % return relative to initial_capital.

    Args:
        simulation: The dict returned by simulate_strategy_growth()

    Returns:
        List of dictionaries: [{'date': 'YYYY-MM-DD', 'sim_return': float}, ...]
    """
    trades_log = simulation.get('trades_log', [])
    initial_capital = simulation.get('initial_capital', 10000.0)

    if not trades_log or not initial_capital:
        return []

    # Sort by exit date to build a proper running total over time
    sorted_log = sorted(trades_log, key=lambda t: t.get('exit_date', ''))

    from collections import defaultdict
    pnl_by_date = defaultdict(float)
    for entry in sorted_log:
        exit_date = (entry.get('exit_date') or '').split()[0]
        if not exit_date:
            continue
        pnl_by_date[exit_date] += entry.get('pnl_usd', 0)

    cumulative_usd = 0.0
    results = []
    for date in sorted(pnl_by_date.keys()):
        cumulative_usd += pnl_by_date[date]
        sim_return_pct = (cumulative_usd / initial_capital) * 100
        results.append({
            'date': date,
            'sim_return': round(sim_return_pct, 2)
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
    mwr_returns = calculate_mwr_cumulative_return(trades, total_deposits)
    
    # Strategy simulation: "what if $10,000 had followed every signal from day one"
    simulation = simulate_strategy_growth(trades, initial_capital=10000.0, max_slots=3)
    
    # Day-by-day cumulative return series for the simulation, so it can be
    # plotted on the same chart as MWR and SPY
    simulation_returns = calculate_simulation_cumulative_return(simulation)
    

    # Get date range for SPY benchmark - use the SIMULATION's own date range
    # (not MWR's) so alpha compares like-for-like periods. The simulation
    # starts from the very first trade ever taken (including LULU), which
    # can predate the first real deposit.
    if simulation.get('start_date') and simulation.get('end_date'):
        spy_returns = get_spy_benchmark(simulation['start_date'], simulation['end_date'])
    else:
        spy_returns = []
    
    # Calculate performance metrics
    metrics = calculate_performance_metrics(trades)
    
    # Calculate alpha (strategy simulation return - SPY return) - apples to
    # apples, since both are independent of real deposit timing/sizing and
    # cover the exact same date range.
    if spy_returns:
        spy_final_return = spy_returns[-1]['spy_return']
        alpha = simulation['total_return_pct'] - spy_final_return
    else:
        alpha = 0
    
    return {
        'portfolio_state': portfolio_state,
        'mwr_returns': mwr_returns,
        'spy_returns': spy_returns,
        'simulation': simulation,
        'simulation_returns': simulation_returns,
        'metrics': metrics,
        'alpha': round(alpha, 2),
        'trades': trades
    }

