# Linly-Talker-Stream 一键启动脚本（Windows / PowerShell）
# 用法：在项目根目录执行  .\run_all.ps1
# 可选参数：
#   -Config    后端/前端读取的配置文件名（默认 config_musetalk.yaml）
#   -SkipSovits 跳过启动 GPT-SoVITS（如果已经在另一个终端运行）
#   -SkipBrowser 跳过自动打开浏览器
#   -New       强制重启：先杀掉占用相关端口的旧进程，再启动新的
#
# 每个服务会在独立的 PowerShell 窗口里运行，Ctrl+C 可单独停止。

[CmdletBinding()]
param(
    [string]$Config = 'config_musetalk.yaml',
    [switch]$SkipSovits,
    [switch]$SkipBrowser,
    [switch]$New
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$CondaExe    = "$env:USERPROFILE\anaconda3\Scripts\conda.exe"
$NodeDir     = 'C:\Program Files\nodejs'
$SovitsDir   = 'C:\code\ModelH\third_party\GPT-SoVITS'
$EnvFile     = 'C:\code\ModelH\config\.env'

function Test-Port($port) {
    Test-NetConnection -ComputerName 127.0.0.1 -Port $port `
        -InformationLevel Quiet -WarningAction SilentlyContinue
}

function Stop-Port($port, $label) {
    # 杀掉所有监听指定端口的进程；返回是否真的杀过
    $pids = @()
    try {
        $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty OwningProcess -Unique
    } catch { }
    if (-not $pids -or $pids.Count -eq 0) {
        Write-Host ("    {0,-10} :{1} no listener" -f $label, $port) -ForegroundColor DarkGray
        return $false
    }
    foreach ($procId in $pids) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            Write-Host ("    {0,-10} :{1} kill PID {2} ({3})" -f $label, $port, $procId, $proc.ProcessName) -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction Stop
        } catch {
            Write-Host ("    {0,-10} :{1} kill PID {2} failed: {3}" -f $label, $port, $procId, $_.Exception.Message) -ForegroundColor Red
        }
    }
    # 等端口真正释放
    for ($i = 0; $i -lt 20; $i++) {
        if (-not (Test-Port $port)) { return $true }
        Start-Sleep -Milliseconds 500
    }
    Write-Host ("    {0,-10} :{1} still listening after kill" -f $label, $port) -ForegroundColor Red
    return $true
}

function Start-NewWindow($title, $command) {
    # 在新 PowerShell 窗口里运行命令，标题方便区分
    $full = "`$Host.UI.RawUI.WindowTitle='$title'; $command"
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList '-NoExit', '-Command', $full `
        -WorkingDirectory $ProjectRoot
}

Write-Host "==> Linly-Talker-Stream launcher" -ForegroundColor Cyan
Write-Host "    Config: $Config"
Write-Host "    Root:   $ProjectRoot"
if ($New) { Write-Host "    Mode:   -New (force restart)" -ForegroundColor Magenta }

# --------------------------------------------------------------------
# 0) -New 模式：先停掉旧进程
# --------------------------------------------------------------------
if ($New) {
    Write-Host ''
    Write-Host '==> Stopping existing services...' -ForegroundColor Magenta
    if (-not $SkipSovits) { [void](Stop-Port 9880 'GPT-SoVITS') }
    [void](Stop-Port 8010 'Backend')
    [void](Stop-Port 3000 'Frontend')
}

# --------------------------------------------------------------------
# 1) GPT-SoVITS (port 9880)
# --------------------------------------------------------------------
if ($SkipSovits) {
    Write-Host "[1/3] GPT-SoVITS    : skipped (--SkipSovits)" -ForegroundColor Yellow
} elseif (Test-Port 9880) {
    Write-Host "[1/3] GPT-SoVITS    : already running on :9880" -ForegroundColor Green
} else {
    Write-Host "[1/3] GPT-SoVITS    : starting in new window..." -ForegroundColor Cyan
    $cmd = @"
(& '$CondaExe' shell.powershell hook) | Out-String | Invoke-Expression;
conda activate sovits;
Set-Location '$SovitsDir';
python api_v2.py
"@
    Start-NewWindow 'GPT-SoVITS :9880' $cmd
}

# --------------------------------------------------------------------
# 2) 后端 (port 8010)
# --------------------------------------------------------------------
if (Test-Port 8010) {
    Write-Host "[2/3] Backend       : already running on :8010" -ForegroundColor Green
} else {
    if (-not (Test-Path $EnvFile)) {
        throw "找不到 .env: $EnvFile"
    }
    $key = (Select-String -Path $EnvFile -Pattern '^LLM_API_KEY=(.+)$').Matches.Groups[1].Value
    if (-not $key) { throw "无法从 $EnvFile 读取 LLM_API_KEY" }

    Write-Host "[2/3] Backend       : starting in new window..." -ForegroundColor Cyan
    $cmd = @"
chcp 65001 > `$null;
[Console]::OutputEncoding = [Text.UTF8Encoding]::new();
(& '$CondaExe' shell.powershell hook) | Out-String | Invoke-Expression;
conda activate linly_stream;
Set-Location '$ProjectRoot';
Remove-Item env:HF_HUB_OFFLINE -ErrorAction SilentlyContinue;
`$env:DEEPSEEK_API_KEY = '$key';
`$env:PYTHONIOENCODING = 'utf-8';
`$env:PYTHONUTF8 = '1';
python src/server/app.py --config config/$Config 2>&1 | Tee-Object -FilePath '$ProjectRoot\backend.log'
"@
    Start-NewWindow 'Backend :8010' $cmd
}

# --------------------------------------------------------------------
# 3) 前端 (port 3000)
# --------------------------------------------------------------------
if (Test-Port 3000) {
    Write-Host "[3/3] Frontend      : already running on :3000" -ForegroundColor Green
} else {
    Write-Host "[3/3] Frontend      : starting in new window..." -ForegroundColor Cyan
    $cmd = @"
`$env:Path = '$NodeDir;' + `$env:Path;
Set-Location '$ProjectRoot\web';
`$env:CONFIG_FILE = '$Config';
npm run dev 2>&1 | Tee-Object -FilePath '$ProjectRoot\frontend.log'
"@
    Start-NewWindow 'Frontend :3000' $cmd
}

# --------------------------------------------------------------------
# 等待端口就绪
# --------------------------------------------------------------------
Write-Host ''
Write-Host '==> Waiting for services to come up (max 180s)...' -ForegroundColor Cyan
$ports = @{ 'GPT-SoVITS' = 9880; 'Backend' = 8010; 'Frontend' = 3000 }
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

# --------------------------------------------------------------------
# 健康检查 + 打开浏览器
# --------------------------------------------------------------------
Write-Host ''
Write-Host '==> /health check' -ForegroundColor Cyan
$health = & curl.exe --ssl-no-revoke -s https://localhost:3000/health 2>$null
if ($health -match 'ready') {
    Write-Host "    $health" -ForegroundColor Green
    if (-not $SkipBrowser) {
        Write-Host '==> Opening https://localhost:3000/ ...' -ForegroundColor Cyan
        Start-Process 'https://localhost:3000/'
    }
} else {
    Write-Host "    Health check failed: $health" -ForegroundColor Red
    Write-Host '    检查后端窗口日志，或查看 backend.log' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '完成。三个服务在各自窗口运行，Ctrl+C 可单独停止。' -ForegroundColor Cyan
