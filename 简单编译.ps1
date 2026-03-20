# 直接编译 - 最简化版本
$ErrorActionPreference = "Continue"

Write-Host "========================================"
Write-Host "开始编译安装程序"
Write-Host "========================================"
Write-Host ""

$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$script = "$PSScriptRoot\installer_setup.iss"

if (-not (Test-Path $iscc)) {
    Write-Host "错误: 未找到 $iscc" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $script)) {
    Write-Host "错误: 未找到 $script" -ForegroundColor Red
    exit 1
}

Write-Host "编译器: $iscc"
Write-Host "脚本: $script"
Write-Host ""
Write-Host "正在编译..."
Write-Host ""

# 直接调用，显示所有输出
& $iscc $script

Write-Host ""
Write-Host "退出代码: $LASTEXITCODE"
Write-Host ""

# 检查结果
$output = "$PSScriptRoot\installer_output\鲲穹AI证件照_Setup_v1.0.0.exe"
if (Test-Path $output) {
    $file = Get-Item $output
    Write-Host "成功!" -ForegroundColor Green
    Write-Host "文件: $($file.Name)"
    Write-Host "大小: $([math]::Round($file.Length/1MB, 2)) MB"
    Write-Host "路径: $($file.FullName)"
} else {
    Write-Host "失败: 未找到输出文件" -ForegroundColor Red
    Write-Host "预期路径: $output"
}
