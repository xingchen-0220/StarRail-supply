$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "清理旧构建..."
Remove-Item build, dist -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "开始打包（首次约 2-5 分钟）..."
python -m PyInstaller build.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "打包失败" }
Write-Host "构建完成：dist\星穹签到助手.exe"
