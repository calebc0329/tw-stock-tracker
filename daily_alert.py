#!/usr/bin/env python3
"""
Daily Market Alert Script for Taiwan ETF & Stock Tracker.
Runs after market close (e.g. 14:00) to push updates to LINE Messaging API.
"""
import sys
import os

# Add script directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import fetch_ticker_data, DEFAULT_TICKERS
from strategy import calculate_indicators, evaluate_signals, get_latest_signal_summary
from line_notifier import load_line_config, send_line_push_message, format_daily_report_message, format_signal_alert_message

DEFAULT_MONITOR_LIST = ["0050.TW", "009800.TW", "2330.TW", "00631L.TW", "2454.TW", "2317.TW"]

def main():
    cfg = load_line_config()
    if not cfg.get("channel_access_token") or not cfg.get("user_id"):
        print("[!] 尚未設定 LINE Channel Access Token 或 User ID。請先透過 Web 介面或 .line_config.json 進行設定。")
        sys.exit(1)
        
    symbols = cfg.get("symbols", DEFAULT_MONITOR_LIST)
    print(f"[*] 開始抓取監控清單行情數據: {symbols}")
    summaries = []
    
    for sym in symbols:
        try:
            df, meta, err = fetch_ticker_data(sym, period="1y")
            if err or df is None or df.empty:
                print(f"[-] 抓取 {sym} 失敗: {err}")
                continue
                
            df_ind = calculate_indicators(df)
            df_scored = evaluate_signals(df_ind, strategy_type="綜合評分模式")
            summary = get_latest_signal_summary(df_scored, meta, strategy_type="綜合評分模式")
            
            summaries.append({
                "symbol": sym,
                "name": meta["name"],
                "current_price": meta["current_price"],
                "change_pct": meta["change_pct"],
                "label": summary["label"],
                "score": summary["score"],
                "action_text": summary.get("action_text", ""),
                "stop_loss": summary["stop_loss"],
                "take_profit": summary["take_profit"]
            })
            print(f"[+] {meta['name']} ({sym}): 現價 {meta['current_price']:.2f}, 訊號: {summary['label']}")
        except Exception as e:
            print(f"[-] 處理 {sym} 時發生錯誤: {e}")
            
    if not summaries:
        print("[-] 無可用數據，取消發送。")
        sys.exit(1)
        
    # Check if notify_only_on_signals is enabled
    if cfg.get("notify_only_on_signals", False):
        actionable_signals = [s for s in summaries if "買進" in s["label"] or "賣出" in s["label"] or "調節" in s["label"]]
        if not actionable_signals:
            print("[*] 設定為『僅有買賣時機點才推播』，今日所有標的皆處於觀望持有狀態，無關鍵訊號，靜默結束。")
            sys.exit(0)
        print(f"[+] 發現 {len(actionable_signals)} 檔標的觸發買賣訊號，準備發送專屬時機快報！")
        msg = format_signal_alert_message(actionable_signals)
    else:
        msg = format_daily_report_message(summaries)
    print("[*] 正在推播至 LINE...")
    ok, res_msg = send_line_push_message(msg)
    if ok:
        print("[✓] 成功推播訊息至 LINE！")
    else:
        print(f"[X] LINE 推播失敗: {res_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
