@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ==========================================
echo 正在自動建立連線 (IPC$)...
echo ==========================================
echo.

set SERVER_IP=172.16.3.155
set SHARED_FOLDER=GEMINI TEST2
set USERNAME=test
set PASSWORD=0508

echo [1/4] 測試網路連通性...
ping -n 2 %SERVER_IP% >nul 2>&1
if !errorlevel! equ 0 (
    echo 伺服器 IP 可連通：%SERVER_IP%
) else (
    echo 無法連通伺服器 IP：%SERVER_IP%
    echo 將嘗試繼續連線...
)
echo.

echo [2/4] 刪除舊的網路連線...
net use \\%SERVER_IP%\IPC$ /delete /y >nul 2>&1
timeout /t 1 /nobreak >nul 2>&1

echo [3/4] 建立新的網路連線...
set RETRY_COUNT=1
set MAX_RETRIES=3

:retry_loop
echo 嘗試 !RETRY_COUNT!/!MAX_RETRIES!: 正在建立連線...

net use \\%SERVER_IP%\IPC$ /user:%USERNAME% %PASSWORD% /persistent:yes

if !errorlevel! equ 0 (
    echo 網路連線建立成功！
    goto :test_share
)

if !RETRY_COUNT! geq !MAX_RETRIES! (
    echo 網路連線建立失敗！
    echo 已嘗試 !MAX_RETRIES! 次仍無法連接。
    echo.
    echo 請檢查：
    echo - 帳號密碼是否正確（目前：%USERNAME% / %PASSWORD%）
    echo - 伺服器是否允許此帳號連線
    echo - 伺服器的網路共用是否已啟用
    echo.
    goto :start_app
)

echo 連線失敗，等待 3 秒後重試...
timeout /t 3 /nobreak >nul 2>&1
set /a RETRY_COUNT+=1
goto :retry_loop

:test_share
echo [4/4] 測試共享資料夾存取...
timeout /t 2 /nobreak >nul 2>&1

set "SHARED_PATH=\\%SERVER_IP%\%SHARED_FOLDER%"
dir "%SHARED_PATH%" >nul 2>&1
if !errorlevel! equ 0 (
    echo 共享資料夾可存取：%SHARED_PATH%
    echo.
    echo ==========================================
    echo 連線完成！所有測試通過。
    echo ==========================================
) else (
    echo 無法存取共享資料夾：%SHARED_PATH%
    echo 警告：將嘗試以單機模式啟動。
)
echo.

:start_app
echo ==========================================
echo 正在啟動產線系統（重構版）...
echo ==========================================
echo.

cd /d "%~dp0"
streamlit run main_refactored.py

pause
