#!/usr/bin/env bash
# Script TF - 跨品牌機器人劇本轉換工具（Ubuntu 啟動腳本）
set -e
cd "$(dirname "$0")"

echo
echo " ============================================="
echo "  Script TF - 跨品牌機器人劇本轉換工具"
echo " ============================================="
echo

# ===== 環境變數（依本機 Ollama 已下載的模型調整）=====
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:latest}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

# 檢查 Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "[錯誤] 找不到 python3，請先安裝：sudo apt install python3 python3-venv"
    exit 1
fi

# 建立並啟用虛擬環境（系統缺 python3-venv 時改用 pip --user）
echo "[*] 檢查依賴套件..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    pip install -r requirements.txt -q
elif python3 -m venv venv >/dev/null 2>&1 && [ -f "venv/bin/activate" ]; then
    echo "[*] 已建立虛擬環境 venv/"
    source venv/bin/activate
    pip install -r requirements.txt -q
else
    rm -rf venv
    echo "[*] 系統未安裝 python3-venv，改以 pip --user 安裝依賴"
    pip3 install --user -r requirements.txt -q
fi

# 檢查 Ollama 與模型
if curl -s --max-time 3 "${OLLAMA_BASE_URL}/api/tags" | grep -q "${OLLAMA_MODEL}"; then
    echo "[*] Ollama 已連線，使用模型：${OLLAMA_MODEL}"
else
    echo "[警告] 無法連上 Ollama 或找不到模型 ${OLLAMA_MODEL}，將以基本模式執行。"
fi

# 啟動服務
echo "[*] 啟動服務中..."
echo "[*] 瀏覽器請開啟 http://localhost:7860"
echo
python3 cli.py ui
