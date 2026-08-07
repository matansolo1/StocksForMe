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
            
            <div style="text-align: left; margin-top: 15px;">
                <label>Deposit Amount (USD) for this week:</label>
                <input type="number" name="deposit" step="0.01" value="0" autofocus>
            </div>
            <button type="submit" class="btn">Confirm & Run Scan</button>
        </form>
    </div>
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
    return render_template_string(DEPOSIT_FORM_HTML)

@app.route('/execute-scan', methods=['POST'])
def execute_scan():
    deposit_amount = float(request.form.get('deposit', 0))
    deposit_currency = request.form.get('deposit_currency', 'USD')
    strategy_mode = 'momentum'
    target_rsi = float(request.form.get('target_rsi', 55.0))
    stop_loss_pct = float(request.form.get('stop_loss_pct', 5.0))
    take_profit_pct = float(request.form.get('take_profit_pct', 10.0))
    
    if deposit_amount > 0:
        import currency_manager
        deposit_info = currency_manager.add_deposit(
            amount=deposit_amount,
            currency=deposit_currency,
            description=f"Weekly scan deposit - {datetime.now().strftime('%Y-%m-%d')}"
        )
        deposits_history = currency_manager.load_deposits_history()
        total_net_usd = deposits_history['metadata']['total_deposits_usd_net']
        total_gross_usd = deposits_history['metadata']['total_deposits_usd_gross']
        total_conversion_fees = deposits_history['metadata']['total_conversion_fees_usd']
        data_manager.update_metadata(
            total_deposits=total_net_usd,
            total_deposits_gross=total_gross_usd,
            total_conversion_fees=total_conversion_fees
        )
    
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
        
        # Calculate a preliminary position size estimate (used only to check if any cash exists)
        active_count = len([t for t in trades if t.get("status") == "ACTIVE"])
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
        trades, added = trading_logic.add_new_trades(
            trades, top_setups, position_size_usd=pos_size,
            commission_per_trade=commission_per_trade, cash_available=cash_available
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
        return jsonify({"success": False, "message": "חסר ticker או exit_price"}), 400

    try:
        exit_price = float(exit_price)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "exit_price לא תקין"}), 400

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
        # Load current active positions to determine how many slots are available
        trades = data_manager.load_trades()
        active_count = len([t for t in trades if t.get("status") == "ACTIVE"])
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
        return jsonify({"success": False, "message": "לא נבחר קובץ."}), 400

    file = request.files['backup_file']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "לא נבחר קובץ."}), 400

    try:
        backup_data = json.load(file.stream)
    except Exception as e:
        return jsonify({"success": False, "message": f"קובץ JSON לא תקין: {e}"}), 400

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


