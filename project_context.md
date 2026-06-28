# Project Context: StocksForMe Stock Scanner

This document serves as the single "Source of Truth" for the StocksForMe Stock Scanner project, capturing the current architecture, implementation details, tech stack, and future roadmap.

---

## 1. Current Project Architecture

The project is a lightweight, local stock scanner and portfolio tracker built with Python Flask and Tailwind CSS. It scans a universe of ~100 tickers to identify high-probability swing trading setups based on technical indicators (EMA, RSI, MACD, Volume, and ATR) and manages active trades.

### Project Structure:

```
stocks_for_me/
├── 📁 archive/              # Old files and archives (demo_archive.json, test files, reports)
├── 📁 cache/                # Cache files (*.pkl, backtest_5min_cache/)
├── 📁 output/               # Dynamically generated HTML files (dashboards)
├── 📁 media/                # Demo videos and screenshots
├── 📁 data/                 # Production data (trades_db.json)
├── 📄 app.py                # Flask server - main entry point
├── 📄 scanner.py            # Weekly scanning engine
├── 📄 backtester.py         # Backtesting engine
├── 📄 trading_logic.py      # Trading logic and decisions
├── 📄 tracker.py            # Portfolio tracking
├── 📄 ui_generator.py       # HTML interface generation
├── 📄 analytics_generator.py # Performance calculations
├── 📄 data_manager.py       # Data management
├── 📄 stock_api.py          # Yahoo Finance interface
└── 📄 finance_utils.py      # Financial utilities
```

**Note:** The project structure was reorganized to separate concerns:
- **Code files** remain in the root for easy access
- **Generated files** (cache, output) are in dedicated directories
- **Archive files** are separated from active development
- **Media files** are isolated to prevent clutter

### File Breakdown & Responsibilities:

* **`app.py`**:
    * The main Flask application entry point.
    * Defines web routes:
        * `/` (Dashboard): Renders the main dashboard UI.
        * `/execute-scan` (GET): Renders the real-time scanning page with the progress bar and live activity log.
        * `/api/scan-stream` (GET): Server-Sent Events (SSE) stream route that runs the scanner generator, streams real-time progress/logs, processes swaps, updates portfolio status, and regenerates the dashboard. **Now injects frontend dynamic parameters directly into the CLI scanner process.**
        * `/api/backtest` (POST): Runs the week-by-week backtester with the customized initial capital and returns statistics + equity curve JSON.
* **`scanner.py`**:
    * Contains the core scanning engine.
    * `scan_universe_generator()`: A generator function that iterates through the stock universe. **Production mode is fixed to `momentum` strategy only.** Includes a global market trend filter of SPY above its SMA 200.
    * `scan_universe()`: Dynamically parameterized wrapper that consumes the generator and passes parameters.
    * `main()`: Upgraded to utilize `sys.argv` to capture dynamic parameters passed directly from the Flask UI subprocess.
* **`backtester.py`**:
    * The core backtesting engine for week-by-week simulation over different market regimes.
    * Caches downloaded data in `backtest_data_cache.pkl` to make subsequent runs instantaneous.
* **`trading_logic.py`**:
    * Defines the technical criteria for identifying trade setups (Momentum Breakouts only - production strategy).
* **`tracker.py`** & **`data_manager.py`**: Handles JSON persistence, active trades, history, and automated weekly trade logs.
* **`ui_generator.py`**:
    * Generates the HTML dashboard with Tailwind CSS and Chart.js graphs. Includes the persistent **"📊 Strategy Cheat Sheet & Robustness Matrix"** to lock in proven R&D parameters.
* **`analytics_generator.py`**:
    * Core analytics and portfolio state management module.
    * `calculate_portfolio_state()`: Calculates complete portfolio state (equity, cash, realized/unrealized P&L).
    * `calculate_position_size()`: Determines position size based on available cash (Conservative approach: Cash / 3).
    * `calculate_simple_cumulative_return()`: Calculates equal-weighted cumulative returns, aggregated by exit date.
    * `calculate_mwr_cumulative_return()`: Calculates Money-Weighted Return accounting for position sizes.
    * `prepare_analytics_data()`: Prepares all data for the Trade Analytics dashboard.
* **`trade_analytics.html`**:
    * Interactive analytics dashboard with Plotly.js charts.
    * Displays 8 key performance metrics, cumulative return charts, and advanced filtering options.

---

## 2. Production Strategy (Momentum Scenario 3 - The Winner)

