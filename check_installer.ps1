# 检查安装程序是否成功生成
$installerPath = ".\installer_output\鲲穹AI证件照_Setup_v1.0.0.exe"

if (Test-Path $installerPath) {
    $file = Get-Item $installerPath
    Write-Host "✓ 安装程序已成功生成!" -ForegroundColor Green
    Write-Host ""
    Write-Host "文件信息:" -ForegroundColor Cyan
    Write-Host "  路径: $($file.FullName)" -ForegroundColor Yellow
    Write-Host "  大小: $([math]::Round($file.Length / 1MB, 2)) MB" -ForegroundColor Yellow
    Write-Host "  创建时间: $($file.CreationTime)" -ForegroundColor Yellow
    Write-Host "  修改时间: $($file.LastWriteTime)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "安装程序位置: installer_output\鲲穹AI证件照_Setup_v1.0.0.exe" -ForegroundColor Green
} else {
    Write-Host "✗ 未找到安装程序文件" -ForegroundColor Red
    Write-Host "预期路径: $installerPath" -ForegroundColor Yellow
}
