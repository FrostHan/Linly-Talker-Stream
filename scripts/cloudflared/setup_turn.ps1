# 拉取 Cloudflare Realtime TURN 临时凭据并导出到当前 shell 的 ICE_SERVERS_JSON
#
# 用法：
#   . .\scripts\cloudflared\setup_turn.ps1     # 注意前面的点 (dot-source)
#   .\run_all.ps1 -New -SkipSovits
#
# 参数从 scripts\cloudflared\.env 读取（参考 .env.example）
#
# 工作原理：
# - 调 https://rtc.live.cloudflare.com/v1/turn/keys/<id>/credentials/generate
# - 返回的 JSON 里 .iceServers 直接喂给我们的后端 ICE_SERVERS_JSON

[CmdletBinding()]
param(
    [string]$TurnEnvFile = ''
)

# 计算脚本目录（dot-source 时 $PSScriptRoot 在 param 默认表达式里可能为空）
$_scriptDir = if ($PSScriptRoot) {
    $PSScriptRoot
} elseif ($MyInvocation.MyCommand.Path) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    (Get-Location).Path
}

if (-not $TurnEnvFile) {
    $TurnEnvFile = Join-Path $_scriptDir '.env'
}

if (-not (Test-Path $TurnEnvFile)) {
    Write-Host "缺少 $TurnEnvFile，请先复制 .env.example 并填入真实凭据" -ForegroundColor Red
    return
}

# 解析 .env
$envVars = @{}
Get-Content $TurnEnvFile | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$') {
        $envVars[$matches[1]] = $matches[2].Trim('"').Trim("'")
    }
}

$tokenId  = $envVars['TURN_TOKEN_ID']
$apiToken = $envVars['TURN_API_TOKEN']
$ttl      = if ($envVars['TURN_TTL']) { [int]$envVars['TURN_TTL'] } else { 86400 }

if (-not $tokenId -or -not $apiToken -or $tokenId -like 'put-your-*') {
    Write-Host "TURN_TOKEN_ID / TURN_API_TOKEN 未填写" -ForegroundColor Red
    return
}

$uri = "https://rtc.live.cloudflare.com/v1/turn/keys/$tokenId/credentials/generate"
$headers = @{ 'Authorization' = "Bearer $apiToken" }
$body = @{ ttl = $ttl } | ConvertTo-Json -Compress

Write-Host "==> 申请 TURN 凭据 (TTL ${ttl}s)..." -ForegroundColor Cyan
try {
    $resp = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers `
        -ContentType 'application/json' -Body $body -ErrorAction Stop
} catch {
    Write-Host "申请失败：$($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message -ForegroundColor DarkRed }
    return
}

if (-not $resp.iceServers) {
    Write-Host "返回里没有 iceServers：$($resp | ConvertTo-Json -Depth 5)" -ForegroundColor Red
    return
}

# CF 返回的格式是 { urls: [...], username, credential }
# 我们额外把它的 STUN 一并下发
$iceList = @(
    @{ urls = @('stun:stun.cloudflare.com:3478') },
    $resp.iceServers
)

$json = $iceList | ConvertTo-Json -Depth 5 -Compress
$env:ICE_SERVERS_JSON = $json

Write-Host "==> ICE_SERVERS_JSON 已导出到当前 shell：" -ForegroundColor Green
Write-Host ("    " + ($resp.iceServers.urls -join ', '))
$expiresHours = [math]::Round($ttl / 3600, 1)
Write-Host "    凭据有效 $expiresHours 小时；过期后重新 dot-source 本脚本即可" -ForegroundColor DarkGray
