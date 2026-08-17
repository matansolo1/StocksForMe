from datetime import datetime, timedelta
import stock_api
import finance_utils
import pandas as pd
import pytz

# ---------------------------------------------------------------------------
# Trade status constants & predicates (single source of truth)
#
# A trade produced by the weekly scan is NOT a position yet. In the real world
# the order is placed as a GTC (Good-Til-Cancelled) LIMIT order at the signal
# price (last Friday's close), and it is only executed if the market actually
# trades at or below that price. Until then the trade is PENDING_ENTRY.
#
# GTC means the order NEVER expires on its own - it stays live across days and
# weeks, giving a stock time to pull back after profit-taking. It ends only
# when the price touches the limit (-> ACTIVE) or the user cancels it from the
# dashboard (-> NOT_FILLED).
#
#   scan -> PENDING_ENTRY --(price touched target)---> ACTIVE -> HIT_TP/HIT_SL
#                         \--(user cancels manually)-> NOT_FILLED
# ---------------------------------------------------------------------------
STATUS_ACTIVE = "ACTIVE"
STATUS_PENDING_ENTRY = "PENDING_ENTRY"
STATUS_NOT_FILLED = "NOT_FILLED"
STATUS_HIT_TP = "HIT_TP"
STATUS_HIT_SL = "HIT_SL"
STATUS_MANUAL_CLOSE = "MANUAL_CLOSE"

# Statuses that represent a trade that was actually executed AND closed,
# i.e. the only ones that carry a real, realized P&L.
CLOSED_STATUSES = (STATUS_HIT_TP, STATUS_HIT_SL, STATUS_MANUAL_CLOSE)

# Minimum time to wait after the opening bell before evaluating whether a
# pending limit order was filled. Gives yfinance time to publish the first
# intraday candles (and matches the "check ~15 minutes after open" rule).
ENTRY_CHECK_DELAY_MINUTES = 15

# yfinance only serves 5-minute candles for roughly the last 60 days. Beyond
# that a GTC order can no longer be verified automatically, so it is left
# pending for the user to resolve manually rather than silently mis-resolved.
INTRADAY_HISTORY_LIMIT_DAYS = 55

MARKET_TZ = "US/Eastern"


def is_open_position(trade):
    """True only for trades that are actually held right now (money at risk)."""
    return trade.get("status") == STATUS_ACTIVE


def is_pending_entry(trade):
    """True for scanned setups whose limit order has not been filled yet."""
    return trade.get("status") == STATUS_PENDING_ENTRY


def is_not_filled(trade):
    """True for orders that expired without ever being executed."""
    return trade.get("status") == STATUS_NOT_FILLED


def holds_slot(trade):
    """
    True for trades that occupy one of the 3 portfolio slots and reserve cash:
    both open positions and pending (still live) limit orders.
    """
    return trade.get("status") in (STATUS_ACTIVE, STATUS_PENDING_ENTRY)


def is_closed_trade(trade):
    """
    True only for trades that were executed and then closed. NOT_FILLED and
    PENDING_ENTRY must never be counted here - they have no P&L and would
    otherwise pollute win-rate / realized-P&L statistics.
    """
    return trade.get("status") in CLOSED_STATUSES


def get_reserved_capital(trade):
    """
    Capital tied up by a trade. For ACTIVE trades this is quantity * entry_price;
    for PENDING_ENTRY orders it is the cash reserved for the pending fill.
    """
    if is_pending_entry(trade):
        return float(trade.get("reserved_capital", 0) or 0)
    return float(trade.get("quantity", 0) or 0) * float(trade.get("entry_price", 0) or 0)


def _to_market_tz(dt):
    """
    Converts a datetime to US/Eastern. Naive datetimes are interpreted as the
    machine's local time (that is how `datetime.now()` timestamps are stored
    throughout this project).
    """
    eastern = pytz.timezone(MARKET_TZ)
    if dt.tzinfo is None:
        dt = dt.astimezone()  # naive -> aware, using local timezone
    return dt.astimezone(eastern)


