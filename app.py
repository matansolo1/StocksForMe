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
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    is_weekday = now_eastern.weekday() <= 4
    market_open = eastern.localize(datetime.combine(now_eastern.date(), datetime.strptime("09:30", "%H:%M").time()))
    market_close = eastern.localize(datetime.combine(now_eastern.date(), datetime.strptime("16:00", "%H:%M").time()))
    is_open = is_weekday and (market_open <= now_eastern <= market_close)
    
    return jsonify({
        "status": "open" if is_open else "closed",
        "message": "Market Open (US)" if is_open else "Market Closed (US)"
    })

@app.route('/structure')
def structure():
    return ui_generator.generate_structure_html()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
