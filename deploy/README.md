# Novel Studio Pro - 部署指南

## 架构说明

```
Windows 电脑（本地）                    您的服务器（远程）
┌──────────────────┐                 ┌──────────────────┐
│  Electron EXE    │  ── HTTP ──→   │  FastAPI 后端     │
│  桌面应用         │  ←── JSON ──   │  端口: 8765       │
│  (用户双击运行)   │                 │  数据: JSON 文件   │
└──────────────────┘                 └──────────────────┘
```

- **前端**：Electron 桌面应用，打包为 Windows EXE，在用户本地电脑运行
- **后端**：FastAPI 后端，部署在您的 Ubuntu 服务器上
- **连接**：EXE 启动后在「DeepSeek API」页面填入服务器地址，关闭 Mock 模式即可连接

## 服务器环境

| 项目 | 信息 |
|------|------|
| 操作系统 | Ubuntu |
| 管理面板 | 1Panel |
| Web 服务器 | OpenResty (Nginx) |
| CPU | 2 核 |
| 内存 | 1.92 GB |
| 磁盘 | 29.42 GB |

## 一、部署后端到服务器

### 方式一：一键部署脚本（推荐）

```bash
# 1. 将整个 NovelStudioProject 目录上传到服务器
scp -r NovelStudioProject root@您的服务器IP:/tmp/

# 2. SSH 登录服务器
ssh root@您的服务器IP

# 3. 执行部署脚本（只需部署后端）
cd /tmp/NovelStudioProject
chmod +x deploy_backend.sh
sudo bash deploy_backend.sh
```

### 方式二：手动部署

```bash
# 1. 创建目录
sudo mkdir -p /opt/novel-studio
sudo mkdir -p /var/lib/novel-studio

# 2. 复制后端文件
sudo cp -r novel-studio-pro-backend-v1 /opt/novel-studio/

# 3. 创建 Python 虚拟环境
cd /opt/novel-studio/novel-studio-pro-backend-v1
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env:
# APP_HOST=0.0.0.0
# DEBUG=false
# DATA_DIR=/var/lib/novel-studio
# CORS_ORIGINS=*

# 5. 启动
.venv/bin/python start_production.py
```

### 部署后验证

```bash
# 健康检查
curl http://127.0.0.1:8765/api/health

# 预期返回:
# {"ok":true,"host":"0.0.0.0","port":8765,"dataDir":"/var/lib/novel-studio","message":"后端运行正常。"}
```

## 二、（可选）配置 OpenResty 反向代理 + SSL

如果您的服务器有域名，建议通过 OpenResty 反向代理并配置 SSL：

### 在 1Panel 中操作

1. **创建网站**：1Panel → 网站 → 创建网站，填写域名
2. **配置反向代理**：网站设置 → 反向代理 → 添加
   - 代理名称：`novel-studio-api`
   - 代理地址：`http://127.0.0.1:8765`
3. **配置 SSL**：网站设置 → HTTPS → 申请 Let's Encrypt 证书

### 或手动配置 Nginx

将以下内容添加到网站配置中：

```nginx
# API 反向代理
location /api/ {
    proxy_pass http://127.0.0.1:8765;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # 生成任务可能需要较长时间
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}

# 健康检查
location /api/health {
    proxy_pass http://127.0.0.1:8765;
    access_log off;
}

# API 文档
location /docs {
    proxy_pass http://127.0.0.1:8765;
}
```

配置完成后，后端地址变为：`https://your-domain.com`

## 三、本地 Electron EXE 使用

### 开发模式（调试用）

```bash
cd novel-studio-pro-frontend-v3
npm install
npm run dev
```

### 打包 EXE

```bash
cd novel-studio-pro-frontend-v3
npm run dist
# 打包文件在 dist/ 目录
```

### 连接远程后端

1. 打开 Electron 应用
2. 进入左侧菜单 **「生成设置」**
3. **关闭 Mock 模式**
4. 进入左侧菜单 **「DeepSeek API」**
5. 在 **「本地后端地址」** 中填入：
   - 无域名：`http://您的服务器IP:8765`
   - 有域名+SSL：`https://your-domain.com`
6. 暂时不需要填 DeepSeek API Key（Mock 模式已关闭，后端会使用内置 Mock 数据）

### 测试流程

1. 新建项目 → 输入小说名和大纲 → 自动构建小说
2. 查看故事蓝图 → 角色系统 → 伏笔与真相
3. 章节写作 → 生成下一章 → 确认本章入库
4. 状态面板 → 事件账本 → 全局记忆
5. 生成设置 / 模型配置 → 保存设置

## 四、环境变量说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_HOST` | `0.0.0.0` | 监听地址（部署必须为 0.0.0.0） |
| `APP_PORT` | `8765` | 监听端口 |
| `DATA_DIR` | `./data` | 数据存储目录（建议绝对路径） |
| `CORS_ORIGINS` | `*` | 允许的来源（EXE 跨域需要） |
| `DEBUG` | `false` | 调试模式（生产环境关闭） |
| `USE_DEEPSEEK` | `false` | 是否启用 DeepSeek API |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 地址 |

## 五、常用运维命令

```bash
# 查看服务状态
systemctl status novel-studio

# 查看实时日志
journalctl -u novel-studio -f

# 重启服务
systemctl restart novel-studio

# 停止服务
systemctl stop novel-studio

# 健康检查
curl http://127.0.0.1:8765/api/health

# 查看 API 文档（浏览器）
# http://服务器IP:8765/docs
```

## 六、注意事项

1. **防火墙**：确保服务器 8765 端口已开放（或在 1Panel 防火墙中放行）
2. **数据备份**：定期备份 `/var/lib/novel-studio/` 目录
3. **安全建议**：
   - 生产环境建议配置 SSL（通过 OpenResty）
   - 可在 `.env` 中将 `CORS_ORIGINS` 改为具体域名
4. **DeepSeek 接入**：后续在服务器 `.env` 中配置 `USE_DEEPSEEK=true` 和 API Key
5. **EXE 打包**：前端代码无需修改，直接 `npm run dist` 即可打包
