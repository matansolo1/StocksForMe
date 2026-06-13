import json
import os
import shutil
from datetime import datetime

DB_FILE = "trades_db.json"

def load_db():
    """
    Loads the entire database (metadata + trades).
    """
    if not os.path.exists(DB_FILE):
        # Auto-create trades_db.json if missing to prevent crashes on first run
        default_db = {"portfolio_metadata": {"total_deposits": 0.0, "last_updated": ""}, "trades": []}
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_db, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error creating default DB: {e}")
        return default_db
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Migration logic if it's still just a list
            if isinstance(data, list):
                return {
                    "portfolio_metadata": {"total_deposits": len(data) * 1000.0 if data else 0.0, "last_updated": ""},
                    "trades": data
                }
            return data
    except Exception as e:
        print(f"Error loading DB: {e}")
        return {"portfolio_metadata": {"total_deposits": 0.0, "last_updated": ""}, "trades": []}

def save_db(data):
    """
    Saves the entire database.
    """
    try:
        data["portfolio_metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving DB: {e}")

def load_trades():
    return load_db()["trades"]

def save_trades(trades):
    db = load_db()
    db["trades"] = trades
    save_db(db)

def get_metadata():
    return load_db()["portfolio_metadata"]

def update_metadata(total_deposits=None, **kwargs):
    """
    Updates portfolio metadata with any provided fields.
    """
    db = load_db()
    if total_deposits is not None:
        db["portfolio_metadata"]["total_deposits"] = total_deposits
    
    # Update any additional fields passed as kwargs
    for key, value in kwargs.items():
        db["portfolio_metadata"][key] = value
    
    save_db(db)

def update_portfolio_state(trades):
    """
    Updates the portfolio state in metadata based on current trades.
    Uses analytics_generator to calculate state.
    """
    import analytics_generator
    
    db = load_db()
    metadata = db["portfolio_metadata"]
    total_deposits = metadata.get("total_deposits", 0)
    
    # Calculate portfolio state
    portfolio_state = analytics_generator.calculate_portfolio_state(trades, total_deposits)
    
    # Update metadata with portfolio state
    metadata["current_equity"] = portfolio_state["current_equity"]
    metadata["cash_available"] = portfolio_state["cash_available"]
    metadata["invested_capital"] = portfolio_state["invested_capital"]
    metadata["realized_pnl"] = portfolio_state["realized_pnl"]
    metadata["unrealized_pnl"] = portfolio_state["unrealized_pnl"]
    
    save_db(db)
    return portfolio_state

def archive_db(archive_name="demo_archive.json"):
    if os.path.exists(DB_FILE):
        try:
            shutil.copy2(DB_FILE, archive_name)
            return True
        except Exception as e:
            print(f"Error archiving DB: {e}")
    return False

def reset_db():
    save_db({"portfolio_metadata": {"total_deposits": 0.0, "last_updated": ""}, "trades": []})
