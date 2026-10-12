import pandas as pd
import numpy as np

def run_backtest(df: pd.DataFrame, initial_capital: float = 100000.0) -> dict:
    """Run historical backtest comparing the strategy signal vs Buy & Hold benchmark."""
    d = df.dropna(subset=['Close', 'SIGNAL']).copy()
    if len(d) < 30:
        return None
        
    cash = initial_capital
    position = 0.0
    equity_curve = []
    benchmark_curve = []
    trade_history = []
    
    start_price = d['Close'].iloc[0]
    benchmark_shares = initial_capital / start_price
    
    current_entry_price = 0.0
    current_entry_date = None
    
    for i in range(len(d)):
        date = d.index[i]
        price = d['Close'].iloc[i]
        sig = d['SIGNAL'].iloc[i]
        
        # Strategy Execution:
        # Buy when sig == 1 and not holding
        if sig == 1 and position == 0:
            position = cash / price
            cash = 0.0
            current_entry_price = price
            current_entry_date = date
            trade_history.append({
                "type": "BUY",
                "date": date.strftime('%Y-%m-%d'),
                "price": price,
                "shares": position
            })
            
        # Sell when sig == -1 and holding
        elif sig == -1 and position > 0:
            revenue = position * price
            pnl = revenue - (position * current_entry_price)
            pnl_pct = (price - current_entry_price) / current_entry_price * 100
            cash = revenue
            position = 0.0
            trade_history.append({
                "type": "SELL",
                "date": date.strftime('%Y-%m-%d'),
                "price": price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "entry_price": current_entry_price,
                "entry_date": current_entry_date.strftime('%Y-%m-%d') if current_entry_date else ""
            })
            current_entry_price = 0.0
            current_entry_date = None
            
        total_equity = cash + (position * price)
        equity_curve.append(total_equity)
        benchmark_curve.append(benchmark_shares * price)
        
    d['Strategy_Equity'] = equity_curve
    d['Benchmark_Equity'] = benchmark_curve
    
    # Calculate performance metrics
    final_strat_equity = equity_curve[-1]
    final_bench_equity = benchmark_curve[-1]
    strat_return = ((final_strat_equity - initial_capital) / initial_capital) * 100
    bench_return = ((final_bench_equity - initial_capital) / initial_capital) * 100
    alpha = strat_return - bench_return
    
    # Max Drawdown
    strat_series = pd.Series(equity_curve)
    strat_cummax = strat_series.cummax()
    strat_dd = (strat_series - strat_cummax) / strat_cummax * 100
    max_dd = strat_dd.min()
    
    bench_series = pd.Series(benchmark_curve)
    bench_cummax = bench_series.cummax()
    bench_dd = (bench_series - bench_cummax) / bench_cummax * 100
    bench_max_dd = bench_dd.min()
    
    # Win rate
    sell_trades = [t for t in trade_history if t.get("type") == "SELL"]
    total_trades = len(sell_trades)
    winning_trades = len([t for t in sell_trades if t.get("pnl", 0) > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    # Annualized CAGR
    days = (d.index[-1] - d.index[0]).days
    years = max(days / 365.25, 0.1)
    strat_cagr = (((final_strat_equity / initial_capital) ** (1 / years)) - 1) * 100
    bench_cagr = (((final_bench_equity / initial_capital) ** (1 / years)) - 1) * 100
    
    return {
        "strat_return": strat_return,
        "bench_return": bench_return,
        "alpha": alpha,
        "max_dd": max_dd,
        "bench_max_dd": bench_max_dd,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "strat_cagr": strat_cagr,
        "bench_cagr": bench_cagr,
        "trade_history": trade_history,
        "equity_df": d[['Strategy_Equity', 'Benchmark_Equity', 'Close']]
    }
