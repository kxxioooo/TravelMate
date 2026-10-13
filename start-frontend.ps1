<#
    TravelMate 前端启动脚本(Vite dev server)

    用法:在项目根目录执行
        .\start-frontend.ps1

    保持这个窗口开着即为服务运行中,按 Ctrl+C 停止。
    浏览器打开 http://localhost:5173

    优先使用系统安装的 node + npm;没有则回退到 DSH 内置的 Node + pnpm。
#>

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$frontend = Join-Path $root 'frontend'

if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Host 'node_modules 不存在,请先在 frontend 目录安装依赖:' -ForegroundColor Red
    Write-Host '    cd frontend'
    Write-Host '    npm install'
    exit 1
}

Write-Host ''
Write-Host '  TravelMate 前端' -ForegroundColor Green
Write-Host '  地址 http://localhost:5173'
Write-Host '  按 Ctrl+C 停止'
Write-Host ''

$systemNode = Get-Command node -ErrorAction SilentlyContinue
$systemNpm = Get-Command npm -ErrorAction SilentlyContinue

Set-Location $frontend

if ($systemNode -and $systemNpm) {
    Write-Host "使用系统 Node:$($systemNode.Source)" -ForegroundColor DarkGray
    & $systemNpm.Source run dev
    exit $LASTEXITCODE
}

# 回退:DSH 桌面端自带的 Node 运行时
$deps = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies'
$bundledNode = Join-Path $deps 'node\bin\node.exe'
$bundledPnpm = Join-Path $deps 'pnpm\bin\pnpm.mjs'

if (-not (Test-Path $bundledNode)) {
    Write-Host '系统里没有 node,也没找到 DSH 内置运行时。' -ForegroundColor Red
    Write-Host '请安装 Node.js LTS(≥20):https://nodejs.org'
    exit 1
}

Write-Host '系统未安装 Node,改用 DSH 内置 Node + pnpm' -ForegroundColor DarkGray
# vite 需要在 PATH 里找到 node 才能拉起自己的子进程
$env:PATH = "$(Split-Path $bundledNode);$env:PATH"
& $bundledNode $bundledPnpm run dev
