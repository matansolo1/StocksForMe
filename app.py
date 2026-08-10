from flask import Flask, redirect, url_for, jsonify, render_template_string, request
import subprocess
import os
import json
from datetime import datetime
import pytz
import data_manager
import ui_generator


app = Flask(__name__)

DASHBOARD_FILE = "output/tracker_dashboard.html"

DEPOSIT_FORM_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Weekly Scan - Deposit</title>
    <style>
        body { background: #0a0a0a; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #141414; padding: 40px; border-radius: 16px; border: 1px solid #262626; text-align: center; width: 450px; }
        input, select { background: #1a1a1a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; margin: 10px 0; box-sizing: border-box; }
        .btn { background: #ff5252; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 1.1rem; margin-top: 15px; }
        .param-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 10px 0; }
        label { display: block; color: #aaa; font-size: 0.8rem; text-align: left; margin-bottom: 2px; }
        .deposit-section { text-align: left; margin-top: 15px; border-top: 1px solid #262626; padding-top: 15px; }
        .currency-toggle { display: flex; gap: 8px; margin: 10px 0; }
        .currency-toggle label { display: flex; align-items: center; gap: 6px; color: #ddd; font-size: 0.9rem; margin-bottom: 0; cursor: pointer; }
        .currency-toggle input[type="radio"] { width: auto; margin: 0; }
        #ils-fields { display: block; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Weekly Scan Setup</h2>
        <form action="/execute-scan" method="post">
            <div class="param-grid">
                <div>
                    <label>Target RSI:</label>
                    <input type="number" id="live-rsi" name="target_rsi" value="55">
                </div>
                <div>
                    <label>Stop Loss %:</label>
                    <input type="number" id="live-sl" name="stop_loss_pct" value="5.0" step="0.1">
                </div>
                <div>
                    <label>Take Profit %:</label>
                    <input type="number" id="live-tp" name="take_profit_pct" value="10.0" step="0.1">
                </div>
            </div>

            <div class="deposit-section">
                <label>Deposit Date:</label>
                <input type="date" name="deposit_date" id="deposit_date" value="{{ today }}">

                <label style="margin-top: 10px;">Deposit Type:</label>
                <div class="currency-toggle">
                    <label><input type="radio" name="deposit_currency" value="ILS" checked onchange="toggleDepositFields()"> ILS deposit (with conversion)</label>
                    <label><input type="radio" name="deposit_currency" value="USD" onchange="toggleDepositFields()"> Direct USD deposit</label>
                </div>

                <label id="amount-label">Deposit Amount (₪):</label>
                <input type="number" name="deposit" step="0.01" value="0" autofocus>

                <div id="ils-fields">
                    <label>Conversion Fee (USD):</label>
                    <input type="number" name="conversion_fee" id="conversion_fee" step="0.01" value="{{ default_deposit_fee }}">
                    <div style="color:#777; font-size:0.75rem; margin-top:-6px;">The USD rate for the selected date is fetched automatically.</div>
                </div>
            </div>
            <button type="submit" class="btn">Confirm & Run Scan</button>
        </form>
    </div>

    <script>
        function toggleDepositFields() {
            const isIls = document.querySelector('input[name="deposit_currency"]:checked').value === 'ILS';
            document.getElementById('ils-fields').style.display = isIls ? 'block' : 'none';
            document.getElementById('amount-label').innerText = isIls ? 'Deposit Amount (₪):' : 'Deposit Amount ($):';
        }
        toggleDepositFields();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    if not os.path.exists(DASHBOARD_FILE):
        subprocess.run(["python", "tracker.py"], env={**os.environ, "FLASK_TRIGGERED": "true"})
    
    if os.path.exists(DASHBOARD_FILE):
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return "<h1>Dashboard not found. Please run a scan or refresh.</h1><a href='/run-scan'>Run Weekly Scan</a>"

@app.route('/run-scan')
def run_scan():
    import currency_manager
    default_fee = currency_manager.get_default_deposit_fee()
    today_str = datetime.now().strftime('%Y-%m-%d')
    return render_template_string(DEPOSIT_FORM_HTML, default_deposit_fee=default_fee, today=today_str)

def _sync_deposits_metadata():
    """
    Mirrors the aggregate deposit totals from deposits_history.json into the
    trades DB's portfolio_metadata, so portfolio calculations (cash available,
    next position size, etc.) always reflect the latest deposits.
    Shared by execute_scan() and api_create_deposit() to keep them in sync (DRY).
    """
    import currency_manager
    history = currency_manager.load_deposits_history()
    meta = history.get('metadata', {})
    data_manager.update_metadata(
        total_deposits=meta.get('total_deposits_usd_net', 0.0),
        total_deposits_gross=meta.get('total_deposits_usd_gross', 0.0),
        total_conversion_fees=meta.get('total_conversion_fees_usd', 0.0)
    )


@app.route('/execute-scan', methods=['POST'])
def execute_scan():
    deposit_amount = float(request.form.get('deposit', 0))
    deposit_currency = request.form.get('deposit_currency', 'USD')
    deposit_date = request.form.get('deposit_date') or datetime.now().strftime('%Y-%m-%d')
    conversion_fee_raw = request.form.get('conversion_fee')
    strategy_mode = 'momentum'
    target_rsi = float(request.form.get('target_rsi', 55.0))
    stop_loss_pct = float(request.form.get('stop_loss_pct', 5.0))
    take_profit_pct = float(request.form.get('take_profit_pct', 10.0))
    
    if deposit_amount > 0:
        import currency_manager

        conversion_fee = None
        if deposit_currency.upper() == 'ILS' and conversion_fee_raw not in (None, ''):
            try:
                conversion_fee = float(conversion_fee_raw)
            except (TypeError, ValueError):
                conversion_fee = None

        deposit_info = currency_manager.add_deposit(
            amount=deposit_amount,
            currency=deposit_currency,
            date=deposit_date,
            conversion_fee=conversion_fee,
            description=f"Weekly scan deposit - {deposit_date}"
        )
        _sync_deposits_metadata()
    
    # Instead of running scanner.py as a subprocess and blocking, we render a scanning page

    # that connects to the SSE stream.
    return render_template_string(
        SCANNING_HTML,
        strategy_mode=strategy_mode,
        target_rsi=target_rsi,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct
    )

SCANNING_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Weekly Scan - Progress</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0a0a0a; color: #ffffff; }
    </style>
</head>
<body class="flex flex-col items-center justify-center min-h-screen p-4">
    <div class="w-full max-w-2xl bg-[#141414] border border-[#262626] rounded-2xl p-8 shadow-2xl">
        <h2 class="text-2xl font-extrabold mb-2 text-center text-white">Weekly Market Scan</h2>
        <p class="text-gray-400 text-sm text-center mb-6">Scanning ~100 tickers for Momentum Breakout setups...</p>
        
        <!-- Progress Bar -->
        <div class="mb-6">
            <div class="flex justify-between text-sm font-semibold mb-2">
                <span id="status-text" class="text-gray-300">Initializing...</span>
                <span id="progress-text" class="text-[#ff5252]">0%</span>
            </div>
            <div class="w-full bg-[#1a1a1a] rounded-full h-4 border border-[#333]">
                <div id="progress-bar" class="bg-gradient-to-r from-[#ff5252] to-[#ff7b7b] h-full rounded-full transition-all duration-300" style="width: 0%"></div>
            </div>
        </div>

        <!-- Live Activity Log -->
        <div class="mb-6">
            <h3 class="text-sm font-bold text-gray-400 mb-2 uppercase tracking-wider">Live Activity Log</h3>
            <div id="activity-log" class="w-full h-64 bg-black border border-[#262626] rounded-xl p-4 font-mono text-xs overflow-y-auto text-green-400 flex flex-col gap-1">
                <div class="text-gray-500">[System] Ready to start stream...</div>
            </div>
        </div>

        <div class="flex justify-center">
            <button id="done-btn" class="bg-[#ff5252] hover:bg-[#ff7b7b] text-white font-bold py-3 px-8 rounded-xl transition duration-300 opacity-50 cursor-not-allowed" disabled onclick="window.location.href='/'">
                Waiting for completion...
            </button>
        </div>
    </div>

    <script>
        const logBox = document.getElementById('activity-log');
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const statusText = document.getElementById('status-text');
        const doneBtn = document.getElementById('done-btn');

        function appendLog(message, type = 'info') {
            const div = document.createElement('div');
            let colorClass = 'text-green-400';
            if (message.includes('Failed') || message.includes('Error')) {
                colorClass = 'text-red-400';
            } else if (message.includes('Skipped') || message.includes('Skipping')) {
                colorClass = 'text-yellow-500';
            } else if (message.includes('Found setup')) {
                colorClass = 'text-cyan-400 font-bold';
            } else if (message.includes('[System]')) {
                colorClass = 'text-gray-500';
            }
            div.className = colorClass;
            div.innerText = `[${new Date().toLocaleTimeString()}] ${message}`;
            logBox.appendChild(div);
            logBox.scrollTop = logBox.scrollHeight;
        }

        const eventSource = new EventSource('/api/scan-stream?strategy_mode={{ strategy_mode }}&target_rsi={{ target_rsi }}&stop_loss_pct={{ stop_loss_pct }}&take_profit_pct={{ take_profit_pct }}');

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.progress !== undefined) {
                const pct = Math.round(data.progress);
                progressBar.style.width = pct + '%';
                progressText.innerText = pct + '%';
            }

            if (data.message) {
                appendLog(data.message);
                statusText.innerText = data.message;
            }

            if (data.complete) {
                appendLog('[System] Scan completed successfully!', 'system');
                statusText.innerText = 'Scan Complete!';
                doneBtn.innerText = 'View Dashboard';
                doneBtn.className = 'bg-green-500 hover:bg-green-400 text-white font-bold py-3 px-8 rounded-xl transition duration-300 cursor-pointer';
                doneBtn.disabled = false;
                eventSource.close();
            }
        };

        eventSource.onerror = function(err) {
            appendLog('Error: Connection to scan stream lost.', 'error');
            statusText.innerText = 'Connection Error';
            eventSource.close();
        };
    </script>
</body>
</html>
"""

@app.route('/api/scan-stream')
def scan_stream():
    from flask import Response, request

    import scanner
    import trading_logic
    import data_manager
    import analytics_generator
    
    strategy_mode = 'momentum'  # Fixed to momentum strategy
    target_rsi = float(request.args.get('target_rsi', 55.0))
    stop_loss_pct = float(request.args.get('stop_loss_pct', 5.0))
    take_profit_pct = float(request.args.get('take_profit_pct', 10.0))
    
    def generate():
        db = data_manager.load_db()
        trades = db["trades"]
        metadata = db["portfolio_metadata"]
        
        total_deposits = metadata.get("total_deposits", 0)
        commission_per_trade = metadata.get("commission_per_trade", 2.5)
        
        # Calculate portfolio state using analytics_generator
        portfolio_state = analytics_generator.calculate_portfolio_state(trades, total_deposits, commission_per_trade)
        
        # Calculate a preliminary position size estimate (used only to check if any cash exists).
        # Pending limit orders occupy a slot too - they are live orders at the broker.
        active_count = len([t for t in trades if trading_logic.holds_slot(t)])
        pos_size = analytics_generator.calculate_position_size(portfolio_state, max_positions=3, active_positions=active_count)
        
        if pos_size <= 0:
            yield f"data: {json.dumps({'progress': 0, 'message': 'No cash available for new positions. Close existing trades first.'})}\n\n"
            yield f"data: {json.dumps({'progress': 100, 'complete': True})}\n\n"
            return
            
        top_setups = []
        
        # Stream the scan progress
        for event in scanner.scan_universe_generator(strategy_mode, target_rsi, stop_loss_pct, take_profit_pct):
            if "top_setups" in event:
                top_setups = event["top_setups"]
            yield f"data: {json.dumps(event)}\n\n"
            
        # Once scan is complete, add new trades to fill empty slots.
        # Recalculate position size NOW that we know exactly how many setups were found,
        # so a single setup found in an empty portfolio gets a fair share of cash
        # (e.g. 50% instead of a flat 33% split across all 3 slots).
        yield f"data: {json.dumps({'progress': 100, 'message': 'Adding new trades (filling empty slots)...'})}\n\n"
        
        cash_available = portfolio_state['cash_available']
        # stop_loss_pct / take_profit_pct are stored on each pending order so
        # SL/TP can be recalculated from the ACTUAL fill price later.
        trades, added = trading_logic.add_new_trades(
            trades, top_setups, position_size_usd=pos_size,
            commission_per_trade=commission_per_trade, cash_available=cash_available,
            stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct
        )
        data_manager.save_trades(trades)

        
        yield f"data: {json.dumps({'progress': 100, 'message': 'Triggering tracker update...'})}\n\n"
        
        # Run tracker update to generate the new dashboard
        import tracker
        trades = data_manager.load_trades()
        updated_trades = trading_logic.update_portfolio_status(trades)
        data_manager.save_trades(updated_trades)
        ui_generator.generate_dashboard_file(updated_trades)
        
        yield f"data: {json.dumps({'progress': 100, 'message': 'Dashboard updated!', 'complete': True})}\n\n"
        
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/close-trade', methods=['POST'])
def api_close_trade():
    """
    Manually closes an ACTIVE trade (exception to the standard SL/TP-only exit rule).
    Used for special cases like a sharp after-hours move around earnings, or for
    closing a position retroactively with a backdated exit timestamp.
    Expects JSON: { ticker, exit_price, exit_timestamp (optional) }
    """
    import trading_logic

    data = request.get_json() or {}
    ticker = data.get('ticker')
    exit_price = data.get('exit_price')
    exit_timestamp = data.get('exit_timestamp')  # Optional, defaults to now()

    if not ticker or exit_price is None:
        return jsonify({"success": False, "message": "Missing ticker or exit_price"}), 400

    try:
        exit_price = float(exit_price)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid exit_price"}), 400

    trades = data_manager.load_trades()
    trades, success, message = trading_logic.close_trade_manually(trades, ticker, exit_price, exit_timestamp)

    if success:
        data_manager.save_trades(trades)
        # Recalculate and persist portfolio state (equity, cash available, P&L, etc.)
        # so the analytics dashboard and cash-available figures are immediately in sync.
        data_manager.update_portfolio_state(trades)
        # Regenerate the dashboard so the change is reflected immediately
        ui_generator.generate_dashboard_file(trades)

    return jsonify({"success": success, "message": message})


@app.route('/api/check-pending', methods=['POST'])
def api_check_pending():
    """
    Forces an immediate evaluation of all PENDING_ENTRY limit orders, instead
    of waiting for the next 15-minute auto-refresh cycle. Fills the orders
    whose limit price was actually touched during their entry session, and
    expires the ones whose session ended without a fill.
    """
    import trading_logic

    trades = data_manager.load_trades()
    trades = trading_logic.check_pending_entries(trades)
    data_manager.save_trades(trades)
    data_manager.update_portfolio_state(trades)

    still_pending = len([t for t in trades if trading_logic.is_pending_entry(t)])
    ui_generator.generate_dashboard_file(trades)

    return jsonify({
        "success": True,
        "message": f"Pending orders checked. {still_pending} orders are still open.",
        "pending_count": still_pending
    })


@app.route('/api/fill-pending', methods=['POST'])
def api_fill_pending():
    """
    Manually marks a PENDING_ENTRY order as filled (broker sync).
    Expects JSON: { ticker, fill_price, fill_timestamp (optional) }
    """
    import trading_logic

    data = request.get_json() or {}
    ticker = data.get('ticker')
    fill_price = data.get('fill_price')
    fill_timestamp = data.get('fill_timestamp')

    if not ticker:
        return jsonify({"success": False, "message": "Missing ticker."}), 400
    if fill_price is None:
        return jsonify({"success": False, "message": "Missing fill_price."}), 400

    trades = data_manager.load_trades()
    trades, success, message = trading_logic.fill_pending_manually(
        trades, ticker, fill_price, fill_timestamp
    )

    if success:
        data_manager.save_trades(trades)
        data_manager.update_portfolio_state(trades)
        try:
            ui_generator.generate_dashboard_file(trades)
        except Exception as e:
            print(f"Warning: could not regenerate dashboard after manual fill: {e}")
        return jsonify({"success": True, "message": message})

    return jsonify({"success": False, "message": message}), 400


@app.route('/api/cancel-pending', methods=['POST'])
def api_cancel_pending():
    """
    Manually cancels a PENDING_ENTRY order - the position was never opened.
    Frees the slot and the reserved cash.
    Expects JSON: { ticker, reason (optional) }
    """
    import trading_logic

    data = request.get_json() or {}
    ticker = data.get('ticker')
    reason = data.get('reason')

    if not ticker:
        return jsonify({"success": False, "message": "Missing ticker."}), 400

    trades = data_manager.load_trades()
    trades, success, message = trading_logic.cancel_pending_manually(trades, ticker, reason)

    if success:
        data_manager.save_trades(trades)
        data_manager.update_portfolio_state(trades)
        try:
            ui_generator.generate_dashboard_file(trades)
        except Exception as e:
            print(f"Warning: could not regenerate dashboard after cancel: {e}")
        return jsonify({"success": True, "message": message})

    return jsonify({"success": False, "message": message}), 400


@app.route('/refresh-tracker')
def refresh_tracker():
    subprocess.run(["python", "tracker.py"], env={**os.environ, "FLASK_TRIGGERED": "true"})
    return redirect(url_for('index'))


@app.route('/api/dry-run-stream')
def dry_run_stream():
    from flask import Response, request
    import scanner
    import data_manager

    
    strategy_mode = 'momentum'  # Fixed to momentum strategy
    target_rsi = float(request.args.get('target_rsi', 55.0))
    stop_loss_pct = float(request.args.get('stop_loss_pct', 5.0))
    take_profit_pct = float(request.args.get('take_profit_pct', 10.0))
    
    def generate():
        # Load current occupied slots (open positions + live pending orders)
        import trading_logic
        trades = data_manager.load_trades()
        active_count = len([t for t in trades if trading_logic.holds_slot(t)])
        slots_available = max(0, 3 - active_count)  # Ensure non-negative
        
        # Send initial status message
        yield f"data: {json.dumps({'progress': 0, 'message': f'Active Positions: {active_count}/3 | Scanning for {slots_available} new setups...', 'active_positions': active_count, 'slots_available': slots_available})}\n\n"
        
        for event in scanner.scan_universe_generator(strategy_mode, target_rsi, stop_loss_pct, take_profit_pct):
            # Limit top_setups to available slots
            if "top_setups" in event and "complete" in event:
                # Only limit when scan is complete
                event["top_setups"] = event["top_setups"][:slots_available]
                event["active_positions"] = active_count
                event["slots_available"] = slots_available
            yield f"data: {json.dumps(event)}\n\n"
            
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/market-status')
def market_status():
    import pandas_market_calendars as mcal
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    today_str = now_eastern.strftime('%Y-%m-%d')
    
    nyse = mcal.get_calendar('NYSE')
    schedule = nyse.schedule(start_date=today_str, end_date=today_str)
    
    is_trading_day = not schedule.empty
    is_open = False
    message = "Market Closed (US)"
    
    if is_trading_day:
        market_open = schedule.iloc[0]['market_open'].to_pydatetime()
        market_close = schedule.iloc[0]['market_close'].to_pydatetime()
        now_utc = datetime.now(pytz.utc)
        is_open = market_open <= now_utc <= market_close
        if is_open:
            message = "Market Open (US)"
        else:
            message = "Market Closed (US)"
    else:
        is_weekday = now_eastern.weekday() <= 4
        if is_weekday:
            message = "Market Closed (US Holiday)"
        else:
            message = "Market Closed (Weekend)"
            
    return jsonify({
        "status": "open" if is_open else "closed",
        "message": message
    })

@app.route('/under-the-hood')
def under_the_hood():
    with open("output/under_the_hood.html", "r", encoding="utf-8") as f:
        return f.read()

@app.route('/api/backtest', methods=['POST'])
def api_backtest():
    import backtester
    data = request.get_json() or {}
    initial_capital = float(data.get('initial_capital', 10000.0))
    target_rsi = float(data.get('target_rsi', 55.0))
    stop_loss_pct = float(data.get('stop_loss_pct', 5.0))
    take_profit_pct = float(data.get('take_profit_pct', 10.0))
    strategy_mode = 'momentum'  # Fixed to momentum strategy
    use_monte_carlo = data.get('use_monte_carlo', True)  # Default to True for enhanced accuracy
    
    results = backtester.run_backtest(
        initial_capital=initial_capital,
        target_rsi=target_rsi,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        strategy_mode=strategy_mode,
        use_monte_carlo=use_monte_carlo
    )
    return jsonify(results)

@app.route('/trade-analytics')
def trade_analytics():
    with open("output/trade_analytics.html", "r", encoding="utf-8") as f:
        return f.read()

@app.route('/api/trade-analytics')
def api_trade_analytics():
    import analytics_generator
    
    # Load trades and metadata
    trades = data_manager.load_trades()
    metadata = data_manager.get_metadata()
    total_deposits = metadata.get("total_deposits", 0)
    
    # Prepare analytics data
    analytics_data = analytics_generator.prepare_analytics_data(trades, total_deposits)
    
    return jsonify(analytics_data)


@app.route('/api/current-fx-rate')
def api_current_fx_rate():
    """Get current USD/ILS exchange rate"""
    import currency_manager
    rate = currency_manager.get_live_usd_ils_rate()
    return jsonify({
        "rate": round(rate, 4),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/api/deposits')
def api_get_deposits():
    """Returns all deposit records plus the current default FX rate and default deposit fee."""
    import currency_manager
    deposits = currency_manager.get_all_deposits()
    default_rate = currency_manager.get_default_fx_rate()
    default_fee = currency_manager.get_default_deposit_fee()
    return jsonify({
        "deposits": deposits,
        "default_fx_rate": default_rate,
        "default_deposit_fee_usd": default_fee
    })


@app.route('/api/deposits', methods=['POST'])
def api_create_deposit():
    """
    Creates a new manual deposit. Expects JSON:
      { amount, currency ("ILS"/"USD"), date ("YYYY-MM-DD"),
        fx_rate (optional), conversion_fee (optional) }
    Description is auto-generated as "Manual deposit - <date>".
    Uses the same currency_manager.add_deposit() + _sync_deposits_metadata()
    path as the weekly-scan deposit flow, so the stored format is identical,
    then regenerates the dashboard so Cash Available / Next Position update.
    """
    import currency_manager

    data = request.get_json() or {}

    amount_raw = data.get('amount')
    currency = (data.get('currency') or '').upper()
    date_str = data.get('date') or datetime.now().strftime('%Y-%m-%d')
    fx_rate_raw = data.get('fx_rate')
    conversion_fee_raw = data.get('conversion_fee')

    try:
        amount = float(amount_raw)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid amount."}), 400
    if amount <= 0:
        return jsonify({"success": False, "message": "The amount must be greater than 0."}), 400

    if currency not in ("ILS", "USD"):
        return jsonify({"success": False, "message": "Invalid currency."}), 400

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid date format (YYYY-MM-DD)."}), 400

    fx_rate = None
    if fx_rate_raw not in (None, ''):
        try:
            fx_rate = float(fx_rate_raw)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Invalid conversion rate."}), 400

    conversion_fee = None
    if currency == 'ILS' and conversion_fee_raw not in (None, ''):
        try:
            conversion_fee = float(conversion_fee_raw)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Invalid conversion fee."}), 400

    deposit = currency_manager.add_deposit(
        amount=amount,
        currency=currency,
        date=date_str,
        fx_rate=fx_rate,
        conversion_fee=conversion_fee,
        description=f"Manual deposit - {date_str}"
    )

    _sync_deposits_metadata()

    try:
        trades = data_manager.load_trades()
        ui_generator.generate_dashboard_file(trades)
    except Exception as e:
        print(f"Warning: could not regenerate dashboard after manual deposit: {e}")

    return jsonify({"success": True, "message": "Deposit added successfully.", "deposit": deposit})


@app.route('/api/deposits/<int:deposit_id>', methods=['POST'])
def api_update_deposit(deposit_id):
    """Edits an existing deposit's date/amount/fx_rate/description/conversion_fee."""
    import currency_manager
    data = request.get_json() or {}

    success, message = currency_manager.update_deposit(
        deposit_id,
        date=data.get('date'),
        amount=data.get('amount'),
        fx_rate=data.get('fx_rate'),
        description=data.get('description'),
        conversion_fee=data.get('conversion_fee')
    )

    if success:
        try:
            trades = data_manager.load_trades()
            ui_generator.generate_dashboard_file(trades)
        except Exception as e:
            print(f"Warning: could not regenerate dashboard after deposit update: {e}")

    return jsonify({"success": success, "message": message})


@app.route('/api/deposits/<int:deposit_id>', methods=['DELETE'])
def api_delete_deposit(deposit_id):
    """Deletes an existing deposit record."""
    import currency_manager
    success, message = currency_manager.delete_deposit(deposit_id)

    if success:
        try:
            trades = data_manager.load_trades()
            ui_generator.generate_dashboard_file(trades)
        except Exception as e:
            print(f"Warning: could not regenerate dashboard after deposit delete: {e}")

    return jsonify({"success": success, "message": message})


@app.route('/api/default-fx-rate', methods=['POST'])
def api_update_default_fx_rate():
    """Updates the user-editable default FX rate used for deposits with a missing rate."""
    import currency_manager
    data = request.get_json() or {}
    new_rate = data.get('rate')

    if new_rate is None:
        return jsonify({"success": False, "message": "Missing rate."}), 400

    try:
        updated_rate = currency_manager.update_default_fx_rate(new_rate)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid rate."}), 400

    try:
        trades = data_manager.load_trades()
        ui_generator.generate_dashboard_file(trades)
    except Exception as e:
        print(f"Warning: could not regenerate dashboard after default fx rate update: {e}")

    return jsonify({"success": True, "message": "Default FX rate updated successfully.", "default_fx_rate": updated_rate})


@app.route('/api/default-deposit-fee', methods=['POST'])
def api_update_default_deposit_fee():
    """Updates the user-editable default deposit/conversion fee (USD) used
    to pre-fill new ILS deposits (still editable per-deposit)."""
    import currency_manager
    data = request.get_json() or {}
    new_fee = data.get('fee')

    if new_fee is None:
        return jsonify({"success": False, "message": "Missing fee."}), 400

    try:
        updated_fee = currency_manager.update_default_deposit_fee(new_fee)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid fee."}), 400

    return jsonify({"success": True, "message": "Default fee updated successfully.", "default_deposit_fee_usd": updated_fee})



@app.route('/api/export-data')
def api_export_data():
    """
    Exports all user-personal data (trades + deposits history) as a single
    downloadable JSON backup file. Allows moving between computers / users.
    """
    from flask import Response

    backup = data_manager.export_user_data()
    json_str = json.dumps(backup, indent=4, ensure_ascii=False)
    filename = f"stocksforme_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    return Response(
        json_str,
        mimetype='application/json',
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route('/api/import-data', methods=['POST'])
def api_import_data():
    """
    Imports a previously exported backup JSON file, restoring trades and
    deposits history. Overwrites current data (after archiving it as a
    safety net) so the user can continue on a different computer.
    """
    if 'backup_file' not in request.files:
        return jsonify({"success": False, "message": "No file selected."}), 400

    file = request.files['backup_file']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "No file selected."}), 400

    try:
        backup_data = json.load(file.stream)
    except Exception as e:
        return jsonify({"success": False, "message": f"Invalid JSON file: {e}"}), 400

    success, message = data_manager.import_user_data(backup_data)

    if success:
        # Regenerate the dashboard so the restored data is reflected immediately
        try:
            trades = data_manager.load_trades()
            ui_generator.generate_dashboard_file(trades)
        except Exception as e:
            print(f"Warning: could not regenerate dashboard after import: {e}")

    return jsonify({"success": success, "message": message})


if __name__ == '__main__':
    import threading
    import webbrowser

    def _open_browser():
        webbrowser.open("http://127.0.0.1:5000")

    # Only auto-open the browser in the actual server process.
    # Flask's debug reloader spawns a child process; without this check
    # the browser would open twice (once per process).
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.5, _open_browser).start()

    app.run(debug=True, port=5000)
