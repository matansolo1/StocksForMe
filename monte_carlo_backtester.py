"""
Monte Carlo Intraday Path Simulation for Backtesting
=====================================================
This module simulates realistic intraday price movements to improve backtest accuracy
when using daily candles. It uses Geometric Brownian Motion constrained by observed
High/Low values to determine the order of Stop Loss and Take Profit hits.

Key Features:
- Simulates multiple possible intraday paths per trading day
- Respects observed High/Low constraints from daily candles
- Determines probabilistic order of SL/TP hits
- Free alternative to downloading 5-minute candle data
"""

import numpy as np
from typing import Dict, Optional

def simulate_intraday_path(
    open_price: float,
    high: float,
    low: float,
    close: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    volatility: float,
    num_steps: int = 78,
    num_simulations: int = 100
) -> Dict[str, any]:
    """
    Simulates intraday price paths using constrained Brownian motion.
    
    Args:
        open_price: Opening price of the day
        high: Highest price reached during the day
        low: Lowest price reached during the day
        close: Closing price of the day
        stop_loss: Stop loss price level (None if no SL)
        take_profit: Take profit price level (None if no TP)
        volatility: Historical volatility (daily standard deviation of returns)
        num_steps: Number of intraday steps to simulate (default 78 = 6.5 hours * 12 five-min intervals)
        num_simulations: Number of Monte Carlo paths to simulate
    
    Returns:
        Dictionary with:
            - hit_sl_first: Boolean, True if SL was hit before TP in majority of simulations
            - hit_tp_first: Boolean, True if TP was hit before SL in majority of simulations
            - hit_neither: Boolean, True if neither was hit in majority of simulations
            - sl_probability: Probability of hitting SL
            - tp_probability: Probability of hitting TP
            - avg_exit_price: Average exit price across all simulations
            - exit_reason: "HIT_SL", "HIT_TP", or "HELD"
    """
    
    # Validation
    if open_price <= 0 or high <= 0 or low <= 0 or close <= 0:
        return {
            "hit_sl_first": False,
            "hit_tp_first": False,
            "hit_neither": True,
            "sl_probability": 0.0,
            "tp_probability": 0.0,
            "avg_exit_price": close,
            "exit_reason": "HELD"
        }
    
    # If no SL or TP defined, no exit possible
    if stop_loss is None and take_profit is None:
        return {
            "hit_sl_first": False,
            "hit_tp_first": False,
            "hit_neither": True,
            "sl_probability": 0.0,
            "tp_probability": 0.0,
            "avg_exit_price": close,
            "exit_reason": "HELD"
        }
    
    # Calculate daily return and drift
    daily_return = (close - open_price) / open_price
    drift = daily_return / num_steps  # Distribute return across steps
    
    # Scale volatility to intraday (sqrt of time scaling)
    intraday_vol = volatility / np.sqrt(num_steps)
    
    # Counters
    sl_hits = 0
    tp_hits = 0
    sl_first_count = 0
    tp_first_count = 0
    neither_count = 0
    exit_prices = []
    
    for sim in range(num_simulations):
        price = open_price
        hit_sl = False
        hit_tp = False
        exit_price = close
        exit_step = num_steps
        
        # Generate random walk
        for step in range(num_steps):
            # Brownian motion step
            random_shock = np.random.normal(0, intraday_vol)
            price = price * (1 + drift + random_shock)
            
            # Ensure price stays within observed High/Low bounds
            # This is the key constraint that makes the simulation realistic
            price = max(low, min(high, price))
            
            # Check Stop Loss
            if stop_loss is not None and price <= stop_loss and not hit_sl and not hit_tp:
                hit_sl = True
                sl_hits += 1
                sl_first_count += 1
                exit_price = stop_loss
                exit_step = step
                break
            
            # Check Take Profit
            if take_profit is not None and price >= take_profit and not hit_tp and not hit_sl:
                hit_tp = True
                tp_hits += 1
                tp_first_count += 1
                exit_price = take_profit
                exit_step = step
                break
        
        # If neither was hit, position held until close
        if not hit_sl and not hit_tp:
            neither_count += 1
            exit_price = close
        
        exit_prices.append(exit_price)
    
    # Calculate probabilities
    sl_probability = sl_hits / num_simulations
    tp_probability = tp_hits / num_simulations
    neither_probability = neither_count / num_simulations
    
    # Determine most likely outcome
    if sl_first_count > tp_first_count and sl_first_count > neither_count:
        exit_reason = "HIT_SL"
        hit_sl_first = True
        hit_tp_first = False
        hit_neither = False
    elif tp_first_count > sl_first_count and tp_first_count > neither_count:
        exit_reason = "HIT_TP"
        hit_sl_first = False
        hit_tp_first = True
        hit_neither = False
    else:
        exit_reason = "HELD"
        hit_sl_first = False
        hit_tp_first = False
        hit_neither = True
    
    return {
        "hit_sl_first": hit_sl_first,
        "hit_tp_first": hit_tp_first,
        "hit_neither": hit_neither,
        "sl_probability": round(sl_probability, 3),
        "tp_probability": round(tp_probability, 3),
        "neither_probability": round(neither_probability, 3),
        "avg_exit_price": round(np.mean(exit_prices), 2),
        "exit_reason": exit_reason
    }


