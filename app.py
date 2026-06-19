from flask import Flask, redirect, url_for, jsonify, render_template_string, request
import subprocess
import os
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
    deposit = float(request.form.get('deposit', 0))
    strategy_mode = 'momentum'  # Fixed to momentum strategy
    target_rsi = float(request.form.get('target_rsi', 55.0))
    stop_loss_pct = float(request.form.get('stop_loss_pct', 5.0))
    take_profit_pct = float(request.form.get('take_profit_pct', 10.0))
    
    if deposit > 0:
        metadata = data_manager.get_metadata()
        new_total = metadata.get('total_deposits', 0) + deposit
        data_manager.update_metadata(total_deposits=new_total)
    
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
    import json
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
        
        # Calculate portfolio state using analytics_generator
        portfolio_state = analytics_generator.calculate_portfolio_state(trades, total_deposits)
        
        # Calculate position size based on available cash (Option A - Conservative)
        pos_size = analytics_generator.calculate_position_size(portfolio_state, max_positions=3)
        
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
            
        # Once scan is complete, process swaps and new trades
        yield f"data: {json.dumps({'progress': 100, 'message': 'Processing swaps and new trades...'})}\n\n"
        
        trades = trading_logic.process_scanner_swaps(trades, top_setups, position_size_usd=pos_size)
        trades, added = trading_logic.add_new_trades(trades, top_setups, position_size_usd=pos_size)
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

@app.route('/refresh-tracker')
def refresh_tracker():
    subprocess.run(["python", "tracker.py"], env={**os.environ, "FLASK_TRIGGERED": "true"})
    return redirect(url_for('index'))

@app.route('/manual-clearance', methods=['POST'])
def manual_clearance():
    import data_manager
    import ui_generator
    from datetime import datetime
    
    trades = data_manager.load_trades()
    for t in trades:
        if t.get("status") in ["ACTIVE", "REVIEW"]:
            t["status"] = "CLOSED"
            t["exit_price"] = t.get("current_price", t["entry_price"])
            t["exit_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
    data_manager.save_trades(trades)
    ui_generator.generate_dashboard_file(trades)
    return redirect(url_for('index'))

@app.route('/api/dry-run-stream')
def dry_run_stream():
    import json
    from flask import Response, request
    import scanner
    
    strategy_mode = 'momentum'  # Fixed to momentum strategy
    target_rsi = float(request.args.get('target_rsi', 55.0))
    stop_loss_pct = float(request.args.get('stop_loss_pct', 5.0))
    take_profit_pct = float(request.args.get('take_profit_pct', 10.0))
    
    def generate():
        for event in scanner.scan_universe_generator(strategy_mode, target_rsi, stop_loss_pct, take_profit_pct):
            yield f"data: {json.dumps(event)}\n\n"
            
    return Response(generate(), mimetype='text/event-stream')

@app.route('/reset-to-live')
def reset_to_live():
    subprocess.run(["python", "tracker.py", "--reset"], env={**os.environ, "FLASK_TRIGGERED": "true"})
    return redirect(url_for('index'))

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
