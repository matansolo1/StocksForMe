import data_manager
import trading_logic
import ui_generator
import os
import webbrowser
import sys

def main():
    """
    Main entry point for the Portfolio Tracker.
    Updates trades, generates dashboard, and optionally opens browser.
    """
    # 1. Handle Reset if requested
    if "--reset" in sys.argv:
        print("Archiving and resetting database...")
        data_manager.archive_db()
        data_manager.reset_db()
        print("Database reset successfully.")

    print("--- Portfolio Tracker Update ---")
    
    # 2. Load current trades
    trades = data_manager.load_trades()
    
    # 3. Update prices and statuses
    updated_trades = trading_logic.update_portfolio_status(trades)
    
    # 4. Save updated trades
    data_manager.save_trades(updated_trades)
    
    # 5. Generate UI Dashboard
    ui_generator.generate_dashboard_file(updated_trades)
    
    # 6. Open browser if not triggered by Flask
    if os.environ.get("FLASK_TRIGGERED") != "true":
        dashboard_path = os.path.abspath("tracker_dashboard.html")
        webbrowser.open(f"file://{dashboard_path}")

if __name__ == "__main__":
    main()
