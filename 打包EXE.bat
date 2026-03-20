@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== 鲲穹AI证件照 - 打包 EXE =====
echo.
echo 1. 安装 PyInstaller（若未安装）...
pip install pyinstaller -q
echo.
echo 2. 开始打包（单文件、无控制台、含所有模型）...
pyinstaller idphoto_app.spec
if errorlevel 1 (
    echo 打包失败。
    pause
    exit /b 1
)
echo.
echo 完成。EXE 在 dist\鲲穹AI证件照.exe
echo 可将该 exe 复制到任意电脑离线运行。
pause
