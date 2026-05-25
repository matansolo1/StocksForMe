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
        *   `/add-trade` (POST): Adds a new manual trade to the tracker.
        *   `/close-trade` (POST): Closes an active trade.
        *   `/delete-trade` (POST): Deletes a trade from history.
        *   `/update-notes` (POST): Updates notes for an active trade.
*   **`scanner.py`**:
    *   Contains the core scanning engine.
    *   `scan_universe_generator()`: A generator function that iterates through the stock universe, fetches data, calculates technical indicators, checks for upcoming earnings, and yields real-time progress and status messages.
    *   `scan_universe()`: A backward-compatible wrapper that consumes the generator and prints messages to the console.
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
    *   Generates the static HTML dashboard (`tracker_dashboard.html`) with Tailwind CSS, embedding active trades, trade history, and scanned setups.

---

## 2. SSE & Progress Bar Implementation

To prevent the UI from freezing during the ~100 ticker scan (which takes 30-60 seconds), we implemented a real-time progress bar and live status log using **Server-Sent Events (SSE)**.

### Backend Streaming (`app.py` & `scanner.py`):
1.  The frontend initiates a connection to `/api/scan-stream` using the JavaScript `EventSource` API.
2.  The Flask route returns a streaming response: `Response(generate(), mimetype='text/event-stream')`.
3.  Inside the generator, `scanner.scan_universe_generator()` is called.
4.  As the scanner loops through tickers, it calculates completion percentage:
    $$\text{Progress} = \frac{\text{current\_index} + 1}{\text{total\_tickers}} \times 100$$
5.  The generator yields JSON payloads formatted as SSE data blocks:
    ```text
    data: {"progress": 45.2, "message": "Analyzing AAPL: RSI pullback detected", "status": "success"}
    ```
6.  **Edge Cases Handled**:
    *   **Earnings Skip**: If a ticker has earnings within 2 days, it is skipped, and a warning is streamed: `{"progress": X, "message": "Skipped AAPL: Upcoming earnings (2026-05-27)", "status": "warning"}`.
    *   **Download Failures / Rate Limits**: If `yfinance` fails or throws an exception, it is caught, and a warning is streamed: `{"progress": X, "message": "Failed to download MSFT: Rate Limited", "status": "error"}`.
7.  At the end of the stream, the backend processes portfolio swaps, updates active trades, regenerates the dashboard HTML, and yields a final completion message:
    ```text
    data: {"progress": 100, "message": "Scan complete! Dashboard updated.", "status": "complete"}
    ```

### Frontend Hook (`app.py` -> `SCANNING_HTML`):
*   A dedicated, beautiful scanning page is rendered when the user clicks "Run Scan".
*   **Progress Bar**: A Tailwind CSS progress bar (`w-0 transition-all duration-300`) that dynamically updates its width and percentage text.
*   **Live Activity Log**: A terminal-style box (`bg-slate-950 text-slate-200 font-mono text-xs p-4 rounded-lg h-80 overflow-y-auto border border-slate-800`) that appends every incoming message in real-time.
*   **Color-Coded Logs**:
    *   `success` (green): Setups found or successful scans.
    *   `warning` (yellow): Skipped tickers (earnings).
    *   `error` (red): Failed downloads or rate limits.
    *   `info` (blue/gray): General progress updates.
*   **Auto-Scroll**: The terminal automatically scrolls to the bottom as new logs arrive.
*   **Completion Action**: Once the stream receives the `complete` status, the "View Dashboard" button is enabled, allowing the user to return to the updated dashboard.

---

## 3. Tech Stack Details

*   **Language**: Python 3.13+ compatible.
*   **Web Framework**: Flask (v2.0+) with native streaming support.
*   **Data Fetching**: `yfinance` (v0.2.52) for historical stock data and earnings dates.
*   **Data Manipulation**: `pandas` (v1.3+) and `numpy` (v1.20+) for technical indicator calculations.
*   **Styling**: Tailwind CSS (via CDN) for a modern, responsive, dark-themed dashboard.
*   **Data Storage**: Local JSON files (`demo_archive.json`, etc.) for zero-dependency persistence.

---

## 4. Next Steps / Roadmap

*   **Multi-threading / Async Scanning**: Speed up the scanning process by fetching ticker data in parallel using thread pools, while maintaining ordered SSE progress updates.
*   **Interactive Charting**: Integrate lightweight charting libraries (e.g., TradingView Lightweight Charts or Chart.js) directly into the stock setup cards.
*   **Custom Scan Filters**: Allow users to adjust RSI thresholds, EMA periods, and volume filters directly from the UI.
*   **Webhook Notifications**: Add Discord or Telegram webhook alerts when high-probability setups are found.
