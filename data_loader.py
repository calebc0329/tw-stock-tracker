import json
import os
import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime

# Load full Taiwan stock database (TWSE + TPEx, 2,000+ stocks)
TW_STOCK_MAP_FILE = os.path.join(os.path.dirname(__file__), "tw_stock_names.json")
TW_STOCKS_DB = {}
if os.path.exists(TW_STOCK_MAP_FILE):
    try:
        with open(TW_STOCK_MAP_FILE, "r", encoding="utf-8") as f:
            TW_STOCKS_DB = json.load(f)
    except Exception:
        pass

# Default Taiwan & US ETFs/Stocks
DEFAULT_TICKERS = {
    # 核心指定標的
    "0050.TW": {"name": "元大台灣50", "category": "🔥 核心追蹤", "type": "大盤核心 ETF", "desc": "追蹤台灣市值前 50 大企業，台股最具代表性 ETF"},
    "009800.TW": {"name": "中信納斯達克", "category": "🔥 核心追蹤", "type": "海外科技成長 ETF", "desc": "追蹤美國那斯達克 100 指數，涵蓋科技巨頭"},
    "2330.TW": {"name": "台積電 (TSMC)", "category": "🔥 核心追蹤", "type": "權值半導體龍頭", "desc": "全球晶圓代工龍頭，台股最大權值核心"},
    "00631L.TW": {"name": "元大台灣50正2", "category": "🔥 核心追蹤", "type": "槓桿型 ETF (2X)", "desc": "每日追蹤台灣50指數之單日正向2倍報酬，波動劇烈"},

    # AI & 科技半導體熱門個股
    "2454.TW": {"name": "聯發科 (MediaTek)", "category": "🚀 科技半導體個股", "type": "IC設計龍頭", "desc": "全球智慧型手機與邊緣 AI 運算晶片設計龍頭"},
    "2317.TW": {"name": "鴻海 (Foxconn)", "category": "🚀 科技半導體個股", "type": "EMS代工龍頭", "desc": "全球電子代工巨擘，AI伺服器與電動車重點佈局"},
    "2382.TW": {"name": "廣達 (Quanta)", "category": "🚀 科技半導體個股", "type": "AI伺服器代工龍頭", "desc": "全球筆電與雲端 AI 伺服器一線代工領導大廠"},
    "2308.TW": {"name": "台達電 (Delta)", "category": "🚀 科技半導體個股", "type": "電源/散熱管理龍頭", "desc": "全球交換式電源供應器龍頭、AI資料中心散熱方案"},
    "3231.TW": {"name": "緯創 (Wistron)", "category": "🚀 科技半導體個股", "type": "AI伺服器代工", "desc": "AI 伺服器主機板與運算模組關鍵供應商"},
    "2303.TW": {"name": "聯電 (UMC)", "category": "🚀 科技半導體個股", "type": "晶圓代工二哥", "desc": "全球成熟製程晶圓代工領導廠商，具高殖利率特性"},
    "3443.TW": {"name": "創意 (Global Unichip)", "category": "🚀 科技半導體個股", "type": "客製化晶片 (ASIC)", "desc": "台積電旗下 ASIC 設計服務龍頭"},

    # 金融權值股 (穩健定存存股族最愛)
    "2881.TW": {"name": "富邦金 (Fubon)", "category": "🏦 金融權值存股", "type": "金控股王", "desc": "壽險、銀行與證券綜合經營，獲利表現長年居冠"},
    "2882.TW": {"name": "國泰金 (Cathay)", "category": "🏦 金融權值存股", "type": "金控權值核心", "desc": "台灣資產規模頂尖壽險金控，外資資產配置標的"},
    "2886.TW": {"name": "兆豐金 (Mega)", "category": "🏦 金融權值存股", "type": "官股金控龍頭", "desc": "外匯業務優勢、殖利率與配息穩健之官股模範生"},
    "2891.TW": {"name": "中信金 (CTBC)", "category": "🏦 金融權值存股", "type": "民營金控龍頭", "desc": "消金與財富管理龍頭，現金股利殖利率高吸引力"},
    "2884.TW": {"name": "玉山金 (E.SUN)", "category": "🏦 金融權值存股", "type": "民營優質金控", "desc": "數位金融與穩健配息形象，小資存股族首選"},

    # 傳產、重電與航運人氣股
    "2603.TW": {"name": "長榮 (Evergreen)", "category": "🚢 航運重電人氣股", "type": "貨櫃航運龍頭", "desc": "全球航運前茅，高現金殖利率與波段動能股"},
    "1519.TW": {"name": "華城 (Fortune)", "category": "🚢 航運重電人氣股", "type": "重電變壓器龍頭", "desc": "受惠美國電網升級與綠能轉型強勁外銷訂單"},

    # 熱門高股息 ETF
    "00878.TW": {"name": "國泰永續高股息", "category": "💰 熱門高股息 ETF", "type": "高股息 ETF", "desc": "百萬股民高人氣、訴求 ESG 篩選與穩定季配息"},
    "00919.TW": {"name": "群益台灣精選高息", "category": "💰 熱門高股息 ETF", "type": "高股息 ETF", "desc": "鎖定精選高股利宣告個股，高殖利率代表"},
    "00929.TW": {"name": "復華台灣科技優息", "category": "💰 熱門高股息 ETF", "type": "科技高股息 ETF", "desc": "首檔月配息科技優息 ETF，科技成長與收息並重"},
    "0056.TW":  {"name": "元大高股息", "category": "💰 熱門高股息 ETF", "type": "高股息始祖 ETF", "desc": "台股歷史最悠久高股息 ETF，長期定存口碑佳"},

    # 美股科技指標
    "NVDA": {"name": "NVIDIA (輝達)", "category": "🇺🇸 美股科技巨頭", "type": "全球 AI 運算霸主", "desc": "GPU、CUDA 生態系與全球加速運算核心霸主 (美金計價)"},
    "TSM":  {"name": "台積電 ADR (美股)", "category": "🇺🇸 美股科技巨頭", "type": "美股 ADR", "desc": "台積電在美國紐約證交所掛牌之存託憑證 (美金計價)"},
    "QQQ":  {"name": "Invesco QQQ", "category": "🇺🇸 美股科技巨頭", "type": "納斯達克 100", "desc": "直接追蹤美國那斯達克 100 指數 (美金計價)"},
    "VOO":  {"name": "Vanguard S&P 500", "category": "🇺🇸 美股科技巨頭", "type": "標普 500 指數", "desc": "美國標普 500 指數 ETF，長線資產配置核心"}
}

