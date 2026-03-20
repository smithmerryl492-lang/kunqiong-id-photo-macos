@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== 鲲穹AI证件照 - 打包 EXE（onedir 目录模式） =====
echo.
echo 1. 安装 PyInstaller（若未安装）...
pip install pyinstaller -q
echo.
echo 2. 开始打包（onedir 目录模式、无控制台、含所有模型）...
pyinstaller idphoto_app_onedir.spec
if errorlevel 1 (
    echo 打包失败。
    pause
    exit /b 1
)
echo.
echo 完成。程序在 dist\鲲穹AI证件照\ 目录中：
echo - 主程序：dist\鲲穹AI证件照\鲲穹AI证件照.exe
echo - 其余 DLL/依赖文件同目录
echo 可将整个目录复制到任意电脑运行（保留文件结构）。
pause

