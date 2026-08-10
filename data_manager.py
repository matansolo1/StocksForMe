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
        default_db = {
            "portfolio_metadata": {
                "total_deposits": 0.0,
                "commission_per_trade": 2.5,
                "last_updated": ""
            },
            "trades": []
        }
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
                    "portfolio_metadata": {
                        "total_deposits": len(data) * 1000.0 if data else 0.0,
                        "commission_per_trade": 2.5,
                        "last_updated": ""
                    },
                    "trades": data
                }
            # Add commission_per_trade if missing (migration)
            if "commission_per_trade" not in data.get("portfolio_metadata", {}):
                data["portfolio_metadata"]["commission_per_trade"] = 2.5
            return data
    except Exception as e:
        print(f"Error loading DB: {e}")
        return {
            "portfolio_metadata": {
                "total_deposits": 0.0,
                "commission_per_trade": 2.5,
                "last_updated": ""
            },
            "trades": []
        }

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
    commission_per_trade = metadata.get("commission_per_trade", 2.5)
    
    # Calculate portfolio state
    portfolio_state = analytics_generator.calculate_portfolio_state(trades, total_deposits, commission_per_trade)
    
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
    save_db({
        "portfolio_metadata": {
            "total_deposits": 0.0,
            "commission_per_trade": 2.5,
            "last_updated": ""
        },
        "trades": []
    })


def export_user_data():
    """
    Bundles ALL user-personal data (trades + deposits history) into a single
    dictionary, ready to be serialized to JSON and downloaded as a backup file.

    This is the single source of truth for "what belongs to the user" as
    opposed to code/strategy logic. Used by the /api/export-data route.
    """
    import currency_manager

    trades_db = load_db()
    deposits_history = currency_manager.load_deposits_history()

    return {
        "backup_format_version": 1,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trades_db": trades_db,
        "deposits_history": deposits_history
    }


BACKUPS_DIR = "backups"
MAX_PRE_RESTORE_BACKUPS = 3  # how many pre_restore snapshots to keep per file


def _files_are_identical(path_a, path_b):
    """Returns True if both files exist and have identical content."""
    try:
        if not (os.path.exists(path_a) and os.path.exists(path_b)):
            return False
        with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
            return fa.read() == fb.read()
    except Exception:
        return False


def _prune_old_backups(prefix, keep=MAX_PRE_RESTORE_BACKUPS):
    """
    Keeps only the most recent `keep` backup files matching the given
    prefix (e.g. "trades_db.pre_restore_") inside BACKUPS_DIR, deleting
    older ones.
    """
    try:
        if not os.path.isdir(BACKUPS_DIR):
            return
        matching = [
            f for f in os.listdir(BACKUPS_DIR)
            if f.startswith(prefix)
        ]
        matching.sort(reverse=True)  # timestamps in filename sort chronologically
        for old_file in matching[keep:]:
            try:
                os.remove(os.path.join(BACKUPS_DIR, old_file))
            except Exception as e:
                print(f"Warning: could not remove old backup {old_file}: {e}")
    except Exception as e:
        print(f"Warning: could not prune old backups for {prefix}: {e}")


def _create_pre_restore_backup(source_file, prefix):
    """
    Copies `source_file` into BACKUPS_DIR with a timestamped `prefix` name,
    skipping the copy if it would be identical to the most recent existing
    backup with the same prefix. Also prunes old backups beyond the retention
    limit. Returns the path of the created backup, or None if skipped.
    """
    if not os.path.exists(source_file):
        return None

    os.makedirs(BACKUPS_DIR, exist_ok=True)

    existing = sorted(
        [f for f in os.listdir(BACKUPS_DIR) if f.startswith(prefix)],
        reverse=True
    )
    if existing:
        latest_backup_path = os.path.join(BACKUPS_DIR, existing[0])
        if _files_are_identical(source_file, latest_backup_path):
            # No changes since last backup - skip creating a duplicate
            return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUPS_DIR, f"{prefix}{timestamp}.json")
    shutil.copy2(source_file, backup_path)
    _prune_old_backups(prefix)
    return backup_path


def import_user_data(backup_data):
    """
    Restores user-personal data (trades + deposits history) from a backup
    dictionary previously produced by export_user_data().

    Before overwriting, the CURRENT state is archived to a timestamped safety
    file (inside the `backups/` directory) so nothing is lost if the wrong
    backup is uploaded by mistake. Duplicate/identical backups are skipped,
    and only the most recent MAX_PRE_RESTORE_BACKUPS snapshots are kept.

    Args:
        backup_data: dict as produced by export_user_data()

    Returns:
        (success: bool, message: str)
    """
    import currency_manager

    if not isinstance(backup_data, dict):
        return False, "The backup file is invalid (unrecognized format)."

    trades_db = backup_data.get("trades_db")
    deposits_history = backup_data.get("deposits_history")

    if trades_db is None or deposits_history is None:
        return False, "The backup file is missing required fields (trades_db / deposits_history)."

    # Basic structural validation
    if "trades" not in trades_db or "portfolio_metadata" not in trades_db:
        return False, "Invalid backup file: trades_db is missing 'trades' or 'portfolio_metadata'."
    if "deposits" not in deposits_history or "metadata" not in deposits_history:
        return False, "Invalid backup file: deposits_history is missing 'deposits' or 'metadata'."

    # Safety net: archive current state before overwriting (deduplicated + pruned)
    try:
        _create_pre_restore_backup(DB_FILE, "trades_db.pre_restore_")
        _create_pre_restore_backup(currency_manager.DEPOSITS_FILE, "deposits_history.pre_restore_")
    except Exception as e:
        print(f"Warning: could not create pre-restore safety backup: {e}")

    try:
        save_db(trades_db)
        currency_manager.save_deposits_history(deposits_history)
    except Exception as e:
        return False, f"Error while restoring the data: {e}"

    return True, "Data restored successfully! The previous state was saved as a safety backup."


