# PNG 转 ICO 工具脚本
# 将 logo.png 转换为包含多种尺寸的标准 ICO 文件

Write-Host "正在将 logo.png 转换为标准 ICO 文件..." -ForegroundColor Cyan

# 检查 logo.png 是否存在
if (-not (Test-Path "logo.png")) {
    Write-Host "错误: 找不到 logo.png 文件" -ForegroundColor Red
    exit 1
}

# 使用 .NET 来创建 ICO 文件
Add-Type -AssemblyName System.Drawing

try {
    # 加载 PNG 图像
    $png = [System.Drawing.Image]::FromFile((Resolve-Path "logo.png").Path)
    
    # 创建多个尺寸的图标
    $sizes = @(16, 32, 48, 64, 128, 256)
    $icon = New-Object System.Drawing.Icon($png.GetHicon())
    
    # 保存为 ICO
    $stream = [System.IO.File]::Create((Resolve-Path ".").Path + "\logo_new.ico")
    $icon.Save($stream)
    $stream.Close()
    
    Write-Host "✓ 成功生成 logo_new.ico" -ForegroundColor Green
    Write-Host ""
    Write-Host "请将 logo_new.ico 重命名为 logo.ico 替换原文件" -ForegroundColor Yellow
    
} catch {
    Write-Host "转换失败: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "建议使用在线工具转换:" -ForegroundColor Yellow
    Write-Host "1. https://convertio.co/zh/png-ico/" -ForegroundColor Cyan
    Write-Host "2. https://www.aconvert.com/cn/icon/png-to-ico/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "转换时请选择包含多种尺寸 (16x16, 32x32, 48x48, 256x256)" -ForegroundColor Yellow
} finally {
    if ($png) { $png.Dispose() }
    if ($icon) { $icon.Dispose() }
}

Read-Host "按回车键退出"