def simple_intraday_check(
    open_price: float,
    high: float,
    low: float,
    close: float,
    stop_loss: Optional[float],
    take_profit: Optional[float]
) -> Dict[str, any]:
    """
    Simplified heuristic for intraday SL/TP detection without full Monte Carlo.
    Uses the "worst case first" assumption based on price action.
    
    This is faster but less accurate than full Monte Carlo simulation.
    
    Returns:
        Dictionary with exit_reason and exit_price
    """
    
    # If both SL and TP were reached during the day
    if stop_loss is not None and take_profit is not None:
        sl_reached = (low <= stop_loss)
        tp_reached = (high >= take_profit)
        
        if sl_reached and tp_reached:
            # Both were hit - need to determine order
            # Heuristic: if open is closer to SL, assume SL hit first
            dist_to_sl = abs(open_price - stop_loss)
            dist_to_tp = abs(open_price - take_profit)
            
            if dist_to_sl < dist_to_tp:
                return {"exit_reason": "HIT_SL", "exit_price": stop_loss}
            else:
                return {"exit_reason": "HIT_TP", "exit_price": take_profit}
        
        elif sl_reached:
            return {"exit_reason": "HIT_SL", "exit_price": stop_loss}
        
        elif tp_reached:
            return {"exit_reason": "HIT_TP", "exit_price": take_profit}
    
    # Only SL defined
    elif stop_loss is not None and low <= stop_loss:
        return {"exit_reason": "HIT_SL", "exit_price": stop_loss}
    
    # Only TP defined
    elif take_profit is not None and high >= take_profit:
        return {"exit_reason": "HIT_TP", "exit_price": take_profit}
    
    # Neither hit
    return {"exit_reason": "HELD", "exit_price": close}


if __name__ == "__main__":
    # Test the Monte Carlo simulator
    print("Testing Monte Carlo Intraday Path Simulation\n")
    print("=" * 60)
    
    # Test Case 1: Both SL and TP reached
    print("\nTest 1: Both SL and TP reached during the day")
    print("-" * 60)
    result = simulate_intraday_path(
        open_price=100.0,
        high=108.0,
        low=94.0,
        close=105.0,
        stop_loss=95.0,
        take_profit=110.0,
        volatility=0.02,
        num_simulations=1000
    )
    print(f"Open: $100, High: $108, Low: $94, Close: $105")
    print(f"SL: $95, TP: $110")
    print(f"Result: {result['exit_reason']}")
    print(f"SL Probability: {result['sl_probability']:.1%}")
    print(f"TP Probability: {result['tp_probability']:.1%}")
    print(f"Held Probability: {result['neither_probability']:.1%}")
    print(f"Average Exit Price: ${result['avg_exit_price']:.2f}")
    
    # Test Case 2: Only SL reached
    print("\n\nTest 2: Only SL reached")
    print("-" * 60)
    result = simulate_intraday_path(
        open_price=100.0,
        high=102.0,
        low=93.0,
        close=98.0,
        stop_loss=95.0,
        take_profit=110.0,
        volatility=0.02,
        num_simulations=1000
    )
    print(f"Open: $100, High: $102, Low: $93, Close: $98")
    print(f"SL: $95, TP: $110")
    print(f"Result: {result['exit_reason']}")
    print(f"SL Probability: {result['sl_probability']:.1%}")
    
    # Test Case 3: Neither reached
    print("\n\nTest 3: Neither SL nor TP reached")
    print("-" * 60)
    result = simulate_intraday_path(
        open_price=100.0,
        high=104.0,
        low=97.0,
        close=102.0,
        stop_loss=95.0,
        take_profit=110.0,
        volatility=0.015,
        num_simulations=1000
    )
    print(f"Open: $100, High: $104, Low: $97, Close: $102")
    print(f"SL: $95, TP: $110")
    print(f"Result: {result['exit_reason']}")
    print(f"Held Probability: {result['neither_probability']:.1%}")
    
    print("\n" + "=" * 60)
    print("✅ Monte Carlo simulation tests completed!")
