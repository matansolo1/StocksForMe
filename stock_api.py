import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def get_next_earnings_date(ticker_symbol):
    """
    Checks the next earnings date for a company using yfinance.
    Returns: datetime object or None
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        calendar = ticker.calendar
        if calendar is not None:
            # calendar might be a dict or DataFrame depending on yfinance version
            if isinstance(calendar, dict) and 'Earnings Date' in calendar:
                dates = calendar['Earnings Date']
                return dates[0] if isinstance(dates, list) and dates else dates
            elif isinstance(calendar, pd.DataFrame) and not calendar.empty:
                if 'Earnings Date' in calendar.index:
                    earnings_dates = calendar.loc['Earnings Date']
                    if isinstance(earnings_dates, (list, pd.Series)):
                        return earnings_dates[0]
                    return earnings_dates
        return None
    except Exception as e:
        print(f"Error fetching earnings date for {ticker_symbol}: {e}")
        return None

def get_live_data(ticker, period="5d", interval="1d"):
    """
    Downloads live data for a ticker from yfinance.
    Inputs: ticker (str), period (str), interval (str)
    Output: pd.DataFrame or None
    """
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]
        return df
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None

def get_historical_data(ticker, days=180):
    """
    Downloads historical data for scanner or charts.
    Inputs: ticker (str), days (int)
    Output: pd.DataFrame or None
    """
    from datetime import datetime, timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    try:
        df = yf.download(ticker, start=start_date, end=end_date, interval='1d', progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"Error fetching historical data for {ticker}: {e}")
        return None

def get_intraday_data(ticker, period="5d", interval="5m"):
    """
    Downloads intraday data (5-minute candles) for a ticker from yfinance.
    Used for precise stop loss / take profit detection.
    Inputs: ticker (str), period (str), interval (str)
    Output: pd.DataFrame or None
    
    Note: yfinance provides 5-minute data for up to 60 days back.
    """
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]
        return df
    except Exception as e:
        print(f"Error fetching intraday data for {ticker}: {e}")
        return None
