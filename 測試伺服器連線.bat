@echo off
:: 測試伺服器連線的診斷工具
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ==========================================
echo 伺服器連線診斷工具
echo ==========================================
echo.

:: 設定伺服器資訊
set SERVER_IP=172.16.3.155
set SHARED_FOLDER=GEMINI TEST2
set USERNAME=test
set PASSWORD=0508

echo [1/5] 測試網路連通性...
ping -n 2 %SERVER_IP% >nul 2>&1
if !errorlevel! equ 0 (
    echo ✅ 伺服器 IP 可連通：%SERVER_IP%
) else (
    echo ❌ 無法連通伺服器 IP：%SERVER_IP%
    echo    請檢查：
    echo    - 平板和伺服器是否在同一網路
    echo    - 防火牆是否阻擋連線
    echo    - IP 位址是否正確
    goto :end
)
echo.

echo [2/5] 刪除舊的網路連線...
net use \\%SERVER_IP%\IPC$ /delete /y >nul 2>&1
echo ✅ 已清除舊連線
echo.

echo [3/5] 建立新的網路連線...
net use \\%SERVER_IP%\IPC$ /user:%USERNAME% %PASSWORD%
if !errorlevel! equ 0 (
    echo ✅ 網路連線建立成功
) else (
    echo ❌ 網路連線建立失敗
    echo    請檢查：
    echo    - 帳號密碼是否正確（目前：%USERNAME% / %PASSWORD%）
    echo    - 伺服器是否允許此帳號連線
    echo    - 伺服器的網路共用是否已啟用
    goto :end
)
echo.

echo [4/5] 測試共享資料夾存取...
set "SHARED_PATH=\\%SERVER_IP%\%SHARED_FOLDER%"
dir "%SHARED_PATH%" >nul 2>&1
if !errorlevel! equ 0 (
    echo ✅ 共享資料夾可存取：%SHARED_PATH%
    echo.
    echo [5/5] 列出共享資料夾內容：
    dir "%SHARED_PATH%"
) else (
    echo ❌ 無法存取共享資料夾：%SHARED_PATH%
    echo.
    echo 請檢查：
    echo - 共享資料夾名稱是否正確（目前：%SHARED_FOLDER%）
    echo - 共享資料夾是否已正確設定權限
    echo - 帳號是否有存取權限
    echo.
    echo 嘗試列出伺服器上的所有共享資料夾：
    net view \\%SERVER_IP%
)
echo.

:end
echo ==========================================
echo 診斷完成
echo ==========================================
echo.
echo 如果以上測試都通過，但系統仍無法連線，請檢查：
echo 1. config.py 中的 SERVER_IP 和 SHARED_FOLDER 設定
echo 2. 啟動系統.bat 中的帳號密碼設定
echo 3. Python 程式是否有權限存取網路路徑
echo.
pause


