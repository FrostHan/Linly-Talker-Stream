# Cloudflare Tunnel + TURN 启动脚本
# 用法： .\scripts\cloudflared\start_tunnel.ps1
#
# 前置：
# 1. cloudflared tunnel create talker      （已完成）
# 2. 把 scripts\cloudflared\config.yml 复制到 %USERPROFILE%\.cloudflared\config.yml
# 3. cloudflared tunnel route dns talker talker.frostnova.uk

[CmdletBinding()]
param(
    [string]$TunnelName = 'talker'
)

$ErrorActionPreference = 'Stop'

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    # 尝试 winget 默认安装位置
    $candidates = @(
        'C:\Program Files (x86)\cloudflared\cloudflared.exe',
        'C:\Program Files\cloudflared\cloudflared.exe'
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) {
            $env:Path = (Split-Path $p) + ';' + $env:Path
            $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
            if ($cf) { break }
        }
    }
}
if (-not $cf) {
    Write-Host "找不到 cloudflared，请先安装：winget install Cloudflare.cloudflared" -ForegroundColor Red
    exit 1
}

$srcConfig = Join-Path $PSScriptRoot 'config.yml'
$dstConfig = Join-Path $env:USERPROFILE '.cloudflared\config.yml'

# 总是用最新的 config.yml 覆盖（仓库里改了立刻生效）
if (Test-Path $srcConfig) {
    $needCopy = -not (Test-Path $dstConfig) -or `
                ((Get-FileHash $srcConfig).Hash -ne (Get-FileHash $dstConfig).Hash)
    if ($needCopy) {
        Write-Host "==> 同步 config.yml -> $dstConfig" -ForegroundColor Cyan
        Copy-Item $srcConfig $dstConfig -Force
    }
} else {
    Write-Host "缺少 $srcConfig" -ForegroundColor Red
    exit 1
}

# 检测 DNS route 是否已存在，未配置就尝试一次（重复运行会失败但不致命）
Write-Host "==> 确保 DNS 路由 talker.frostnova.uk -> $TunnelName" -ForegroundColor Cyan

# cloudflared 会把所有日志写到 stderr，PowerShell 在 $ErrorActionPreference='Stop'
# 模式下会把 stderr 当成致命错误。临时关掉 + 自己解析返回码。
$prevErr = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $dnsOutput = & cloudflared tunnel route dns $TunnelName talker.frostnova.uk 2>&1
    $dnsExit = $LASTEXITCODE
    foreach ($line in $dnsOutput) {
        Write-Host "    $line" -ForegroundColor DarkGray
    }
    if ($dnsExit -ne 0 -and ($dnsOutput -join "`n") -notmatch 'already configured|already exists') {
        Write-Host "    DNS 路由配置失败 (exit=$dnsExit)" -ForegroundColor Yellow
    }
} finally {
    $ErrorActionPreference = $prevErr
}

Write-Host "==> 启动 Tunnel：talker.frostnova.uk -> https://localhost:3000" -ForegroundColor Green
$ErrorActionPreference = 'Continue'   # 别让 INF 日志再次中断
& cloudflared tunnel run $TunnelName
