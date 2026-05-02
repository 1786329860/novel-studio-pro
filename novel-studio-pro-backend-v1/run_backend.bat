@echo off
chcp 65001 >nul
echo 启动 Novel Studio Pro 本地后端...
if not exist .venv (
  echo 创建 Python 虚拟环境...
  python -m venv .venv
)
call .venv\Scripts\activate
echo 安装依赖...
pip install -r requirements.txt
echo 启动服务：http://127.0.0.1:8765
python start_backend.py
pause
