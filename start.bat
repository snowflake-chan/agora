@echo off
chcp 65001 >nul
title Agora
mode con cols=60 lines=12
echo ==================================
echo        Agora
echo ==================================
echo.
set DATABASE_URL=postgresql+asyncpg://agora:agora@localhost:5432/agora
set JWT_SECRET=local-dev-secret-32-chars-not-for-prod
set REDIS_URL=redis://localhost:6379/0
set APP_ENV=development
set CORS_ORIGIN=
echo [1] 清理端口
powershell -NoProfile "Get-NetTCPConnection -LocalPort 8000 -EA 0|Select -Exp OwningProcess|ForEach{Stop-Process -Id $_ -Force -EA 0}"
echo [2] 迁移数据库
cd /d "%~dp0backend"
"%~dp0venv\Scripts\python.exe" -m alembic upgrade head > "%~dp0migrate.log" 2>&1
if %errorlevel% neq 0 (type "%~dp0migrate.log" & pause & exit /b 1)
cd /d "%~dp0"
echo [3] 启动后端
cd /d "%~dp0backend"
start /MIN cmd /c ""%~dp0venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
cd /d "%~dp0"
echo [4] 启动前端
cd /d "%~dp0frontend"
if not exist node_modules call pnpm install >nul 2>&1
start /MIN cmd /c "pnpm astro dev --force --port 4321"
cd /d "%~dp0"
echo.
echo  启动完毕，请打开 http://localhost:4321
echo  关闭此窗口即停止服务
echo.
pause