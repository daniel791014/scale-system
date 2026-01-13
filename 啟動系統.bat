@echo off
:: 設定編碼為 UTF-8（靜默執行，避免顯示訊息）
chcp 65001 >nul 2>&1

:: 啟用延遲變數擴展（避免環境變數解析問題）
setlocal enabledelayedexpansion

:: 清除可能導致問題的 PATH 環境變數中的無效項目
:: （這可以避免某些亂碼錯誤訊息）

echo ==========================================
echo 正在自動建立連線 (IPC$)...
echo ==========================================

:: 1. 先刪除舊連線 (避免卡住，所有輸出重定向)
net use \\172.16.3.155\IPC$ /delete /y >nul 2>&1

:: 2. 建立新連線 (請確認帳號是 test 密碼是 0508，所有輸出重定向)
net use \\172.16.3.155\IPC$ /user:test 0508 >nul 2>&1

if !errorlevel! equ 0 (
    echo 連線成功！伺服器已掛載。
    :: 測試共享資料夾是否可存取
    timeout /t 1 /nobreak >nul 2>&1
    dir "\\172.16.3.155\GEMINI TEST2" >nul 2>&1
    if !errorlevel! equ 0 (
        echo 共享資料夾連線確認成功。
    ) else (
        echo 警告：無法存取共享資料夾，將使用單機模式。
    )
) else (
    echo 連線失敗！將嘗試以單機模式啟動...
)

echo.
echo 正在啟動產線系統（重構版）...

:: 切換到批次檔所在目錄
cd /d "%~dp0"

:: 啟動 Streamlit
streamlit run main_refactored.py

pause