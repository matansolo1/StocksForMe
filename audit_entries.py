"""
Retroactive Entry Audit
=======================

Re-evaluates EXISTING trades against the real-world GTC limit-order entry
model introduced in `trading_logic.check_pending_entries()`.

Historically, a setup found by the Sunday scan was written straight into the
database as an ACTIVE position at Friday's closing price. In reality the buy
limit order is only executed if the market actually trades at or below that
price. Stocks that gapped up and never came back were therefore recorded as
positions that were never actually bought ("phantom positions").

Because orders are GTC (Good-Til-Cancelled), a phantom position is NOT a
cancelled order - it is an order that is STILL LIVE and may yet fill. This
script therefore converts phantom positions back to PENDING_ENTRY, so they
keep waiting for the price to reach the target, exactly like at the broker.

To close such an order for good, use the "Cancel Order" button on the dashboard.

Usage:
    python audit_entries.py            # dry run - report only, changes nothing
    python audit_entries.py --apply    # apply the fixes (creates a backup first)

Only ACTIVE trades are considered. Trades that already closed (HIT_TP/HIT_SL/
MANUAL_CLOSE) are never touched: their outcome is already realized history.
"""

import sys
from datetime import datetime

import data_manager
import trading_logic

# Windows consoles default to cp1252, which cannot encode the status symbols
# used in this report. Force UTF-8 so the output is readable everywhere.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def audit_trade(trade):
    """
    Evaluates whether a single ACTIVE trade would really have been filled.

    Returns a dict describing the verdict, or None if the trade could not be
    evaluated (missing data / no market data available).
    """
    ticker = trade.get("ticker")
    entry_price = trade.get("entry_price")
    timestamp = trade.get("timestamp")

    if not ticker or not entry_price or not timestamp:
        return None

    try:
        signal_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    session_date, _open, _close = trading_logic.get_entry_session(signal_dt)
    if session_date is None:
        return None

    evaluation = trading_logic.evaluate_limit_fill(ticker, float(entry_price), session_date)

    return {
        "ticker": ticker,
        "target": float(entry_price),
        "session_date": session_date,
        "evaluation": evaluation,
    }


def revert_to_pending(trade, reason):
    """
    Converts a phantom ACTIVE trade back into a live PENDING_ENTRY GTC order.

    The original signal price becomes the limit price, the capital that was
    wrongly reported as invested becomes reserved capital, and the trade stops
    contributing any P&L until it actually fills.
    """
    target = float(trade.get("target_entry") or trade.get("entry_price"))
    # Capital that was wrongly booked as an open position becomes the reserve
    reserved = float(trade.get("reserved_capital") or 0) or \
        float(trade.get("quantity", 0) or 0) * float(trade.get("entry_price", 0) or 0)

    trade["status"] = trading_logic.STATUS_PENDING_ENTRY
    trade["target_entry"] = target
    trade["signal_price"] = trade.get("signal_price", target)
    trade["entry_price"] = target
    trade["reserved_capital"] = round(reserved, 2)
    trade["time_in_force"] = "GTC"
    trade["sessions_waiting"] = 0
    trade.setdefault("signal_timestamp", trade.get("timestamp"))
    trade.setdefault("stop_loss_pct", 5.0)
    trade.setdefault("take_profit_pct", 10.0)

    # No position -> no P&L and no live price of its own
    trade["pnl_pct"] = 0.0
    trade.pop("current_price", None)
    trade.pop("price_note", None)

    trade["entry_check_note"] = f"Retroactive audit: {reason}"

    # Make sure the order is anchored to a real trading session
    if not trade.get("entry_session_date"):
        try:
            signal_dt = datetime.strptime(trade["timestamp"], "%Y-%m-%d %H:%M:%S")
            session_date, _o, _c = trading_logic.get_entry_session(signal_dt)
            trade["entry_session_date"] = session_date
        except Exception:
            pass

    return trade


def main():
    apply_changes = "--apply" in sys.argv

    trades = data_manager.load_trades()
    active_trades = [t for t in trades if trading_logic.is_open_position(t)]

    if not active_trades:
        print("No ACTIVE trades to audit.")
        return

    print("=" * 78)
    print(f"RETROACTIVE ENTRY AUDIT ({'APPLY' if apply_changes else 'DRY RUN'})")
    print("=" * 78)

    to_expire = []

    for trade in active_trades:
        report = audit_trade(trade)
        if report is None:
            print(f"\n⚠️  {trade.get('ticker', '?')}: could not evaluate (missing data) - left untouched")
            continue

        evaluation = report["evaluation"]
        outcome = evaluation["outcome"]
        low = evaluation["session_low"]
        open_px = evaluation["session_open_price"]

        print(f"\n▶ {report['ticker']}  (session {report['session_date']})")
        print(f"    target/limit : ${report['target']:.2f}")
        if open_px is not None:
            print(f"    session open : ${open_px:.2f}")
        if low is not None:
            print(f"    session low  : ${low:.2f}")
        print(f"    verdict      : {outcome} - {evaluation['reason']}")

        if outcome == "FILLED":
            print(f"    ✅ Genuinely filled at ${evaluation['fill_price']:.2f} - keeping as ACTIVE.")
        elif outcome == "PENDING":
            print(f"    ❌ This position was NEVER actually bought.")
            print(f"       -> will be reverted to PENDING_ENTRY (GTC order still waiting).")
            to_expire.append((trade, evaluation["reason"]))
        else:
            print(f"    ⏳ Inconclusive ({outcome}) - keeping as ACTIVE (conservative).")

    print("\n" + "=" * 78)
    if not to_expire:
        print("SUMMARY: all ACTIVE positions were genuinely filled. Nothing to fix.")
        return

    print(f"SUMMARY: {len(to_expire)} phantom position(s) found:")
    for trade, _reason in to_expire:
        qty = trade.get("quantity", 0)
        entry = trade.get("entry_price", 0)
        print(f"  - {trade['ticker']}: ${qty * entry:,.2f} wrongly reported as an open position")
    print("\nThese will be reverted to PENDING_ENTRY - the GTC order stays live and")
    print("may still fill. To close one for good, use \"Cancel Order\" on the dashboard.")

    if not apply_changes:
        print("\nThis was a DRY RUN. No files were modified.")
        print("Run `python audit_entries.py --apply` to revert these to PENDING_ENTRY.")
        return

    # Safety net: snapshot the current DB before mutating it
    backup_path = data_manager._create_pre_restore_backup(data_manager.DB_FILE, "trades_db.pre_audit_")
    if backup_path:
        print(f"\n🛟 Backup created: {backup_path}")

    for trade, reason in to_expire:
        revert_to_pending(trade, reason)
        print(f"  ✔ {trade['ticker']} reverted to PENDING_ENTRY (GTC order still live)")

    data_manager.save_trades(trades)
    data_manager.update_portfolio_state(trades)

    try:
        import ui_generator
        ui_generator.generate_dashboard_file(trades)
        print("  ✔ Dashboard regenerated")
    except Exception as e:
        print(f"  ⚠️ Could not regenerate dashboard: {e}")

    print("\nDone. These are no longer counted as open positions; they now appear")
    print("in the \"Pending Entries\" table and will fill if the price reaches the target.")


if __name__ == "__main__":
    main()
