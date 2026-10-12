import json
import os
import datetime
import requests
from typing import Dict, List, Optional

CONFIG_FILE = os.path.join(os.path.dirname(__file__), ".line_config.json")

def load_line_config() -> dict:
    """Load LINE Messaging API settings from config file, environment variables, or st.secrets."""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    uid = os.environ.get("LINE_USER_ID", "")
    url = os.environ.get("DASHBOARD_URL", "") or "https://tw-stock-tracker-klbx9enyxbnwlfs8ztvapa.streamlit.app/"
    
    # Check Streamlit Cloud secrets if available
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            token = token or st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
            uid = uid or st.secrets.get("LINE_USER_ID", "")
            url = url or st.secrets.get("DASHBOARD_URL", "")
    except Exception:
        pass

    notify_env = os.environ.get("NOTIFY_ONLY_ON_SIGNALS", "")
    notify_only_val = notify_env.lower() in ("true", "1", "yes") if notify_env else False
    
    config = {
        "channel_access_token": token,
        "user_id": uid,
        "dashboard_url": url,
        "notify_only_on_signals": notify_only_val,
        "enabled": bool(token and uid)
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if saved.get("channel_access_token"):
                    config["channel_access_token"] = saved["channel_access_token"]
                if saved.get("user_id"):
                    config["user_id"] = saved["user_id"]
                if saved.get("dashboard_url"):
                    config["dashboard_url"] = saved["dashboard_url"]
                if not notify_env:
                    config["notify_only_on_signals"] = saved.get("notify_only_on_signals", False)
                config["enabled"] = saved.get("enabled", True)
        except Exception:
            pass
    return config

def save_line_config(channel_access_token: str, user_id: str, dashboard_url: str = "", notify_only_on_signals: bool = False, enabled: bool = True) -> bool:
    """Save LINE config to local file."""
    config = {
        "channel_access_token": channel_access_token.strip(),
        "user_id": user_id.strip(),
        "dashboard_url": dashboard_url.strip(),
        "notify_only_on_signals": notify_only_on_signals,
        "enabled": enabled
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving line config: {e}")
        return False

def send_line_push_message(text_message: str, channel_access_token: Optional[str] = None, user_id: Optional[str] = None) -> tuple[bool, str]:
    """Send push message via LINE Messaging API."""
    cfg = load_line_config()
    token = channel_access_token or cfg.get("channel_access_token")
    target_id = user_id or cfg.get("user_id")
    
    if not token:
        return False, "缺少 LINE Channel Access Token，請先設定。"
    if not target_id:
        return False, "缺少 LINE User ID，請先設定。"
        
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": target_id,
        "messages": [
            {
                "type": "text",
                "text": text_message
            }
        ]
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            return True, "訊息發送成功！"
        else:
            try:
                err_data = resp.json()
                msg = err_data.get("message", resp.text)
                details = err_data.get("details", [])
                detail_str = "; ".join([d.get("message", "") for d in details]) if details else ""
                return False, f"LINE API 回傳錯誤 ({resp.status_code}): {msg} {detail_str}"
            except Exception:
                return False, f"LINE API 回傳錯誤 ({resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"連線至 LINE 失敗: {str(e)}"

def format_daily_report_message(summaries: List[Dict], dashboard_url: Optional[str] = None) -> str:
    """Format multiple stock/ETF summaries into a sleek LINE push notification text."""
    lines = [
        "📊【台股 ETF & 個股 智能追蹤日報】",
        "━━━━━━━━━━━━━━━"
    ]
    
    has_buy_or_sell = False
    
    for item in summaries:
        sym = item.get("symbol", "")
        name = item.get("name", sym)
        price = item.get("current_price", 0.0)
        chg_pct = item.get("change_pct", 0.0)
        label = item.get("label", "中立觀望")
        score = int(round(float(item.get("score", 0))))
        stop_loss = item.get("stop_loss", 0.0)
        take_profit = item.get("take_profit", 0.0)
        
        # Check if active signal
        if "買進" in label or "賣出" in label or "調節" in label:
            has_buy_or_sell = True
            
        icon = "🟢" if "買進" in label else "🔴" if "賣出" in label or "調節" in label else "🟡"
        chg_str = f"+{chg_pct:.2f}%" if chg_pct > 0 else f"{chg_pct:.2f}%"
        
        clean_lbl = label.replace("🟢", "").replace("🔴", "").replace("🟡", "").split('(')[0].strip()
        lines.append(f"{icon} {name} ({sym})")
        lines.append(f"  現價: ${price:.2f} ({chg_str})")
        lines.append(f"  決策: {clean_lbl} (評分: {score:+d})")
        lines.append(f"  停損: ${stop_loss:.2f} ｜ 停利: ${take_profit:.2f}")
        lines.append("────────────────")
        
    cfg = load_line_config()
    target_url = dashboard_url or cfg.get("dashboard_url") or "https://tw-stock-tracker-klbx9enyxbnwlfs8ztvapa.streamlit.app/"
    lines.append("💡 點此查看即時互動圖表與回測:")
    lines.append(f"👉 {target_url}")
    
    return "\n".join(lines)


def format_signal_alert_message(signal_items: List[Dict], dashboard_url: Optional[str] = None) -> str:
    """Format notification specifically for triggered buy/sell timing events."""
    tz_taipei = datetime.timezone(datetime.timedelta(hours=8))
    now_taipei = datetime.datetime.now(tz_taipei)
    time_str = now_taipei.strftime("%m/%d %H:%M")
    
    hr = now_taipei.hour
    if hr < 11:
        session_tag = "早盤巡檢 10:00"
    elif hr < 13:
        session_tag = "盤中巡檢 12:00"
    elif hr <= 15:
        session_tag = "盤後結算 14:00"
    else:
        session_tag = "即時巡檢"

    lines = [
        "🚨【台股關鍵買賣時機點觸發快報】",
        f"⏰ 巡檢時間：{time_str} ({session_tag})",
        "━━━━━━━━━━━━━━━",
        f"⚡ 系統偵測到以下標的觸發關鍵進出場時機：\n"
    ]
    
    for item in signal_items:
        sym = item.get("symbol", "")
        name = item.get("name", sym)
        price = item.get("current_price", 0.0)
        chg_pct = item.get("change_pct", 0.0)
        label = item.get("label", "")
        action_text = item.get("action_text", "")
        score = int(round(float(item.get("score", 0))))
        stop_loss = item.get("stop_loss", 0.0)
        take_profit = item.get("take_profit", 0.0)
        
        is_buy = "買進" in label
        icon = "🟢" if is_buy else "🔴"
        action_title = "【適合買進 / 進場佈局】" if is_buy else "【建議減碼 / 出場避險】"
        chg_str = f"+{chg_pct:.2f}%" if chg_pct > 0 else f"{chg_pct:.2f}%"
        
        clean_label = label.replace("🟢", "").replace("🔴", "").replace("🟡", "").split('(')[0].strip()
        lines.append(f"{icon} {action_title} {name} ({sym})")
        lines.append(f"  • 現價: ${price:.2f} ({chg_str})")
        lines.append(f"  • 訊號: {clean_label} (評分: {score:+d})")
        if action_text:
            lines.append(f"  • 策略建議: {action_text}")
        lines.append(f"  • 建議價位: 停損 ${stop_loss:.2f} ｜ 停利 ${take_profit:.2f}")
        lines.append("────────────────")
        
    cfg = load_line_config()
    target_url = dashboard_url or cfg.get("dashboard_url") or "https://tw-stock-tracker-klbx9enyxbnwlfs8ztvapa.streamlit.app/"
    lines.append("💡 點此查看即時互動圖表與策略回測:")
    lines.append(f"👉 {target_url}")
    
    return "\n".join(lines)

