import pandas as pd
import numpy as np

def calculate_rsi(data, window=14):
    """
    Calculates the Relative Strength Index (RSI).
    Inputs: data (pd.Series), window (int)
    Output: pd.Series
    """
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_pnl_pct(current_price, entry_price):
    """
    Calculates the percentage profit/loss.
    Inputs: current_price (float), entry_price (float)
    Output: float (percentage)
    """
    if entry_price == 0:
        return 0
    return ((current_price - entry_price) / entry_price) * 100

def calculate_realized_usd(entry_price, exit_price, notion=None, quantity=None):
    """
    Calculates realized P&L in USD based on notion or quantity.
    """
    if entry_price == 0:
        return 0
    if quantity:
        return (exit_price - entry_price) * quantity
    if notion:
        return (exit_price - entry_price) * (notion / entry_price)
    return 0

def calculate_mwr(total_deposits, current_equity):

    """
    Simple Money-Weighted Return approximation (Total ROI).
    (Current Equity - Total Deposits) / Total Deposits
    """
    if total_deposits == 0:
        return 0
    return ((current_equity - total_deposits) / total_deposits) * 100
