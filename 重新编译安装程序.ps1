# 鲲穹AI证件照 - 重新编译安装程序
# 本脚本会清理旧文件并重新编译

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 鲲穹AI证件照 - 重新编译安装程序" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 Inno Setup
Write-Host "[1/6] 检查 Inno Setup..." -ForegroundColor Yellow
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
        Write-Host "  ✓ 找到: $path" -ForegroundColor Green
        break
    }
}

if (-not $isccPath) {
    Write-Host "  ✗ 未找到 Inno Setup 编译器!" -ForegroundColor Red
    Write-Host ""
    Write-Host "请先安装 Inno Setup 6:" -ForegroundColor Yellow
    Write-Host "下载地址: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

# 2. 检查源文件
Write-Host "[2/6] 检查源文件..." -ForegroundColor Yellow
$exePath = "dist\鲲穹AI证件照\鲲穹AI证件照.exe"
if (Test-Path $exePath) {
    $exeFile = Get-Item $exePath
    Write-Host "  ✓ 程序文件: $([math]::Round($exeFile.Length / 1MB, 2)) MB" -ForegroundColor Green
} else {
    Write-Host "  ✗ 未找到程序文件: $exePath" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 3. 检查脚本文件
Write-Host "[3/6] 检查安装脚本..." -ForegroundColor Yellow
$issPath = "installer_setup.iss"
if (Test-Path $issPath) {
    Write-Host "  ✓ 脚本文件存在" -ForegroundColor Green
} else {
    Write-Host "  ✗ 未找到脚本文件: $issPath" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 4. 清理旧文件
Write-Host "[4/6] 清理旧的安装程序..." -ForegroundColor Yellow
if (Test-Path "installer_output") {
    $oldFiles = Get-ChildItem "installer_output\*.exe" -ErrorAction SilentlyContinue
    if ($oldFiles) {
        foreach ($file in $oldFiles) {
            Remove-Item $file.FullName -Force
            Write-Host "  ✓ 删除旧文件: $($file.Name)" -ForegroundColor Green
        }
    } else {
        Write-Host "  - 没有旧文件需要清理" -ForegroundColor Gray
    }
} else {
    New-Item -ItemType Directory -Path "installer_output" -Force | Out-Null
    Write-Host "  ✓ 创建输出目录" -ForegroundColor Green
}

# 5. 编译安装程序
Write-Host "[5/6] 开始编译..." -ForegroundColor Yellow
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor Cyan

$fullIssPath = (Resolve-Path $issPath).Path
$process = Start-Process -FilePath $isccPath -ArgumentList "`"$fullIssPath`"" -Wait -PassThru -NoNewWindow

Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host ""

# 6. 验证结果
Write-Host "[6/6] 验证编译结果..." -ForegroundColor Yellow
$installerPath = "installer_output\鲲穹AI证件照_Setup_v1.0.0.exe"

if ($process.ExitCode -eq 0 -and (Test-Path $installerPath)) {
    $installerFile = Get-Item $installerPath
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "    ✓✓✓ 编译成功! ✓✓✓" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "安装程序信息:" -ForegroundColor Cyan
    Write-Host "  文件名: $($installerFile.Name)" -ForegroundColor Yellow
    Write-Host "  大小: $([math]::Round($installerFile.Length / 1MB, 2)) MB" -ForegroundColor Yellow
    Write-Host "  位置: $($installerFile.FullName)" -ForegroundColor Yellow
    Write-Host "  创建时间: $($installerFile.CreationTime)" -ForegroundColor Yellow
    Write-Host ""
    
    # 打开输出目录
    $choice = Read-Host "是否打开输出目录? (Y/N)"
    if ($choice -eq "Y" -or $choice -eq "y") {
        explorer "installer_output"
    }
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "    ✗✗✗ 编译失败! ✗✗✗" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "错误代码: $($process.ExitCode)" -ForegroundColor Yellow
    Write-Host "请检查上方错误信息" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host ""
Read-Host "按回车键退出"
