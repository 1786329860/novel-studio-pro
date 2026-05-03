@echo off
REM Novel Studio Pro 后端启动脚本
REM 此脚本由 Electron 主进程调用，用于启动 Python 后端服务

cd /d "%~dp0..\backend"

REM 检查 Python 是否可用
python --version >nul 2>&1
if %errorlevel% neq 0 (
    python3 --version >nul 2>&1
    if %errorlevel% neq 0 (
        py --version >nul 2>&1
        if %errorlevel% neq 0 (
            echo ERROR: 未找到 Python 环境
            exit /b 1
        )
        py start_backend.py
    ) else (
        python3 start_backend.py
    )
) else (
    python start_backend.py
)
