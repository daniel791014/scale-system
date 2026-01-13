@echo off
chcp 65001
echo ==========================================
echo 🔧 平板 COM Port 設定工具
echo ==========================================
echo.

set /p LINE_NUM="請輸入產線編號 (1/2/3/4): "
set /p COM_PORT="請輸入該平板連接的 COM Port (例如 COM3/COM4/COM5/COM6): "

echo.
echo 正在修改 config.py...
echo 產線: Line %LINE_NUM%
echo COM Port: %COM_PORT%

:: 使用 PowerShell 來修改檔案
powershell -Command "(Get-Content config.py) -replace 'SCALE_PORT = \".*\"', 'SCALE_PORT = \"%COM_PORT%\"' | Set-Content config.py"

echo.
echo ✅ 設定完成！
echo.
echo 請確認 config.py 中的設定是否正確：
findstr "SCALE_PORT" config.py
echo.
pause



