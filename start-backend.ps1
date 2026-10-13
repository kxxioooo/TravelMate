<#
    TravelMate 后端启动脚本(FastAPI + MySQL)

    用法:在项目根目录执行
        .\start-backend.ps1
    或
        powershell -ExecutionPolicy Bypass -File .\start-backend.ps1

    保持这个窗口开着即为服务运行中,按 Ctrl+C 停止。
#>

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host "找不到虚拟环境:$python" -ForegroundColor Red
    Write-Host '请先在 backend 目录创建环境并安装依赖:' -ForegroundColor Yellow
    Write-Host '    cd backend'
    Write-Host '    python -m venv .venv'
    Write-Host '    .venv\Scripts\activate'
    Write-Host '    pip install -r requirements.txt'
    exit 1
}

# 后端启动时会自动建表(create_all),所以 MySQL 必须先用得上
$mysqlService = Get-Service -Name 'MySQL80' -ErrorAction SilentlyContinue
if ($mysqlService -and $mysqlService.Status -ne 'Running') {
    Write-Host 'MySQL80 未运行,尝试启动…' -ForegroundColor Yellow
    try {
        Start-Service -Name 'MySQL80'
    } catch {
        Write-Host 'MySQL80 启动失败(通常需要管理员权限)。请用管理员身份执行:' -ForegroundColor Red
        Write-Host '    net start MySQL80'
        exit 1
    }
}

# .env 是必需的:数据库密码与 JWT_SECRET 都在里面
if (-not (Test-Path (Join-Path $root '.env'))) {
    Write-Host '缺少 .env,请从 .env.example 复制一份并填写 MYSQL_PASSWORD / JWT_SECRET。' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '  TravelMate 后端' -ForegroundColor Green
Write-Host '  API      http://127.0.0.1:8000'
Write-Host '  文档     http://127.0.0.1:8000/docs'
Write-Host '  健康检查 http://127.0.0.1:8000/health'
Write-Host '  按 Ctrl+C 停止'
Write-Host ''

Set-Location (Join-Path $root 'backend')
# 注意:用 python -m uvicorn,因为项目自带的 venv 没有生成 uvicorn.exe
& $python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
