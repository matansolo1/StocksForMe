"""
FX API - Historical and current exchange rates
"""

import yfinance as yf
from datetime import datetime, timedelta

def get_usd_ils_historical(date_str):
    """
    Get historical USD/ILS rate for a specific date
    
    Args:
        date_str: Date in format "YYYY-MM-DD"
    
    Returns:
        float: USD/ILS rate (ILS per 1 USD)
    """
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        end_date = (date + timedelta(days=3)).strftime("%Y-%m-%d")
        
        # Try USDILS=X (USD to ILS)
        ticker = yf.Ticker("USDILS=X")
        hist = ticker.history(start=date_str, end=end_date)
        
        if not hist.empty:
            return float(hist['Close'].iloc[0])
        
        # Fallback: try ILS=X and invert
        ticker = yf.Ticker("ILS=X")
        hist = ticker.history(start=date_str, end=end_date)
        
        if not hist.empty:
            return 1.0 / float(hist['Close'].iloc[0])
            
    except Exception as e:
        print(f"Error fetching historical rate for {date_str}: {e}")
    
    return 3.6  # Fallback

def get_current_portfolio_value_ils(portfolio_value_usd):
    """Convert current portfolio USD value to ILS"""
    from currency_manager import get_live_usd_ils_rate
    
    current_rate = get_live_usd_ils_rate()
    ils_value = portfolio_value_usd * current_rate
    
    return {
        "portfolio_usd": portfolio_value_usd,
        "current_fx_rate": current_rate,
        "portfolio_ils": round(ils_value, 2)
    }
