#!/bin/bash
# ============================================================
# Novel Studio Pro - 后端服务器部署脚本
# 架构: Electron EXE (本地) + FastAPI 后端 (远程服务器)
# 适用于: Ubuntu + 1Panel + OpenResty
# ============================================================

set -e

# ---------- 颜色定义 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ---------- 配置项 ----------
INSTALL_DIR="/opt/novel-studio"
BACKEND_DIR="${INSTALL_DIR}/novel-studio-pro-backend-v1"
DATA_DIR="/var/lib/novel-studio"
SERVICE_USER="novel-studio"
SERVICE_NAME="novel-studio"

# ---------- 检查 root 权限 ----------
if [ "$(id -u)" -ne 0 ]; then
    error "请使用 root 权限运行此脚本: sudo bash deploy_backend.sh"
fi

echo ""
echo "============================================"
echo "  Novel Studio Pro 后端部署脚本"
echo "  架构: Electron EXE (本地) + 服务器后端"
echo "============================================"
echo ""

# ---------- 步骤 1: 安装系统依赖 ----------
info "步骤 1/7: 安装系统依赖..."

apt-get update -qq

if ! command -v python3 &> /dev/null; then
    info "安装 Python3..."
    apt-get install -y python3 python3-pip python3-venv > /dev/null 2>&1
    ok "Python3 安装完成"
else
    ok "Python3 已安装: $(python3 --version)"
fi

apt-get install -y curl wget git unzip > /dev/null 2>&1
ok "系统依赖安装完成"

# ---------- 步骤 2: 创建用户和目录 ----------
info "步骤 2/7: 创建部署用户和目录..."

if ! id "$SERVICE_USER" &> /dev/null; then
    useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
    ok "创建用户: $SERVICE_USER"
else
    ok "用户已存在: $SERVICE_USER"
fi

mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
ok "目录创建完成: $INSTALL_DIR, $DATA_DIR"

# ---------- 步骤 3: 复制后端文件 ----------
info "步骤 3/7: 复制后端文件..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -d "$SCRIPT_DIR/novel-studio-pro-backend-v1" ]; then
    # 清理旧文件（保留数据）
    rm -rf "$BACKEND_DIR"
    cp -r "$SCRIPT_DIR/novel-studio-pro-backend-v1" "$INSTALL_DIR/"
    ok "后端文件复制完成"
else
    error "找不到后端目录: $SCRIPT_DIR/novel-studio-pro-backend-v1"
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
ok "文件权限设置完成"

# ---------- 步骤 4: 配置 Python 虚拟环境 ----------
info "步骤 4/7: 配置 Python 虚拟环境..."

cd "$BACKEND_DIR"

python3 -m venv .venv
ok "虚拟环境创建完成"

.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
ok "Python 依赖安装完成"

# ---------- 步骤 5: 配置环境变量 ----------
info "步骤 5/7: 配置环境变量..."

if [ ! -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    ok "从 .env.example 生成 .env"
else
    ok ".env 已存在，保留现有配置"
fi

# 确保关键配置正确
sed -i "s|^APP_HOST=.*|APP_HOST=0.0.0.0|" "$BACKEND_DIR/.env"
sed -i "s|^DEBUG=.*|DEBUG=false|" "$BACKEND_DIR/.env"
sed -i "s|^DATA_DIR=.*|DATA_DIR=${DATA_DIR}|" "$BACKEND_DIR/.env"
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=*|" "$BACKEND_DIR/.env"

chown "$SERVICE_USER:$SERVICE_USER" "$BACKEND_DIR/.env"
chmod 600 "$BACKEND_DIR/.env"
ok "环境变量配置完成"

# ---------- 步骤 6: 配置 systemd 服务 ----------
info "步骤 6/7: 配置 systemd 服务..."

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Novel Studio Pro Backend
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${BACKEND_DIR}/.env
ExecStart=${BACKEND_DIR}/.venv/bin/python start_production.py
Restart=always
RestartSec=5

# 安全加固
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${DATA_DIR} ${BACKEND_DIR}

# 资源限制 (适配 2GB 内存服务器)
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" > /dev/null 2>&1
ok "systemd 服务配置完成"

# ---------- 步骤 7: 启动并验证 ----------
info "步骤 7/7: 启动服务..."

systemctl restart "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "服务启动成功!"
else
    error "服务启动失败，请检查日志: journalctl -u ${SERVICE_NAME} -n 50"
fi

# 验证
HEALTH_CHECK=$(curl -s --max-time 5 http://127.0.0.1:8765/api/health 2>/dev/null || echo "FAILED")

if echo "$HEALTH_CHECK" | grep -q '"ok"'; then
    ok "后端健康检查通过!"
    echo ""
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo "  后端地址: http://${SERVER_IP}:8765"
    echo "  API 文档: http://${SERVER_IP}:8765/docs"
    echo ""
    echo "  ========================================"
    echo "  在 Electron EXE 中配置后端地址:"
    echo "  http://${SERVER_IP}:8765"
    echo "  ========================================"
else
    warn "健康检查未通过，服务可能还在启动中"
    warn "请稍后手动检查: curl http://127.0.0.1:8765/api/health"
fi

echo ""
echo "============================================"
echo "  后端部署完成!"
echo "============================================"
echo ""
echo "  常用命令:"
echo "  查看状态:   systemctl status ${SERVICE_NAME}"
echo "  查看日志:   journalctl -u ${SERVICE_NAME} -f"
echo "  重启服务:   systemctl restart ${SERVICE_NAME}"
echo "  停止服务:   systemctl stop ${SERVICE_NAME}"
echo ""
echo "  配置文件:   ${BACKEND_DIR}/.env"
echo "  数据目录:   ${DATA_DIR}"
echo ""
echo "  下一步:"
echo "  1. 如有域名，在 1Panel/OpenResty 中配置反向代理和 SSL"
echo "  2. 在 Electron EXE 的「DeepSeek API」页面填入服务器地址"
echo "  3. 关闭 Mock 模式，连接远程后端"
echo ""
