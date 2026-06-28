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
    """Get current USD/ILS exchange rate from Yahoo Finance"""
    try:
        ticker = yf.Ticker("ILS=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            usd_to_ils = 1.0 / float(hist['Close'].iloc[-1])
            return usd_to_ils
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
        deposit_entry.update({
            "amount_ils": None,
            "amount_usd": amount,
            "converted_to_usd": amount,
            "conversion_fee_usd": 0.0,
            "fx_rate_at_deposit": None,
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

