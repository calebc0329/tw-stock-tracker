#!/bin/bash
# 啟動台股 ETF 追蹤與決策 Web 應用程式
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "🚀 正在啟動 台股 ETF 智能追蹤與買賣決策系統 (Streamlit)..."
echo "=========================================================="
"$DIR/.venv/bin/streamlit" run app.py
