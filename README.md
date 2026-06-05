# Stocks For Me - Quantitative Trading System

מערכת מסחר כמותי מבוססת RSI וחזרה לממוצע (Mean Reversion) עבור מניות נאסד"ק (Nasdaq).

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

#### 1. כישלון אסטרטגיית ה-Mean Reversion (RSI < 30) בשוק רגוע
* **תפיסת סכינים נופלות (Catching Falling Knives):** אסטרטגיית חזרה לממוצע קלאסית עם RSI נמוך מ-30 קונה מניות בתיקון עמוק. בשוק רגוע, מניות חלשות שחורגות למכירת יתר קיצונית נוטות לעיתים קרובות להמשיך לדמם או לבלות זמן ממושך בתחתית, במקום להתאושש במהירות.
* **ביצועי חסר מול ה-Benchmark:** בשוק שורי וליניארי (כמו בעשור 2010-2020), החזקת מניות מומנטום חזקות מניבה תשואת יתר משמעותית. אסטרטגיית Mean Reversion הציגה ביצועי חסר קיצוניים אל מול המדד בשל חוסר יכולת לרכוב על מגמות עולות חזקות ויציאה מהירה מדי בגלל יעדי TP קרובים.

#### 2. מדוע תרחיש 3 של המומנטום (RSI = 55) הוא המנצח הבלתי מעורער?
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
| **Mean Reversion** | 30 | 3.0% | 6.0% | Catching oversold bounces in strong stocks |
| **Momentum** ⭐ | 55 | 5.0% | 10.0% | **Winning Strategy** - Riding established uptrends with confirmation |

**Note:** The Momentum strategy (RSI=55, SL=5%, TP=10%) is the **winning configuration** based on backtesting results showing +567.8% cumulative return over the full period (2010-2026) with consistent Win Rate of ~43% across both market regimes.

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

## 🔧 Under the Hood - Strategy Architecture Dashboard

The **"Under the Hood"** page provides a comprehensive technical view of the dual-strategy architecture, showcasing complete isolation between Mean Reversion and Momentum strategies.

### Access the Dashboard

Navigate to: [http://127.0.0.1:5000/under-the-hood](http://127.0.0.1:5000/under-the-hood)

Or click the **"Under the Hood"** button (blue border) in the main dashboard navigation bar.

### What You'll Find

#### 1. **Backend Isolation Verification**
Visual confirmation that both strategies operate on completely separate execution tracks:
- **Strategy Decoupling**: ISOLATED ✅
- **Parameter Contamination**: NONE ✅
- **Execution Tracks**: INDEPENDENT ✅

The `scan_universe_generator()` function uses conditional branching (`if strategy_mode == "mean_reversion"` vs `if strategy_mode == "momentum"`) to ensure zero cross-contamination between strategies.

#### 2. **Side-by-Side Strategy Blocks**
Two independent visual blocks displaying:

**Mean Reversion Strategy:**
- Target RSI: < 30
- Price Position: Below SMA 20
- Stop Loss: -3.0%
- Take Profit: +6.0%
- Ranking Logic: `(SMA_20 - Close) / Volatility`
- Entry Condition: RSI crosses above 30 from below, while price is below SMA 20

**Momentum Strategy:**
- Target RSI: > 55
- Price Position: Above SMA 50
- Stop Loss: -5.0%
- Take Profit: +10.0%
- Ranking Logic: `Current_Close / 52_Week_High`
- Entry Condition: RSI crosses above 55 from below, while price is above SMA 50

#### 3. **Data Flow Architecture Diagram**
A 5-step visual flow showing how parameters travel through the system:
1. **Frontend UI Layer** → User selects strategy and parameters
2. **Flask Route Handler (app.py)** → Receives isolated parameters
3. **Scanner Generator (scanner.py)** → Executes ONLY selected strategy logic
4. **Trading Logic (trading_logic.py)** → Processes results independently
5. **Database Persistence (data_manager.py)** → Saves to DB (LIVE only)

#### 4. **Strategy Comparison Matrix**
A detailed table comparing both strategies across 8 dimensions:
- Market Condition
- RSI Signal
- Price Position
- Ranking Logic
- Risk/Reward Ratio
- Holding Period
- Best Market Regime
- Historical Performance (2010-2026)

### Architecture Guarantees

**No Global State Pollution:**
- Each scan (DRY RUN or LIVE) passes its own `strategy_mode`, `target_rsi`, `stop_loss_pct`, and `take_profit_pct` parameters explicitly through the entire pipeline
- No shared variables or global state between strategies
- Parameters are function arguments, not class attributes or module-level variables

**Complete Execution Isolation:**
- Mean Reversion and Momentum filters never execute simultaneously
- Each strategy has its own conditional branch in `scanner.py`
- Ranking mechanisms are completely different and never mixed

**Visual Verification:**
The "Under the Hood" page serves as a living documentation and verification tool, allowing you to visually confirm that the backend architecture maintains strict separation between the two trading strategies.
