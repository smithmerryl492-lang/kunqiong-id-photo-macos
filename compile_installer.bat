@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo Compiling Installer...
echo ========================================
echo.

:: Try different possible paths for Inno Setup
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
if exist "C:\Program Files\Inno Setup 5\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 5\ISCC.exe"

if "%ISCC%"=="" (
    echo [ERROR] Inno Setup not found!
    echo Please install Inno Setup from: https://jrsoftware.org/isdl.php
    exit /b 1
)

echo Found Inno Setup: %ISCC%
echo.

:: Check if source files exist
if not exist "dist\鲲穹AI证件照\鲲穹AI证件照.exe" (
    echo [ERROR] Source files not found in dist\鲲穹AI证件照
    exit /b 1
)

echo Compiling...
echo.

"%ISCC%" "%~dp0installer_setup.iss"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Compilation successful!
    echo ========================================
    echo.
    echo Output: installer_output folder
    if exist "installer_output" explorer "installer_output"
) else (
    echo.
    echo [ERROR] Compilation failed with code: %ERRORLEVEL%
)