def normalize_ticker(symbol: str) -> str:
    """Normalize user input symbol or name to yfinance format (.TW or .TWO)."""
    s = symbol.strip().upper()
    if s in DEFAULT_TICKERS:
        return s
    if s in TW_STOCKS_DB:
        return s
        
    # Check if raw code matches in TW_STOCKS_DB (e.g. "3293" -> "3293.TWO", "2609" -> "2609.TW")
    raw_code = s.split(".")[0]
    for full_sym, info in TW_STOCKS_DB.items():
        if info.get("code") == raw_code:
            return full_sym
            
    # Check if user typed Chinese name (e.g. "陽明", "鈊象", "長榮航")
    for full_sym, info in TW_STOCKS_DB.items():
        name_val = info.get("name", "")
        if s == name_val or (len(s) >= 2 and (s in name_val or name_val in s)):
            return full_sym
            
    # If 4-6 digits or ends with L/R without extension, default to .TW
    if s.isdigit() or (s[:-1].isdigit() and s[-1] in ['L', 'R']):
        return f"{s}.TW"
    return s

@st.cache_data(ttl=600)
def fetch_ticker_data(symbol: str, period: str = "2y"):
    """Fetch historical OHLCV data and basic info from yfinance with cache."""
    try:
        norm_sym = normalize_ticker(symbol)
        tk = yf.Ticker(norm_sym)
        df = tk.history(period=period)
        
        # If .TW failed and it's a 4-5 digit stock, try .TWO (Taipei Exchange / OTC)
        if (df is None or df.empty) and norm_sym.endswith(".TW"):
            alt_sym = norm_sym.replace(".TW", ".TWO")
            tk_alt = yf.Ticker(alt_sym)
            df_alt = tk_alt.history(period=period)
            if df_alt is not None and not df_alt.empty:
                norm_sym = alt_sym
                df = df_alt
                tk = tk_alt
                
        if df is None or df.empty:
            return None, None, f"找不到標的代碼 {symbol} 的數據，請確認代碼是否正確。"
            
        # Clean dataframe
        df.index = pd.to_datetime(df.index)
        df = df[~df.index.duplicated(keep='first')]
        df = df.dropna(subset=['Close'])
        
        # Get info
        try:
            info = tk.fast_info
            curr_price = float(info.last_price) if hasattr(info, 'last_price') and info.last_price else float(df['Close'].iloc[-1])
            prev_close = float(info.previous_close) if hasattr(info, 'previous_close') and info.previous_close else float(df['Close'].iloc[-2] if len(df) > 1 else curr_price)
        except Exception:
            curr_price = float(df['Close'].iloc[-1])
            prev_close = float(df['Close'].iloc[-2] if len(df) > 1 else curr_price)
            
        stock_db_entry = TW_STOCKS_DB.get(norm_sym, {})
        def_entry = DEFAULT_TICKERS.get(norm_sym, {})
        
        display_name = def_entry.get("name") or stock_db_entry.get("name") or norm_sym
        display_type = def_entry.get("type") or (stock_db_entry.get("market", "") + "個股" if stock_db_entry else "股票 / ETF")
        display_desc = def_entry.get("desc") or f"全台股自由查詢標的 ({norm_sym})"
        
        meta = {
            "symbol": norm_sym,
            "raw_symbol": symbol,
            "name": display_name,
            "type": display_type,
            "desc": display_desc,
            "current_price": curr_price,
            "prev_close": prev_close,
            "change": curr_price - prev_close,
            "change_pct": ((curr_price - prev_close) / prev_close) * 100 if prev_close else 0.0,
            "last_date": df.index[-1].strftime('%Y-%m-%d')
        }
        return df, meta, None
    except Exception as e:
        return None, None, f"獲取標的數據失敗: {str(e)}"