def get_entry_session(signal_dt, lookahead_days=10):
    """
    Returns the trading session in which a limit order created at `signal_dt`
    would be live: the first NYSE session that OPENS strictly after the signal.

    A scan run on Sunday evening -> Monday's session. A scan run during
    Monday's session -> Tuesday's session (the order could not have been
    placed before that day's open).

    Args:
        signal_dt: datetime (naive = local time) when the scan produced the setup
        lookahead_days: how many calendar days ahead to search for a session

    Returns:
        (session_date_str "YYYY-MM-DD", market_open_et, market_close_et)
        or (None, None, None) if the calendar is unavailable.
    """
    try:
        import pandas_market_calendars as mcal
        eastern = pytz.timezone(MARKET_TZ)
        signal_et = _to_market_tz(signal_dt)

        nyse = mcal.get_calendar('NYSE')
        schedule = nyse.schedule(
            start_date=signal_et.strftime('%Y-%m-%d'),
            end_date=(signal_et + timedelta(days=lookahead_days)).strftime('%Y-%m-%d')
        )

        for _, row in schedule.iterrows():
            market_open = row['market_open'].tz_convert(eastern)
            market_close = row['market_close'].tz_convert(eastern)
            if market_open > signal_et:
                return market_open.strftime('%Y-%m-%d'), market_open, market_close
    except Exception as e:
        print(f"Error resolving entry session for {signal_dt}: {e}")

    return None, None, None


def get_session_bounds(session_date):
    """
    Returns (market_open_et, market_close_et) for a given NYSE session date
    string ("YYYY-MM-DD"), or (None, None) if it is not a trading day.
    """
    try:
        import pandas_market_calendars as mcal
        eastern = pytz.timezone(MARKET_TZ)
        nyse = mcal.get_calendar('NYSE')
        schedule = nyse.schedule(start_date=session_date, end_date=session_date)
        if schedule.empty:
            return None, None
        row = schedule.iloc[0]
        return row['market_open'].tz_convert(eastern), row['market_close'].tz_convert(eastern)
    except Exception as e:
        print(f"Error resolving session bounds for {session_date}: {e}")
        return None, None


