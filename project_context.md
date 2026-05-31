# Project Context: StocksForMe Stock Scanner

This document serves as the single "Source of Truth" for the StocksForMe Stock Scanner project, capturing the current architecture, implementation details, tech stack, and future roadmap.

---

## 1. Current Project Architecture

The project is a lightweight, local stock scanner and portfolio tracker built with Python Flask and Tailwind CSS. It scans a universe of ~100 tickers to identify high-probability swing trading setups based on technical indicators (EMA, RSI, MACD, Volume, and ATR) and manages active trades.

### File Breakdown & Responsibilities:

*   **`app.py`**:
    *   The main Flask application entry point.
    *   Defines web routes:
        *   `/` (Dashboard): Renders the main dashboard UI.
        *   `/execute-scan` (GET): Renders the real-time scanning page with the progress bar and live activity log.
        *   `/api/scan-stream` (GET): Server-Sent Events (SSE) stream route that runs the scanner generator, streams real-time progress/logs, processes swaps, updates portfolio status, and regenerates the dashboard.
        *   `/api/backtest` (POST): Runs the 5-year week-by-week backtester with the customized initial capital and returns statistics + equity curve JSON.
        *   `/add-trade` (POST): Adds a new manual trade to the tracker.
        *   `/close-trade` (POST): Closes an active trade.
        *   `/delete-trade` (POST): Deletes a trade from history.
        *   `/update-notes` (POST): Updates notes for an active trade.
*   **`scanner.py`**:
    *   Contains the core scanning engine.
    *   `scan_universe_generator()`: A generator function that iterates through the stock universe, fetches data, calculates technical indicators, checks for upcoming earnings, and yields real-time progress and status messages. Includes a global market trend filter of SPY above its SMA 200 and checks for optimized RSI < 35 criteria.
    *   `scan_universe()`: A backward-compatible wrapper that consumes the generator and prints messages to the console.
*   **`backtester.py`**:
    *   The core backtesting engine for week-by-week simulation over the last 5 years.
    *   Implements single-batch download for the entire ~100 tickers + SPY for ultimate API token efficiency.
    *   Caches downloaded data in `backtest_data_cache.pkl` to make subsequent runs instantaneous (taking <1 second) with zero API calls.
    *   Simulates realistic daily/intraday Stop Loss (3x Volatility, 1.5x wider to reduce noise) and Take Profit (SMA 20) hit times day-by-day during each week, and falls back to Friday close if neither is hit.
    *   Incorporates realistic transaction fees (0.05% per trade side) and compounds equity.
*   **`stock_api.py`**:
    *   Handles interaction with the `yfinance` API.
    *   Fetches historical price data, ticker info, and upcoming earnings dates.
    *   Implements caching to minimize API rate limits and speed up scans.
*   **`trading_logic.py`**:
    *   Defines the technical criteria for identifying trade setups (e.g., EMA alignment, RSI pullbacks, MACD crossovers, volume expansion).
    *   Calculates position sizing, stop-loss, and take-profit levels based on ATR (Average True Range).
*   **`tracker.py`**:
    *   Manages active trades, portfolio tracking, and trade history.
    *   Handles trade entry, exit, and performance metrics.
*   **`data_manager.py`**:
    *   Handles JSON-based data persistence for active trades, trade history, and cached scan results.
*   **`ui_generator.py`**:
    *   Generates the static HTML dashboard (`tracker_dashboard.html`) with Tailwind CSS, embedding active trades, trade history, scanned setups, as well as the new interactive **Historical Backtesting** dashboard using Chart.js.

---

## 2. Updated Strategy Rules (Optimized)

To enhance the robustness of the Mean Reversion strategy and minimize drawdowns, the algorithm implements the following optimized guidelines:

1.  **Global Trend Filter**: Trades are only allowed to be scanned and entered if the S&P 500 ETF is bullish:
    $$\text{SPY Close} > \text{SPY SMA}_{200}$$
2.  **Oversold Setup Criteria**: The RSI 14-period limit is tightened to the extreme to select only the safest trades:
    $$\text{RSI}_{14} < 30 \quad \text{and} \quad \text{Price} < \text{SMA}_{20}$$
3.  **Risk Management (Stop Loss)**: Tight fixed 3% Stop Loss for capital protection:
    $$\text{SL} = \text{Price} \times 0.97$$
4.  **Profit Target**: Fixed 6% Take Profit (guaranteeing a strict, mathematically built 1:2 Risk/Reward ratio):
    $$\text{TP} = \text{Price} \times 1.06$$
5.  **Multi-week Holding**: Active trades are held across weeks until either TP or SL is triggered, rather than forced closing on Fridays.

---

## 3. SSE & Progress Bar Implementation

To prevent the UI from freezing during the ~100 ticker scan (which takes 30-60 seconds), we implemented a real-time progress bar and live status log using **Server-Sent Events (SSE)**.

---

## 4. Next Steps / Roadmap

*   **Multi-threading / Async Scanning**: Speed up the scanning process by fetching ticker data in parallel using thread pools, while maintaining ordered SSE progress updates.
*   **Custom Scan Filters**: Allow users to adjust RSI thresholds, EMA periods, and volume filters directly from the UI.
*   **Webhook Notifications**: Add Discord or Telegram webhook alerts when high-probability setups are found.
