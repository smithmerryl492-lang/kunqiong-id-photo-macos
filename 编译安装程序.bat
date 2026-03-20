@echo off
chcp 65001 >nul
echo ============================================
echo 鲲穹AI证件照 - 编译安装程序
echo ============================================
echo.
echo 正在编译安装程序，请稍候...
echo 由于文件较大（约245MB），压缩过程可能需要几分钟时间
echo.

"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_setup.iss

if %ERRORLEVEL% == 0 (
    echo.
    echo ✅ 编译成功！
    echo.
    echo 安装程序已生成在: installer_output\鲲穹AI证件照_Setup_v1.0.0.exe
    echo.
    dir installer_output\鲲穹AI证件照_Setup_v1.0.0.exe
    echo.
    pause
) else (
    echo.
    echo ❌ 编译失败，错误代码: %ERRORLEVEL%
    echo.
    pause
)
