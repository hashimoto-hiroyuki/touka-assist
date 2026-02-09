@echo off
chcp 65001 >nul
echo ========================================
echo 糖化アンケート照合システム v2.1
echo ========================================
echo.
echo [v2.1] 質問2「QRコードで回答」チェックボックス対応
echo.

if not exist venv (
    echo 仮想環境が見つかりません。setup.bat を実行してください。
    pause
    exit /b 1
)

.\venv\Scripts\python.exe verify_survey.py %*

echo.
echo 照合HTMLをブラウザで開きます...
start cropped_images\verification.html
pause