def evaluate_limit_fill(ticker, target_entry, session_date, now_et=None):
    """
    Determines whether a GTC (Good-Til-Cancelled) BUY LIMIT order at
    `target_entry` has been filled at any point from the start of
    `session_date` up to now, using 5-minute candles.

    GTC semantics: the order NEVER expires on its own. It stays live across
    trading sessions until either the price touches the limit, or the user
    cancels it manually from the dashboard. This mirrors how the order is
    actually placed at the broker, and gives a stock a day or two to pull
    back after profit-taking so the setup can still be caught.

    Fill rules (hard limit):
      * If any session OPENS at or below the limit -> filled at that open
        (a marketable limit order executes immediately, at the better price).
      * Otherwise, if any candle's Low touches the limit -> filled at the limit.
      * Otherwise -> still PENDING (indefinitely).

    Note: this function never returns 'NOT_FILLED'. Only an explicit manual
    cancel (`cancel_pending_manually`) can end a pending order.

    Args:
        ticker: ticker symbol
        target_entry: the limit price (float)
        session_date: "YYYY-MM-DD" of the first session the order is live in
        now_et: optional "current time" in US/Eastern (for retroactive checks)

    Returns:
        dict: {
            'outcome': 'FILLED' | 'PENDING' | 'UNKNOWN',
            'fill_price': float|None,
            'fill_time_et': datetime|None,
            'session_open_price': float|None,   # open of the FIRST session
            'session_low': float|None,          # lowest low seen so far
            'sessions_checked': int,
            'reason': str
        }
    """
    eastern = pytz.timezone(MARKET_TZ)
    if now_et is None:
        now_et = datetime.now(eastern)

    result = {
        'outcome': 'UNKNOWN',
        'fill_price': None,
        'fill_time_et': None,
        'session_open_price': None,
        'session_low': None,
        'sessions_checked': 0,
        'reason': ''
    }

    first_open, _first_close = get_session_bounds(session_date)
    if first_open is None:
        # The stored session date is not a trading day (holiday shift etc.).
        # Fall back to the next real session so the order is not lost.
        resolved, first_open, _first_close = get_entry_session(
            datetime.strptime(session_date, "%Y-%m-%d")
        )
        if first_open is None:
            result['outcome'] = 'PENDING'
            result['reason'] = f"could not resolve a trading session from {session_date}"
            return result
        session_date = resolved

    # Order not live yet, or too early in the first session for data to exist
    if now_et < first_open + timedelta(minutes=ENTRY_CHECK_DELAY_MINUTES):
        result['outcome'] = 'PENDING'
        result['reason'] = (f"waiting for session {session_date} "
                            f"(checks start {ENTRY_CHECK_DELAY_MINUTES} min after the open)")
        return result

    # yfinance only serves 5-minute candles for the last ~60 days.
    days_back = (now_et.date() - first_open.date()).days
    if days_back > INTRADAY_HISTORY_LIMIT_DAYS:
        result['outcome'] = 'PENDING'
        result['reason'] = (f"order older than {INTRADAY_HISTORY_LIMIT_DAYS} days - "
                            f"intraday history no longer available, cannot verify automatically")
        return result

    period = f"{max(5, min(days_back + 3, 59))}d"
    df = stock_api.get_intraday_data(ticker, period=period, interval="5m")

    if df is None or df.empty or "Low" not in df.columns or "Open" not in df.columns:
        result['outcome'] = 'PENDING'
        result['reason'] = f"no intraday data available for {ticker} - order left live"
        return result

    # Keep every regular-hours candle from the first session onwards. GTC means
    # we scan ALL sessions since the order was placed, not just the first one.
    try:
        idx = df.index
        if idx.tz is None:
            idx = idx.tz_localize('UTC')
            df = df.copy()
            df.index = idx
        window = df[idx >= first_open]
        # Drop pre/post-market prints: a limit order only executes in RTH here.
        window = window.between_time("09:30", "16:00")
    except Exception as e:
        result['outcome'] = 'PENDING'
        result['reason'] = f"could not filter candles for {ticker}: {e}"
        return result

    if window.empty:
        result['outcome'] = 'PENDING'
        result['reason'] = f"no candles for {ticker} since {session_date} - order left live"
        return result

    result['sessions_checked'] = window.index.normalize().nunique()
    result['session_low'] = float(window["Low"].min())

    # Walk sessions in order; the first session that opens at/below the limit
    # fills at its open, otherwise the first candle that touches it fills at
    # the limit price.
    for session_day, day_candles in window.groupby(window.index.normalize()):
        if day_candles.empty:
            continue

        day_open = float(day_candles["Open"].iloc[0])
        if result['session_open_price'] is None:
            result['session_open_price'] = day_open

        # Case 1: session opens at or below the limit -> immediate fill at open
        if day_open <= target_entry:
            result['outcome'] = 'FILLED'
            result['fill_price'] = day_open
            result['fill_time_et'] = day_candles.index[0].to_pydatetime()
            result['reason'] = (f"{session_day.strftime('%Y-%m-%d')} opened at {day_open:.2f} "
                                f"<= limit {target_entry:.2f} (filled at the open)")
            return result

        # Case 2: price traded down through the limit during the session
        for idx_ts, row in day_candles.iterrows():
            if float(row["Low"]) <= target_entry:
                result['outcome'] = 'FILLED'
                result['fill_price'] = float(target_entry)
                result['fill_time_et'] = idx_ts.to_pydatetime()
                result['reason'] = (f"price touched limit {target_entry:.2f} on "
                                    f"{session_day.strftime('%Y-%m-%d')} "
                                    f"(candle low {float(row['Low']):.2f})")
                return result

    # Never touched so far. GTC -> the order simply stays live.
    days_live = result['sessions_checked']
    result['outcome'] = 'PENDING'
    result['reason'] = (f"limit {target_entry:.2f} not touched in {days_live} "
                        f"session(s) (lowest {result['session_low']:.2f}) - GTC order still live")
    return result


