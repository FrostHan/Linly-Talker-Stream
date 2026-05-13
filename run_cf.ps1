# Linly-Talker-Stream + Cloudflare Tunnel 一键启动脚本（Windows / PowerShell）
#
# 干的事：
#   1. 拉 Cloudflare Realtime TURN 临时凭据 → ICE_SERVERS_JSON
#   2. 设直播间口令 ROOM_PASSWORD
#   3. 在新窗口启动 Backend (8010) + Frontend (3000)
#   4. 在新窗口启动 cloudflared tunnel → talker.frostnova.uk
#
# 用法：
#   .\run_cf.ps1                              # 默认密码 4321
#   .\run_cf.ps1 -RoomPassword 'mypwd'        # 自定义密码
#   .\run_cf.ps1 -New                         # 强制重启已有进程
#   .\run_cf.ps1 -SkipSovits                  # 不启动 GPT-SoVITS（用 EdgeTTS 时用）
#
# 启动后访问：
#   https://talker.frostnova.uk/
# 第一次会弹密码框，输入 -RoomPassword 设置的口令即可。

[CmdletBinding()]
param(
    [string]$Config = 'config_musetalk.yaml',
    [string]$RoomPassword = '4321',
    [string]$TunnelName = 'talker',
    [switch]$SkipSovits = $true,   # 默认跳过；想用 sovits 的话 -SkipSovits:$false
    [switch]$New
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$CondaExe    = "$env:USERPROFILE\anaconda3\Scripts\conda.exe"
$NodeDir     = 'C:\Program Files\nodejs'
$SovitsDir   = 'C:\code\ModelH\third_party\GPT-SoVITS'
$EnvFile     = 'C:\code\ModelH\config\.env'
$TurnEnv     = Join-Path $ProjectRoot 'scripts\cloudflared\.env'

function Test-Port($port) {
    Test-NetConnection -ComputerName 127.0.0.1 -Port $port `
        -InformationLevel Quiet -WarningAction SilentlyContinue
}

function Stop-Port($port, $label) {
    $pids = @()
    try {
        $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty OwningProcess -Unique
    } catch { }
    if (-not $pids -or $pids.Count -eq 0) {
        Write-Host ("    {0,-12} :{1} no listener" -f $label, $port) -ForegroundColor DarkGray
        return
    }
    foreach ($procId in $pids) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            Write-Host ("    {0,-12} :{1} kill PID {2} ({3})" -f $label, $port, $procId, $proc.ProcessName) -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction Stop
        } catch {
            Write-Host ("    {0,-12} :{1} kill PID {2} failed: {3}" -f $label, $port, $procId, $_.Exception.Message) -ForegroundColor Red
        }
    }
    for ($i = 0; $i -lt 20; $i++) {
        if (-not (Test-Port $port)) { return }
        Start-Sleep -Milliseconds 500
    }
}

function Start-NewWindow($title, $command, $extraEnv = $null) {
    # env 变量先 set 到父进程，子 powershell.exe 自动继承（避免把含引号的 JSON
    # 嵌进 -Command 字符串导致引号被吃掉）。启动后再清理父进程的临时变量。
    $touchedKeys = @()
    if ($extraEnv -and $extraEnv.Keys) {
        foreach ($key in $extraEnv.Keys) {
            $rawVal = [string]$extraEnv[$key]
            [Environment]::SetEnvironmentVariable($key, $rawVal, 'Process')
            $touchedKeys += $key
        }
    }
    $full = "`$Host.UI.RawUI.WindowTitle='$title'; $command"
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList '-NoExit', '-Command', $full `
        -WorkingDirectory $ProjectRoot
    # 父 shell 不应该长期持有 LLM key / 密码 / TURN 凭据
    foreach ($k in $touchedKeys) {
        [Environment]::SetEnvironmentVariable($k, $null, 'Process')
    }
}

function Stop-Cloudflared {
    Get-Process -Name cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host ("    {0,-12} kill PID {1}" -f 'Tunnel', $_.Id) -ForegroundColor Yellow
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}

# ============================================================
# 0) -New 模式：清理旧进程
# ============================================================
Write-Host "==> Linly-Talker-Stream + Cloudflare launcher" -ForegroundColor Cyan
Write-Host "    Config:       $Config"
Write-Host "    Tunnel:       $TunnelName -> talker.frostnova.uk"
Write-Host "    Room password: $RoomPassword"
if ($New) { Write-Host "    Mode:         -New (force restart)" -ForegroundColor Magenta }

if ($New) {
    Write-Host ''
    Write-Host '==> Stopping existing services...' -ForegroundColor Magenta
    if (-not $SkipSovits) { Stop-Port 9880 'GPT-SoVITS' }
    Stop-Port 8010 'Backend'
    Stop-Port 3000 'Frontend'
    Stop-Cloudflared
}

# ============================================================
# 1) 拉 Cloudflare TURN 临时凭据
# ============================================================
Write-Host ''
Write-Host '==> [1/4] Fetching Cloudflare TURN credentials...' -ForegroundColor Cyan
if (-not (Test-Path $TurnEnv)) {
    throw "缺少 $TurnEnv，请先复制 .env.example 并填 TURN_TOKEN_ID / TURN_API_TOKEN"
}
. (Join-Path $ProjectRoot 'scripts\cloudflared\setup_turn.ps1') -TurnEnvFile $TurnEnv
if (-not $env:ICE_SERVERS_JSON) {
    throw 'TURN 凭据获取失败，无法继续'
}
$IceJson = $env:ICE_SERVERS_JSON

# ============================================================
# 2) 准备 LLM API key
# ============================================================
Write-Host '==> [2/4] Reading LLM_API_KEY...' -ForegroundColor Cyan
if (-not (Test-Path $EnvFile)) { throw "找不到 $EnvFile" }
$LlmKey = $null
foreach ($line in (Get-Content $EnvFile -ErrorAction Stop)) {
    if ($line -match '^\s*LLM_API_KEY\s*=\s*(.+?)\s*$') {
        $LlmKey = $matches[1].Trim('"').Trim("'")
        break
    }
}
if (-not $LlmKey) {
    throw "无法从 $EnvFile 读取 LLM_API_KEY（请确认行格式：LLM_API_KEY=xxx）"
}
Write-Host ("    OK ({0} chars)" -f $LlmKey.Length) -ForegroundColor DarkGray

# ============================================================
# 3) (可选) GPT-SoVITS
# ============================================================
if ($SkipSovits) {
    Write-Host '==> [3/4] GPT-SoVITS    : skipped' -ForegroundColor Yellow
} elseif (Test-Port 9880) {
    Write-Host '==> [3/4] GPT-SoVITS    : already running on :9880' -ForegroundColor Green
} else {
    Write-Host '==> [3/4] GPT-SoVITS    : starting...' -ForegroundColor Cyan
    $cmd = @"
(& '$CondaExe' shell.powershell hook) | Out-String | Invoke-Expression;
conda activate sovits;
Set-Location '$SovitsDir';
python api_v2.py
"@
    Start-NewWindow 'GPT-SoVITS :9880' $cmd
}

# ============================================================
# 4) Backend (8010)  —— 带 ICE_SERVERS_JSON + ROOM_PASSWORD + DEEPSEEK_API_KEY
# ============================================================
if (Test-Port 8010) {
    Write-Host '==> [4/5] Backend       : already running on :8010' -ForegroundColor Green
} else {
    Write-Host '==> [4/5] Backend       : starting...' -ForegroundColor Cyan
    $cmd = @"
chcp 65001 > `$null;
[Console]::OutputEncoding = [Text.UTF8Encoding]::new();
(& '$CondaExe' shell.powershell hook) | Out-String | Invoke-Expression;
conda activate linly_stream;
Set-Location '$ProjectRoot';
Remove-Item env:HF_HUB_OFFLINE -ErrorAction SilentlyContinue;
python src/server/app.py --config config/$Config 2>&1 | Tee-Object -FilePath '$ProjectRoot\backend.log'
"@
    Start-NewWindow 'Backend :8010' $cmd @{
        DEEPSEEK_API_KEY   = $LlmKey
        ICE_SERVERS_JSON   = $IceJson
        ROOM_PASSWORD      = $RoomPassword
        PYTHONIOENCODING   = 'utf-8'   # 防止 Windows GBK stdout 在打印 emoji 时崩日志
        PYTHONUTF8         = '1'
    }
}

# ============================================================
# 5) Frontend (3000)
# ============================================================
if (Test-Port 3000) {
    Write-Host '==> [5/5] Frontend      : already running on :3000' -ForegroundColor Green
} else {
    Write-Host '==> [5/5] Frontend      : starting...' -ForegroundColor Cyan
    $cmd = @"
`$env:Path = '$NodeDir;' + `$env:Path;
Set-Location '$ProjectRoot\web';
npm run dev 2>&1 | Tee-Object -FilePath '$ProjectRoot\frontend.log'
"@
    Start-NewWindow 'Frontend :3000' $cmd @{ CONFIG_FILE = $Config }
}

# ============================================================
# 6) 等后端 + 前端就绪，再起 Tunnel
# ============================================================
Write-Host ''
Write-Host '==> Waiting for backend + frontend (max 180s)...' -ForegroundColor Cyan
$ports = @{ 'Backend' = 8010; 'Frontend' = 3000 }
foreach ($name in $ports.Keys) {
    $p = $ports[$name]
    $ready = $false
    for ($i = 0; $i -lt 90; $i++) {
        if (Test-Port $p) { $ready = $true; break }
        Start-Sleep -Seconds 2
    }
    if ($ready) {
        Write-Host ("    {0,-10} :{1} OK ({2}s)" -f $name, $p, ($i * 2)) -ForegroundColor Green
    } else {
        Write-Host ("    {0,-10} :{1} TIMEOUT" -f $name, $p) -ForegroundColor Red
    }
}

# ============================================================
# 7) Cloudflared Tunnel
# ============================================================
Write-Host ''
Write-Host '==> Starting Cloudflare tunnel...' -ForegroundColor Cyan
Start-NewWindow 'Cloudflared talker' "Set-Location '$ProjectRoot'; .\scripts\cloudflared\start_tunnel.ps1 -TunnelName $TunnelName"

Write-Host ''
Write-Host '完成。三/四个服务在各自窗口运行，Ctrl+C 可单独停止。' -ForegroundColor Cyan
Write-Host ''
Write-Host '==> 公网入口:' -ForegroundColor Green
Write-Host "    https://talker.frostnova.uk/"
Write-Host "    密码:  $RoomPassword"
Write-Host ''
Write-Host '==> 本地入口（同样需要密码，因为后端只认环境变量）:' -ForegroundColor DarkGray
Write-Host '    https://localhost:3000/'
Write-Host ''
Write-Host '提示：想本地免密码调试，请改用 .\run_all.ps1 启动（不设 ROOM_PASSWORD）' -ForegroundColor DarkGray
