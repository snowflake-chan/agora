#Requires -RunAsAdministrator
<#
  Agora 一键本地启动脚本
  启动顺序: PostgreSQL -> Redis -> 数据库迁移 -> 后端(8000) -> 前端(4321)
#>

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
if (-not $root) { $root = Get-Location }

Write-Host "=== Agora Local Development Startup ===" -ForegroundColor Cyan

# ── 查找 Python 3.12+ ──
$python = $null
$candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:ProgramFiles\Python312\python.exe",
    "$env:ProgramFiles\Python313\python.exe",
    "$env:ProgramFiles\Python\Python312\python.exe",
    "$env:ProgramFiles\Python\Python313\python.exe",
    "C:\Python312\python.exe",
    "C:\Python313\python.exe"
)
foreach ($c in $candidates) {
    if (Test-Path $c) { $python = $c; Write-Host "  Found Python: $c" -ForegroundColor Green; break }
}
# Fallback: PATH python
if (-not $python) {
    try { $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver -and [version]$ver -ge [version]"3.12") { $python = "python" } } catch {}
}
if (-not $python) { Write-Error "Python 3.12+ not found. Install Python 3.12+ and try again."; exit 1 }
Write-Host "  Using: $python" -ForegroundColor Green

# ── 创建/激活 venv ──
$venvPath = "$root\venv"
if (-not (Test-Path "$venvPath\Scripts\python.exe")) {
    Write-Host "[1/8] Creating virtual environment..." -ForegroundColor Yellow
    & $python -m venv "$venvPath"
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create virtual environment."; exit 1 }
} else { Write-Host "[1/8] Virtual environment already exists, skipping." -ForegroundColor Green }
$pip = "$venvPath\Scripts\pip.exe"
$pythonVenv = "$venvPath\Scripts\python.exe"

# ── 安装后端依赖 ──
$reqFile = "$root\backend\requirements-dev.txt"
$reqHashFile = "$venvPath\requirements.hash"
$needInstall = $true
if (Test-Path $reqHashFile) { $oldHash = Get-Content $reqHashFile -Raw; $newHash = Get-FileHash $reqFile -Algorithm MD5
    if ($oldHash.Trim() -eq $newHash.Hash) { $needInstall = $false } }
if ($needInstall) {
    Write-Host "[2/8] Installing backend dependencies..." -ForegroundColor Yellow
    & $pip install -r $reqFile
    if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed."; exit 1 }
    Get-FileHash $reqFile -Algorithm MD5 | Select-Object -ExpandProperty Hash | Set-Content $reqHashFile
} else { Write-Host "[2/8] Dependencies up to date, skipping." -ForegroundColor Green }

# ── 生成 .env 文件 ──
$envFile = "$root\backend\.env"
if (-not (Test-Path $envFile)) {
    Write-Host "[3/8] Generating .env file..." -ForegroundColor Yellow
    @"
DATABASE_URL=postgresql+asyncpg://agora:agora@localhost:5432/agora
JWT_SECRET=local-dev-secret-not-for-production
REDIS_URL=redis://localhost:6379/0
APP_ENV=development
CORS_ORIGIN=""
"@ | Out-File -FilePath $envFile -Encoding utf8
} else { Write-Host "[3/8] .env already exists, skipping." -ForegroundColor Green }

# ── 启动 PostgreSQL ──
Write-Host "[4/8] Starting PostgreSQL..." -ForegroundColor Yellow
$pgSvc = Get-Service | Where-Object { $_.Name -like "*postgresql*" } | Select-Object -First 1
if ($pgSvc) {
    if ($pgSvc.Status -ne "Running") { Start-Service -Name $pgSvc.Name -ErrorAction SilentlyContinue
        if ($?) { Write-Host "  PostgreSQL service started." -ForegroundColor Green }
        else { Write-Host "  PostgreSQL service found but could not be started. Start it manually." -ForegroundColor Red } }
    else { Write-Host "  PostgreSQL already running." -ForegroundColor Green }
} else { Write-Host "  PostgreSQL service not found. Make sure it is installed and running." -ForegroundColor Red }

