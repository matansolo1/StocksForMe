from flask import Flask, redirect, url_for, jsonify, render_template_string, request
import subprocess
import os
from datetime import datetime
import pytz
import data_manager
import ui_generator

app = Flask(__name__)

DASHBOARD_FILE = "tracker_dashboard.html"

DEPOSIT_FORM_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Weekly Scan - Deposit</title>
    <style>
        body { background: #0a0a0a; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #141414; padding: 40px; border-radius: 16px; border: 1px solid #262626; text-align: center; }
        input { background: #1a1a1a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 200px; font-size: 1.2rem; margin: 20px 0; }
        .btn { background: #ff5252; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Weekly Scan</h2>
        <p>Did you deposit money this week?</p>
        <form action="/execute-scan" method="post">
            <input type="number" name="deposit" step="0.01" value="0" autofocus>
            <br>
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
    if deposit > 0:
        metadata = data_manager.get_metadata()
        new_total = metadata.get('total_deposits', 0) + deposit
        data_manager.update_metadata(total_deposits=new_total)
    
    subprocess.run(["python", "scanner.py"], env={**os.environ, "FLASK_TRIGGERED": "true"})
    return redirect(url_for('index'))

@app.route('/refresh-tracker')
def refresh_tracker():
    subprocess.run(["python", "tracker.py"], env={**os.environ, "FLASK_TRIGGERED": "true"})
    return redirect(url_for('index'))

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

@app.route('/structure')
def structure():
    return ui_generator.generate_structure_html()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
