import json
import os
import stock_api
import finance_utils
import data_manager

FUNNEL_TEMPLATE = """
<div class="funnel-container">
    <div class="funnel-stage stage-1">
        <div class="funnel-shape"></div>
        <div class="funnel-content">
            <h3>שלב 1: סינון ראשוני (Market Universe)</h3>
            <p><strong>הלוגיקה:</strong> התמקדות במניות צמיחה וטכנולוגיה מובילות (Nasdaq-100 & High Growth).</p>
            <p><strong>המתמטיקה:</strong> רשימה נבחרת של ~100 מניות עם נזילות גבוהה ושווי שוק משמעותי שמנפה 98% מהשוק.</p>
        </div>
    </div>
    <div class="funnel-stage stage-2">
        <div class="funnel-shape"></div>
        <div class="funnel-content">
            <h3>שלב 2: הלב הטכני (RSI & Global Trend Filter)</h3>
            <p><strong>הלוגיקה:</strong> איתור מניות במצב "מכירת יתר" קיצוני (Oversold) רק כאשר המדד המרכזי במגמת עלייה גלובלית.</p>
            <p><strong>המתמטיקה:</strong> <code>RSI(14) < 35</code> וגם <code>Price < SMA(20)</code>, ובנוסף מדד ה-S&P 500 במצב שורי: <code>SPY > SMA(200)</code>.</p>
        </div>
    </div>
    <div class="funnel-stage stage-3">
        <div class="funnel-shape"></div>
        <div class="funnel-content">
            <h3>שלב 3: הגנת דוחות (Earnings Filter)</h3>
            <p><strong>הלוגיקה:</strong> מניעת סיכון "Gap Risk" הנובע מפרסומים כספיים קרובים.</p>
            <p><strong>המתמטיקה:</strong> בדיקה מול <code>yfinance</code>. אם יש דוח ב-7 הימים הקרובים, המניה נפסלת אוטומטית ללא קשר לאיתות הטכני.</p>
        </div>
    </div>
    <div class="funnel-stage stage-4">
        <div class="funnel-shape"></div>
        <div class="funnel-content">
            <h3>שלב 4: מנוע הדירוג (Scoring Engine)</h3>
            <p><strong>הלוגיקה:</strong> בחירת 3 המניות עם פוטנציאל ההתאוששות הגבוה ביותר ביחס לתנודתיות.</p>
            <p><strong>המתמטיקה:</strong> <code>RankScore = (SMA20 - Close) / Volatility</code>. אנחנו מדרגים לפי המרחק מהממוצע חלקי סטיית התקן (Z-Score) ובוחרים את ה-TOP 3.</p>
        </div>
    </div>
    <div class="funnel-stage stage-5">
        <div class="funnel-shape"></div>
        <div class="funnel-content">
            <h3>שלב 5: ניהול סיכונים (Execution)</h3>
            <p><strong>הלוגיקה:</strong> הגנה מוגברת על ההון והצבת יעדים ריאליים מבוססי תנודתיות.</p>
            <p><strong>המתמטיקה:</strong> 
                <code>TP = SMA(20)</code> (חזרה לממוצע), 
                <code>SL = Price - (3 * Volatility * Price)</code> (שימוש ב-3 סטיות תקן - מורחב פי 1.5 להגנה מרעשי שוק).
            </p>
        </div>
    </div>
</div>

<div class="strategy-doc">
    <h2>ספר הדרכה: אסטרטגיית "Mean Reversion" מבוססת תנודתיות</h2>
    <p>המערכת פועלת על פי עקרון החזרה לממוצע (Mean Reversion). היא מחפשת מניות חזקות שנמצאות בתיקון זמני.</p>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
        <div class="doc-card">
            <h4>🛡️ מנגנוני הגנה</h4>
            <ul>
                <li><strong>ניהול סיכונים:</strong> חשיפה של מקסימום 33% מהפורטפוליו לכל פוזיציה.</li>
                <li><strong>Stop Loss קבוע:</strong> 5% מתחת למחיר הכניסה.</li>
                <li><strong>Take Profit קבוע:</strong> 10% מעל מחיר הכניסה (יחס 1:2).</li>
            </ul>
        </div>
        <div class="doc-card">
            <h4>📈 חוקי יציאה</h4>
            <ul>
                <li><strong>HIT_TP:</strong> יציאה אוטומטית ב-+10% רווח.</li>
                <li><strong>HIT_SL:</strong> יציאה אוטומטית ב--5% הפסד.</li>
                <li><strong>אין יציאה ידנית:</strong> פוזיציות נסגרות רק ב-SL/TP, ללא מגבלת זמן.</li>
            </ul>
        </div>
    </div>
</div>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Portfolio Tracker Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        :root { --bg: #0a0a0a; --card-bg: #141414; --border: #262626; --text: #ffffff; --text-dim: #a0a0a0; --neon-green: #39FF14; --accent: #ff5252; --warning: #f39c12; }
        body { background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .nav-header { width: 100%; max-width: 1200px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid var(--border); padding-bottom: 15px; }
        .market-status { display: flex; align-items: center; gap: 10px; font-size: 0.85rem; font-weight: 600; color: var(--text-dim); }
        .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; width: 100%; max-width: 1200px; margin-bottom: 30px; }
        .metric-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 25px; text-align: center; }
        .metric-label { color: var(--text-dim); font-size: 0.9rem; font-weight: 600; margin-bottom: 10px; }
        .metric-value { font-size: 2.5rem; font-weight: 800; }
        .main-content { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; width: 100%; max-width: 1200px; }
        .table-section, .chart-section { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; color: var(--text-dim); padding: 12px; border-bottom: 1px solid var(--border); }
        td { padding: 12px; border-bottom: 1px solid var(--border); }
        .stock-row { cursor: pointer; transition: background 0.2s; }
        .stock-row:hover { background: #1f1f1f; }
        .led-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
        .led-green { background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); animation: pulse 2s infinite; }
        .led-orange { background: var(--warning); box-shadow: 0 0 10px var(--warning); animation: pulse 1.5s infinite; }
        .led-red { background: #b33939; box-shadow: 0 0 5px #b33939; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        #chart-container { min-height: 400px; margin-bottom: 20px; }
        #tv-container { height: 400px; }
        .explanation-section { margin-top: 50px; padding: 30px; background: #111; border-radius: 16px; border: 1px solid #262626; width: 100%; max-width: 1200px; box-sizing: border-box; }
        .btn { padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; text-decoration: none; border: none; transition: 0.3s; }
        .btn-primary { background: var(--accent); color: white; }
        .btn-secondary { background: transparent; color: white; border: 1px solid var(--border); }
        #reset-btn { margin-top: 50px; padding: 10px 20px; background: #1a1a1a; border: 1px solid #333; color: #777; cursor: pointer; border-radius: 8px; font-size: 0.8rem; transition: 0.3s; }
        #reset-btn:hover { background: #ff5252; color: white; border-color: #ff5252; }
        
        /* New Styles for Metrics Dashboard */
        .ticker-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
        .t-metric { background: #1c1c1c; padding: 15px; border-radius: 12px; border: 1px solid #333; }
        .t-label { font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; margin-bottom: 5px; }
        .t-value { font-size: 1.25rem; font-weight: 800; }
        .t-sub { font-size: 0.8rem; margin-top: 4px; }
    </style>
</head>
<body>
    <div class="nav-header">
        <div class="market-status">
            <div id="market-led" class="led-dot"></div>
            <span id="market-label">Checking Market...</span>
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
            {{clearance_button}}
            <a href="/trade-analytics" class="btn btn-secondary" style="border-color: #FFD700; color: #FFD700; background: transparent;">📊 Trade Analytics</a>
            <button onclick="openDryRunModal()" class="btn btn-secondary" style="border-color: #39FF14; color: #39FF14; background: transparent;">Dry Run Scanner</button>
            <a href="/under-the-hood" class="btn btn-secondary" style="border-color: #2196F3; color: #2196F3;">Under the Hood</a>
            <a href="/run-scan" class="btn btn-primary">Run Weekly Scan</a>
            <a href="/refresh-tracker" class="btn btn-secondary">Refresh Prices</a>
        </div>
    </div>
    <div class="header" style="max-width: 1200px; width: 100%; justify-content: center;">
        <h1 style="margin: 0;">Portfolio Tracker Pro</h1>
    </div>
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-label">PORTFOLIO EQUITY</div>
            <div class="metric-value" style="color: {{equity_color}};">${{current_equity}}</div>
            <div style="color: var(--text-dim); font-size: 0.85rem;">
                Deposits: ${{total_deposits}} | Return: {{portfolio_pnl}}
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-label">CASH AVAILABLE</div>
            <div class="metric-value" style="color: {{cash_color}};">${{cash_available}}</div>
            <div style="color: var(--text-dim); font-size: 0.85rem;">
                Invested: ${{invested_capital}} | {{next_position_label}}

            </div>
        </div>
    </div>
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-label">REALIZED P&L</div>
            <div class="metric-value" style="color: {{realized_color}};">{{realized_pnl_sign}}${{realized_pnl_abs}}</div>
            <div style="color: {{realized_color}}; font-size: 0.85rem;">From closed trades</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">UNREALIZED P&L</div>
            <div class="metric-value" style="color: {{unrealized_color}};">{{unrealized_pnl_sign}}${{unrealized_pnl_abs}}</div>
            <div style="color: {{unrealized_color}}; font-size: 0.85rem;">From active positions</div>
        </div>
    </div>
    <div class="metrics-grid" style="grid-template-columns: 1fr 1fr;">
        <div class="metric-card" style="background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%); border: 1px solid #333;">
            <div class="metric-label" style="color: #f39c12;">💰 TRADING COMMISSIONS</div>
            <div class="metric-value" style="color: #f39c12; font-size: 2rem;">${{total_commissions}}</div>
            <div style="color: var(--text-dim); font-size: 0.85rem;">
                ${{commission_per_trade}} per trade | {{total_trades_count}} trades
            </div>
        </div>
        <div class="metric-card" style="background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%); border: 1px solid #2ecc71;">
            <div class="metric-label" style="color: #2ecc71;">💱 CONVERSION FEES</div>
            <div class="metric-value" style="color: #2ecc71; font-size: 2rem;">${{total_conversion_fees}}</div>
            <div style="color: var(--text-dim); font-size: 0.85rem;">
                {{conversion_count}} conversions | Avg: ${{avg_conversion_fee}}
            </div>
        </div>
    </div>
    <div class="metrics-grid" style="grid-template-columns: 1fr;">
        <div class="metric-card" style="background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%); border: 1px solid #0038b8;">
            <div class="metric-label" style="color: #4d94ff;">🇮🇱 TOTAL P&amp;L IN ILS (₪)</div>
            <div class="metric-value" style="color: {{ils_pnl_color}};">{{ils_pnl_sign}}₪{{ils_pnl_abs}}</div>
            <div style="color: var(--text-dim); font-size: 0.85rem; margin-top: 5px;">
                Trading: {{ils_trading_sign}}₪{{ils_trading_abs}} | FX Rate Effect: {{ils_fx_sign}}₪{{ils_fx_abs}}
            </div>
            <div style="color: var(--text-dim); font-size: 0.8rem; margin-top: 5px;">
                Rate: {{ils_buy_rate}}₪ → {{ils_current_rate}}₪ ({{ils_rate_change_sign}}{{ils_rate_change_pct}}%)
            </div>
            <button onclick="openFxManagementModal()" class="btn btn-secondary" style="margin-top: 12px; border-color: #4d94ff; color: #4d94ff; padding: 6px 14px; font-size: 0.8rem;">
                ✏️ ניהול הפקדות ושערי המרה
            </button>
        </div>
    </div>

    <div class="main-content">

        <div class="table-section">
            <h3>Active Positions</h3>
            <table>
                <thead><tr><th>Status</th><th>Ticker</th><th>Phase</th><th>Weight</th><th>Entry</th><th>Price</th><th>Value</th><th>P&L</th><th>Action</th></tr></thead>
                <tbody>{{active_rows}}</tbody>
            </table>

            <div style="margin-top: 25px;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
                    <h3 style="margin: 0;">⏳ Pending Entries (הוראות לימיט ממתינות)</h3>
                    <button onclick="checkPendingNow()" class="btn btn-secondary" style="padding: 5px 12px; font-size: 0.75rem; border-color: #ffb74d; color: #ffb74d;">בדוק עכשיו</button>
                </div>
                <div style="color: var(--text-dim); font-size: 0.78rem; margin: 6px 0 10px;">
                    הוראות אלו טרם בוצעו. הן ייכנסו כפוזיציה רק אם המחיר ייגע במחיר היעד במהלך יום המסחר - אחרת יסומנו כ-NOT_FILLED (בדיוק כמו אצל הברוקר).
                </div>
                <table>
                    <thead><tr><th>Status</th><th>Ticker</th><th>מחיר יעד</th><th>מחיר נוכחי</th><th>מרחק</th><th>יום מסחר</th><th>הון משוריין</th><th>Action</th></tr></thead>
                    <tbody>{{pending_rows}}</tbody>
                </table>
            </div>
        </div>
        <div class="chart-section">
            <!-- New Metrics Dashboard -->
            <div id="ticker-dashboard" class="ticker-metrics">
                <div class="t-metric">
                    <div class="t-label">Target Entry</div>
                    <div id="m-entry" class="t-value">--</div>
                </div>
                <div class="t-metric">
                    <div class="t-label">Take Profit</div>
                    <div id="m-tp" class="t-value" style="color: var(--neon-green);">--</div>
                    <div id="m-tp-pct" class="t-sub" style="color: var(--neon-green);">--</div>
                </div>
                <div class="t-metric">
                    <div class="t-label">Stop Loss</div>
                    <div id="m-sl" class="t-value" style="color: var(--accent);">--</div>
                    <div id="m-sl-pct" class="t-sub" style="color: var(--accent);">--</div>
                </div>
            </div>
            <div id="chart-container"></div>
            <div id="tv-container"></div>
        </div>
    </div>
    <div class="explanation-section">
        <h2 style="color: var(--neon-green); margin-top: 0;">System Guide & Strategy</h2>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px;">
            <div>
                <h3 style="color: white;">Trading Rules (Momentum Scenario 3 🏆)</h3>
                <ul style="color: var(--text-dim); line-height: 1.6;">
                    <li><strong>Max Positions:</strong> Up to 3 stocks active at once.</li>
                    <li><strong>Weighting:</strong> Dynamic based on Available Cash / 3 (~33.3% each).</li>
                    <li><strong>Global Filter:</strong> Entries are ONLY allowed when S&P 500 is bullish (<code>SPY > SMA 200</code>).</li>
                    <li><strong>Setup Criteria:</strong> RSI crosses above 55 (from below) while price is above SMA 50 - capturing momentum breakouts.</li>
                    <li><strong>Exit Conditions:</strong> Fixed <strong>Take Profit</strong> at +10% or <strong>Stop Loss</strong> at -5% (1:2 Risk/Reward Ratio).</li>
                    <li><strong>No Time Limits:</strong> Positions stay open until SL or TP is hit - some take 3 days, some take 15+ days.</li>
                </ul>
            </div>
            <div>
                <h3 style="color: white;">Weekly Trading Workflow</h3>
                <p style="color: var(--text-dim); line-height: 1.6; margin-bottom: 15px;"><strong>🗓️ Sunday Evening (21:00-22:00 Israel Time):</strong></p>
                <ul style="color: var(--text-dim); line-height: 1.6; margin-top: 0;">
                    <li>Run weekly scanner to identify new momentum setups</li>
                    <li>Scanner fills empty position slots only (up to 3 total)</li>
                    <li>If 1 position active → adds 2 new positions</li>
                    <li>If 2 positions active → adds 1 new position</li>
                    <li>If 3 positions active → adds 0 new positions</li>
                    <li>Scanner does NOT close existing positions</li>
                </ul>
                <p style="color: var(--text-dim); line-height: 1.6; margin-top: 15px; margin-bottom: 0;"><strong>📈 Monday Morning (16:30 Israel Time = 9:30 AM US):</strong></p>
                <ul style="color: var(--text-dim); line-height: 1.6; margin-top: 0;">
                    <li>Execute trades at market open using Market Orders</li>
                    <li>Set Stop Loss at Entry × 0.95 (-5%)</li>
                    <li>Set Take Profit at Entry × 1.10 (+10%)</li>
                    <li>Wait for SL/TP to trigger (no manual intervention)</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Historical Backtesting Section -->
    <div class="explanation-section" style="margin-top: 30px;">
        <h2 style="color: #39FF14; margin-top: 0;">Historical Backtesting (5 Years)</h2>
        <p style="color: var(--text-dim); margin-bottom: 20px; line-height: 1.6;">בדיקת אסטרטגיית החזרה לממוצע (Mean Reversion) לאחור לאורך 5 השנים האחרונות שבוצעו שבוע אחר שבוע (קנייה ביום המסחר הראשון של השבוע ב-Open, ומכירה בסוף השבוע ב-Close).</p>
        
        <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 30px; align-items: start;">
            <!-- Inputs and Stats -->
            <div style="background: #1c1c1c; padding: 20px; border-radius: 12px; border: 1px solid #333;">
                <div style="margin-bottom: 15px; text-align: left;">
                    <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">Initial Capital (USD):</label>
                    <input type="number" id="backtest-capital" value="10000" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
                </div>
                <div style="margin-bottom: 15px; text-align: left; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                    <div>
                        <label style="display: block; color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-bottom: 6px;">Target RSI:</label>
                        <input type="number" id="backtest-rsi" value="55" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 8px; border-radius: 8px; width: 100%; font-size: 0.9rem; box-sizing: border-box;">
                    </div>
                    <div>
                        <label style="display: block; color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-bottom: 6px;">Stop Loss %:</label>
                        <input type="number" id="backtest-sl" value="5.0" step="0.1" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 8px; border-radius: 8px; width: 100%; font-size: 0.9rem; box-sizing: border-box;">
                    </div>
                    <div>
                        <label style="display: block; color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-bottom: 6px;">Take Profit %:</label>
                        <input type="number" id="backtest-tp" value="10.0" step="0.1" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 8px; border-radius: 8px; width: 100%; font-size: 0.9rem; box-sizing: border-box;">
                    </div>
                </div>
                
                <!-- Monte Carlo Toggle -->
                <div style="margin-top: 15px; margin-bottom: 15px; padding: 12px; background: #0a0a0a; border-radius: 8px; border: 1px solid #333;">
                    <label style="display: flex; align-items: center; cursor: pointer; color: white; font-size: 0.9rem;">
                        <input type="checkbox" id="backtest-monte-carlo" checked style="margin-left: 10px; width: 18px; height: 18px; cursor: pointer;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: #39FF14;">🎲 Enhanced Monte Carlo Simulation</div>
                            <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 4px;">
                                Uses probabilistic intraday path simulation for more accurate SL/TP detection. Recommended for realistic results.
                            </div>
                        </div>
                    </label>
                </div>
                
                <button onclick="runBacktest()" id="backtest-btn" class="btn btn-primary" style="width: 100%; background: #39FF14; color: black; font-weight: bold; border: none; padding: 12px; border-radius: 8px;">Run 5-Year Backtest</button>
                
                <!-- Backtest Loader -->
                <div id="backtest-loader" style="display: none; text-align: center; margin-top: 20px;">
                    <div style="display: inline-block; width: 24px; height: 24px; border: 3px solid rgba(255,255,255,0.1); border-radius: 50%; border-top-color: #39FF14; animation: spin 1s ease-in-out infinite;"></div>
                    <p style="font-size: 0.85rem; color: #aaa; margin-top: 8px;">Downloading 5-year batch & running simulation...</p>
                </div>
                
                <!-- Backtest Stats -->
                <div id="backtest-stats" style="display: none; margin-top: 25px; border-top: 1px solid #333; padding-top: 20px; text-align: left;">
                    <h4 style="margin: 0 0 10px 0; color: #39FF14; font-size: 1rem;">Recent Period (2021-2026):</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px;">
                        <div style="background: #0a0a0a; padding: 8px; border-radius: 8px; border: 1px solid #222; text-align: center;">
                            <div style="font-size: 0.7rem; color: var(--text-dim);">TOTAL RETURN</div>
                            <div id="recent-return" style="font-size: 1.1rem; font-weight: 800; color: #39FF14; margin-top: 2px;">--</div>
                        </div>
                        <div style="background: #0a0a0a; padding: 8px; border-radius: 8px; border: 1px solid #222; text-align: center;">
                            <div style="font-size: 0.7rem; color: var(--text-dim);">WIN RATE</div>
                            <div id="recent-winrate" style="font-size: 1.1rem; font-weight: 800; color: #39FF14; margin-top: 2px;">--</div>
                        </div>
                        <div style="background: #0a0a0a; padding: 8px; border-radius: 8px; border: 1px solid #222; text-align: center;">
                            <div style="font-size: 0.7rem; color: var(--text-dim);">MAX DRAWDOWN</div>
                            <div id="recent-drawdown" style="font-size: 1.1rem; font-weight: 800; color: #ff5252; margin-top: 2px;">--</div>
                        </div>
                        <div style="background: #0a0a0a; padding: 8px; border-radius: 8px; border: 1px solid #222; text-align: center;">
                            <div style="font-size: 0.7rem; color: var(--text-dim);">TOTAL TRADES</div>
                            <div id="recent-trades" style="font-size: 1.1rem; font-weight: 800; color: #2196F3; margin-top: 2px;">--</div>
                        </div>
                    </div>

                    <h4 style="margin: 0 0 10px 0; color: #2196F3; font-size: 1rem;">Calm Period (2010-2020):</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <div style="background: #0a0a0a; padding: 8px; border-radius: 8px; border: 1px solid #222; text-align: center;">
                            <div style="font-size: 0.7rem; color: var(--text-dim);">TOTAL RETURN</div>
                            <div id="calm-return" style="font-size: 1.1rem; font-weight: 800; color: #39FF14; margin-top: 2px;">--</div>
                        </div>
                        <div style="background: #0a0a0a; padding: 8px; border-radius: 8px; border: 1px solid #222; text-align: center;">
                            <div style="font-size: 0.7rem; color: var(--text-dim);">WIN RATE</div>
                            <div id="calm-winrate" style="font-size: 1.1rem; font-weight: 800; color: #39FF14; margin-top: 2px;">--</div>
                        </div>
                        <div style="background: #0a0a0a; padding: 8px; border-radius: 8px; border: 1px solid #222; text-align: center;">
                            <div style="font-size: 0.7rem; color: var(--text-dim);">MAX DRAWDOWN</div>
                            <div id="calm-drawdown" style="font-size: 1.1rem; font-weight: 800; color: #ff5252; margin-top: 2px;">--</div>
                        </div>
                        <div style="background: #0a0a0a; padding: 8px; border-radius: 8px; border: 1px solid #222; text-align: center;">
                            <div style="font-size: 0.7rem; color: var(--text-dim);">TOTAL TRADES</div>
                            <div id="calm-trades" style="font-size: 1.1rem; font-weight: 800; color: #2196F3; margin-top: 2px;">--</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Backtest Chart -->
            <div style="background: #1c1c1c; padding: 20px; border-radius: 12px; border: 1px solid #333; min-height: 350px; display: flex; flex-direction: column; justify-content: center; position: relative;">
                <div id="backtest-chart-placeholder" style="text-align: center; color: var(--text-dim);">
                    <p>Enter capital and click "Run 5-Year Backtest" to generate the interactive equity curve.</p>
                </div>
                <div id="backtest-chart-container" style="display: none; width: 100%; gap: 20px;">
                    <div style="flex: 1; min-width: 0; height: 350px;">
                        <h4 style="text-align: center; margin: 0 0 10px 0; color: #39FF14; font-size: 0.9rem;">Recent Period (2021-2026)</h4>
                        <canvas id="recentChart" style="max-height: 310px; width: 100%; height: 100%;"></canvas>
                    </div>
                    <div style="flex: 1; min-width: 0; height: 350px;">
                        <h4 style="text-align: center; margin: 0 0 10px 0; color: #2196F3; font-size: 0.9rem;">Calm Period (2010-2020)</h4>
                        <canvas id="calmChart" style="max-height: 310px; width: 100%; height: 100%;"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Strategy Cheat Sheet & Robustness Matrix Section -->
    <div class="explanation-section" style="margin-top: 30px;">
        <h2 style="color: #39FF14; margin-top: 0; display: flex; align-items: center; gap: 10px;">
            <span>📊</span> Strategy Cheat Sheet & Robustness Matrix
        </h2>
        <p style="color: var(--text-dim); margin-bottom: 20px; line-height: 1.6;">
            סיכום ממצאי המחקר ומבחני החוסן (Robustness Tests) על פני תקופות שוק שונות. השורה המודגשת מייצגת את האסטרטגיה המנצחת שנבחרה לייצור.
        </p>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem;">
                <thead>
                    <tr style="border-bottom: 2px solid #333; background: #1a1a1a;">
                        <th style="padding: 12px; color: var(--text-dim);">Strategy Mode</th>
                        <th style="padding: 12px; color: var(--text-dim); text-align: center;">Target RSI</th>
                        <th style="padding: 12px; color: var(--text-dim); text-align: center;">Stop Loss</th>
                        <th style="padding: 12px; color: var(--text-dim); text-align: center;">Take Profit</th>
                        <th style="padding: 12px; color: var(--text-dim); text-align: center;">Chaos Era (2021-2026)</th>
                        <th style="padding: 12px; color: var(--text-dim); text-align: center;">Calm Era (2010-2020)</th>
                        <th style="padding: 12px; color: var(--text-dim); text-align: center;">Full Horizon (2010-2026)</th>
                        <th style="padding: 12px; color: var(--text-dim); text-align: center;">Max DD (Calm/Chaos)</th>
                        <th style="padding: 12px; color: var(--text-dim);">Key Insight</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid #262626; background: #111;">
                        <td style="padding: 12px; font-weight: bold;">Mean Reversion</td>
                        <td style="padding: 12px; text-align: center;">30</td>
                        <td style="padding: 12px; text-align: center;">3.0%</td>
                        <td style="padding: 12px; text-align: center;">6.0%</td>
                        <td style="padding: 12px; text-align: center; color: #ff5252; font-weight: bold;">-30.93% <span style="font-size: 0.8rem; color: var(--text-dim); font-weight: normal;">(WR: 33.2%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+63.34% <span style="font-size: 0.8rem; color: var(--text-dim); font-weight: normal;">(WR: 35.5%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14;">+12.8%</td>
                        <td style="padding: 12px; text-align: center; color: #ff5252;">-38.8% / -44.9%</td>
                        <td style="padding: 12px; color: var(--text-dim); font-size: 0.85rem; text-align: right; direction: rtl;">סובלת מתפיסת סכינים נופלות בשוק רגוע ומפסידה למדד.</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #262626; background: #111;">
                        <td style="padding: 12px; font-weight: bold;">Momentum (Default)</td>
                        <td style="padding: 12px; text-align: center;">60</td>
                        <td style="padding: 12px; text-align: center;">5.0%</td>
                        <td style="padding: 12px; text-align: center;">12.0%</td>
                        <td style="padding: 12px; text-align: center; color: #ff5252; font-weight: bold;">-4.88% <span style="font-size: 0.8rem; color: var(--text-dim); font-weight: normal;">(WR: 31.2%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+148.73% <span style="font-size: 0.8rem; color: var(--text-dim); font-weight: normal;">(WR: 37.5%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14;">+136.6%</td>
                        <td style="padding: 12px; text-align: center; color: #ff5252;">-33.5% / -20.6%</td>
                        <td style="padding: 12px; color: var(--text-dim); font-size: 0.85rem; text-align: right; direction: rtl;">נקודת מוצא טובה, אך נוטה לחטוף Bull Traps בשווקים תנודתיים.</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #262626; background: #111;">
                        <td style="padding: 12px; font-weight: bold;">Momentum (Scenario 1)</td>
                        <td style="padding: 12px; text-align: center;">65</td>
                        <td style="padding: 12px; text-align: center;">4.0%</td>
                        <td style="padding: 12px; text-align: center;">12.0%</td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+12.94% <span style="font-size: 0.8rem; color: var(--text-dim); font-weight: normal;">(WR: 27.6%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+198.16% <span style="font-size: 0.8rem; color: var(--text-dim); font-weight: normal;">(WR: 34.5%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+236.7%</td>
                        <td style="padding: 12px; text-align: center; color: #ff5252;">-27.3% / -19.5%</td>
                        <td style="padding: 12px; color: var(--text-dim); font-size: 0.85rem; text-align: right; direction: rtl;">חגורות בטיחות קשוחות. יחס R:R של 1:3 שמגן על התיק ומציג חוסן גבוה.</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #262626; background: #111;">
                        <td style="padding: 12px; font-weight: bold;">Momentum (Scenario 2)</td>
                        <td style="padding: 12px; text-align: center;">60</td>
                        <td style="padding: 12px; text-align: center;">7.5%</td>
                        <td style="padding: 12px; text-align: center;">15.0%</td>
                        <td style="padding: 12px; text-align: center; color: #ff5252; font-weight: bold;">-8.41% <span style="font-size: 0.8rem; color: var(--text-dim); font-weight: normal;">(WR: 34.0%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+268.60% <span style="font-size: 0.8rem; color: var(--text-dim); font-weight: normal;">(WR: 47.0%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+237.6%</td>
                        <td style="padding: 12px; text-align: center; color: #ff5252;">-41.8% / -17.6%</td>
                        <td style="padding: 12px; color: var(--text-dim); font-size: 0.85rem; text-align: right; direction: rtl;">מקסום רווחים קיצוני בשוק שורי וליניארי, אך מסוכן ומדמם בשוק תנודתי.</td>
                    </tr>
                    <!-- WINNING ROW (Highlighted with soft green background and bright neon green border) -->
                    <tr style="outline: 2px solid #39FF14; background: rgba(57, 255, 20, 0.08); box-shadow: 0 0 15px rgba(57, 255, 20, 0.15);">
                        <td style="padding: 12px; font-weight: bold; color: #39FF14;">🏆 Momentum (Scenario 3)</td>
                        <td style="padding: 12px; text-align: center; font-weight: bold; color: #39FF14;">55</td>
                        <td style="padding: 12px; text-align: center; font-weight: bold; color: #39FF14;">5.0%</td>
                        <td style="padding: 12px; text-align: center; font-weight: bold; color: #39FF14;">10.0%</td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+100.57% <span style="font-size: 0.8rem; color: #39FF14; font-weight: normal;">(WR: 43.1%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+232.78% <span style="font-size: 0.8rem; color: #39FF14; font-weight: normal;">(WR: 43.6%)</span></td>
                        <td style="padding: 12px; text-align: center; color: #39FF14; font-weight: bold;">+567.8%</td>
                        <td style="padding: 12px; text-align: center; color: #ff5252; font-weight: bold;">-22.0% / -25.4%</td>
                        <td style="padding: 12px; color: #fff; font-weight: bold; font-size: 0.85rem; text-align: right; direction: rtl;">הגביע הקדוש. אחוז הצלחה יציב לחלוטין בשתי התקופות ותשואה מטורפת.</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <div style="width: 100%; max-width: 1200px; margin-top: 30px;">
        <h3>Historical Log</h3>
        <table style="background: var(--card-bg); border-radius: 16px; border: 1px solid var(--border);">
            <thead><tr><th style="padding-left:20px;">Date</th><th>Ticker</th><th>Status</th><th>Entry</th><th>Exit</th><th style="padding-right:20px;">P&L</th></tr></thead>
            <tbody>{{history_rows}}</tbody>
        </table>
    </div>

    <!-- Data Management Section (Backup & Restore) -->
    <div class="explanation-section" style="margin-top: 30px;">
        <h2 style="color: #a78bfa; margin-top: 0; display: flex; align-items: center; gap: 10px;">
            <span>🗄️</span> ניהול נתונים (גיבוי ושחזור)
        </h2>
        <p style="color: var(--text-dim); margin-bottom: 20px; line-height: 1.6;">
            כל הדאטה האישי שלך - עסקאות, פוזיציות פעילות והיסטוריות, עמלות מסחר, הפקדות ועמלות המרת מטבע -
            מאוחד בקובץ גיבוי יחיד. ניתן להוריד אותו ולהעלות אותו במחשב אחר כדי להמשיך בדיוק מאותה נקודה.
        </p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div style="background: #1c1c1c; padding: 20px; border-radius: 12px; border: 1px solid #333;">
                <h4 style="margin-top: 0; color: white;">💾 גיבוי דאטה</h4>
                <p style="color: var(--text-dim); font-size: 0.85rem; line-height: 1.5;">
                    מוריד קובץ JSON יחיד עם כל הטריידים, ההפקדות ועמלות המטבע שלך.
                </p>
                <button onclick="downloadBackup()" class="btn btn-primary" style="width: 100%; background: #a78bfa; color: #0a0a0a; font-weight: bold;">
                    💾 הורד גיבוי דאטה
                </button>
            </div>
            <div style="background: #1c1c1c; padding: 20px; border-radius: 12px; border: 1px solid #333;">
                <h4 style="margin-top: 0; color: white;">📤 טעינת דאטה</h4>
                <p style="color: var(--text-dim); font-size: 0.85rem; line-height: 1.5;">
                    מעלה קובץ גיבוי קודם ומשחזר ממנו את כל הנתונים. <strong style="color: #f39c12;">שים לב:</strong>
                    זה יחליף את הנתונים הנוכחיים (גיבוי בטיחות אוטומטי נוצר קודם).
                </p>
                <input type="file" id="restoreFileInput" accept=".json" style="display: none;" onchange="handleRestoreFileSelected(event)">
                <button onclick="document.getElementById('restoreFileInput').click()" class="btn btn-secondary" style="width: 100%; border-color: #a78bfa; color: #a78bfa;">
                    📤 בחר קובץ גיבוי לשחזור
                </button>
            </div>
        </div>
        <div id="dataManagementStatus" style="display: none; margin-top: 15px; padding: 12px; border-radius: 8px; font-size: 0.9rem;"></div>
    </div>

    <!-- Restore Confirmation Modal -->
    <div id="restoreConfirmModal" style="display: none; position: fixed; z-index: 1200; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.85); align-items: center; justify-content: center;">
        <div style="background-color: #141414; margin: auto; padding: 30px; border: 1px solid #262626; width: 90%; max-width: 480px; border-radius: 16px; position: relative; direction: ltr; text-align: left;">
            <h2 style="margin-top: 0; color: #f39c12;">⚠️ אישור שחזור נתונים</h2>
            <p style="color: #e0e0e0; font-size: 0.95rem; line-height: 1.6;">
                פעולה זו תחליף את <strong>כל</strong> הטריידים, ההפקדות ועמלות המטבע הנוכחיים בקובץ שנטען.
            </p>
            <p style="color: var(--text-dim); font-size: 0.85rem; line-height: 1.5;">
                המצב הנוכחי יישמר אוטומטית כגיבוי בטיחות בתיקיית <code>backups/</code> לפני ההחלפה (3 גיבויים אחרונים נשמרים), כך שניתן לשחזר ידנית אם טעית.

            </p>
            <div style="display: flex; justify-content: flex-end; margin-top: 25px; gap: 10px;">
                <button id="restoreConfirmBtn" onclick="confirmRestoreUpload()" class="btn btn-primary" style="background: #f39c12; color: #0a0a0a; border: none;">כן, החלף נתונים</button>
                <button onclick="cancelRestoreUpload()" class="btn btn-secondary">ביטול</button>
            </div>
        </div>
    </div>

    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        const stockData = {{charts_json}};

        async function runBacktest() {
            const capitalInput = document.getElementById('backtest-capital');
            const rsiInput = document.getElementById('backtest-rsi');
            const slInput = document.getElementById('backtest-sl');
            const tpInput = document.getElementById('backtest-tp');
            const capital = parseFloat(capitalInput.value) || 10000.0;
            const targetRsi = parseFloat(rsiInput.value) || 55.0;
            const stopLossPct = parseFloat(slInput.value) || 5.0;
            const takeProfitPct = parseFloat(tpInput.value) || 10.0;
            const strategyMode = 'momentum';
            
            const btn = document.getElementById('backtest-btn');
            const loader = document.getElementById('backtest-loader');
            const statsDiv = document.getElementById('backtest-stats');
            const placeholder = document.getElementById('backtest-chart-placeholder');
            const chartContainer = document.getElementById('backtest-chart-container');
            
            btn.disabled = true;
            btn.style.opacity = '0.5';
            loader.style.display = 'block';
            statsDiv.style.display = 'none';
            placeholder.style.display = 'none';
            chartContainer.style.display = 'none';
            
            try {
                const useMonteCarlo = document.getElementById('backtest-monte-carlo') ? document.getElementById('backtest-monte-carlo').checked : true;
                
                const response = await fetch('/api/backtest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        initial_capital: capital,
                        target_rsi: targetRsi,
                        stop_loss_pct: stopLossPct,
                        take_profit_pct: takeProfitPct,
                        strategy_mode: strategyMode,
                        use_monte_carlo: useMonteCarlo
                    })
                });
                const data = await response.json();
                
                if (data.error) {
                    alert('Error: ' + data.error);
                    placeholder.style.display = 'block';
                    placeholder.innerHTML = `<p style="color: #ff5252;">${data.error}</p>`;
                    return;
                }
                
                const recent = data.recent;
                const calm = data.calm;
                
                if (recent.error || calm.error) {
                    alert('Error running backtest: ' + (recent.error || calm.error));
                    placeholder.style.display = 'block';
                    placeholder.innerHTML = `<p style="color: #ff5252;">${recent.error || calm.error}</p>`;
                    return;
                }
                
                // Show stats for Recent
                document.getElementById('recent-return').innerText = (recent.stats.total_return_pct >= 0 ? '+' : '') + recent.stats.total_return_pct.toFixed(2) + '%';
                document.getElementById('recent-winrate').innerText = recent.stats.win_rate_pct.toFixed(1) + '%';
                document.getElementById('recent-drawdown').innerText = '-' + recent.stats.max_drawdown_pct.toFixed(1) + '%';
                document.getElementById('recent-trades').innerText = recent.stats.total_trades;
                document.getElementById('recent-return').style.color = recent.stats.total_return_pct >= 0 ? '#39FF14' : '#ff5252';

                // Show stats for Calm
                document.getElementById('calm-return').innerText = (calm.stats.total_return_pct >= 0 ? '+' : '') + calm.stats.total_return_pct.toFixed(2) + '%';
                document.getElementById('calm-winrate').innerText = calm.stats.win_rate_pct.toFixed(1) + '%';
                document.getElementById('calm-drawdown').innerText = '-' + calm.stats.max_drawdown_pct.toFixed(1) + '%';
                document.getElementById('calm-trades').innerText = calm.stats.total_trades;
                document.getElementById('calm-return').style.color = calm.stats.total_return_pct >= 0 ? '#39FF14' : '#ff5252';
                
                statsDiv.style.display = 'block';
                chartContainer.style.display = 'flex';
                
                // Destroy previous charts if they exist
                if (window.myRecentChart) window.myRecentChart.destroy();
                if (window.myCalmChart) window.myCalmChart.destroy();
                
                // Create Recent Chart
                const recentLabels = recent.equity_curve.map(p => p.date);
                const recentValues = recent.equity_curve.map(p => p.equity);
                const ctxRecent = document.getElementById('recentChart').getContext('2d');
                window.myRecentChart = new Chart(ctxRecent, {
                    type: 'line',
                    data: {
                        labels: recentLabels,
                        datasets: [{
                            label: 'Recent Period Equity',
                            data: recentValues,
                            borderColor: '#39FF14',
                            backgroundColor: 'rgba(57, 255, 20, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.1,
                            pointRadius: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { grid: { color: '#222' }, ticks: { color: '#aaa', maxTicksLimit: 6 } },
                            y: { grid: { color: '#222' }, ticks: { color: '#aaa' } }
                        }
                    }
                });

                // Create Calm Chart
                const calmLabels = calm.equity_curve.map(p => p.date);
                const calmValues = calm.equity_curve.map(p => p.equity);
                const ctxCalm = document.getElementById('calmChart').getContext('2d');
                window.myCalmChart = new Chart(ctxCalm, {
                    type: 'line',
                    data: {
                        labels: calmLabels,
                        datasets: [{
                            label: 'Calm Period Equity',
                            data: calmValues,
                            borderColor: '#2196F3',
                            backgroundColor: 'rgba(33, 150, 243, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.1,
                            pointRadius: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { grid: { color: '#222' }, ticks: { color: '#aaa', maxTicksLimit: 6 } },
                            y: { grid: { color: '#222' }, ticks: { color: '#aaa' } }
                        }
                    }
                });
                
            } catch (e) {
                alert('An error occurred while running the backtest: ' + e);
                placeholder.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.style.opacity = '1';
                loader.style.display = 'none';
            }
        }
        
        function displayTickerData(ticker) {
            const data = stockData[ticker];
            if (!data) {
                document.getElementById('chart-container').innerHTML = "Chart not available";
                return;
            }

            // Update Metrics Dashboard
            document.getElementById('m-entry').innerText = '$' + data.entry.toFixed(2);
            document.getElementById('m-tp').innerText = '$' + data.tp.toFixed(2);
            document.getElementById('m-sl').innerText = '$' + data.sl.toFixed(2);
            
            const tpPct = ((data.tp - data.entry) / data.entry * 100).toFixed(1);
            const slPct = ((data.sl - data.entry) / data.entry * 100).toFixed(1);
            document.getElementById('m-tp-pct').innerText = '+' + tpPct + '%';
            document.getElementById('m-sl-pct').innerText = slPct + '%';

            // 1. Render Plotly Chart
            const trace = {
                x: data.x,
                y: data.y,
                type: 'scatter',
                mode: 'lines',
                line: { color: '#2196F3', width: 2 },
                name: 'Price'
            };
            const layout = {
                title: ticker + ' - 60 Day History',
                template: 'plotly_dark',
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { l: 40, r: 60, t: 40, b: 40 },
                shapes: [
                    { type: 'line', y0: data.entry, y1: data.entry, x0: data.x[0], x1: data.x[data.x.length-1], line: { color: 'yellow', dash: 'dash', width: 3 } },
                    { type: 'line', y0: data.tp, y1: data.tp, x0: data.x[0], x1: data.x[data.x.length-1], line: { color: '#39FF14', dash: 'dash', width: 3 } },
                    { type: 'line', y0: data.sl, y1: data.sl, x0: data.x[0], x1: data.x[data.x.length-1], line: { color: '#ff5252', dash: 'dash', width: 3 } }
                ],
                annotations: [
                    { x: data.x[data.x.length-1], y: data.entry, text: 'Entry', showarrow: false, xanchor: 'left', font: { color: 'yellow' } },
                    { x: data.x[data.x.length-1], y: data.tp, text: 'TP', showarrow: false, xanchor: 'left', font: { color: '#39FF14' } },
                    { x: data.x[data.x.length-1], y: data.sl, text: 'SL', showarrow: false, xanchor: 'left', font: { color: '#ff5252' } }
                ]
            };
            Plotly.newPlot('chart-container', [trace], layout);

            // 2. Load TradingView Widget
            new TradingView.widget({ "autosize": true, "symbol": ticker, "interval": "5", "theme": "dark", "container_id": "tv-container" });
        }

        async function checkMarket() {
            try {
                const response = await fetch('/api/market-status');
                const data = await response.json();
                document.getElementById('market-led').className = data.status === 'open' ? 'led-dot led-green' : 'led-dot led-red';
                document.getElementById('market-label').innerText = data.message;
            } catch (e) {}
        }
        
        checkMarket();

        setInterval(checkMarket, 60000);
        const firstRow = document.querySelector('.stock-row');
        if (firstRow) firstRow.click();

        // Dry Run Scanner Logic
        let dryRunEventSource = null;

        window.openDryRunModal = function() {
            document.getElementById('dryRunModal').style.display = 'flex';
            document.getElementById('dryRunProgressSection').style.display = 'block';
            document.getElementById('dryRunResultsSection').style.display = 'none';
            document.getElementById('dryRunProgressBar').style.width = '0%';
            document.getElementById('dryRunProgressText').innerText = '0%';
            document.getElementById('dryRunStatusText').innerText = 'Ready to start';
            document.getElementById('dryRunLog').innerHTML = '<div style="color: #555;">[System] Ready to start dry run...</div>';
            document.getElementById('dryRunStartBtn').disabled = false;
            document.getElementById('dryRunStartBtn').style.opacity = '1';
        };

        window.closeDryRunModal = function() {
            if (dryRunEventSource) {
                dryRunEventSource.close();
                dryRunEventSource = null;
            }
            document.getElementById('dryRunModal').style.display = 'none';
        };

        // Pending Entry (limit order) Management
        window.checkPendingNow = async function() {
            try {
                const response = await fetch('/api/check-pending', { method: 'POST' });
                const data = await response.json();
                alert(data.message || 'הבדיקה הושלמה.');
                location.reload();
            } catch (e) {
                alert('שגיאת רשת: ' + e);
            }
        };

        window.fillPendingOrder = async function(ticker, targetPrice) {
            const input = prompt(`באיזה מחיר נקנתה ${ticker} בפועל?`, targetPrice);
            if (input === null) return;
            const fillPrice = parseFloat(input);
            if (isNaN(fillPrice) || fillPrice <= 0) {
                alert('יש להזין מחיר תקין.');
                return;
            }
            try {
                const response = await fetch('/api/fill-pending', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ticker: ticker, fill_price: fillPrice })
                });
                const data = await response.json();
                alert(data.message);
                if (data.success) location.reload();
            } catch (e) {
                alert('שגיאת רשת: ' + e);
            }
        };

        window.cancelPendingOrder = async function(ticker) {
            if (!confirm(`לבטל את ההוראה עבור ${ticker}? הפוזיציה תסומן כ-NOT_FILLED וההון ישוחרר.`)) return;
            try {
                const response = await fetch('/api/cancel-pending', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ticker: ticker, reason: 'בוטלה ידנית מהדשבורד' })
                });
                const data = await response.json();
                alert(data.message);
                if (data.success) location.reload();
            } catch (e) {
                alert('שגיאת רשת: ' + e);
            }
        };

        // Manual Close Trade Logic
        function pad2(n) { return n.toString().padStart(2, '0'); }
        function nowForDatetimeLocalInput() {
            const d = new Date();
            return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
        }

        window.openCloseTradeModal = function(ticker, currentPrice) {
            document.getElementById('closeTradeTicker').innerText = ticker;
            document.getElementById('closeTradeTickerHidden').value = ticker;
            document.getElementById('closeTradeExitPrice').value = currentPrice;
            document.getElementById('closeTradeExitTimestamp').value = nowForDatetimeLocalInput();
            document.getElementById('closeTradeError').style.display = 'none';
            document.getElementById('closeTradeError').innerText = '';
            document.getElementById('closeTradeModal').style.display = 'flex';
        };

        window.closeCloseTradeModal = function() {
            document.getElementById('closeTradeModal').style.display = 'none';
        };

        window.submitCloseTrade = async function() {
            const ticker = document.getElementById('closeTradeTickerHidden').value;
            const exitPrice = parseFloat(document.getElementById('closeTradeExitPrice').value);
            const exitTimestampRaw = document.getElementById('closeTradeExitTimestamp').value; // "YYYY-MM-DDTHH:MM"
            const errorBox = document.getElementById('closeTradeError');
            errorBox.style.display = 'none';
            errorBox.innerText = '';

            if (!ticker || isNaN(exitPrice) || exitPrice <= 0) {
                errorBox.innerText = 'יש להזין מחיר יציאה תקין.';
                errorBox.style.display = 'block';
                return;
            }
            if (!exitTimestampRaw) {
                errorBox.innerText = 'יש להזין תאריך/שעת סגירה.';
                errorBox.style.display = 'block';
                return;
            }

            // Convert "YYYY-MM-DDTHH:MM" -> "YYYY-MM-DD HH:MM:SS"
            const exitTimestamp = exitTimestampRaw.replace('T', ' ') + ':00';

            const btn = document.getElementById('closeTradeSubmitBtn');
            btn.disabled = true;
            btn.style.opacity = '0.5';

            try {
                const response = await fetch('/api/close-trade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ticker: ticker, exit_price: exitPrice, exit_timestamp: exitTimestamp })
                });
                const data = await response.json();

                if (data.success) {
                    location.reload();
                } else {
                    errorBox.innerText = data.message || 'שגיאה בסגירת הפוזיציה.';
                    errorBox.style.display = 'block';
                }
            } catch (e) {
                errorBox.innerText = 'שגיאת רשת: ' + e;
                errorBox.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        };


        function appendDryRunLog(message) {
            const logBox = document.getElementById('dryRunLog');
            const div = document.createElement('div');
            let colorStyle = 'color: #39FF14;';
            if (message.includes('Failed') || message.includes('Error')) {
                colorStyle = 'color: #ff5252;';
            } else if (message.includes('Skipped') || message.includes('Skipping')) {
                colorStyle = 'color: #e67e22;';
            } else if (message.includes('Found setup')) {
                colorStyle = 'color: #00ffff; font-weight: bold;';
            } else if (message.includes('[System]')) {
                colorStyle = 'color: #555;';
            }
            div.style = colorStyle;
            div.innerText = '[' + new Date().toLocaleTimeString() + '] ' + message;
            logBox.appendChild(div);
            logBox.scrollTop = logBox.scrollHeight;
        }

        window.startDryRun = function() {
            document.getElementById('dryRunStartBtn').disabled = true;
            document.getElementById('dryRunStartBtn').style.opacity = '0.5';
            
            const targetRsi = document.getElementById('dryrun-rsi').value;
            const stopLossPct = document.getElementById('dryrun-sl').value;
            const takeProfitPct = document.getElementById('dryrun-tp').value;
            
            appendDryRunLog('[System] Connecting to dry run stream...');
            dryRunEventSource = new EventSource(`/api/dry-run-stream?target_rsi=${targetRsi}&stop_loss_pct=${stopLossPct}&take_profit_pct=${takeProfitPct}`);

            dryRunEventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.progress !== undefined) {
                    const pct = Math.round(data.progress);
                    document.getElementById('dryRunProgressBar').style.width = pct + '%';
                    document.getElementById('dryRunProgressText').innerText = pct + '%';
                }

                if (data.message) {
                    appendDryRunLog(data.message);
                    document.getElementById('dryRunStatusText').innerText = data.message;
                }

                if (data.complete) {
                    appendDryRunLog('[System] Dry run completed successfully!');
                    document.getElementById('dryRunStatusText').innerText = 'Scan Complete!';
                    
                    const tableBody = document.getElementById('dryRunResultsTableBody');
                    tableBody.innerHTML = '';
                    
                    if (data.top_setups && data.top_setups.length > 0) {
                        data.top_setups.forEach(s => {
                            const tr = document.createElement('tr');
                            tr.style.borderBottom = '1px solid #262626';
                            tr.innerHTML = `
                                <td style="padding: 8px;"><strong>${s.Ticker}</strong></td>
                                <td style="padding: 8px;">$${s.Close.toFixed(2)}</td>
                                <td style="padding: 8px; color: #ff5252;">$${s.StopLoss.toFixed(2)}</td>
                                <td style="padding: 8px; color: #39FF14;">$${s.TakeProfit.toFixed(2)}</td>
                                <td style="padding: 8px; color: #00ffff;">${s.RSI_14.toFixed(1)}</td>
                                <td style="padding: 8px; color: #39FF14;">${s.RiskReward.toFixed(2)}</td>
                            `;
                            tableBody.appendChild(tr);
                        });
                    } else {
                        tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 15px; color: #aaa;">No setups found passing the strategy rules.</td></tr>';
                    }

                    document.getElementById('dryRunResultsSection').style.display = 'block';
                    dryRunEventSource.close();
                    dryRunEventSource = null;
                }
            };

            dryRunEventSource.onerror = function(err) {
                appendDryRunLog('[Error] Lost connection to dry run stream.');
                document.getElementById('dryRunStatusText').innerText = 'Connection Error';
                dryRunEventSource.close();
                dryRunEventSource = null;
                document.getElementById('dryRunStartBtn').disabled = false;
                document.getElementById('dryRunStartBtn').style.opacity = '1';
            };
        };
        
        // Auto-refresh functionality - updates prices every 15 minutes during market hours
        const REFRESH_INTERVAL = 15 * 60 * 1000; // 15 minutes in milliseconds
        let lastUpdateTime = new Date();
        
        async function autoRefreshPrices() {
            try {
                // Check market status
                const marketResp = await fetch('/api/market-status');
                const marketData = await marketResp.json();
                
                // Update last refresh time display
                lastUpdateTime = new Date();
                const timeStr = lastUpdateTime.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });
                document.getElementById('market-label').innerText = `${marketData.message} | עודכן: ${timeStr}`;
                
                // If market is open or it's a weekday, refresh prices
                const day = new Date().getDay();
                const isWeekday = day >= 1 && day <= 5;
                
                if (marketData.status === 'open' || isWeekday) {
                    console.log('Auto-refreshing prices...');
                    const refreshResp = await fetch('/refresh-tracker');
                    if (refreshResp.ok) {
                        console.log('✅ Prices refreshed successfully');
                        // Reload the page to show updated prices
                        location.reload();
                    }
                }
            } catch (e) {
                console.error('Error in auto-refresh:', e);
            }
        }
        
        // Initialize auto-refresh
        (async () => {
            // Check market status immediately on load
            try {
                const response = await fetch('/api/market-status');
                const data = await response.json();
                document.getElementById('market-led').className = data.status === 'open' ? 'led-dot led-green' : 'led-dot led-red';
                const timeStr = new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });
                document.getElementById('market-label').innerText = `${data.message} | עודכן: ${timeStr}`;
            } catch (e) {
                console.error('Error checking market status:', e);
            }
            
            // Set up auto-refresh interval
            setInterval(autoRefreshPrices, REFRESH_INTERVAL);
            console.log(`🔄 Auto-refresh enabled: every ${REFRESH_INTERVAL / 60000} minutes`);
        })();

        // Data Management: Backup & Restore Logic
        function showDataManagementStatus(message, isError) {
            const box = document.getElementById('dataManagementStatus');
            box.style.display = 'block';
            box.style.background = isError ? 'rgba(255, 82, 82, 0.15)' : 'rgba(57, 255, 20, 0.15)';
            box.style.border = isError ? '1px solid #ff5252' : '1px solid #39FF14';
            box.style.color = isError ? '#ff5252' : '#39FF14';
            box.innerText = message;
        }

        function downloadBackup() {
            window.location.href = '/api/export-data';
        }

        let pendingRestoreFile = null;

        function handleRestoreFileSelected(event) {
            const file = event.target.files[0];
            if (!file) return;
            pendingRestoreFile = file;
            document.getElementById('restoreConfirmModal').style.display = 'flex';
        }

        function cancelRestoreUpload() {
            pendingRestoreFile = null;
            document.getElementById('restoreFileInput').value = '';
            document.getElementById('restoreConfirmModal').style.display = 'none';
        }

        async function confirmRestoreUpload() {
            if (!pendingRestoreFile) {
                cancelRestoreUpload();
                return;
            }

            const btn = document.getElementById('restoreConfirmBtn');
            btn.disabled = true;
            btn.style.opacity = '0.5';

            const formData = new FormData();
            formData.append('backup_file', pendingRestoreFile);

            try {
                const response = await fetch('/api/import-data', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                document.getElementById('restoreConfirmModal').style.display = 'none';
                pendingRestoreFile = null;
                document.getElementById('restoreFileInput').value = '';

                if (data.success) {
                    showDataManagementStatus('✅ ' + data.message + ' טוען מחדש...', false);
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showDataManagementStatus('❌ ' + data.message, true);
                }
            } catch (e) {
                showDataManagementStatus('❌ שגיאת רשת: ' + e, true);
                document.getElementById('restoreConfirmModal').style.display = 'none';
            } finally {
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        }

        // FX / Deposits Management Logic
        function showDepositsManagementStatus(message, isError) {
            const box = document.getElementById('depositsManagementStatus');
            box.style.display = 'block';
            box.style.background = isError ? 'rgba(255, 82, 82, 0.15)' : 'rgba(57, 255, 20, 0.15)';
            box.style.border = isError ? '1px solid #ff5252' : '1px solid #39FF14';
            box.style.color = isError ? '#ff5252' : '#39FF14';
            box.innerText = message;
        }

        window.openFxManagementModal = async function() {
            document.getElementById('fxManagementModal').style.display = 'flex';
            document.getElementById('depositsManagementStatus').style.display = 'none';
            await loadDepositsTable();
        };

        window.closeFxManagementModal = function() {
            document.getElementById('fxManagementModal').style.display = 'none';
        };

        async function loadDepositsTable() {
            const tbody = document.getElementById('depositsTableBody');
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 15px; color: #aaa;">טוען...</td></tr>';
            try {
                const response = await fetch('/api/deposits');
                const data = await response.json();

                document.getElementById('defaultFxRateInput').value = data.default_fx_rate || '';
                document.getElementById('defaultDepositFeeInput').value = (data.default_deposit_fee_usd != null) ? data.default_deposit_fee_usd : '';

                if (!data.deposits || data.deposits.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 15px; color: #aaa;">אין הפקדות רשומות.</td></tr>';
                    return;
                }

                tbody.innerHTML = '';
                data.deposits.forEach(dep => {
                    const currency = dep.source_currency || 'USD';
                    const amount = currency === 'ILS' ? dep.amount_ils : dep.amount_usd;
                    const rate = dep.fx_rate_at_deposit;
                    const netUsd = dep.converted_to_usd;
                    const fee = dep.conversion_fee_usd;

                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid #262626';
                    tr.innerHTML = `
                        <td style="padding: 8px;">${dep.date || ''}</td>
                        <td style="padding: 8px;">${dep.description || ''}</td>
                        <td style="padding: 8px; text-align: center;">${currency}</td>
                        <td style="padding: 8px; text-align: right;">${amount != null ? amount.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : '--'}</td>
                        <td style="padding: 8px; text-align: right; ${rate ? '' : 'color: #f39c12;'}">${rate ? rate.toFixed(4) : 'חסר (ברירת מחדל)'}</td>
                        <td style="padding: 8px; text-align: right;">${currency === 'ILS' ? (fee != null ? '$' + fee.toFixed(2) : '--') : '--'}</td>
                        <td style="padding: 8px; text-align: right;">${netUsd != null ? netUsd.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : '--'}</td>
                        <td style="padding: 8px; text-align: center;">
                            <button onclick="openEditDepositModal(${dep.id})" class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.75rem; border-color: #4d94ff; color: #4d94ff;">✏️ ערוך</button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 15px; color: #ff5252;">שגיאה בטעינת נתונים: ${e}</td></tr>`;
            }
        }

        window.saveDefaultFxRate = async function() {
            const input = document.getElementById('defaultFxRateInput');
            const statusEl = document.getElementById('defaultFxRateStatus');
            const rate = parseFloat(input.value);

            if (isNaN(rate) || rate <= 0) {
                statusEl.style.color = '#ff5252';
                statusEl.innerText = 'יש להזין שער תקין.';
                return;
            }

            try {
                const response = await fetch('/api/default-fx-rate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rate: rate })
                });
                const data = await response.json();
                if (data.success) {
                    statusEl.style.color = '#39FF14';
                    statusEl.innerText = '✅ נשמר!';
                    setTimeout(() => location.reload(), 1000);
                } else {
                    statusEl.style.color = '#ff5252';
                    statusEl.innerText = '❌ ' + data.message;
                }
            } catch (e) {
                statusEl.style.color = '#ff5252';
                statusEl.innerText = '❌ שגיאת רשת: ' + e;
            }
        };

        window.saveDefaultDepositFee = async function() {
            const input = document.getElementById('defaultDepositFeeInput');
            const statusEl = document.getElementById('defaultDepositFeeStatus');
            const fee = parseFloat(input.value);

            if (isNaN(fee) || fee < 0) {
                statusEl.style.color = '#ff5252';
                statusEl.innerText = 'יש להזין עמלה תקינה.';
                return;
            }

            try {
                const response = await fetch('/api/default-deposit-fee', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fee: fee })
                });
                const data = await response.json();
                if (data.success) {
                    statusEl.style.color = '#39FF14';
                    statusEl.innerText = '✅ נשמר!';
                    setTimeout(() => { statusEl.innerText = ''; }, 2000);
                } else {
                    statusEl.style.color = '#ff5252';
                    statusEl.innerText = '❌ ' + data.message;
                }
            } catch (e) {
                statusEl.style.color = '#ff5252';
                statusEl.innerText = '❌ שגיאת רשת: ' + e;
            }
        };

        let currentEditDeposit = null;

        window.openEditDepositModal = async function(depositId) {
            try {
                const response = await fetch('/api/deposits');
                const data = await response.json();
                const dep = (data.deposits || []).find(d => d.id === depositId);
                if (!dep) {
                    alert('הפקדה לא נמצאה.');
                    return;
                }
                currentEditDeposit = dep;

                const currency = dep.source_currency || 'USD';
                const amount = currency === 'ILS' ? dep.amount_ils : dep.amount_usd;

                document.getElementById('editDepositId').value = dep.id;
                document.getElementById('editDepositDate').value = dep.date || '';
                document.getElementById('editDepositAmount').value = amount != null ? amount : '';
                document.getElementById('editDepositCurrencyLabel').innerText = currency;
                document.getElementById('editDepositFxRate').value = dep.fx_rate_at_deposit || '';

                const feeRow = document.getElementById('editDepositFeeRow');
                if (currency === 'ILS') {
                    feeRow.style.display = 'block';
                    document.getElementById('editDepositFee').value = (dep.conversion_fee_usd != null) ? dep.conversion_fee_usd : '';
                } else {
                    feeRow.style.display = 'none';
                }

                document.getElementById('editDepositError').style.display = 'none';

                document.getElementById('editDepositModal').style.display = 'flex';
            } catch (e) {
                alert('שגיאה בטעינת הפקדה: ' + e);
            }
        };

        window.closeEditDepositModal = function() {
            document.getElementById('editDepositModal').style.display = 'none';
            currentEditDeposit = null;
        };

        window.submitEditDeposit = async function() {
            const depositId = parseInt(document.getElementById('editDepositId').value);
            const date = document.getElementById('editDepositDate').value;
            const amount = parseFloat(document.getElementById('editDepositAmount').value);
            const fxRateRaw = document.getElementById('editDepositFxRate').value;
            const fxRate = fxRateRaw ? parseFloat(fxRateRaw) : null;
            const feeRaw = document.getElementById('editDepositFee').value;
            const feeRowVisible = document.getElementById('editDepositFeeRow').style.display !== 'none';
            const conversionFee = (feeRowVisible && feeRaw !== '') ? parseFloat(feeRaw) : null;
            const errorBox = document.getElementById('editDepositError');
            errorBox.style.display = 'none';

            if (isNaN(amount) || amount <= 0) {
                errorBox.innerText = 'יש להזין סכום תקין.';
                errorBox.style.display = 'block';
                return;
            }

            const btn = document.getElementById('editDepositSubmitBtn');
            btn.disabled = true;
            btn.style.opacity = '0.5';

            try {
                const payload = { date: date, amount: amount, fx_rate: fxRate };
                if (conversionFee !== null) {
                    payload.conversion_fee = conversionFee;
                }
                const response = await fetch(`/api/deposits/${depositId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (data.success) {
                    closeEditDepositModal();
                    closeFxManagementModal();
                    showDataManagementStatus('✅ ' + data.message + ' טוען מחדש...', false);
                    setTimeout(() => location.reload(), 1000);
                } else {
                    errorBox.innerText = data.message || 'שגיאה בעדכון ההפקדה.';
                    errorBox.style.display = 'block';
                }
            } catch (e) {
                errorBox.innerText = 'שגיאת רשת: ' + e;
                errorBox.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        };

        window.deleteDepositFromModal = async function() {
            const depositId = parseInt(document.getElementById('editDepositId').value);
            if (!confirm('האם אתה בטוח שברצונך למחוק הפקדה זו? פעולה זו אינה הפיכה.')) {
                return;
            }

            try {
                const response = await fetch(`/api/deposits/${depositId}`, { method: 'DELETE' });
                const data = await response.json();

                if (data.success) {
                    closeEditDepositModal();
                    closeFxManagementModal();
                    showDataManagementStatus('✅ ' + data.message + ' טוען מחדש...', false);
                    setTimeout(() => location.reload(), 1000);
                } else {
                    alert('❌ ' + data.message);
                }
            } catch (e) {
                alert('❌ שגיאת רשת: ' + e);
            }
        };

        // Add Manual Deposit Logic
        window.openAddDepositModal = async function() {
            document.getElementById('addDepositDate').value = new Date().toISOString().slice(0, 10);
            document.getElementById('addDepositAmount').value = '';
            document.getElementById('addDepositFxRate').value = '';
            document.getElementById('addDepositError').style.display = 'none';
            document.querySelector('input[name="addDepositCurrency"][value="ILS"]').checked = true;

            let defaultFee = 0;
            try {
                const response = await fetch('/api/deposits');
                const data = await response.json();
                defaultFee = (data.default_deposit_fee_usd != null) ? data.default_deposit_fee_usd : 0;
            } catch (e) {
                defaultFee = 0;
            }
            document.getElementById('addDepositFee').value = defaultFee;

            toggleAddDepositCurrencyFields();
            document.getElementById('addDepositModal').style.display = 'flex';
        };

        window.closeAddDepositModal = function() {
            document.getElementById('addDepositModal').style.display = 'none';
        };

        window.toggleAddDepositCurrencyFields = function() {
            const isIls = document.querySelector('input[name="addDepositCurrency"]:checked').value === 'ILS';
            document.getElementById('addDepositAmountLabel').innerText = isIls ? '\u05e1\u05db\u05d5\u05dd (\u20aa):' : '\u05e1\u05db\u05d5\u05dd ($):';
            document.getElementById('addDepositFeeRow').style.display = isIls ? 'block' : 'none';
            document.getElementById('addDepositFxRate').parentElement.style.display = isIls ? 'block' : 'none';
            updateAddDepositPreview();
        };

        window.updateAddDepositPreview = function() {
            const previewEl = document.getElementById('addDepositPreview');
            const isIls = document.querySelector('input[name="addDepositCurrency"]:checked').value === 'ILS';
            const amount = parseFloat(document.getElementById('addDepositAmount').value);
            const fxRateRaw = document.getElementById('addDepositFxRate').value;
            const fxRate = fxRateRaw ? parseFloat(fxRateRaw) : null;
            const fee = parseFloat(document.getElementById('addDepositFee').value) || 0;

            if (isNaN(amount) || amount <= 0) {
                previewEl.innerText = '\u05e0\u05d8\u05d5 \u05dc\u05ea\u05d9\u05e7: --';
                return;
            }
            if (!isIls) {
                previewEl.innerText = '\u05e0\u05d8\u05d5 \u05dc\u05ea\u05d9\u05e7: ~$' + amount.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                return;
            }
            if (!fxRate || fxRate <= 0) {
                previewEl.innerText = '\u05e0\u05d8\u05d5 \u05dc\u05ea\u05d9\u05e7: \u05d9\u05d7\u05d5\u05e9\u05d1 \u05d0\u05d5\u05d8\u05d5\u05de\u05d8\u05d9\u05ea \u05dc\u05e4\u05d9 \u05d4\u05ea\u05d0\u05e8\u05d9\u05da';
                return;
            }
            const net = (amount / fxRate) - fee;
            previewEl.innerText = '\u05e0\u05d8\u05d5 \u05dc\u05ea\u05d9\u05e7: ~$' + net.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
        };

        window.submitAddDeposit = async function() {
            const date = document.getElementById('addDepositDate').value;
            const currency = document.querySelector('input[name="addDepositCurrency"]:checked').value;
            const amount = parseFloat(document.getElementById('addDepositAmount').value);
            const fxRateRaw = document.getElementById('addDepositFxRate').value;
            const feeRaw = document.getElementById('addDepositFee').value;
            const errorBox = document.getElementById('addDepositError');
            errorBox.style.display = 'none';

            if (!date) {
                errorBox.innerText = '\u05d9\u05e9 \u05dc\u05d1\u05d7\u05d5\u05e8 \u05ea\u05d0\u05e8\u05d9\u05da.';
                errorBox.style.display = 'block';
                return;
            }
            if (isNaN(amount) || amount <= 0) {
                errorBox.innerText = '\u05d9\u05e9 \u05dc\u05d4\u05d6\u05d9\u05df \u05e1\u05db\u05d5\u05dd \u05ea\u05e7\u05d9\u05df (\u05d2\u05d3\u05d5\u05dc \u05de-0).';
                errorBox.style.display = 'block';
                return;
            }

            const payload = { date: date, currency: currency, amount: amount };
            if (currency === 'ILS' && fxRateRaw !== '') {
                payload.fx_rate = parseFloat(fxRateRaw);
            }
            if (currency === 'ILS' && feeRaw !== '') {
                payload.conversion_fee = parseFloat(feeRaw);
            }

            const btn = document.getElementById('addDepositSubmitBtn');
            btn.disabled = true;
            btn.style.opacity = '0.5';

            try {
                const response = await fetch('/api/deposits', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (data.success) {
                    closeAddDepositModal();
                    closeFxManagementModal();
                    showDataManagementStatus('\u2705 ' + data.message, false);
                    setTimeout(() => location.reload(), 800);
                } else {
                    errorBox.innerText = data.message || 'Error';
                    errorBox.style.display = 'block';
                }
            } catch (e) {
                errorBox.innerText = 'Network error: ' + e;
                errorBox.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        };
    </script>



    <!-- Dry Run Scanner Modal -->
    <div id="dryRunModal" style="display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.85); align-items: center; justify-content: center;">
        <div style="background-color: #141414; margin: auto; padding: 30px; border: 1px solid #262626; width: 80%; max-width: 800px; border-radius: 16px; position: relative; direction: ltr; text-align: left;">
            <span onclick="closeDryRunModal()" style="position: absolute; right: 20px; top: 15px; color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer;">&times;</span>
            <h2 style="margin-top: 0; color: #39FF14;">Dry Run Scanner</h2>
            <p style="color: #a0a0a0; font-size: 0.9rem;">Runs the full scanning algorithm on live data. Results are NOT saved to the database.</p>
            
            <!-- Strategy Configuration Section -->
            <div style="background: #1c1c1c; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-bottom: 20px;">
                <h3 style="margin-top: 0; color: white; font-size: 1rem;">Strategy Configuration</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                    <div>
                        <label style="display: block; color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-bottom: 6px;">Target RSI:</label>
                        <input type="number" id="dryrun-rsi" value="55" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 8px; border-radius: 8px; width: 100%; font-size: 0.9rem; box-sizing: border-box;">
                    </div>
                    <div>
                        <label style="display: block; color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-bottom: 6px;">Stop Loss %:</label>
                        <input type="number" id="dryrun-sl" value="5.0" step="0.1" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 8px; border-radius: 8px; width: 100%; font-size: 0.9rem; box-sizing: border-box;">
                    </div>
                    <div>
                        <label style="display: block; color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-bottom: 6px;">Take Profit %:</label>
                        <input type="number" id="dryrun-tp" value="10.0" step="0.1" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 8px; border-radius: 8px; width: 100%; font-size: 0.9rem; box-sizing: border-box;">
                    </div>
                </div>
            </div>
            
            <!-- Progress Section -->
            <div id="dryRunProgressSection" style="margin: 20px 0;">
                <div style="display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 5px; font-size: 0.85rem;">
                    <span id="dryRunStatusText" style="color: #ccc;">Initializing...</span>
                    <span id="dryRunProgressText" style="color: #39FF14;">0%</span>
                </div>
                <div style="width: 100%; background: #1a1a1a; height: 10px; border-radius: 5px; border: 1px solid #333; overflow: hidden;">
                    <div id="dryRunProgressBar" style="width: 0%; height: 100%; background: linear-gradient(to right, #39FF14, #32cd32); transition: width 0.3s;"></div>
                </div>
                
                <div id="dryRunLog" style="height: 200px; background: #000; color: #39FF14; font-family: monospace; font-size: 11px; padding: 10px; border-radius: 8px; border: 1px solid #262626; overflow-y: auto; margin-top: 15px; display: flex; flex-direction: column; gap: 2px;">
                    <div style="color: #555;">[System] Ready to start dry run...</div>
                </div>
            </div>

            <!-- Results Section -->
            <div id="dryRunResultsSection" style="display: none; margin-top: 20px;">
                <h3 style="color: white; border-bottom: 1px solid #262626; padding-bottom: 8px; margin-bottom: 15px;">Top Scan Results</h3>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 1px solid #262626;">
                                <th style="text-align: left; padding: 8px; color: #a0a0a0;">Ticker</th>
                                <th style="text-align: left; padding: 8px; color: #a0a0a0;">Price</th>
                                <th style="text-align: left; padding: 8px; color: #a0a0a0;">Stop Loss</th>
                                <th style="text-align: left; padding: 8px; color: #a0a0a0;">Take Profit</th>
                                <th style="text-align: left; padding: 8px; color: #a0a0a0;">RSI</th>
                                <th style="text-align: left; padding: 8px; color: #a0a0a0;">Risk/Reward</th>
                            </tr>
                        </thead>
                        <tbody id="dryRunResultsTableBody">
                        </tbody>
                    </table>
                </div>
            </div>

            <div style="display: flex; justify-content: flex-end; margin-top: 25px; gap: 10px;">
                <button id="dryRunStartBtn" onclick="startDryRun()" class="btn btn-primary" style="background: #39FF14; color: black; border: none;">Start Dry Run</button>
                <button onclick="closeDryRunModal()" class="btn btn-secondary">Close</button>
            </div>
        </div>
    </div>

    <!-- FX / Deposits Management Modal -->
    <div id="fxManagementModal" style="display: none; position: fixed; z-index: 1150; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.85); align-items: center; justify-content: center;">
        <div style="background-color: #141414; margin: auto; padding: 30px; border: 1px solid #262626; width: 90%; max-width: 950px; border-radius: 16px; position: relative; direction: rtl; text-align: right;">
            <span onclick="closeFxManagementModal()" style="position: absolute; left: 20px; top: 15px; color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer;">&times;</span>
            <h2 style="margin-top: 0; color: #4d94ff; display: flex; align-items: center; justify-content: space-between; gap: 20px;">
                <span>✏️ ניהול הפקדות ושערי המרה</span>
                <button onclick="openAddDepositModal()" class="btn btn-secondary" style="border-color: #39FF14; color: #39FF14; font-size: 0.85rem; padding: 8px 14px;">➕ הוסף הפקדה ידנית</button>
            </h2>

            <!-- Default FX Rate + Default Deposit Fee Section -->
            <div style="background: #1c1c1c; padding: 18px; border-radius: 12px; border: 1px solid #333; margin-bottom: 20px;">
                <h4 style="margin-top: 0; color: white; font-size: 0.95rem;">שער ברירת מחדל (עבור הפקדות ללא שער רשום)</h4>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="number" id="defaultFxRateInput" step="0.0001" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 180px; font-size: 1rem; box-sizing: border-box;">
                    <button onclick="saveDefaultFxRate()" class="btn btn-secondary" style="border-color: #4d94ff; color: #4d94ff;">💾 שמור שער</button>
                    <span id="defaultFxRateStatus" style="font-size: 0.85rem; margin-right: 10px;"></span>
                </div>

                <h4 style="margin-top: 18px; color: white; font-size: 0.95rem;">עמלת הפקדה/המרה - ברירת מחדל (בדולר, עבור הפקדות שקליות חדשות)</h4>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="number" id="defaultDepositFeeInput" step="0.01" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 180px; font-size: 1rem; box-sizing: border-box;">
                    <button onclick="saveDefaultDepositFee()" class="btn btn-secondary" style="border-color: #4d94ff; color: #4d94ff;">💾 שמור עמלה</button>
                    <span id="defaultDepositFeeStatus" style="font-size: 0.85rem; margin-right: 10px;"></span>
                </div>
                <div style="color:#777; font-size:0.75rem; margin-top: 8px;">שער הדולר לכל הפקדה נמשך אוטומטית מתאריך ההפקדה (או שער ברירת המחדל אם אין שער היסטורי). ניתן לעדכן את עמלת ההפקדה בכל זמן, וכל ההפקדות הקיימות/ההיסטוריה יסונכרנו בהתאם.</div>
            </div>

            <!-- Deposits Table -->
            <div style="overflow-x: auto; max-height: 400px; overflow-y: auto; border: 1px solid #262626; border-radius: 12px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                    <thead>
                        <tr style="border-bottom: 1px solid #262626; background: #1a1a1a; position: sticky; top: 0;">
                            <th style="padding: 10px; color: var(--text-dim); text-align: right;">תאריך</th>
                            <th style="padding: 10px; color: var(--text-dim); text-align: right;">תיאור</th>
                            <th style="padding: 10px; color: var(--text-dim); text-align: center;">מטבע</th>
                            <th style="padding: 10px; color: var(--text-dim); text-align: right;">סכום</th>
                            <th style="padding: 10px; color: var(--text-dim); text-align: right;">שער המרה</th>
                            <th style="padding: 10px; color: var(--text-dim); text-align: right;">עמלת המרה</th>
                            <th style="padding: 10px; color: var(--text-dim); text-align: right;">נטו (USD)</th>
                            <th style="padding: 10px; color: var(--text-dim); text-align: center;">פעולה</th>
                        </tr>
                    </thead>
                    <tbody id="depositsTableBody">
                        <tr><td colspan="8" style="text-align:center; padding: 15px; color: #aaa;">טוען...</td></tr>
                    </tbody>
                </table>
            </div>

            <div id="depositsManagementStatus" style="display: none; margin-top: 15px; padding: 12px; border-radius: 8px; font-size: 0.9rem;"></div>

            <div style="display: flex; justify-content: flex-end; margin-top: 20px; gap: 10px;">
                <button onclick="closeFxManagementModal()" class="btn btn-secondary">סגור</button>
            </div>
        </div>
    </div>

    <!-- Edit Deposit Modal -->
    <div id="editDepositModal" style="display: none; position: fixed; z-index: 1200; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.9); align-items: center; justify-content: center;">
        <div style="background-color: #141414; margin: auto; padding: 30px; border: 1px solid #262626; width: 90%; max-width: 450px; border-radius: 16px; position: relative; direction: rtl; text-align: right;">
            <span onclick="closeEditDepositModal()" style="position: absolute; left: 20px; top: 15px; color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer;">&times;</span>
            <h2 style="margin-top: 0; color: #4d94ff;">✏️ עריכת הפקדה</h2>
            <input type="hidden" id="editDepositId">

            <div style="margin-bottom: 15px; margin-top: 20px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">תאריך:</label>
                <input type="date" id="editDepositDate" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div style="margin-bottom: 15px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">סכום (<span id="editDepositCurrencyLabel">USD</span>):</label>
                <input type="number" id="editDepositAmount" step="0.01" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div style="margin-bottom: 15px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">שער המרה (השאר ריק לשימוש בברירת מחדל):</label>
                <input type="number" id="editDepositFxRate" step="0.0001" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div id="editDepositFeeRow" style="margin-bottom: 15px; display: none;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">עמלת המרה (בדולר):</label>
                <input type="number" id="editDepositFee" step="0.01" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div id="editDepositError" style="display: none; color: #ff5252; font-size: 0.85rem; margin-bottom: 10px;"></div>

            <div style="display: flex; justify-content: space-between; margin-top: 20px; gap: 10px;">
                <button onclick="deleteDepositFromModal()" class="btn btn-secondary" style="border-color: #ff5252; color: #ff5252;">🗑️ מחק</button>
                <div style="display: flex; gap: 10px;">
                    <button id="editDepositSubmitBtn" onclick="submitEditDeposit()" class="btn btn-primary" style="background: #4d94ff; color: white; border: none;">שמור שינויים</button>
                    <button onclick="closeEditDepositModal()" class="btn btn-secondary">ביטול</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Add Manual Deposit Modal -->
    <div id="addDepositModal" style="display: none; position: fixed; z-index: 1250; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.9); align-items: center; justify-content: center;">
        <div style="background-color: #141414; margin: auto; padding: 30px; border: 1px solid #262626; width: 90%; max-width: 460px; border-radius: 16px; position: relative; direction: rtl; text-align: right;">
            <span onclick="closeAddDepositModal()" style="position: absolute; left: 20px; top: 15px; color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer;">&times;</span>
            <h2 style="margin-top: 0; color: #39FF14;">➕ הפקדה חדשה</h2>
            <p style="color: #a0a0a0; font-size: 0.85rem;">הוספת הפקדה ללא הרצת סריקה שבועית. הכסף יתווסף מיידית ל-Cash Available.</p>

            <div style="margin-bottom: 15px; margin-top: 20px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">תאריך:</label>
                <input type="date" id="addDepositDate" onchange="updateAddDepositPreview()" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div style="margin-bottom: 15px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">סוג הפקדה:</label>
                <div style="display: flex; gap: 15px;">
                    <label style="display: flex; align-items: center; gap: 6px; color: #ddd; font-size: 0.9rem; cursor: pointer;">
                        <input type="radio" name="addDepositCurrency" value="ILS" checked onchange="toggleAddDepositCurrencyFields()" style="width: auto; margin: 0;"> שקלים (₪)
                    </label>
                    <label style="display: flex; align-items: center; gap: 6px; color: #ddd; font-size: 0.9rem; cursor: pointer;">
                        <input type="radio" name="addDepositCurrency" value="USD" onchange="toggleAddDepositCurrencyFields()" style="width: auto; margin: 0;"> דולר ($)
                    </label>
                </div>
            </div>

            <div style="margin-bottom: 15px;">
                <label id="addDepositAmountLabel" style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">סכום (₪):</label>
                <input type="number" id="addDepositAmount" step="0.01" oninput="updateAddDepositPreview()" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div style="margin-bottom: 15px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">שער המרה (ריק = שליפה אוטומטית לפי התאריך):</label>
                <input type="number" id="addDepositFxRate" step="0.0001" placeholder="אוטומטי" oninput="updateAddDepositPreview()" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div id="addDepositFeeRow" style="margin-bottom: 15px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">עמלת המרה (בדולר):</label>
                <input type="number" id="addDepositFee" step="0.01" oninput="updateAddDepositPreview()" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div id="addDepositPreview" style="background: #1c1c1c; border: 1px solid #333; border-radius: 8px; padding: 12px; color: #39FF14; font-weight: 600; font-size: 0.9rem; margin-bottom: 15px;">נטו לתיק: --</div>

            <div id="addDepositError" style="display: none; color: #ff5252; font-size: 0.85rem; margin-bottom: 10px;"></div>

            <div style="display: flex; justify-content: flex-end; margin-top: 20px; gap: 10px;">
                <button id="addDepositSubmitBtn" onclick="submitAddDeposit()" class="btn btn-primary" style="background: #39FF14; color: #0a0a0a; border: none; font-weight: bold;">הוסף הפקדה</button>
                <button onclick="closeAddDepositModal()" class="btn btn-secondary">ביטול</button>
            </div>
        </div>
    </div>

    <!-- Manual Close Trade Modal -->
    <div id="closeTradeModal" style="display: none; position: fixed; z-index: 1100; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.85); align-items: center; justify-content: center;">

        <div style="background-color: #141414; margin: auto; padding: 30px; border: 1px solid #262626; width: 90%; max-width: 450px; border-radius: 16px; position: relative; direction: ltr; text-align: left;">
            <span onclick="closeCloseTradeModal()" style="position: absolute; right: 20px; top: 15px; color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer;">&times;</span>
            <h2 style="margin-top: 0; color: #ff5252;">Close Position: <span id="closeTradeTicker"></span></h2>
            <p style="color: #a0a0a0; font-size: 0.85rem;">סגירה ידנית של פוזיציה פעילה. שימוש למקרי קצה בלבד (תיקון טעויות, סנכרון עם הברוקר).</p>
            <input type="hidden" id="closeTradeTickerHidden">

            <div style="margin-bottom: 15px; margin-top: 20px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">Exit Price ($):</label>
                <input type="number" id="closeTradeExitPrice" step="0.01" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div style="margin-bottom: 15px;">
                <label style="display: block; color: var(--text-dim); font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">Exit Date/Time:</label>
                <input type="datetime-local" id="closeTradeExitTimestamp" style="background: #0a0a0a; border: 1px solid #333; color: white; padding: 10px; border-radius: 8px; width: 100%; font-size: 1rem; box-sizing: border-box;">
            </div>

            <div id="closeTradeError" style="display: none; color: #ff5252; font-size: 0.85rem; margin-bottom: 10px;"></div>

            <div style="display: flex; justify-content: flex-end; margin-top: 20px; gap: 10px;">
                <button id="closeTradeSubmitBtn" onclick="submitCloseTrade()" class="btn btn-primary" style="background: #ff5252; color: white; border: none;">Confirm Close</button>
                <button onclick="closeCloseTradeModal()" class="btn btn-secondary">Cancel</button>
            </div>
        </div>
    </div>
</body>
</html>"""

