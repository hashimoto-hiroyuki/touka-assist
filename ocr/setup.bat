@echo off
chcp 65001 >nul
echo ========================================
echo 糖化アンケート照合システム - セットアップ
echo ========================================
echo.

if exist venv (
    echo 仮想環境が既に存在します。
) else (
    echo Python仮想環境を作成中...
    python -m venv venv
)

echo パッケージをインストール中...
.\venv\Scripts\pip.exe install -r requirements.txt

echo.
echo セットアップ完了!
echo.
echo 次のステップ:
echo   1. Scan Data フォルダにPDFを配置
echo   2. start_verification.bat をダブルクリック
echo.
pause
