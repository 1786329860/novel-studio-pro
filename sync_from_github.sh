#!/bin/bash
# ============================================================
# Novel Studio Pro - 服务器自动同步脚本
# 功能: 从 GitHub 拉取最新代码，如有更新则自动重启后端服务
# 用法: 配合 cron 定时执行，每 5 分钟检查一次
# ============================================================

LOG_FILE="/var/log/novel-studio-sync.log"
REPO_DIR="/opt/novel-studio/novel-studio-pro-backend-v1"
SERVICE_NAME="novel-studio"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 检查是否在仓库目录中
if [ ! -d "$REPO_DIR/.git" ]; then
    log "错误: $REPO_DIR 不是 Git 仓库，跳过同步"
    exit 1
fi

cd "$REPO_DIR"

# 记录当前 commit
OLD_COMMIT=$(git rev-parse HEAD)

# 拉取最新代码（静默模式）
git fetch origin main --quiet 2>> "$LOG_FILE"

# 检查是否有更新
NEW_COMMIT=$(git rev-parse origin/main)

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    # 没有更新，什么都不做
    exit 0
fi

# 有更新，执行拉取
log "检测到代码更新: $OLD_COMMIT -> $NEW_COMMIT"
git pull origin main --quiet 2>> "$LOG_FILE"

# 更新 Python 依赖（如果有变化）
$REPO_DIR/.venv/bin/pip install -r requirements.txt -q 2>> "$LOG_FILE"

# 重启后端服务
systemctl restart "$SERVICE_NAME" 2>> "$LOG_FILE"

if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "同步完成，服务已重启"
else
    log "错误: 服务重启失败！"
fi