1.  **Global Trend Filter**: Trades are only allowed to be scanned and entered if the S&P 500 ETF is bullish:
    $$\text{SPY Close} > \text{SPY SMA}_{200}$$

2.  **Momentum Breakout Mode (Scenario 3 - Production Default)**:
    * **Trigger**: RSI 14 crosses ABOVE 55 while price is above SMA 50.
        $$\text{RSI}_{\text{prev}} < 55 \quad \text{and} \quad \text{RSI}_{\text{current}} \ge 55 \quad \text{and} \quad \text{Price} > \text{SMA}_{50}$$
    * **Risk Management**: Fixed 5.0% Stop Loss.
        $$\text{SL} = \text{Price} \times 0.95$$
    * **Profit Target**: Fixed 10.0% Take Profit (Strict 1:2 Risk/Reward Ratio).
        $$\text{TP} = \text{Price} \times 1.10$$
    * **Performance**: Achieved +100.57% in Chaos Era (2021-2026) and +232.78% in Calm Era (2010-2020) with a stable 43% win rate across both periods.

**Note**: The Mean Reversion strategy has been **completely removed from the codebase** (deprecated in production) due to poor performance in volatile markets (-30.93% in recent period). All routes, UI elements, and backend logic now exclusively use the Momentum Scenario 3 strategy.

---

## 3. SSE & Progress Bar Implementation

To prevent the UI from freezing during the ~100 ticker scan, a real-time progress bar and live status log are fully operational using **Server-Sent Events (SSE)**.

---

## 4. 🔬 Quantitative Research & Robustness Lab Findings

During intensive backtesting across two distinct market eras—the **Calm Era (2010–2020)** and the **Chaos Era (2021–2026)**—we uncovered key insights:

* **The Mean Reversion Failure**: Relying on a raw snapshot of `RSI < 30` caused the system to buy during free-falls ("catching falling knives"), netting a disastrous `-30.93%` return in the Chaos Era. **This strategy has been completely removed from production.**
* **The Momentum Breakthrough (Scenario 3) - PRODUCTION WINNER**: Lowering the momentum entry bar to `RSI = 55` captured strong trends right as they formed (above SMA 50). Coupled with tight risk management (`SL = 5%`, `TP = 10%`), it proved highly robust, maintaining a perfectly stable **~43.3% Win Rate** across *both* market regimes, generating **`+100.57%`** in the recent volatile years and over **`+567%`** across the full 16-year horizon. **This is now the sole production strategy.**

---

## 5. Trade Analytics & Capital Management System

### Portfolio State Tracking
The system now includes comprehensive portfolio state management through `analytics_generator.py`:

* **Current Equity**: `Deposits + Realized P&L + Unrealized P&L`
* **Cash Available**: `Deposits + Realized P&L - Invested Capital`
* **Position Sizing**: `Cash Available / Max Positions (3)`

### Capital Management Logic
The scanner now uses intelligent capital management:
1. Before opening new positions, calculates available cash from historical trades
2. If cash is unavailable (all capital deployed), prevents new position entries
3. Position size dynamically adjusts based on realized P&L from closed trades

### Trade Analytics Dashboard (`/trade-analytics`)
Interactive analytics page featuring:

**Performance Metrics:**
- Total Trades, Win Rate, Avg Duration, Profit Factor
- Simple Return (equal-weighted), MWR Return (capital-weighted)
- SPY Benchmark comparison, Alpha calculation

**Interactive Charts (Plotly.js):**
- Cumulative Returns Over Time (Simple, MWR, SPY)
- Duration vs P&L scatter plot
- Win/Loss distribution histogram

**Advanced Filtering:**
- Status (Closed/Active)
- Performance (All/Winners/Losers)
- Date range selection

**Data Aggregation:**
- Trades are aggregated by exit date (one point per day)
- Prevents visual clutter from multiple trades on same date
- Cumulative returns calculated correctly across entire history

### Dashboard Integration
The main dashboard now displays 4 metric cards:
1. **Portfolio Equity**: Total value with return percentage
2. **Cash Available**: Free cash + next position size
3. **Realized P&L**: Profit/loss from closed trades
4. **Unrealized P&L**: Profit/loss from active positions

---

## 6. Recent Changes & System Alignment (June 2026)

### 6.1 Backtester Alignment & REVIEW Mechanism Removal

