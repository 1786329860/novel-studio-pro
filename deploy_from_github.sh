#!/bin/bash
# ============================================================
# Novel Studio Pro - 服务器首次部署脚本（从 GitHub 拉取）
# 用法: sudo bash deploy_from_github.sh
# ============================================================

set -e

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
GITHUB_REPO="https://github.com/1786329860/novel-studio-pro.git"
GITHUB_BRANCH="main"
INSTALL_DIR="/opt/novel-studio"
BACKEND_DIR="${INSTALL_DIR}/novel-studio-pro-backend-v1"
DATA_DIR="/var/lib/novel-studio"
SERVICE_USER="novel-studio"
SERVICE_NAME="novel-studio"
SYNC_SCRIPT="/opt/novel-studio/sync_from_github.sh"
CRON_INTERVAL=5  # 每 5 分钟检查一次

if [ "$(id -u)" -ne 0 ]; then
    error "请使用 root 权限运行: sudo bash deploy_from_github.sh"
fi

echo ""
echo "============================================"
echo "  Novel Studio Pro - 从 GitHub 部署"
echo "============================================"
echo ""

# ---------- 步骤 1: 安装依赖 ----------
info "步骤 1/7: 安装系统依赖..."
apt-get update -qq

if ! command -v git &> /dev/null; then
    apt-get install -y git > /dev/null 2>&1
fi
if ! command -v python3 &> /dev/null; then
    apt-get install -y python3 python3-pip python3-venv > /dev/null 2>&1
fi
if ! command -v curl &> /dev/null; then
    apt-get install -y curl > /dev/null 2>&1
fi
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
ok "目录创建完成"

# ---------- 步骤 3: 从 GitHub 克隆代码 ----------
info "步骤 3/7: 从 GitHub 克隆代码..."

if [ -d "$BACKEND_DIR/.git" ]; then
    info "仓库已存在，执行更新..."
    cd "$BACKEND_DIR"
    git pull origin "$GITHUB_BRANCH" --quiet
    ok "代码更新完成"
else
    if [ -d "$BACKEND_DIR" ]; then
        rm -rf "$BACKEND_DIR"
    fi
    git clone -b "$GITHUB_BRANCH" "$GITHUB_REPO" "$BACKEND_DIR" --quiet
    ok "代码克隆完成"
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
ok "文件权限设置完成"

# ---------- 步骤 4: 配置 Python 虚拟环境 ----------
info "步骤 4/7: 配置 Python 虚拟环境..."
cd "$BACKEND_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
ok "Python 依赖安装完成"

# ---------- 步骤 5: 配置环境变量 ----------
info "步骤 5/7: 配置环境变量..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
fi
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

NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${DATA_DIR} ${BACKEND_DIR}
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" > /dev/null 2>&1
ok "systemd 服务配置完成"

# ---------- 步骤 7: 启动服务 + 配置自动同步 ----------
info "步骤 7/7: 启动服务并配置自动同步..."

systemctl restart "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "服务启动成功!"
else
    error "服务启动失败，请检查: journalctl -u ${SERVICE_NAME} -n 50"
fi

# 配置自动同步脚本
cp "$BACKEND_DIR/../sync_from_github.sh" "$SYNC_SCRIPT" 2>/dev/null || true
if [ ! -f "$SYNC_SCRIPT" ]; then
    # 如果脚本不在仓库中，手动创建
    cat > "$SYNC_SCRIPT" << 'SYNCEOF'
#!/bin/bash
LOG_FILE="/var/log/novel-studio-sync.log"
REPO_DIR="/opt/novel-studio"
SERVICE_NAME="novel-studio"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; }
cd "$REPO_DIR" || exit 1
OLD_COMMIT=$(git rev-parse HEAD)
git fetch origin main --quiet 2>> "$LOG_FILE"
NEW_COMMIT=$(git rev-parse origin/main)
if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then exit 0; fi
log "检测到更新: $(echo $OLD_COMMIT | cut -c1-7) -> $(echo $NEW_COMMIT | cut -c1-7)"
git pull origin main --quiet 2>> "$LOG_FILE"
cd "$REPO_DIR/novel-studio-pro-backend-v1"
.venv/bin/pip install -r requirements.txt -q 2>> "$LOG_FILE"
systemctl restart "$SERVICE_NAME" 2>> "$LOG_FILE"
log "同步完成，服务已重启"
SYNCEOF
fi

chmod +x "$SYNC_SCRIPT"

# 配置 cron 定时任务（每 5 分钟检查一次）
CRON_JOB="*/${CRON_INTERVAL} * * * * ${SYNC_SCRIPT}"
(crontab -l 2>/dev/null | grep -v "novel-studio-sync"; echo "$CRON_JOB") | crontab -
ok "自动同步已配置（每 ${CRON_INTERVAL} 分钟检查一次）"

# 验证
HEALTH_CHECK=$(curl -s --max-time 5 http://127.0.0.1:8765/api/health 2>/dev/null || echo "FAILED")
if echo "$HEALTH_CHECK" | grep -q '"ok"'; then
    ok "后端健康检查通过!"
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo ""
    echo "  后端地址: http://${SERVER_IP}:8765"
    echo "  API 文档: http://${SERVER_IP}:8765/docs"
    echo ""
    echo "  在 Electron EXE 中填入: http://${SERVER_IP}:8765"
else
    warn "健康检查未通过，稍后检查: curl http://127.0.0.1:8765/api/health"
fi

echo ""
echo "============================================"
echo "  部署完成! GitHub 自动同步已开启"
echo "============================================"
echo ""
echo "  仓库地址: ${GITHUB_REPO}"
echo "  同步频率: 每 ${CRON_INTERVAL} 分钟"
echo "  同步日志: /var/log/novel-studio-sync.log"
echo ""
echo "  常用命令:"
echo "  查看状态:   systemctl status ${SERVICE_NAME}"
echo "  查看日志:   journalctl -u ${SERVICE_NAME} -f"
echo "  手动同步:   bash ${SYNC_SCRIPT}"
echo "  查看同步日志: tail -f /var/log/novel-studio-sync.log"
echo ""
