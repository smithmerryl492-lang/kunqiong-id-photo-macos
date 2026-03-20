@echo off
chcp 65001 >nul
echo ========================================
echo 清除 Windows 图标缓存
echo ========================================
echo.

echo 正在清除图标缓存...
echo.

:: 结束 Windows 资源管理器
taskkill /f /im explorer.exe >nul 2>&1

:: 删除图标缓存文件
echo 删除缓存文件...
del /f /s /q /a "%localappdata%\IconCache.db" >nul 2>&1
del /f /s /q /a "%localappdata%\Microsoft\Windows\Explorer\iconcache_*.db" >nul 2>&1
del /f /s /q /a "%localappdata%\Microsoft\Windows\Explorer\thumbcache_*.db" >nul 2>&1

:: 重启 Windows 资源管理器
echo 重启资源管理器...
start explorer.exe

echo.
echo ========================================
echo ✓ 图标缓存已清除!
echo ========================================
echo.
echo 请重新打开文件夹查看安装程序图标
echo.
pause
