@echo off
chcp 65001 >nul
echo ========================================
echo 直接编译安装程序
echo ========================================
echo.

set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
    echo 错误: 未找到 ISCC.exe
    pause
    exit /b 1
)

echo 开始编译...
echo.

"%ISCC%" "%~dp0installer_setup.iss"

echo.
echo 编译完成，退出代码: %ERRORLEVEL%
echo.

if exist "%~dp0installer_output\鲲穹AI证件照_Setup_v1.0.0.exe" (
    echo 成功! 安装程序已生成
    dir "%~dp0installer_output\*.exe"
) else (
    echo 失败! 未找到输出文件
)

pause
