# 检查 Inno Setup 中文语言文件
$innoPath = "C:\Program Files (x86)\Inno Setup 6"

Write-Host "检查 Inno Setup 安装目录..." -ForegroundColor Cyan
if (Test-Path $innoPath) {
    Write-Host "找到 Inno Setup: $innoPath" -ForegroundColor Green
} else {
    Write-Host "未找到 Inno Setup" -ForegroundColor Red
    exit
}

Write-Host "`n查找语言文件..." -ForegroundColor Cyan
$langPath = Join-Path $innoPath "Languages"
if (Test-Path $langPath) {
    Write-Host "语言文件夹: $langPath" -ForegroundColor Green
    $langFiles = Get-ChildItem $langPath -Filter "*.isl"
    Write-Host "`n可用的语言文件:" -ForegroundColor Yellow
    foreach ($file in $langFiles) {
        Write-Host "  - $($file.Name)"
    }
    
    # 检查中文语言文件
    $chineseFiles = $langFiles | Where-Object { $_.Name -like "*Chinese*" }
    if ($chineseFiles) {
        Write-Host "`n找到中文语言文件:" -ForegroundColor Green
        foreach ($file in $chineseFiles) {
            Write-Host "  ✓ $($file.FullName)" -ForegroundColor Green
        }
    } else {
        Write-Host "`n未找到中文语言文件" -ForegroundColor Red
        Write-Host "请从 Inno Setup 官网下载中文语言包:" -ForegroundColor Yellow
        Write-Host "https://jrsoftware.org/files/istrans/" -ForegroundColor Cyan
    }
} else {
    Write-Host "未找到语言文件夹" -ForegroundColor Red
}