def check_pending_entries(trades):
    """
    Processes all PENDING_ENTRY trades: fills the ones whose limit price was
    actually touched at any point since the order was placed.

    GTC behaviour: orders are NEVER expired automatically. An unfilled order
    stays PENDING_ENTRY indefinitely - across days and weeks - exactly like a
    Good-Til-Cancelled order at the broker. This deliberately gives a stock a
    day or two to pull back after profit-taking so the setup can still be
    caught. Only the user can end an order, via the "Cancel" button on the
    dashboard (`cancel_pending_manually`).

    On fill, the trade is converted into a real position:
      * entry_price = the ACTUAL fill price (may be better than the limit)
      * stop_loss / take_profit are RECALCULATED from that fill price
      * quantity    = reserved capital / fill price
      * timestamp   = the real execution time

    Inputs: trades (list)
    Output: list (updated trades)
    """
    eastern = pytz.timezone(MARKET_TZ)
    now_et = datetime.now(eastern)

    for trade in trades:
        if not is_pending_entry(trade):
            continue

        ticker = trade.get("ticker")
        target_entry = trade.get("target_entry", trade.get("entry_price"))
        session_date = trade.get("entry_session_date")

        if not ticker or not target_entry or not session_date:
            print(f"⚠️ Skipping malformed pending entry: {trade.get('ticker', '?')}")
            continue

        try:
            evaluation = evaluate_limit_fill(ticker, float(target_entry), session_date, now_et=now_et)
        except Exception as e:
            print(f"Error evaluating pending entry for {ticker}: {e}")
            continue

        trade["entry_check_note"] = evaluation['reason']
        trade["entry_last_checked"] = now_et.strftime("%Y-%m-%d %H:%M:%S %Z")

        if evaluation['outcome'] == 'FILLED':
            apply_entry_fill(
                trade,
                fill_price=evaluation['fill_price'],
                fill_time_et=evaluation['fill_time_et'],
                note=evaluation['reason']
            )
            print(f"🟢 {ticker} limit order FILLED at ${evaluation['fill_price']:.2f} - {evaluation['reason']}")
        else:
            # GTC: never auto-expire. The order stays live until the user
            # cancels it explicitly from the dashboard.
            trade["sessions_waiting"] = evaluation.get('sessions_checked', 0)
            print(f"⏳ {ticker} still pending - {evaluation['reason']}")

    return trades


def apply_entry_fill(trade, fill_price, fill_time_et=None, note=""):
    """
    Converts a PENDING_ENTRY trade into an ACTIVE position at `fill_price`,
    recalculating SL/TP and quantity from the ACTUAL execution price.

    Args:
        trade: the pending trade dict (mutated in place)
        fill_price: actual execution price (float)
        fill_time_et: datetime of the fill (US/Eastern). Defaults to now.
        note: human-readable explanation stored on the trade
    """
    fill_price = float(fill_price)
    if fill_price <= 0:
        raise ValueError("fill_price must be greater than 0")

    if fill_time_et is None:
        fill_time_et = datetime.now(pytz.timezone(MARKET_TZ))

    # Store the execution time in local time, matching the project convention
    # for `timestamp` (every other timestamp comes from datetime.now()).
    fill_time_local = fill_time_et.astimezone()

    sl_pct = float(trade.get("stop_loss_pct", 5.0))
    tp_pct = float(trade.get("take_profit_pct", 10.0))
    reserved_capital = float(trade.get("reserved_capital", 0) or 0)

    trade["status"] = STATUS_ACTIVE
    trade["entry_price"] = fill_price
    trade["stop_loss"] = fill_price * (1 - sl_pct / 100.0)
    trade["take_profit"] = fill_price * (1 + tp_pct / 100.0)
    trade["quantity"] = (reserved_capital / fill_price) if reserved_capital > 0 else trade.get("quantity", 0)
    trade["timestamp"] = fill_time_local.strftime("%Y-%m-%d %H:%M:%S")
    trade["fill_timestamp_et"] = fill_time_et.strftime("%Y-%m-%d %H:%M:%S %Z")
    trade["current_price"] = fill_price
    trade["pnl_pct"] = 0.0
    trade["entry_fill_note"] = note or f"Filled at ${fill_price:.2f}"
    return trade


