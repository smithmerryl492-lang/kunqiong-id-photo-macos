@echo off
chcp 65001 >nul
echo ========================================
echo 清除 Python 缓存
echo ========================================
echo.

echo 正在删除 __pycache__ 文件夹...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo 正在删除 .pyc 文件...
del /s /q *.pyc >nul 2>&1

echo.
echo ========================================
echo ✓ 缓存已清除!
echo ========================================
echo.
echo 现在可以重新运行程序了
echo.
pause
