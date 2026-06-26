# StocksForMe - Trading Rules & Execution Guide

## 🎯 Core Strategy (Momentum Scenario 3)

**Backtested Performance:**
- Calm Era (2010-2020): +232.78%
- Chaos Era (2021-2026): +100.57%
- Total (16 years): +567%
- Win Rate: 43% (stable across both periods)

**Risk Management:**
- Maximum 3 concurrent positions
- Stop Loss: 5% (fixed)
- Take Profit: 10% (fixed)
- Risk/Reward Ratio: 1:2

**Entry Criteria:**
- SPY above SMA 200 (global trend filter)
- RSI crosses above 55
- Price above SMA 50
- Ranked by proximity to 52-week high

---

## 📅 Weekly Schedule (Israel Time)

### Sunday Evening (21:00-22:00)
**Action: Run Weekly Scanner**

1. Navigate to `/run-scan` in the web interface
2. Review parameters (default: RSI=55, SL=5%, TP=10%)
3. Add deposit if needed (optional)
4. Click "Confirm & Run Scan"
5. Wait for scan to complete (~2-3 minutes)

**What the scanner does:**
- Analyzes ~100 stocks
- Uses Friday's closing prices (last available data)
- Identifies top 3 setups based on momentum criteria
- Fills empty position slots (up to 3 total)

**Important:**
- Scanner only adds positions to fill empty slots
- Does NOT close existing positions
- If you have 2 active positions → adds 1 new
- If you have 3 active positions → adds 0 new

---

### Monday Morning (16:30 Israel Time = 9:30 AM US/Eastern)

**Action: Execute Trades at Market Open**

1. Review the suggested positions from Sunday's scan
2. Place **Market Orders** for each suggested position
3. Set Stop Loss: Entry Price × 0.95 (-5%)
4. Set Take Profit: Entry Price × 1.10 (+10%)

**Why Market Orders?**
- Backtester enters at Monday's opening price
- Market orders ensure execution
- Small slippage (0.1%-0.2%) is acceptable
- Simpler than limit orders

**Alternative: Limit Orders**
- If you prefer precision, use Friday's closing price
- Risk: Order may not fill if market gaps up
- Not recommended for this strategy

---

## 🚫 Exit Rules (Critical!)

**Positions close ONLY when:**
1. ✅ Stop Loss is hit (-5%)
2. ✅ Take Profit is hit (+10%)

**Positions do NOT close when:**
- ❌ 7 days have passed
- ❌ Scanner finds "better" setups
- ❌ You manually decide to exit
- ❌ Market conditions change

**Why?**
- The backtester achieved 532% by letting winners run
- 43% of positions eventually hit Take Profit
- Some take 3 days, some take 15 days
- Patience is part of the strategy

---

## 💰 Position Sizing

**Formula:**
```
Position Size = Available Cash / 3
```

**Available Cash:**
```
Available Cash = Total Deposits + Realized P&L - Invested Capital
```

**Example:**
- Total Deposits: $10,000
- Realized P&L: +$500 (from closed trades)
- Invested Capital: $3,000 (1 active position)
- Available Cash: $10,000 + $500 - $3,000 = $7,500
- Position Size: $7,500 / 3 = $2,500

**Dynamic Sizing:**
- Grows with profits (more capital available)
- Shrinks with losses (less capital available)
- Always maintains 3 equal-sized positions

---

## 📊 Daily Monitoring

**What to check:**
1. Have any positions hit Stop Loss or Take Profit?
2. Update current prices (automatic via tracker)
3. Review unrealized P&L

**What NOT to do:**
- ❌ Don't close positions manually
- ❌ Don't adjust Stop Loss or Take Profit
- ❌ Don't run scanner mid-week
- ❌ Don't add positions outside of Sunday scan

---

## 🧪 Dry Run Mode

**For testing without affecting real positions:**

1. Use the Dry Run Scanner (if available)
2. See what positions would be suggested
3. No changes to actual portfolio
4. Good for learning the system

---

## 📈 Performance Tracking

**Key Metrics:**
- Total Equity: Deposits + Realized P&L + Unrealized P&L
- Cash Available: For new positions
- Realized P&L: From closed trades
- Unrealized P&L: From active positions

**Analytics Dashboard:**
- View cumulative returns
- Compare to SPY benchmark
- Track win rate and profit factor
- Analyze trade duration

---

## ⚠️ Important Notes

### Market Conditions
- Scanner only runs if SPY > SMA 200
- If market is bearish, no new positions are added
- Existing positions remain active (SL/TP still apply)

### Earnings Filter
- Stocks with earnings in next 7 days are excluded
- Reduces volatility risk around earnings announcements

### Commission
- Backtester assumes 0.05% commission per trade
- Factor this into your broker selection

### Timezone Awareness
- All times in this guide are Israel time
- US market opens at 16:30 Israel time (summer)
- US market opens at 17:30 Israel time (winter)

---

## 🎓 Strategy Philosophy

**"Let your winners run, cut your losers short"**

This strategy achieves a 43% win rate but still generates 532% returns over 16 years because:

1. **Winners are 2x bigger than losers** (10% vs 5%)
2. **No premature exits** - positions have time to reach TP
3. **Consistent execution** - same rules every week
4. **Risk management** - always 3 positions, never more

**Trust the process. Follow the rules. Be patient.**

---

## 📞 Troubleshooting

**Q: What if all 3 positions close on Wednesday?**
A: Wait until Sunday evening to run the next scan. Don't scan mid-week.

**Q: What if a position is stuck for 2 weeks?**
A: Let it run. It will eventually hit SL or TP. No time-based exits.

**Q: What if the scanner finds 0 setups?**
A: Stay in cash. Wait for next Sunday. Market conditions may not be favorable.

**Q: Can I adjust the Stop Loss if a position is doing well?**
A: No. Fixed SL/TP is part of the strategy. Don't modify.

**Q: What if I miss Monday's market open?**
A: Enter as soon as possible on Monday. Small delay is acceptable.

---

## 📚 Additional Resources

- **Backtester**: Test different parameters on historical data
- **Analytics Dashboard**: Track performance vs SPY
- **Project Context**: See `project_context.md` for technical details

---

**Last Updated:** June 26, 2026
**Strategy Version:** Momentum Scenario 3 (Production)