def expire_pending_entry(trade, note=""):
    """
    Marks a PENDING_ENTRY trade as NOT_FILLED: the order ended without ever
    being executed, so no position was opened. Capital and the slot are freed,
    and no commission is charged.

    Under GTC this is only ever reached through an explicit user action
    (the "Cancel" button / `cancel_pending_manually`), or from the retroactive
    audit tool. Nothing in the automatic cycle calls it.
    """
    trade["status"] = STATUS_NOT_FILLED
    trade["quantity"] = 0
    trade["reserved_capital"] = 0
    trade["commission_entry"] = 0
    trade["commission_exit"] = 0
    trade["total_commission"] = 0
    trade["pnl_pct"] = 0.0
    trade["entry_fill_note"] = note or "Limit order expired unfilled"
    trade["expired_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return trade


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
    First resolves pending limit orders (fill / expire), then checks intraday
    5-minute candles for precise SL/TP detection, then updates current prices
    with daily data.
    Uses fallback methods for weekend/market closed scenarios.
    Inputs: trades (list)
    Output: list (updated trades)
    """
    # Step 0: resolve pending limit orders BEFORE anything else, so a trade
    # that just got filled is immediately eligible for SL/TP checks, and one
    # that expired unfilled never reaches the P&L logic at all.
    trades = check_pending_entries(trades)

    # Then, check intraday candles for precise stop loss / take profit detection
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
                    price_source = f"As of the market close on {last_date}"
                except Exception as e:
                    print(f"Error parsing live data for {ticker}: {e}")
            
            # Method 2: Fallback to get_last_price (works on weekends)
            if current_price is None:
                print(f"📊 {ticker}: using the last closing price (market closed)")
                current_price, last_date = stock_api.get_last_price(ticker)
                if current_price and last_date:
                    price_source = f"As of the last market close ({last_date})"
                elif current_price:
                    price_source = "As of the last market close"
            
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
                print(f"❌ {ticker}: could not fetch a price - skipping update")
                
    return trades


def add_new_trades(trades, new_setups, max_positions=3, position_size_usd=1000.0, commission_per_trade=2.5,
                    cash_available=None, stop_loss_pct=5.0, take_profit_pct=10.0, signal_dt=None, scan_as_of=None):
    """
    Adds new setups from the scanner as PENDING_ENTRY limit orders, if there's
    room in the portfolio. Only fills empty slots - does not close existing
    positions.

    IMPORTANT (real-world entry model): a setup found by the Sunday scan is NOT
    a position. It is a BUY LIMIT order at the signal price (Friday's close)
    that will only be executed if the market actually trades at or below that
    price during the next session. `check_pending_entries()` resolves it later
    into ACTIVE (filled) or NOT_FILLED (expired). This prevents the system from
    reporting phantom positions for stocks that gapped up above the target and
    were therefore never bought.

    Position sizing: if cash_available is provided, the position size is
    split across the number of currently EMPTY slots (max_positions minus
    open/pending trades), not just the number of setups actually found this
    run. This deliberately reserves capital for slots that stay empty this
    week (e.g. 2 setups found with an empty 3-slot portfolio -> each setup
    gets 1/3 of cash, not 1/2), so a slot is always kept free for future
    opportunities rather than fully deploying cash into fewer names.

    Args:
        trades: List of existing trades
        new_setups: List of new setup dictionaries from scanner
        max_positions: Maximum concurrent positions
        position_size_usd: Fallback/base position size in USD (used if cash_available is None)
        commission_per_trade: Commission per trade in USD (default: $2.5)
        cash_available: Total cash available in USD to split among new setups (optional)
        stop_loss_pct: Stop loss percentage, stored so SL can be recalculated
                        from the ACTUAL fill price (default: 5.0)
        take_profit_pct: Take profit percentage, stored for the same reason
                        (default: 10.0)
        signal_dt: optional datetime to use as the signal timestamp instead of
                        datetime.now(). Used by the Catch-Up Scan to backdate
                        the signal to "last Sunday evening" so the GTC limit
                        order resolves into the correct (already-past) entry
                        session instead of a future one.
        scan_as_of: optional "YYYY-MM-DD" string recorded on the trade for
                        traceability when it came from a retroactive
                        Catch-Up Scan (None for a normal live scan).
    """
    # Both open positions AND live pending orders occupy a slot and reserve
    # cash - otherwise a second scan could allocate the same money twice.
    active_trades = [t for t in trades if holds_slot(t)]
    active_tickers = [t['ticker'] for t in active_trades]

    slots_available = max_positions - len(active_trades)

    # Setups that will actually be added (not already active, within slot limit)
    fillable_setups = [s for s in new_setups if s['Ticker'] not in active_tickers][:max(0, slots_available)]
    num_setups = len(fillable_setups)

    # Determine position size for this batch. Always split by the number of
    # EMPTY slots (never just the setups found), so unused slots keep their
    # share of cash reserved for future scans instead of it being deployed
    # into fewer names.
    if cash_available is not None and num_setups > 0 and slots_available > 0:
        divisor = max(2, slots_available)
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
            trade_signal_dt = signal_dt or datetime.now()

            # Resolve the FIRST trading session in which this limit order goes
            # live. Being GTC, it has no deadline - it stays active from this
            # session onwards until filled or manually cancelled.
            session_date, _session_open, _session_close = get_entry_session(trade_signal_dt)

            trade = {
                "ticker": s['Ticker'],
                # entry_price starts as the target; it is overwritten with the
                # ACTUAL fill price once the order executes.
                "entry_price": entry_price,
                "target_entry": entry_price,
                "signal_price": entry_price,
                "take_profit": s.get('TakeProfit', s['SMA_20']),
                "stop_loss": s['StopLoss'],
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct,
                "risk_reward": s['RiskReward'],
                "rsi": s['RSI_14'],
                "status": STATUS_PENDING_ENTRY,
                "timestamp": trade_signal_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "signal_timestamp": trade_signal_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "entry_session_date": session_date,
                "time_in_force": "GTC",  # no expiry - cancelled manually only
                "sessions_waiting": 0,
                "weight_pct": weight_per_trade,
                # Cash is reserved now; quantity is only final once we know the
                # real fill price (which may be better than the limit).
                "reserved_capital": batch_position_size,
                "quantity": batch_position_size / entry_price if entry_price else 0,
                "commission_entry": commission_per_trade,
                "commission_exit": 0,  # Will be set when position closes
                "total_commission": commission_per_trade  # Will be updated on exit
            }
            if scan_as_of:
                # Marks this trade as coming from a retroactive Catch-Up Scan,
                # evaluated on the close of this date rather than live data.
                trade["scan_as_of"] = scan_as_of
            trades.append(trade)
            active_trades.append(trade)
            active_tickers.append(trade['ticker'])
            added_any = True
            print(f"📋 Placed GTC LIMIT order: {trade['ticker']} @ ${entry_price:.2f} "
                  f"(live from {session_date}, Weight: {weight_per_trade}%, Reserved: ${batch_position_size})")

    return trades, added_any


def fill_pending_manually(trades, ticker, fill_price, fill_timestamp=None):
    """
    Manually marks a PENDING_ENTRY order as filled. Used to sync with the real
    broker when the actual execution differs from what yfinance data suggests
    (e.g. the broker filled slightly off, or on a venue with different prints).

    Args:
        trades: List of existing trades
        ticker: Ticker symbol of the PENDING_ENTRY order
        fill_price: The actual execution price (float)
        fill_timestamp: Optional "YYYY-MM-DD HH:MM:SS" (local time). Defaults to now.

    Returns:
        (trades, success: bool, message: str)
    """
    target_trade = None
    for trade in trades:
        if trade.get("ticker") == ticker and is_pending_entry(trade):
            target_trade = trade
            break

    if target_trade is None:
        message = f"No pending order found for {ticker}"
        print(f"❌ fill_pending_manually: {message}")
        return trades, False, message

    try:
        fill_price = float(fill_price)
    except (TypeError, ValueError):
        message = "Invalid fill price (fill_price)"
        print(f"❌ fill_pending_manually: {message}")
        return trades, False, message

    if fill_price <= 0:
        message = "Fill price must be greater than 0"
        print(f"❌ fill_pending_manually: {message}")
        return trades, False, message

    eastern = pytz.timezone(MARKET_TZ)
    if fill_timestamp:
        try:
            naive_dt = datetime.strptime(fill_timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            message = "Invalid fill date format (expected YYYY-MM-DD HH:MM:SS)"
            print(f"❌ fill_pending_manually: {message}")
            return trades, False, message
        fill_dt_et = naive_dt.astimezone().astimezone(eastern)
    else:
        fill_dt_et = datetime.now(eastern)

    apply_entry_fill(target_trade, fill_price, fill_time_et=fill_dt_et,
                     note="Filled manually (broker sync)")

    message = f"{ticker} was marked as manually filled at ${fill_price:.2f}"
    print(f"✍️ {message}")
    return trades, True, message


def cancel_pending_manually(trades, ticker, reason=None):
    """
    Manually cancels a PENDING_ENTRY order (the position was never opened in
    the real broker account). Frees the slot and the reserved cash.

    Args:
        trades: List of existing trades
        ticker: Ticker symbol of the PENDING_ENTRY order
        reason: Optional human-readable reason

    Returns:
        (trades, success: bool, message: str)
    """
    target_trade = None
    for trade in trades:
        if trade.get("ticker") == ticker and is_pending_entry(trade):
            target_trade = trade
            break

    if target_trade is None:
        message = f"No pending order found for {ticker}"
        print(f"❌ cancel_pending_manually: {message}")
        return trades, False, message

    expire_pending_entry(target_trade, note=reason or "Cancelled manually - no actual buy was executed")

    message = f"The order for {ticker} was cancelled - no position was opened"
    print(f"🚫 {message}")
    return trades, True, message


def close_trade_manually(trades, ticker, exit_price, exit_timestamp=None):
    """
    Manually closes an ACTIVE trade (exception to the standard SL/TP-only exit rule).
    Used for special cases like a sharp after-hours move around earnings, or for
    closing a position retroactively (backdated exit_timestamp).

    Args:
        trades: List of existing trades
        ticker: Ticker symbol of the ACTIVE trade to close
        exit_price: The price at which the trade is being closed (float)
        exit_timestamp: Optional string "YYYY-MM-DD HH:MM:SS". Defaults to now()
                         if not provided (e.g. for a retroactive/backdated close).

    Returns:
        (trades, success: bool, message: str)
    """
    # Find the ACTIVE trade matching this ticker (there should be at most one)
    target_trade = None
    for trade in trades:
        if trade.get("ticker") == ticker and trade.get("status") == "ACTIVE":
            target_trade = trade
            break

    if target_trade is None:
        message = f"No active position found for {ticker}"
        print(f"❌ close_trade_manually: {message}")
        return trades, False, message

    try:
        exit_price = float(exit_price)
    except (TypeError, ValueError):
        message = "Invalid exit price (exit_price)"
        print(f"❌ close_trade_manually: {message}")
        return trades, False, message

    if exit_price <= 0:
        message = "Exit price must be greater than 0"
        print(f"❌ close_trade_manually: {message}")
        return trades, False, message

    # Determine exit timestamp - default to now, but allow backdating
    if exit_timestamp:
        try:
            # Validate provided timestamp format
            datetime.strptime(exit_timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            message = "Invalid exit date format (expected YYYY-MM-DD HH:MM:SS)"
            print(f"❌ close_trade_manually: {message}")
            return trades, False, message
    else:
        exit_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update the trade to reflect the manual close
    target_trade["status"] = "MANUAL_CLOSE"
    target_trade["exit_price"] = exit_price
    target_trade["exit_timestamp"] = exit_timestamp
    target_trade["current_price"] = exit_price
    target_trade["pnl_pct"] = finance_utils.calculate_pnl_pct(exit_price, target_trade["entry_price"])
    target_trade["exit_reason"] = "MANUAL_CLOSE"

    # Add exit commission, matching the pattern used by SL/TP auto-close logic
    commission = target_trade.get("commission_entry", 2.5)
    target_trade["commission_exit"] = commission
    target_trade["total_commission"] = target_trade.get("commission_entry", commission) + commission

    message = f"{ticker} was closed manually at ${exit_price:.2f} (P&L: {target_trade['pnl_pct']:+.2f}%)"
    print(f"✋ {message}")

    return trades, True, message