**Problem Identified:**
The live trading system had diverged from the backtester logic, introducing complexity that wasn't tested:
- **REVIEW mechanism**: Positions that didn't hit TP within 7 days were marked for potential swaps
- **Weekly swaps**: Scanner would close REVIEW positions and replace them with better setups
- **Manual clearance**: UI buttons to force-close positions

**Solution Implemented:**
Complete alignment with backtester logic:
1. **Removed REVIEW status** - Only ACTIVE and CLOSED statuses exist
2. **Removed `process_scanner_swaps()`** - No automatic position closures
3. **Removed manual intervention buttons** - No force-closing positions
4. **Scanner only fills empty slots** - Up to 3 positions maximum
5. **Positions close ONLY via SL/TP** - No time limits, no manual exits

**Files Modified:**
- `trading_logic.py`: Removed REVIEW logic and swap functions
- `scanner.py`: Removed swap calls, only calls `add_new_trades()`
- `app.py`: Removed `/manual-clearance` and `/reset-to-live` routes
- `ui_generator.py`: Updated UI text to reflect new rules
- `TRADING_RULES.md`: Created comprehensive documentation

### 6.2 Dry Run Scanner Enhancement

**Enhancement:**
Improved the Dry Run Scanner to provide better visibility and match live scanner behavior:

**Changes:**
1. **Active Position Awareness**: 
   - Backend now loads current trades and counts active positions
   - Calculates available slots: `3 - active_count`
   - Limits results to available slots only

2. **Enhanced UI Display**:
   - Initial message: "Active Positions: X/3 | Scanning for Y new setups..."
   - Table columns reordered: Ticker | Price | **Stop Loss** | **Take Profit** | RSI | Risk/Reward
   - Color coding: Stop Loss (red), Take Profit (green)

3. **Complete Alignment**:
   - Uses same `scan_universe_generator()` as live scanner
   - Shows exactly what would be added to portfolio
   - Results NOT saved to database (dry run only)

**Files Modified:**
- `app.py`: Enhanced `/api/dry-run-stream` with position counting
- `ui_generator.py`: Updated table headers and row generation

### 6.3 Trading Rules Documentation

**Created:** `TRADING_RULES.md`
- Complete strategy documentation (Momentum Scenario 3)
- Weekly workflow (Sunday scan → Monday entry)
- Position management rules
- Entry/exit criteria
- FAQ and troubleshooting


### 6.4 Position Sizing & Weight Calculation Fix (June 28, 2026)

**Problem Identified:**
The position sizing logic always divided available cash by 3 (max_positions), regardless of how many slots were actually empty. This caused suboptimal capital deployment.

**Example of the bug:**
- 1 active position → 2 empty slots
- Available cash: $3,354.78
- **Buggy behavior:** Each new trade got $3,354.78 / 3 = $1,118.26 (33.33% weight)
- **Correct behavior:** Each new trade should get $3,354.78 / 2 = $1,677.39 (50% weight)
- **Result:** ~$1,118 stayed as idle cash instead of being deployed

**Solution Implemented:**
1. **`analytics_generator.py`**: Modified `calculate_position_size()` to accept `active_positions` parameter and divide by `slots_available = max_positions - active_positions`
2. **`app.py`**: Calculate active position count and pass it to `calculate_position_size()`
3. **`trading_logic.py`**: Calculate `weight_per_trade = 100 / slots_available` dynamically instead of hardcoded 33.33
4. **`trades_db.json`**: Retroactive fix for FTNT and ASML trades from 2026-06-28 scan:
   - FTNT: quantity 7.389 → 11.083, weight 33.33 → 50.0
   - ASML: quantity 0.623 → 0.935, weight 33.33 → 50.0

**New behavior:**
- 3 empty slots → cash/3 (33.33% weight each) ✓
- 2 empty slots → cash/2 (50% weight each) ✓
- 1 empty slot → cash/1 (100% weight) ✓

**Files Modified:**
- `analytics_generator.py`
- `app.py`
- `trading_logic.py`
- `trades_db.json`
- `TRADING_RULES.md` (updated position sizing documentation)

---
## 7. Next Steps / Roadmap

* **Multi-threading / Async Scanning**: Speed up the scanning process by fetching ticker data in parallel using thread pools.
* **Trailing Stop Loss Integration**: Test a dynamic trailing stop for the momentum engine to capture runaway extensions past the 10% target.
* **Webhook Notifications**: Add Discord or Telegram webhook alerts when high-probability setups are found.
* **Enhanced Analytics**: Add drawdown analysis, Sharpe ratio, and trade correlation metrics.
