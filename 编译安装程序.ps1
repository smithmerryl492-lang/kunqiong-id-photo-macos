# 鲲穹AI证件照 - 安装程序编译脚本 (PowerShell)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "鲲穹AI证件照 - 安装程序编译脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 查找 Inno Setup 编译器
$possiblePaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    "C:\Program Files\Inno Setup 5\ISCC.exe"
)

$isccPath = $null
foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $isccPath = $path
        break
    }
}

if (-not $isccPath) {
    Write-Host "[错误] 未找到 Inno Setup 编译器!" -ForegroundColor Red
    Write-Host ""
    Write-Host "请先安装 Inno Setup:" -ForegroundColor Yellow
    Write-Host "下载地址: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "[✓] 找到 Inno Setup: $isccPath" -ForegroundColor Green

# 检查源文件
$exePath = "dist\鲲穹AI证件照\鲲穹AI证件照.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "[错误] 未找到程序文件: $exePath" -ForegroundColor Red
    Write-Host "请确保 dist\鲲穹AI证件照 目录存在且包含程序文件" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "[✓] 找到程序文件" -ForegroundColor Green

# 检查脚本文件
$issPath = "installer_setup.iss"
if (-not (Test-Path $issPath)) {
    Write-Host "[错误] 未找到安装脚本文件: $issPath" -ForegroundColor Red
    Write-Host ""
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "[✓] 找到安装脚本" -ForegroundColor Green
Write-Host ""

# 编译安装程序
Write-Host "正在编译安装程序..." -ForegroundColor Cyan
Write-Host ""

$fullIssPath = (Resolve-Path $issPath).Path
& $isccPath $fullIssPath

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "✓ 编译完成!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "安装程序已生成在 installer_output 文件夹中" -ForegroundColor Yellow
    Write-Host ""
    
    # 打开输出目录
    if (Test-Path "installer_output") {
        $choice = Read-Host "是否打开输出目录? (Y/N)"
        if ($choice -eq "Y" -or $choice -eq "y") {
            explorer "installer_output"
        }
    }
} else {
    Write-Host ""
    Write-Host "[错误] 编译失败! 错误代码: $LASTEXITCODE" -ForegroundColor Red
    Write-Host "请检查上方错误信息并修正后重试" -ForegroundColor Yellow
    Write-Host ""
}

Read-Host "按回车键退出"
