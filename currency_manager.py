"""
Currency Manager - Handles deposits, conversions, and FX rates
Manages the deposits_history.json file and currency conversions
"""

import json
import os
from datetime import datetime, timedelta
import yfinance as yf

DEPOSITS_FILE = "deposits_history.json"
CONVERSION_FEE = 10.27  # Legacy fallback USD fee for ILS→USD conversions (used only if no default_deposit_fee_usd is set)
DEFAULT_DEPOSIT_FEE_USD = 3.0  # Initial default deposit/conversion fee (editable via update_default_deposit_fee)

def load_deposits_history():
    """Load deposits history from JSON"""
    if not os.path.exists(DEPOSITS_FILE):
        return {
            "deposits": [],
            "metadata": {
                "total_deposits_ils": 0.0,
                "total_deposits_usd_gross": 0.0,
                "total_conversion_fees_usd": 0.0,
                "total_deposits_usd_net": 0.0,
                "conversion_count": 0,
                "avg_conversion_fee": 0.0,
                "default_fx_rate": None,
                "default_deposit_fee_usd": None,
                "last_updated": ""
            }
        }
    try:
        with open(DEPOSITS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault('metadata', {}).setdefault('default_fx_rate', None)
            data.setdefault('metadata', {}).setdefault('default_deposit_fee_usd', None)
            return data
    except Exception as e:
        print(f"Error loading deposits history: {e}")
        return {
            "deposits": [],
            "metadata": {
                "total_deposits_ils": 0.0,
                "total_deposits_usd_gross": 0.0,
                "total_conversion_fees_usd": 0.0,
                "total_deposits_usd_net": 0.0,
                "conversion_count": 0,
                "avg_conversion_fee": 0.0,
                "default_fx_rate": None,
                "default_deposit_fee_usd": None,
                "last_updated": ""
            }
        }


def save_deposits_history(data):
    """Save deposits history to JSON"""
    data['metadata']['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(DEPOSITS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving deposits history: {e}")

def get_live_usd_ils_rate():
    """Get current USD/ILS exchange rate from Yahoo Finance (how many ILS per 1 USD)"""
    try:
        ticker = yf.Ticker("ILS=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            # ILS=X on Yahoo Finance already quotes ILS per 1 USD directly
            return float(hist['Close'].iloc[-1])
    except:
        pass

    try:
        ticker = yf.Ticker("USDILS=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except:
        pass

    return 3.6  # Fallback rate


def get_historical_usd_ils_rate(date_str):
    """
    Fetches the historical USD/ILS exchange rate (ILS per 1 USD) for a given
    date (format "YYYY-MM-DD"). Used when recording a deposit that was made
    on a specific past date, so the FX rate reflects that day rather than
    "today".

    Falls back to the live/current rate if historical data isn't available
    for that exact date (e.g. weekends/holidays - walks a small window
    around the date and picks the closest trading day at/before it; if
    nothing is found at all, uses the live rate).

    Args:
        date_str: "YYYY-MM-DD" date string

    Returns:
        float: ILS per 1 USD on (or nearest trading day to) that date.
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return get_live_usd_ils_rate()

    for ticker_symbol in ("ILS=X", "USDILS=X"):
        try:
            ticker = yf.Ticker(ticker_symbol)
            start = (target_date - timedelta(days=7)).strftime("%Y-%m-%d")
            end = (target_date + timedelta(days=7)).strftime("%Y-%m-%d")
            hist = ticker.history(start=start, end=end)
            if hist is None or hist.empty:
                continue

            hist_index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index

            on_or_before_mask = hist_index <= target_date
            if on_or_before_mask.any():
                # Take the LAST trading day at or before the target date
                pos = on_or_before_mask.nonzero()[0][-1] if hasattr(on_or_before_mask, 'nonzero') else None
                if pos is None:
                    # Fallback for older pandas versions
                    idx_list = [i for i, v in enumerate(on_or_before_mask) if v]
                    pos = idx_list[-1]
            else:
                # No trading day before/on target - take the first one after
                pos = 0

            return float(hist['Close'].iloc[pos])
        except Exception:
            continue

    # Could not find historical data - fall back to live rate
    return get_live_usd_ils_rate()


def calculate_ils_to_usd_net(amount_ils, fx_rate=None, fee=None):
    """Calculate net USD after converting ILS. `fee` defaults to the
    editable default deposit fee if not explicitly provided."""
    if fx_rate is None:
        fx_rate = get_live_usd_ils_rate()
    if fee is None:
        fee = get_default_deposit_fee()

    gross_usd = amount_ils / fx_rate
    net_usd = gross_usd - fee
    
    return {
        "amount_ils": amount_ils,
        "fx_rate": round(fx_rate, 4),
        "gross_usd": round(gross_usd, 2),
        "conversion_fee_usd": fee,
        "net_usd": round(net_usd, 2)
    }

def add_deposit(amount, currency, date=None, description="", fx_rate=None, conversion_fee=None):
    """
    Add a new deposit to history.

    Args:
        amount: deposit amount in `currency`
        currency: "ILS" or "USD"
        date: "YYYY-MM-DD" date of the deposit (defaults to today)
        description: free-text description
        fx_rate: explicit ILS-per-USD rate to use. If None and currency is ILS,
                 the historical rate for `date` is fetched automatically.
        conversion_fee: explicit USD fee for this ILS->USD conversion (manually
                        entered by the user). If None, falls back to the
                        editable default_deposit_fee_usd. Ignored for USD deposits.
    """
    history = load_deposits_history()
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    deposit_id = len(history['deposits']) + 1
    deposit_entry = {
        "id": deposit_id,
        "date": date,
        "description": description or f"{currency} deposit",
        "source_currency": currency.upper()
    }
    
    if currency.upper() == "ILS":
        if fx_rate is None:
            fx_rate = get_historical_usd_ils_rate(date)
        if conversion_fee is None:
            conversion_fee = get_default_deposit_fee()

        conversion = calculate_ils_to_usd_net(amount, fx_rate, fee=conversion_fee)
        deposit_entry.update({
            "amount_ils": amount,
            "amount_usd": None,
            "converted_to_usd": conversion['net_usd'],
            "conversion_fee_usd": conversion['conversion_fee_usd'],
            "fx_rate_at_deposit": conversion['fx_rate'],
            "gross_usd": conversion['gross_usd']
        })
        
        history['metadata']['total_deposits_ils'] += amount
        history['metadata']['total_deposits_usd_gross'] += conversion['gross_usd']
        history['metadata']['total_conversion_fees_usd'] += conversion['conversion_fee_usd']
        history['metadata']['total_deposits_usd_net'] += conversion['net_usd']
        history['metadata']['conversion_count'] += 1
        history['metadata']['avg_conversion_fee'] = round(
            history['metadata']['total_conversion_fees_usd'] / history['metadata']['conversion_count'], 2
        )
    else:
        # USD deposit - still record the day's rate (historical if a past date
        # was given) so we can later calculate ILS-denominated P&L / FX gains
        # even though no conversion happened. No conversion fee applies.
        try:
            if fx_rate is not None:
                recorded_fx_rate = fx_rate
            else:
                recorded_fx_rate = get_historical_usd_ils_rate(date)
        except Exception:
            recorded_fx_rate = fx_rate

        deposit_entry.update({
            "amount_ils": None,
            "amount_usd": amount,
            "converted_to_usd": amount,
            "conversion_fee_usd": 0.0,
            "fx_rate_at_deposit": round(recorded_fx_rate, 4) if recorded_fx_rate else None,
            "gross_usd": amount
        })
        
        history['metadata']['total_deposits_usd_gross'] += amount
        history['metadata']['total_deposits_usd_net'] += amount

    
    history['deposits'].append(deposit_entry)
    save_deposits_history(history)
    return deposit_entry

def get_total_net_deposits_usd():
    """Get total net deposits in USD"""
    history = load_deposits_history()
    return history['metadata']['total_deposits_usd_net']

def get_total_gross_deposits_usd():
    """Get total gross deposits in USD"""
    history = load_deposits_history()
    return history['metadata']['total_deposits_usd_gross']

def get_total_conversion_fees():
    """Get total conversion fees paid"""
    history = load_deposits_history()
    return history['metadata']['total_conversion_fees_usd']


def get_default_deposit_fee():
    """
    Returns the user-editable default deposit/conversion fee (in USD) applied
    to new ILS deposits when no explicit fee is entered. Initializes to
    DEFAULT_DEPOSIT_FEE_USD (persisted) the first time it's requested.
    """
    history = load_deposits_history()
    fee = history['metadata'].get('default_deposit_fee_usd')

    if fee is not None:
        return fee

    # Not set yet - initialize with the built-in default and persist it
    history['metadata']['default_deposit_fee_usd'] = DEFAULT_DEPOSIT_FEE_USD
    save_deposits_history(history)
    return DEFAULT_DEPOSIT_FEE_USD


def update_default_deposit_fee(new_fee):
    """Allows the user to manually override the default deposit/conversion
    fee (in USD) used for new deposits."""
    history = load_deposits_history()
    history['metadata']['default_deposit_fee_usd'] = round(float(new_fee), 2)
    save_deposits_history(history)
    return history['metadata']['default_deposit_fee_usd']


def get_default_fx_rate(auto_calculate=True):
    """
    Returns the user-editable "default" FX rate used to fill in gaps for
    deposits that have no fx_rate_at_deposit recorded (legacy/partial
    conversions that were never completed as a single record).

    If no default has been set yet, it is auto-calculated once as the
    weighted-average rate of all deposits/conversions that DO have a valid
    rate, then persisted to metadata so it becomes the stable baseline
    (editable later by the user via update_default_fx_rate()).
    """
    history = load_deposits_history()
    default_rate = history['metadata'].get('default_fx_rate')

    if default_rate:
        return default_rate

    if not auto_calculate:
        return None

    # Auto-calculate from deposits/conversions that have a valid rate
    total_weight_usd = 0.0
    weighted_sum = 0.0
    for deposit in history.get('deposits', []):
        conversion_details = deposit.get('conversion_details')
        if conversion_details:
            for conv in conversion_details.values():
                fx_rate = conv.get('fx_rate')
                units = conv.get('quantity_units')
                if fx_rate and units:
                    weighted_sum += fx_rate * units
                    total_weight_usd += units
        else:
            fx_rate = deposit.get('fx_rate_at_deposit')
            usd_amount = deposit.get('converted_to_usd') or deposit.get('amount_usd') or deposit.get('gross_usd')
            if fx_rate and usd_amount:
                weighted_sum += fx_rate * usd_amount
                total_weight_usd += usd_amount

    if total_weight_usd > 0:
        calculated = round(weighted_sum / total_weight_usd, 4)
        # Persist so it becomes a stable, editable baseline going forward
        history['metadata']['default_fx_rate'] = calculated
        save_deposits_history(history)
        return calculated

    return None


def update_default_fx_rate(new_rate):
    """Allows the user to manually override the default FX rate used for
    deposits missing an explicit fx_rate_at_deposit value."""
    history = load_deposits_history()
    history['metadata']['default_fx_rate'] = round(float(new_rate), 4)
    save_deposits_history(history)
    return history['metadata']['default_fx_rate']


def get_weighted_avg_fx_rate():
    """
    Calculates the weighted-average USD/ILS rate at which the deposited dollars
    were effectively "bought", based on all deposit records.

    Supports two record shapes:
      - Legacy consolidated records with a 'conversion_details' dict containing
        multiple sub-conversions (date/fx_rate/quantity_units per conversion).
      - Simple records with a single 'fx_rate_at_deposit' field (both ILS and
        USD deposits, since USD deposits now also record the day's live rate).

    Weighting is done by the USD amount associated with each rate, so larger
    deposits/conversions influence the average proportionally more.

    Deposits missing a valid rate (fx_rate_at_deposit is null/0, no
    conversion_details) fall back to the editable "default_fx_rate" so their
    USD amount is still represented in the average instead of being silently
    dropped.

    Returns:
        float: weighted average fx_rate (ILS per USD), or None if no rate data exists.
    """
    history = load_deposits_history()
    total_weight_usd = 0.0
    weighted_sum = 0.0
    default_rate = None

    for deposit in history.get('deposits', []):
        conversion_details = deposit.get('conversion_details')
        if conversion_details:
            for conv in conversion_details.values():
                fx_rate = conv.get('fx_rate')
                units = conv.get('quantity_units')
                if fx_rate and units:
                    weighted_sum += fx_rate * units
                    total_weight_usd += units
        else:
            fx_rate = deposit.get('fx_rate_at_deposit')
            usd_amount = deposit.get('converted_to_usd') or deposit.get('amount_usd') or deposit.get('gross_usd')
            if not fx_rate and usd_amount:
                # Missing rate - fall back to the editable default so this
                # deposit's USD amount is still represented in the average.
                if default_rate is None:
                    default_rate = get_default_fx_rate()
                fx_rate = default_rate
            if fx_rate and usd_amount:
                weighted_sum += fx_rate * usd_amount
                total_weight_usd += usd_amount

    if total_weight_usd > 0:
        return weighted_sum / total_weight_usd
    return None



def calculate_ils_pnl(current_equity_usd):
    """
    Calculates the total P&L in ILS terms, factoring in both trading performance
    (in USD) and the USD/ILS exchange rate movement since deposits were made.

    Args:
        current_equity_usd: Current portfolio equity in USD (deposits + realized + unrealized P&L)

    Returns:
        Dictionary with:
            - buy_rate: weighted average USD/ILS rate at deposit time
            - current_rate: live USD/ILS rate today
            - rate_change_pct: % change in the exchange rate
            - total_deposits_usd: net USD deposited
            - cost_basis_ils: what the deposits actually cost in ILS
            - current_value_ils: current equity converted to ILS at today's rate
            - total_pnl_ils: total ILS P&L (current_value_ils - cost_basis_ils)
            - trading_pnl_ils: P&L from trading performance only (in ILS, at today's rate)
            - fx_pnl_ils: P&L purely from exchange rate movement
            - available: False if insufficient data to compute
    """
    history = load_deposits_history()
    total_deposits_usd = history['metadata'].get('total_deposits_usd_net', 0.0)

    buy_rate = get_weighted_avg_fx_rate()

    if not buy_rate or total_deposits_usd <= 0:
        return {
            'available': False,
            'buy_rate': buy_rate,
            'current_rate': None,
            'rate_change_pct': 0.0,
            'total_deposits_usd': total_deposits_usd,
            'cost_basis_ils': 0.0,
            'current_value_ils': 0.0,
            'total_pnl_ils': 0.0,
            'trading_pnl_ils': 0.0,
            'fx_pnl_ils': 0.0
        }

    try:
        current_rate = get_live_usd_ils_rate()
    except Exception:
        current_rate = buy_rate

    cost_basis_ils = total_deposits_usd * buy_rate
    current_value_ils = current_equity_usd * current_rate

    total_pnl_ils = current_value_ils - cost_basis_ils

    # Trading P&L in USD terms, revalued at today's FX rate
    trading_pnl_usd = current_equity_usd - total_deposits_usd
    trading_pnl_ils = trading_pnl_usd * current_rate

    # FX P&L: effect of the exchange rate moving on the original deposited capital
    fx_pnl_ils = total_deposits_usd * (current_rate - buy_rate)

    rate_change_pct = ((current_rate - buy_rate) / buy_rate) * 100 if buy_rate else 0.0

    return {
        'available': True,
        'buy_rate': round(buy_rate, 4),
        'current_rate': round(current_rate, 4),
        'rate_change_pct': round(rate_change_pct, 2),
        'total_deposits_usd': round(total_deposits_usd, 2),
        'cost_basis_ils': round(cost_basis_ils, 2),
        'current_value_ils': round(current_value_ils, 2),
        'total_pnl_ils': round(total_pnl_ils, 2),
        'trading_pnl_ils': round(trading_pnl_ils, 2),
        'fx_pnl_ils': round(fx_pnl_ils, 2)
    }


def _recalculate_metadata_from_deposits(history):
    """
    Rebuilds the aggregate metadata fields (totals, conversion count/avg fee,
    per-owner breakdown) from scratch by summing over history['deposits'].
    Called after any edit/delete to a deposit so all downstream totals stay
    consistent (single source of truth = the deposits list).
    """
    metadata = history.setdefault('metadata', {})

    total_deposits_ils = 0.0
    total_deposits_usd_gross = 0.0
    total_conversion_fees_usd = 0.0
    total_deposits_usd_net = 0.0
    conversion_count = 0
    per_owner = {}

    for deposit in history.get('deposits', []):
        owner = deposit.get('owner', 'default')
        per_owner.setdefault(owner, {
            'total_deposits_ils': 0.0,
            'total_deposits_usd_gross': 0.0,
            'total_conversion_fees_usd': 0.0,
            'total_deposits_usd_net': 0.0,
            'conversion_count': 0,
            'avg_conversion_fee': 0.0,
        })

        source_currency = (deposit.get('source_currency') or 'USD').upper()
        amount_ils = deposit.get('amount_ils') or 0.0
        gross_usd = deposit.get('gross_usd')
        net_usd = deposit.get('converted_to_usd')
        fee_usd = deposit.get('conversion_fee_usd') or 0.0

        if gross_usd is None:
            gross_usd = deposit.get('amount_usd') or 0.0
        if net_usd is None:
            net_usd = gross_usd - fee_usd

        if source_currency == 'ILS':
            total_deposits_ils += amount_ils
            per_owner[owner]['total_deposits_ils'] += amount_ils
            conversion_count += 1
            per_owner[owner]['conversion_count'] += 1

        total_deposits_usd_gross += gross_usd
        total_conversion_fees_usd += fee_usd
        total_deposits_usd_net += net_usd

        per_owner[owner]['total_deposits_usd_gross'] += gross_usd
        per_owner[owner]['total_conversion_fees_usd'] += fee_usd
        per_owner[owner]['total_deposits_usd_net'] += net_usd

    for owner_data in per_owner.values():
        owner_data['avg_conversion_fee'] = round(
            owner_data['total_conversion_fees_usd'] / owner_data['conversion_count'], 2
        ) if owner_data['conversion_count'] > 0 else 0.0

    metadata['total_deposits_ils'] = round(total_deposits_ils, 2)
    metadata['total_deposits_usd_gross'] = round(total_deposits_usd_gross, 2)
    metadata['total_conversion_fees_usd'] = round(total_conversion_fees_usd, 2)
    metadata['total_deposits_usd_net'] = round(total_deposits_usd_net, 2)
    metadata['conversion_count'] = conversion_count
    metadata['avg_conversion_fee'] = round(
        total_conversion_fees_usd / conversion_count, 2
    ) if conversion_count > 0 else 0.0

    if 'per_owner' in metadata or per_owner:
        metadata['per_owner'] = per_owner

    return history


def get_all_deposits():
    """Returns the full list of deposit records (for the management UI table)."""
    history = load_deposits_history()
    return history.get('deposits', [])


def update_deposit(deposit_id, date=None, amount=None, fx_rate=None, description=None, conversion_fee=None):
    """
    Edits an existing deposit record's date / amount / fx_rate / description /
    conversion_fee, then recalculates all derived fields (gross/net USD, fees)
    and aggregate metadata totals so everything stays consistent.

    Args:
        deposit_id: the 'id' of the deposit to edit
        date: optional new date string "YYYY-MM-DD"
        amount: optional new amount (interpreted in the deposit's existing source_currency)
        fx_rate: optional new fx_rate_at_deposit value
        description: optional new description
        conversion_fee: optional new conversion_fee_usd value (ILS deposits only)

    Returns:
        (success: bool, message: str)
    """
    history = load_deposits_history()
    deposit = next((d for d in history['deposits'] if d.get('id') == deposit_id), None)

    if deposit is None:
        return False, f"Deposit with id {deposit_id} was not found."

    if date is not None:
        deposit['date'] = date
    if description is not None:
        deposit['description'] = description

    source_currency = (deposit.get('source_currency') or 'USD').upper()

    if amount is not None:
        amount = float(amount)
        if source_currency == 'ILS':
            deposit['amount_ils'] = amount
        else:
            deposit['amount_usd'] = amount

    if fx_rate is not None:
        deposit['fx_rate_at_deposit'] = round(float(fx_rate), 4)

    if conversion_fee is not None and source_currency == 'ILS':
        deposit['conversion_fee_usd'] = round(float(conversion_fee), 2)

    # Recompute derived USD fields based on (possibly updated) amount/rate/fee
    effective_rate = deposit.get('fx_rate_at_deposit')

    if source_currency == 'ILS':
        amount_ils = deposit.get('amount_ils') or 0.0
        fee = deposit.get('conversion_fee_usd') or 0.0
        if effective_rate:
            gross_usd = amount_ils / effective_rate
            deposit['gross_usd'] = round(gross_usd, 2)
            deposit['converted_to_usd'] = round(gross_usd - fee, 2)
        # If no rate, leave gross/net as-is (will fall back to default_fx_rate
        # in the weighted-average calculation used for the ILS P&L card).
    else:
        amount_usd = deposit.get('amount_usd') or 0.0
        deposit['gross_usd'] = amount_usd
        deposit['converted_to_usd'] = amount_usd

    # Clear conversion_details if it exists and we edited the rate manually,
    # since the single fx_rate_at_deposit now takes precedence and mixing
    # both would double-count in the weighted average.
    if fx_rate is not None and deposit.get('conversion_details'):
        del deposit['conversion_details']

    _recalculate_metadata_from_deposits(history)
    save_deposits_history(history)
    return True, "Deposit updated successfully."


def delete_deposit(deposit_id):
    """
    Removes a deposit record entirely and recalculates aggregate metadata.

    Returns:
        (success: bool, message: str)
    """
    history = load_deposits_history()
    original_len = len(history['deposits'])
    history['deposits'] = [d for d in history['deposits'] if d.get('id') != deposit_id]

    if len(history['deposits']) == original_len:
        return False, f"Deposit with id {deposit_id} was not found."

    _recalculate_metadata_from_deposits(history)
    save_deposits_history(history)
    return True, "Deposit deleted successfully."
