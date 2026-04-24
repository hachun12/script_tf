@echo off
title Script TF - 跨品牌機器人劇本轉換工具
cd /d "%~dp0"

echo.
echo  =============================================
echo   Script TF - 跨品牌機器人劇本轉換工具
echo  =============================================
echo.

:: 檢查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python，請先安裝 Python 3.10 以上版本。
    echo  下載網址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 啟動虛擬環境（如果存在）
if exist "venv\Scripts\activate.bat" (
    echo [*] 啟用虛擬環境...
    call venv\Scripts\activate.bat
)

:: 安裝依賴（首次執行或有更新時）
echo [*] 檢查依賴套件...
pip install -r requirements.txt -q

:: 啟動服務
echo [*] 啟動服務中...
echo [*] 瀏覽器請開啟 http://localhost:7860
echo.
start "" http://localhost:7860
python cli.py ui

pause
