import numpy as np
import pandas as pd

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate core technical indicators used in Taiwan stock/ETF market."""
    d = df.copy()
    
    # Moving Averages
    d['MA5'] = d['Close'].rolling(5).mean()
    d['MA10'] = d['Close'].rolling(10).mean()
    d['MA20'] = d['Close'].rolling(20).mean()   # 月線
    d['MA60'] = d['Close'].rolling(60).mean()   # 季線
    d['MA120'] = d['Close'].rolling(120).mean() # 半年線
    d['MA240'] = d['Close'].rolling(240).mean() # 年線
    
    # Volume MA
    d['VOL_MA5'] = d['Volume'].rolling(5).mean()
    d['VOL_MA20'] = d['Volume'].rolling(20).mean()

    # KD (9, 3, 3) - Stochastic Oscillator
    low_min9 = d['Low'].rolling(9).min()
    high_max9 = d['High'].rolling(9).max()
    denom = (high_max9 - low_min9).replace(0, np.nan)
    rsv = ((d['Close'] - low_min9) / denom * 100).fillna(50)
    
    k_vals = []
    d_vals = []
    curr_k = 50.0
    curr_d = 50.0
    for r in rsv:
        curr_k = (2.0 / 3.0) * curr_k + (1.0 / 3.0) * r
        curr_d = (2.0 / 3.0) * curr_d + (1.0 / 3.0) * curr_k
        k_vals.append(curr_k)
        d_vals.append(curr_d)
    d['K'] = k_vals
    d['D'] = d_vals

    # RSI (14) - Wilder's smoothing or standard SMA
    delta = d['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    d['RSI'] = 100.0 - (100.0 / (1.0 + rs))
    d['RSI'] = d['RSI'].fillna(50)

    # MACD (12, 26, 9)
    ema12 = d['Close'].ewm(span=12, adjust=False).mean()
    ema26 = d['Close'].ewm(span=26, adjust=False).mean()
    d['DIF'] = ema12 - ema26
    d['MACD_SIGNAL'] = d['DIF'].ewm(span=9, adjust=False).mean()
    d['MACD_HIST'] = (d['DIF'] - d['MACD_SIGNAL']) * 2  # OSC 柱狀體

    # Bollinger Bands (20, 2)
    bb_std = d['Close'].rolling(20).std()
    d['BB_MID'] = d['MA20']
    d['BB_UPPER'] = d['BB_MID'] + (2.0 * bb_std)
    d['BB_LOWER'] = d['BB_MID'] - (2.0 * bb_std)
    bb_range = (d['BB_UPPER'] - d['BB_LOWER']).replace(0, np.nan)
    d['BB_PCT_B'] = ((d['Close'] - d['BB_LOWER']) / bb_range).fillna(0.5)

    # 乖離率 (BIAS %)
    d['BIAS20'] = ((d['Close'] - d['MA20']) / d['MA20'].replace(0, np.nan)) * 100.0
    d['BIAS60'] = ((d['Close'] - d['MA60']) / d['MA60'].replace(0, np.nan)) * 100.0

    # ATR (14) - Average True Range
    h_l = d['High'] - d['Low']
    h_pc = (d['High'] - d['Close'].shift(1)).abs()
    l_pc = (d['Low'] - d['Close'].shift(1)).abs()
    tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
    d['ATR'] = tr.rolling(14).mean().fillna(tr.mean())

    return d

def evaluate_signals(df: pd.DataFrame, strategy_type: str = "綜合評分模式") -> pd.DataFrame:
    """Generate Buy (1), Hold (0), Sell (-1) signals and multi-factor scores for each row."""
    d = df.copy()
    scores = []
    signals = []
    
    # Calculate row-by-row
    for idx in range(len(d)):
        if idx < 60:
            scores.append(0)
            signals.append(0)
            continue
            
        row = d.iloc[idx]
        prev_row = d.iloc[idx - 1]
        
        score = 0
        
        # 1. 均線趨勢 (Trend Score: -35 to +35)
        # 價格站上月線與季線
        if pd.notna(row['MA20']) and row['Close'] > row['MA20']:
            score += 15
        elif pd.notna(row['MA20']):
            score -= 15
            
        if pd.notna(row['MA60']) and row['Close'] > row['MA60']:
            score += 15
        elif pd.notna(row['MA60']):
            score -= 15
            
        # 月線與季線多頭排列
        if pd.notna(row['MA20']) and pd.notna(row['MA60']):
            if row['MA20'] > row['MA60']:
                score += 5
            else:
                score -= 5
                
        # 2. 動能指標 (Momentum: -35 to +35)
        # KD 交叉與區間
        kd_golden_cross = (prev_row['K'] <= prev_row['D']) and (row['K'] > row['D'])
        kd_death_cross = (prev_row['K'] >= prev_row['D']) and (row['K'] < row['D'])
        
        if kd_golden_cross:
            score += 20 if row['K'] < 40 else 10
        elif kd_death_cross:
            score -= 20 if row['K'] > 60 else -10
        else:
            if row['K'] > row['D']:
                score += 5
            else:
                score -= 5
                
        # MACD 柱狀體
        if pd.notna(row['MACD_HIST']):
            if row['MACD_HIST'] > 0:
                score += 10
                if row['MACD_HIST'] > prev_row['MACD_HIST']:
                    score += 5  # 紅柱放大
            else:
                score -= 10
                if row['MACD_HIST'] < prev_row['MACD_HIST']:
                    score -= 5  # 綠柱放大

        # 3. 擺盪與乖離 (Mean Reversion / Exhaustion: -20 to +20)
        # RSI 狀態
        if row['RSI'] < 30:
            score += 15  # 超賣區反彈契機
        elif row['RSI'] > 75:
            score -= 15  # 超買區獲利回吐風險
            
        # 布林通道 / 乖離率
        if pd.notna(row['BIAS20']):
            if row['BIAS20'] < -4.0:
                score += 10  # 負乖離過大逢低偏多
            elif row['BIAS20'] > 6.0:
                score -= 10  # 正乖離過大防拉回
                
        # 4. 成交量配合 (Volume: -10 to +10)
        if pd.notna(row['VOL_MA5']) and row['Volume'] > row['VOL_MA5']:
            if row['Close'] > prev_row['Close']:
                score += 5   # 出量上攻
            else:
                score -= 5   # 出量下跌
                
        # Bound score between -100 and +100
        score = int(round(max(-100, min(100, score))))
        scores.append(score)
        
        # Strategy-specific Signal Triggering
        if strategy_type == "波段操作模式":
            # 偏重短線均線、KD交叉與MACD轉折
            if (kd_golden_cross or (row['K'] > row['D'] and row['Close'] > row['MA20'])) and row['RSI'] < 70:
                sig = 1
            elif (kd_death_cross or row['Close'] < row['MA20']) and row['RSI'] > 40:
                sig = -1
            else:
                sig = 0
        elif strategy_type == "中長線趨勢模式":
            # 偏重月線、季線排列與關鍵跌破
            if row['Close'] > row['MA60'] and row['MA20'] >= row['MA60'] and row['MACD_HIST'] > -0.2:
                sig = 1
            elif row['Close'] < row['MA60'] or (row['MA20'] < row['MA60'] and row['MACD_HIST'] < 0):
                sig = -1
            else:
                sig = 0
        elif strategy_type == "存股低接模式":
            # 逢低分批加碼：負乖離、RSI超賣、跌破布林下軌
            if (row['BIAS20'] < -2.5 or row['RSI'] < 40 or row['BB_PCT_B'] < 0.2) and row['Close'] > row['MA240'] * 0.95:
                sig = 1
            elif row['BIAS20'] > 5.0 or row['RSI'] > 75:
                sig = -1  # 調節/不追高
            else:
                sig = 0
        else: # 綜合評分模式
            if score >= 35:
                sig = 1
            elif score <= -35:
                sig = -1
            else:
                sig = 0
                
        signals.append(sig)
        
    d['SCORE'] = scores
    d['SIGNAL'] = signals
    
    # Identify distinct signal change points (for charting buy/sell arrows)
    d['SIGNAL_CHANGE'] = d['SIGNAL'].diff().fillna(0)
    
    return d

def get_latest_signal_summary(df: pd.DataFrame, ticker_info: dict, strategy_type: str = "綜合評分模式") -> dict:
    """Analyze the latest row and output detailed trade plan, rating, indicators, and risk alerts."""
    row = df.iloc[-1]
    prev = df.iloc[-2]
    
    score = int(round(float(row['SCORE'])))
    signal = int(row['SIGNAL'])
    price = float(row['Close'])
    atr = float(row['ATR']) if pd.notna(row['ATR']) else price * 0.02
    
    # Determine Rating Label
    if score >= 50:
        label = "🟢 強烈買進 (Strong Buy)"
        status_color = "green"
        action_text = "技術面呈現全面多頭共振，各項指標偏多，適合積極進場佈局。"
    elif score >= 20:
        label = "🟢 偏多買進 / 分批進場 (Buy / Accumulate)"
        status_color = "green"
        action_text = "多方動能佔優，趨勢健康，建議逢拉回分批建倉。"
    elif score >= -19:
        label = "🟡 觀望中立 / 續抱持有 (Hold / Neutral)"
        status_color = "orange"
        action_text = "盤勢處於整理或震盪狀態，無明顯突破訊號，持股者續抱，空手者暫緩觀望。"
    elif score >= -49:
        label = "🔴 偏空調節 / 減碼出場 (Trim / Take Profit)"
        status_color = "red"
        action_text = "指標轉弱或正乖離過大出現回檔訊號，建議調降部位、獲利了結或部分停損。"
    else:
        label = "🔴 強烈賣出 / 空手避險 (Strong Sell / Exit)"
        status_color = "red"
        action_text = "技術面跌破關鍵支撐，均線呈空頭排列，建議出清或嚴格避險。"

    # Suggested Levels (Trade Plan)
    # 停損參考價：月線下緣或 ATR * 1.5
    stop_loss = max(row['MA20'] * 0.98 if pd.notna(row['MA20']) else price * 0.95, price - (1.5 * atr))
    # 停利目標價：布林上軌或目前價 + 2 * ATR
    take_profit = max(row['BB_UPPER'] if pd.notna(row['BB_UPPER']) else price * 1.06, price + (2.0 * atr))
    
    # Specific asset warnings
    sym = ticker_info.get("symbol", "")
    risk_warnings = []
    
    if "00631L" in sym:
        risk_warnings.append("⚠️ **槓桿 ETF (正2) 特別警示**：此標的具有複利耗損與高波動特性。當大盤震盪盤整時易受耗損；建議『順勢交易』，跌破月線或季線時務必果斷減碼停損，切勿長期凹單。")
    if "009800" in sym or "QQQ" in sym:
        risk_warnings.append("💡 **海外科技指數提醒**：此標的追蹤美股那斯達克 100 指數，受美股科技巨頭（Nvidia、Apple、Microsoft）與匯率波動影響較大，注意美股開盤聯動。")
    if "2330" in sym:
        risk_warnings.append("💡 **個股權值特質**：台積電為台股大盤最大火車頭，其位階與外資籌碼方向直接影響指數發展。")

    # Checklist Breakdown
    factors = [
        {
            "category": "月線 (MA20)",
            "value": f"{row['MA20']:.2f}" if pd.notna(row['MA20']) else "N/A",
            "status": "站上月線 (多方控盤)" if row['Close'] > row['MA20'] else "跌破月線 (短線弱勢)",
            "is_bullish": row['Close'] > row['MA20']
        },
        {
            "category": "季線 (MA60 - 生命線)",
            "value": f"{row['MA60']:.2f}" if pd.notna(row['MA60']) else "N/A",
            "status": "站上季線 (中長多格局)" if row['Close'] > row['MA60'] else "季線之下 (中空格局)",
            "is_bullish": row['Close'] > row['MA60']
        },
        {
            "category": "KD 指標 (9, 3, 3)",
            "value": f"K: {row['K']:.1f} | D: {row['D']:.1f}",
            "status": "黃金交叉 / K值高於D" if row['K'] > row['D'] else "死亡交叉 / K值低於D",
            "is_bullish": row['K'] > row['D']
        },
        {
            "category": "RSI 強弱 (14)",
            "value": f"{row['RSI']:.1f}",
            "status": "強勢多頭 (>50)" if row['RSI'] > 50 else ("超跌超賣 (<30)" if row['RSI'] < 30 else "弱勢盤整 (<50)"),
            "is_bullish": row['RSI'] >= 45
        },
        {
            "category": "MACD 柱狀體 (OSC)",
            "value": f"{row['MACD_HIST']:.2f}",
            "status": "紅柱擴大 (多方動能續強)" if row['MACD_HIST'] > 0 and row['MACD_HIST'] >= prev['MACD_HIST'] else ("紅柱收縮" if row['MACD_HIST'] > 0 else "綠柱偏空"),
            "is_bullish": row['MACD_HIST'] > 0
        },
        {
            "category": "月線乖離率 (BIAS20)",
            "value": f"{row['BIAS20']:+.2f}%",
            "status": "短線過熱注意拉回" if row['BIAS20'] > 5 else ("超跌可留意低接" if row['BIAS20'] < -4 else "乖離率正常健康"),
            "is_bullish": -4.0 <= row['BIAS20'] <= 5.0
        }
    ]

    return {
        "score": score,
        "signal": signal,
        "label": label,
        "status_color": status_color,
        "action_text": action_text,
        "current_price": price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_warnings": risk_warnings,
        "factors": factors,
        "strategy_type": strategy_type
    }