# ── 启动 Redis ──
Write-Host "[5/8] Starting Redis..." -ForegroundColor Yellow
try { $redisSvc = Get-Service -Name "Redis" -ErrorAction Stop
    if ($redisSvc.Status -ne "Running") { Start-Service -Name "Redis" -ErrorAction SilentlyContinue
        if ($?) { Write-Host "  Redis service started." -ForegroundColor Green }
        else { Write-Host "  Redis service found but could not be started." -ForegroundColor Red } }
    else { Write-Host "  Redis already running." -ForegroundColor Green } }
catch { Write-Host "  Redis service not found. Make sure Redis is installed and running." -ForegroundColor Red }

# ── 设置环境变量 ──
$env:DATABASE_URL = "postgresql+asyncpg://agora:agora@localhost:5432/agora"
$env:JWT_SECRET = "local-dev-secret-not-for-production"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:APP_ENV = "development"
$env:CORS_ORIGIN = ""

# ── 数据库迁移 ──
Write-Host "[6/8] Running database migrations..." -ForegroundColor Yellow
Push-Location "$root\backend"
& $pythonVenv -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Error "Database migration failed."; Pop-Location; exit 1 }
Pop-Location
Write-Host "  Migrations complete." -ForegroundColor Green

# ── 停止旧后端 ──
Write-Host "  Stopping any existing backend..." -ForegroundColor Yellow
try { $oldProcs = Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" }
    foreach ($p in $oldProcs) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } } catch {}

# ── 启动后端 (uvicorn) ──
Write-Host "[7/8] Starting backend (uvicorn)..." -ForegroundColor Yellow
$backendLog = "$root\backend\uvicorn.log"
$psi = @{
    FilePath = "$venvPath\Scripts\python.exe"
    ArgumentList = "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"
    WorkingDirectory = "$root\backend"
    WindowStyle = "Hidden"
    RedirectStandardOutput = "$root\backend\uvicorn_out.log"
    RedirectStandardError = "$root\backend\uvicorn_err.log"
    PassThru = $true
}
$backendProc = Start-Process @psi
Write-Host "  Backend PID: $($backendProc.Id)" -ForegroundColor Green

# ── 等待后端就绪 ──
Write-Host "  Waiting for backend to be ready..." -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 800
    try { $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/patches" -Method GET -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) { $ready = $true; break } } catch {}
}
if (-not $ready) { Write-Host "  Backend may not be ready. Check $root\backend\uvicorn_err.log for details." -ForegroundColor Red }
else { Write-Host "  Backend is ready!" -ForegroundColor Green }

# ── 检查 pnpm ──
try { $null = Get-Command pnpm -ErrorAction Stop }
catch { Write-Error "pnpm not found. Install Node.js 22+ and pnpm, then try again."; exit 1 }

# ── 检查前端依赖 ──
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "  Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location "$root\frontend"
    & pnpm install
    if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "pnpm install failed."; exit 1 }
    Pop-Location
    Write-Host "  Frontend dependencies installed." -ForegroundColor Green
} else { Write-Host "  Frontend dependencies already installed, skipping." -ForegroundColor Green }

# ── 打印 URL ──
Write-Host ""
Write-Host "=== Agora is starting up! ===" -ForegroundColor Cyan
Write-Host "  Backend API: http://localhost:8000" -ForegroundColor Magenta
Write-Host "  Frontend:    http://localhost:4321" -ForegroundColor Magenta
Write-Host "  API Docs:    http://localhost:8000/docs" -ForegroundColor Magenta
Write-Host ""

# ── 启动前端 (前台, 阻塞) ──
Write-Host "[8/8] Starting frontend (Astro dev)..." -ForegroundColor Yellow
Push-Location "$root\frontend"
& pnpm astro dev --port 4321
Pop-Location
