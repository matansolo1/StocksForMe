# Stocks For Me - Quantitative Trading System

מערכת מסחר כמותי מבוססת RSI ומומנטום (Momentum Breakout) עבור מניות נאסד"ק (Nasdaq).

## התקנה (Installation)

התקן את כל הספריות הנדרשות בפקודה אחת:
```bash
pip install -r requirements.txt
```

## הרצה (Running)

הרץ את השרת המקומי:
```bash
python app.py
```

לאחר ההרצה, פתח את הדפדפן בכתובת: [http://127.0.0.1:5000](http://127.0.0.1:5000)

### מבנה המערכת הויזואלי (Visual Structure)

ניתן לגשת לנתיב הבא כדי לראות את מבנה התיקיות, הקבצים והתפקיד של כל רכיב במערכת בצורה ויזואלית ואינטראקטיבית:
[http://127.0.0.1:5000/structure](http://127.0.0.1:5000/structure)

### 🔬 Quantitative Research & Robustness Lab Findings

ממצאי המחקר הכמותי ומבחני החוסן (Robustness Lab) שבוצעו על פני שני משטרי שוק מרכזיים (שוק תנודתי/משברי 2021-2026 מול שוק רגוע/עולה 2010-2020):

#### 1. כישלון אסטרטגיית ה-Mean Reversion (RSI < 30) - הוסרה מהייצור
* **תפיסת סכינים נופלות (Catching Falling Knives):** אסטרטגיית חזרה לממוצע קלאסית עם RSI נמוך מ-30 קונה מניות בתיקון עמוק. בשוק רגוע, מניות חלשות שחורגות למכירת יתר קיצונית נוטות לעיתים קרובות להמשיך לדמם או לבלות זמן ממושך בתחתית, במקום להתאושש במהירות.
* **ביצועי חסר מול ה-Benchmark:** בשוק שורי וליניארי (כמו בעשור 2010-2020), החזקת מניות מומנטום חזקות מניבה תשואת יתר משמעותית. אסטרטגיית Mean Reversion הציגה ביצועי חסר קיצוניים אל מול המדד בשל חוסר יכולת לרכוב על מגמות עולות חזקות ויציאה מהירה מדי בגלל יעדי TP קרובים.
* **⚠️ אסטרטגיה זו הוסרה לחלוטין מהקוד והממשק בגרסה הנוכחית.**

#### 2. מדוע תרחיש 3 של המומנטום (RSI = 55) הוא המנצח הבלתי מעורער? 🏆
* **יציבות מתמטית של ה-Win Rate:** תרחיש 3 מציג עקביות פנומנלית ב-Win Rate עם **43.1%** בתקופת הכאוס (2021-2026) ו-**43.6%** בתקופה הרגועה (2010-2020). היציבות של אחוז ההצלחה בשני משטרי שוק כה שונים מעידה על חוסן סטטיסטי גבוה ביותר (Robustness) והיעדר Overfitting.
* **תוחלת רווח חיובית ויחס סיכון/סיכוי אופטימלי:** עם יעד רווח (TP) של 10.0% והגנת הפסד (SL) של 5.0%, האסטרטגיה פועלת עם יחס סיכון/סיכוי (R:R) מצוין של 1:2. בשילוב עם Win Rate יציב של ~43%, תוחלת הטרייד היא חיובית באופן מובהק ומייצרת אפקט ריבית דריבית מטורף (תשואה מצטברת של **+567.8%** בטווח המלא).

---

### 🔄 Live Scanner Data Pipeline Architecture
זרימת הנתונים של סורק המניות בזמן אמת מהקצה לקצה (End-to-End Data Flow):

```text
Frontend UI (Dropdown/Inputs) -> app.py (Subprocess CLI Args) -> scanner.py (sys.argv) -> scan_universe_generator(strategy_mode)
```

---

## 🩺 Smart Diagnostic System for Zero-Setup Scans

When a weekly scan returns **0 setups**, the system now provides intelligent diagnostics to help you understand **why** no stocks qualified and what action to take.

### What Gets Tracked

The scanner monitors every stage of the filtering process:
- **Download Failures**: API rate limiting or connection issues
- **RSI Crosses**: How many stocks had RSI cross the threshold (30 for Mean Reversion, 55 for Momentum)
- **Price Position**: How many stocks were in the correct position relative to SMA (below SMA 20 for Mean Reversion, above SMA 50 for Momentum)
- **Both Conditions Met**: Stocks that passed both RSI and price filters
- **Earnings Filter**: Stocks that qualified but were filtered due to upcoming earnings

### Example Diagnostic Messages

#### Scenario 1: Bullish Market + Mean Reversion
```
📊 Scan Statistics:
- Analyzed: 97/100 stocks (3 download failures)
- RSI crossed 30: 2 stocks
- Price below SMA 20: 18 stocks
- Both conditions met: 0 stocks ❌

💡 Diagnosis: No stocks below SMA 20. Market is very strong.
📌 Recommendation: Stay in cash or switch to Momentum strategy (RSI=55).
```

#### Scenario 2: Earnings Filter Blocking Setups
```
📊 Scan Statistics:
- Analyzed: 98/100 stocks
- RSI crossed 55: 12 stocks
- Price above SMA 50: 45 stocks
- Both conditions met: 3 stocks ✅
- Filtered by earnings: 3 stocks ❌

💡 Diagnosis: Strong candidates exist but filtered by upcoming earnings.
📌 Recommendation: Wait 1 week for earnings to pass, then re-scan.
```

#### Scenario 3: Sideways Market
```
📊 Scan Statistics:
- Analyzed: 96/100 stocks
- RSI crossed 30: 0 stocks
- Price below SMA 20: 8 stocks
- Both conditions met: 0 stocks ❌

💡 Diagnosis: No RSI crosses detected. Market is in neutral/sideways mode.
📌 Recommendation: Wait for more volatility or adjust RSI threshold.
```

### Where It Works

This diagnostic system is active in:
- ✅ **Dry Run Mode** - Test scans without affecting your portfolio
- ✅ **Live Weekly Scans** - Real scans that update your trades
- ✅ **Both Strategies** - Mean Reversion (RSI=30) and Momentum (RSI=55)

---

## 🧪 Parameterized DRY RUN Mode

The **DRY RUN** feature allows you to test the scanning algorithm on live market data without saving any results to the database. This is perfect for:
- Testing different strategy configurations before committing to a live scan
- Validating parameter changes (RSI thresholds, Stop Loss, Take Profit)
- Comparing Mean Reversion vs. Momentum strategies in real-time

### How to Use DRY RUN

1. **Access the Feature**: Click the **"Dry Run Scanner"** button (green border) in the main dashboard navigation bar
2. **Configure Strategy Parameters**:
   - **Strategy Mode**: Choose between `Mean Reversion` or `Momentum`
   - **Target RSI**: Set the RSI threshold for entry signals (e.g., 30 for oversold, 55 for momentum)
   - **Stop Loss %**: Define your maximum acceptable loss per trade
   - **Take Profit %**: Set your profit target percentage
3. **Run the Simulation**: Click **"Start Dry Run"** to execute the scan
4. **Monitor Progress**: Watch real-time logs as the scanner processes ~100 tickers
5. **Review Results**: View the top setups found, including price, RSI, risk/reward ratio, and stop loss levels

### Strategy Parameter Presets

The UI automatically adjusts parameters when you switch strategy modes:

| Strategy Mode | Target RSI | Stop Loss | Take Profit | Use Case |
|--------------|-----------|-----------|-------------|----------|
| **Momentum** 🏆 | 55 | 5.0% | 10.0% | **Production Strategy** - Riding established uptrends with confirmation |

**Note:** The Momentum strategy (RSI=55, SL=5%, TP=10%) is the **sole production configuration**. Mean Reversion has been completely removed from the codebase based on backtesting results showing the Momentum strategy achieved +567.8% cumulative return over the full period (2010-2026) with consistent Win Rate of ~43% across both market regimes, while Mean Reversion failed with -30.93% in volatile markets.

### Backend Architecture

**Endpoint**: `/api/dry-run-stream`

**Method**: GET with Server-Sent Events (SSE)

**Query Parameters**:
- `strategy_mode`: `mean_reversion` or `momentum`
- `target_rsi`: Float (e.g., 30.0, 55.0)
- `stop_loss_pct`: Float (e.g., 3.0, 5.0)
- `take_profit_pct`: Float (e.g., 6.0, 10.0)

**Response Format**: Streaming JSON events with progress updates, log messages, and final results

**Key Difference from Live Scan**: The dry run uses the same `scan_universe_generator()` function but does NOT:
- Save trades to `trades_db.json`
- Update portfolio metadata
- Trigger tracker updates
- Execute any database writes

This ensures you can safely experiment with different configurations without affecting your live trading system.

---

## 🔧 Under the Hood - Production Strategy Dashboard

The **"Under the Hood"** page provides a comprehensive technical view of the production Momentum strategy architecture and historical performance metrics.

### Access the Dashboard

Navigate to: [http://127.0.0.1:5000/under-the-hood](http://127.0.0.1:5000/under-the-hood)

Or click the **"Under the Hood"** button (blue border) in the main dashboard navigation bar.

### What You'll Find

#### 1. **Production Strategy Status**
Visual confirmation of the production Momentum Scenario 3 configuration:
- **Strategy Mode**: MOMENTUM 🏆
- **Target RSI**: 55
- **Risk Management**: 5% SL / 10% TP

#### 2. **Momentum Strategy Details**
Complete specification of the production strategy:

**Momentum Strategy (Production):**
- Target RSI: > 55
- Price Position: Above SMA 50
- Stop Loss: -5.0%
- Take Profit: +10.0%
- Ranking Logic: `Current_Close / 52_Week_High`
- Entry Condition: RSI crosses above 55 from below, while price is above SMA 50

#### 3. **Data Flow Architecture Diagram**
A 5-step visual flow showing how parameters travel through the production pipeline:
1. **Frontend UI Layer** → User configures momentum parameters (RSI=55, SL=5%, TP=10%)
2. **Flask Route Handler (app.py)** → Strategy mode is hardcoded to "momentum"
3. **Scanner Generator (scanner.py)** → Executes momentum-specific logic
4. **Trading Logic (trading_logic.py)** → Processes results with momentum rules
5. **Database Persistence (data_manager.py)** → Saves to DB (LIVE only)

#### 4. **Historical Performance Table**
Detailed performance metrics across two market eras:
- **Chaos Era (2021-2026)**: +100.57% return, 43.1% win rate
- **Calm Era (2010-2020)**: +232.78% return, 43.6% win rate
- **Full Horizon (2010-2026)**: +567.8% total return, ~43.3% stable win rate

### Production Architecture

**Single Strategy Focus:**
- The system now exclusively uses the Momentum Scenario 3 strategy
- All routes, UI elements, and backend logic are optimized for momentum trading
- Mean Reversion strategy has been completely removed from the codebase

**Parameter Consistency:**
- Default values are set to the winning configuration (RSI=55, SL=5%, TP=10%)
- Users can still adjust parameters for testing via DRY RUN mode
- Live scans use the production-tested configuration

**Visual Documentation:**
The "Under the Hood" page serves as living documentation, showcasing the production strategy's technical implementation and proven historical performance.

---

## 📊 Trade Analytics Dashboard

The **Trade Analytics** page provides comprehensive performance analysis and visualization of your trading history.

### Access the Dashboard

Navigate to: [http://127.0.0.1:5000/trade-analytics](http://127.0.0.1:5000/trade-analytics)

Or click the **"📊 Trade Analytics"** button (gold border) in the main dashboard navigation bar.

### Features

#### 1. **Portfolio State Tracking**
The system now accurately tracks your complete portfolio state:
- **Current Equity**: Total portfolio value (deposits + realized P&L + unrealized P&L)
- **Cash Available**: Free cash for new positions
- **Invested Capital**: Capital currently deployed in active positions
- **Realized P&L**: Profit/loss from closed trades
- **Unrealized P&L**: Profit/loss from active positions
- **Next Position Size**: Calculated position size for the next trade (Cash Available / 3)

#### 2. **Performance Metrics**
Eight key metrics displayed at the top:
- **Total Trades**: Number of trades executed
- **Win Rate**: Percentage of profitable trades
- **Avg Duration**: Average trade duration in days
- **Profit Factor**: Ratio of total wins to total losses
- **Simple Return**: Cumulative return treating all trades equally
- **MWR Return**: Money-Weighted Return accounting for position sizes
- **SPY Return**: S&P 500 benchmark performance
- **Alpha**: Strategy outperformance vs. SPY

#### 3. **Interactive Charts**

**Main Chart - Cumulative Returns Over Time:**
- 🔵 **Simple Return**: Equal-weighted cumulative return
- 🟢 **MWR Return**: Capital-weighted cumulative return
- 🟡 **SPY Benchmark**: S&P 500 comparison (dashed line)
- Hover over points to see detailed information
- One point per day (aggregates multiple trades on same date)

**Secondary Charts:**
- **Duration vs P&L**: Scatter plot showing relationship between trade duration and profitability
- **Win/Loss Distribution**: Histogram of P&L distribution across all trades

#### 4. **Advanced Filters**
Filter your analysis by:
- **Status**: Closed trades, Active positions, or both
- **Performance**: All trades, Winners only, or Losers only
- **Date Range**: Custom start and end dates

### Capital Management System

The analytics system includes a sophisticated capital management module (`analytics_generator.py`) that:

1. **Tracks Historical Performance**: Uses all trades from `trades_db.json` to calculate current portfolio state
2. **Calculates Available Cash**: `Cash = Deposits + Realized P&L - Invested Capital`
3. **Determines Position Sizing**: `Position Size = Cash Available / Max Positions (3)`
4. **Prevents Over-Leverage**: Scanner won't open new positions if cash is unavailable

**Example:**
- Deposits: $4,500
- Realized P&L: -$300 (from closed trades)
- Unrealized P&L: +$200 (from active positions)
- **Current Equity**: $4,400
- **Cash Available**: $4,200 (if no active positions)
- **Next Position Size**: $1,400 ($4,200 / 3)

### Data Aggregation

The system intelligently aggregates trades by exit date:
- Multiple trades closed on the same day are combined into a single data point
- Cumulative returns are calculated correctly across the entire trading history
- This prevents visual clutter and provides clearer trend analysis

### Backend Architecture

**New Files:**
- `analytics_generator.py`: Core analytics calculations and portfolio state management
- `trade_analytics.html`: Frontend visualization with Plotly.js charts

**API Endpoints:**
- `/trade-analytics`: Serves the analytics page
- `/api/trade-analytics`: Returns JSON data for charts and metrics

**Integration:**
- Dashboard now shows 4 metric cards with real-time portfolio state
- Scanner uses `calculate_position_size()` to determine trade sizes
- All calculations use historical trade data for accuracy