def get_charts_data(active_trades):
    """
    Fetches historical data for active trades to be displayed on charts.
    """
    charts_data = {}
    for t in active_trades:
        ticker = t['ticker']
        df = stock_api.get_historical_data(ticker, days=60)
        if df is not None:
            charts_data[ticker] = {
                "x": df.index.strftime("%Y-%m-%d").tolist(),
                "y": df['Close'].tolist(),
                "entry": t['entry_price'],
                "tp": t['take_profit'],
                "sl": t['stop_loss']
            }
    return charts_data

def generate_dashboard_file(trades, output_file="output/tracker_dashboard.html"):
    """
    Generates the final HTML dashboard.
    """
    import trading_logic

    active_trades = [t for t in trades if trading_logic.is_open_position(t)]
    pending_trades = [t for t in trades if trading_logic.is_pending_entry(t)]
    # History shows executed-and-closed trades plus expired (never bought)
    # orders, so the user can see which signals were missed and why.
    historical_trades = [t for t in trades
                         if trading_logic.is_closed_trade(t) or trading_logic.is_not_filled(t)]

    # Use analytics_generator to calculate portfolio state
    import analytics_generator

    
    metadata = data_manager.get_metadata()
    total_deposits = metadata.get("total_deposits", 0)
    commission_per_trade = metadata.get("commission_per_trade", 2.5)
    
    # Load conversion fees from deposits history
    try:
        import currency_manager
        deposits_history = currency_manager.load_deposits_history()
        total_conversion_fees = deposits_history['metadata'].get('total_conversion_fees_usd', 0.0)
        conversion_count = deposits_history['metadata'].get('conversion_count', 0)
        avg_conversion_fee = deposits_history['metadata'].get('avg_conversion_fee', 0.0)
    except:
        total_conversion_fees = metadata.get('total_conversion_fees', 0.0)
        conversion_count = 0
        avg_conversion_fee = 0.0
    
    # Calculate portfolio state using analytics_generator
    portfolio_state = analytics_generator.calculate_portfolio_state(trades, total_deposits, commission_per_trade)
    
    # Calculate ILS-denominated P&L (trading performance + FX rate movement)
    try:
        import currency_manager
        ils_pnl = currency_manager.calculate_ils_pnl(portfolio_state['current_equity'])
    except Exception:
        ils_pnl = {'available': False}

    
    current_equity = portfolio_state['current_equity']
    cash_available = portfolio_state['cash_available']
    invested_capital = portfolio_state['invested_capital']
    realized_pnl = portfolio_state['realized_pnl']
    unrealized_pnl = portfolio_state['unrealized_pnl']
    total_commissions = portfolio_state.get('total_commissions', 0)
    
    # Calculate next position size based on the ACTUAL number of empty slots
    # (active_positions must be passed in, otherwise this always divides by
    # the full max_positions=3 regardless of how many slots are actually free)
    MAX_POSITIONS = 3
    # Pending limit orders hold a slot too (they are live orders at the broker)
    active_position_count = len(active_trades) + len(pending_trades)
    slots_free = max(0, MAX_POSITIONS - active_position_count)
    next_position_size = analytics_generator.calculate_position_size(
        portfolio_state, max_positions=MAX_POSITIONS, active_positions=active_position_count
    )

    if slots_free <= 0:
        next_position_label = "Next Position: N/A (portfolio full)"
    elif cash_available <= 0:
        next_position_label = "Next Position: $0.00 (no cash available)"
    else:
        slot_word = "slot" if slots_free == 1 else "slots"
        next_position_label = f"Next Position: ${next_position_size:,.2f} ({slots_free} {slot_word} free)"
    
    # Calculate portfolio return
    portfolio_mwr = finance_utils.calculate_mwr(total_deposits, current_equity)


    # Table rows
    active_rows = ""
    for t in active_trades:
        pnl = t.get("pnl_pct", 0)
        color = "#39FF14" if pnl >= 0 else "#ff5252"
        led = "led-green" if t["status"] == "ACTIVE" else "led-orange"
        # Position value in USD: current market value vs. the original entry cost.
        # quantity is stored on the trade; fall back to deriving it from the
        # batch position size if an older record is missing it.
        quantity = t.get('quantity')
        if not quantity:
            entry_price = t.get('entry_price') or 0
            quantity = (t.get('batch_position_size', 0) / entry_price) if entry_price else 0
        cost_basis = quantity * t.get('entry_price', 0)
        market_value = quantity * t.get('current_price', 0)
        value_color = "#39FF14" if market_value >= cost_basis else "#ff5252"
        active_rows += f"""<tr class="stock-row" onclick="displayTickerData('{t['ticker']}')">
            <td><div class="led-dot {led}"></div></td>
            <td><strong>{t['ticker']}</strong></td>
            <td>{t['status']}</td>
            <td>{t.get('weight_pct', 33.33)}%</td>
            <td>${t['entry_price']:.2f}</td>
            <td>${t.get('current_price', 0):.2f}</td>
            <td>
                <div style="color: {value_color}; font-weight: bold;">${market_value:,.2f}</div>
                <div style="color: var(--text-dim); font-size: 0.75rem;">(cost ${cost_basis:,.2f})</div>
            </td>
            <td style="color: {color}; font-weight: bold;">{pnl:+.2f}%</td>
            <td><button onclick="event.stopPropagation(); openCloseTradeModal('{t['ticker']}', {t.get('current_price', 0)})" class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.75rem; border-color: #ff5252; color: #ff5252;">Close</button></td>
        </tr>"""

    # Pending limit orders - not positions yet, so no P&L is shown. Instead we
    # show how far the current price is from the target the order is waiting for.
    pending_rows = ""
    for t in pending_trades:
        target = t.get('target_entry', t.get('entry_price', 0)) or 0
        live_price, _ = stock_api.get_last_price(t['ticker'])
        if live_price:
            distance_pct = ((live_price - target) / target * 100) if target else 0
            # Price must come DOWN to the target for a buy limit to fill
            distance_color = "#39FF14" if distance_pct <= 0 else "#ffb74d"
            price_cell = f"${live_price:,.2f}"
            distance_cell = f"{distance_pct:+.2f}%"
        else:
            distance_color = "var(--text-dim)"
            price_cell = "N/A"
            distance_cell = "N/A"

        pending_rows += f"""<tr>
            <td><div class="led-dot led-orange"></div></td>
            <td><strong>{t['ticker']}</strong></td>
            <td>${target:,.2f}</td>
            <td>{price_cell}</td>
            <td style="color: {distance_color}; font-weight: bold;">{distance_cell}</td>
            <td>{t.get('entry_session_date', 'N/A')}</td>
            <td>${t.get('reserved_capital', 0):,.2f}</td>
            <td style="white-space: nowrap;">
                <button onclick="fillPendingOrder('{t['ticker']}', {target})" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.7rem; border-color: #39FF14; color: #39FF14;">מולא</button>
                <button onclick="cancelPendingOrder('{t['ticker']}')" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.7rem; border-color: #ff5252; color: #ff5252;">בטל</button>
            </td>
        </tr>"""

    history_rows = ""
    for t in reversed(historical_trades):
        if trading_logic.is_not_filled(t):
            # Never executed: no entry, no exit, no P&L. Show why it was missed.
            history_rows += f"""<tr style="opacity: 0.75;">
                <td>{t.get('expired_timestamp', t.get('timestamp', 'N/A'))}</td>
                <td><strong>{t.get('ticker', 'N/A')}</strong></td>
                <td style="color: #ffb74d;">NOT_FILLED</td>
                <td>${t.get('target_entry', 0):.2f} (target)</td>
                <td>-</td>
                <td style="color: var(--text-dim); font-size: 0.75rem;">{t.get('entry_fill_note', 'לא בוצעה קנייה')}</td>
            </tr>"""
            continue

        pnl = finance_utils.calculate_pnl_pct(t.get('exit_price', t['entry_price']), t['entry_price'])
        color = "#39FF14" if pnl >= 0 else "#ff5252"
        history_rows += f"""<tr>
            <td>{t.get('exit_timestamp', t.get('timestamp', 'N/A'))}</td>
            <td><strong>{t.get('ticker', 'N/A')}</strong></td>
            <td>{t.get('status', 'N/A')}</td>
            <td>${t['entry_price']:.2f}</td>
            <td>${t.get('exit_price', 0):.2f}</td>
            <td style="color: {color}; font-weight: bold;">{pnl:+.2f}%</td>
        </tr>"""

    # Final HTML assembly - prepare all template variables
    equity_color = "#39FF14" if current_equity >= total_deposits else "#ff5252"
    cash_color = "#39FF14" if cash_available > 0 else "#ff5252"
    realized_color = "#39FF14" if realized_pnl >= 0 else "#ff5252"
    unrealized_color = "#39FF14" if unrealized_pnl >= 0 else "#ff5252"
    
    realized_pnl_sign = "+" if realized_pnl >= 0 else ""
    realized_pnl_abs = f"{abs(realized_pnl):.2f}"
    unrealized_pnl_sign = "+" if unrealized_pnl >= 0 else ""
    unrealized_pnl_abs = f"{abs(unrealized_pnl):.2f}"
    
    charts_json = json.dumps(get_charts_data(active_trades))
    
    # Calculate total trades count (active + closed)
    total_trades_count = len(trades)
    
    # ILS P&L template variables
    if ils_pnl.get('available'):
        ils_total = ils_pnl['total_pnl_ils']
        ils_trading = ils_pnl['trading_pnl_ils']
        ils_fx = ils_pnl['fx_pnl_ils']
        ils_pnl_color = "#39FF14" if ils_total >= 0 else "#ff5252"
        ils_pnl_sign = "+" if ils_total >= 0 else "-"
        ils_pnl_abs = f"{abs(ils_total):,.2f}"
        ils_trading_sign = "+" if ils_trading >= 0 else "-"
        ils_trading_abs = f"{abs(ils_trading):,.2f}"
        ils_fx_sign = "+" if ils_fx >= 0 else "-"
        ils_fx_abs = f"{abs(ils_fx):,.2f}"
        ils_buy_rate = f"{ils_pnl['buy_rate']:.4f}"
        ils_current_rate = f"{ils_pnl['current_rate']:.4f}"
        ils_rate_change_pct = f"{abs(ils_pnl['rate_change_pct']):.2f}"
        ils_rate_change_sign = "+" if ils_pnl['rate_change_pct'] >= 0 else "-"
    else:
        ils_pnl_color = "#a0a0a0"
        ils_pnl_sign = ""
        ils_pnl_abs = "N/A"
        ils_trading_sign = ""
        ils_trading_abs = "N/A"
        ils_fx_sign = ""
        ils_fx_abs = "N/A"
        ils_buy_rate = "N/A"
        ils_current_rate = "N/A"
        ils_rate_change_pct = "0.00"
        ils_rate_change_sign = ""
    
    replacements = {
        "{{equity_color}}": equity_color,
        "{{current_equity}}": f"{current_equity:,.2f}",
        "{{total_deposits}}": f"{total_deposits:,.2f}",
        "{{portfolio_pnl}}": f"{portfolio_mwr:+.2f}%",
        "{{cash_color}}": cash_color,
        "{{cash_available}}": f"{cash_available:,.2f}",
        "{{invested_capital}}": f"{invested_capital:,.2f}",
        "{{ils_pnl_color}}": ils_pnl_color,
        "{{ils_pnl_sign}}": ils_pnl_sign,
        "{{ils_pnl_abs}}": ils_pnl_abs,
        "{{ils_trading_sign}}": ils_trading_sign,
        "{{ils_trading_abs}}": ils_trading_abs,
        "{{ils_fx_sign}}": ils_fx_sign,
        "{{ils_fx_abs}}": ils_fx_abs,
        "{{ils_buy_rate}}": ils_buy_rate,
        "{{ils_current_rate}}": ils_current_rate,
        "{{ils_rate_change_pct}}": ils_rate_change_pct,
        "{{ils_rate_change_sign}}": ils_rate_change_sign,
        "{{next_position_label}}": next_position_label,
        "{{realized_color}}": realized_color,
        "{{realized_pnl_sign}}": realized_pnl_sign,
        "{{realized_pnl_abs}}": realized_pnl_abs,
        "{{unrealized_color}}": unrealized_color,
        "{{unrealized_pnl_sign}}": unrealized_pnl_sign,
        "{{unrealized_pnl_abs}}": unrealized_pnl_abs,
        "{{total_commissions}}": f"{total_commissions:,.2f}",
        "{{commission_per_trade}}": f"{commission_per_trade:.2f}",
        "{{total_trades_count}}": str(total_trades_count),
        "{{total_conversion_fees}}": f"{total_conversion_fees:,.2f}",
        "{{conversion_count}}": str(conversion_count),
        "{{avg_conversion_fee}}": f"{avg_conversion_fee:.2f}",
        "{{active_rows}}": active_rows if active_rows else '<tr><td colspan="9" style="text-align:center;">No active trades</td></tr>',
        "{{pending_rows}}": pending_rows if pending_rows else '<tr><td colspan="8" style="text-align:center; color:#777;">אין הוראות ממתינות</td></tr>',
        "{{history_rows}}": history_rows if history_rows else '<tr><td colspan="6" style="text-align:center;">No history available</td></tr>',
        "{{charts_json}}": charts_json,
        "{{clearance_button}}": "",
    }

    html = HTML_TEMPLATE
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)



    # Ensure the destination directory exists (e.g. on a fresh clone where
    # output/ is gitignored and therefore missing entirely).
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
