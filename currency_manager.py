"""
Currency Manager - Handles deposits, conversions, and FX rates
Manages the deposits_history.json file and currency conversions
"""

import json
import os
from datetime import datetime
import yfinance as yf

DEPOSITS_FILE = "deposits_history.json"
CONVERSION_FEE = 10.27  # Fixed USD fee for ILS→USD conversions

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
                "last_updated": ""
            }
        }
    try:
        with open(DEPOSITS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
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


def calculate_ils_to_usd_net(amount_ils, fx_rate=None, fee=CONVERSION_FEE):
    """Calculate net USD after converting ILS"""
    if fx_rate is None:
        fx_rate = get_live_usd_ils_rate()
    
    gross_usd = amount_ils / fx_rate
    net_usd = gross_usd - fee
    
    return {
        "amount_ils": amount_ils,
        "fx_rate": round(fx_rate, 4),
        "gross_usd": round(gross_usd, 2),
        "conversion_fee_usd": fee,
        "net_usd": round(net_usd, 2)
    }

def add_deposit(amount, currency, date=None, description="", fx_rate=None):
    """Add a new deposit to history"""
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
        conversion = calculate_ils_to_usd_net(amount, fx_rate)
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
        # USD deposit - still record the live USD/ILS rate for the day so we can
        # later calculate ILS-denominated P&L / FX gains even though no conversion happened.
        try:
            recorded_fx_rate = fx_rate if fx_rate is not None else get_live_usd_ils_rate()
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

    Returns:
        float: weighted average fx_rate (ILS per USD), or None if no rate data exists.
    """
    history = load_deposits_history()
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


