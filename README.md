# Novel Studio Pro

> AI 驱动的长篇小说自动化创作工具

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-green.svg)](https://fastapi.tiangolo.com/)
[![Electron](https://img.shields.io/badge/Electron-33.2.0-47848F.svg)](https://www.electronjs.org/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-v4--flash-orange.svg)](https://www.deepseek.com/)

---

## 📖 项目简介

**Novel Studio Pro** 是一款专为长篇小说创作设计的 AI 自动化工具。它采用多 Agent 协作架构，能够自动完成从故事规划、章节导演、正文写作到质量检查、状态管理的全流程创作支持。

### 核心特性

- 🤖 **9 个专业 Agent 协作**：记忆检索、伏笔管理、章节导演、正文写作、质量检查、状态提取
- 📝 **智能状态追踪**：自动维护角色、关系、伏笔、事件的连贯性
- ✨ **质量保障**：多维度质量评分 + 自动重写机制
- ⚙️ **灵活模型配置**：每个 Agent 可独立配置模型、温度、输出上限
- 🔄 **Mock 回退**：AI 服务不可用时自动回退，不中断创作
- 🖥️ **桌面客户端**：基于 Electron 的跨平台桌面应用

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- DeepSeek API Key
- (可选) SiliconFlow API Key（用于 Embedding）

### 后端部署

```bash
# 1. 克隆项目
git clone https://github.com/1786329860/novel-studio-pro.git
cd novel-studio-pro/novel-studio-pro-backend-v1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key

# 4. 启动服务
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端构建

```bash
cd novel-studio-pro-frontend-v3

# 1. 安装依赖
npm install

# 2. 开发模式运行
npm run dev

# 3. 打包桌面应用
npm run dist
```

---

## 📚 使用指南

### 1. 创建项目

1. 打开桌面客户端，点击「新建项目」
2. 填写项目信息：
   - **标题**：小说名称
   - **类型**：奇幻/玄幻/科幻/都市/悬疑/言情
   - **简介**：一句话故事梗概
   - **目标章节数**：计划写作的总章节数（默认 120）
3. 点击「创建项目」，AI 将自动生成：
   - 📋 **故事蓝图**：世界观、核心冲突、主线结构
   - 🎭 **角色设定**：主角、女主、配角等
   - 📖 **章节大纲**：每章的标题和目标

### 2. 生成章节

进入「写作」页面，点击「生成下一章」按钮。系统将自动执行：

```
记忆检索 → 伏笔管理 → 约束构建 → 角色导演 → 章节导演 → 正文写作 → 质量检查 → 状态提取
```

生成过程中可以实时看到每个 Agent 的执行进度。

### 3. 确认入库

生成的章节会进入「待确认」状态：
- ✅ **确认入库**：章节正式加入小说，更新项目状态
- 🔄 **重写本章**：根据质量检查反馈重新生成
- ❌ **放弃**：删除该章节

### 4. 管理章节

已确认的章节支持：
- 📤 **导出**：导出为 TXT 或 Markdown 格式
- 📋 **复制**：复制正文到剪贴板
- ✏️ **重命名**：修改章节标题
- 🗑️ **删除**：删除章节（会自动清理关联的记忆、伏笔、事件）

### 5. 模型配置

进入「设置」→「模型配置」，可以：

| 配置项 | 说明 |
|--------|------|
| **主写作模型** | 正文写作使用的模型 |
| **规划/检查模型** | 蓝图生成、质量检查使用的模型 |
| **Agent 任务路由** | 为每个 Agent 单独配置模型、温度、输出上限 |

**成本优化建议**：
- 正文写作、章节导演使用 `deepseek-v4-flash`（便宜且快速）
- 蓝图生成、质量检查使用 `deepseek-v4-pro`（质量更高）

### 6. 生成设置

进入「设置」→「生成设置」，可以调整：

- **生成模式**：标准/快速/深度
- **质量阈值**：自动重写的触发阈值（默认 85 分）
- **字数范围**：每章的目标字数（建议 3000-6000 字）
- **Mock 模式**：关闭 AI 调用，使用模板输出（用于测试）

---

## 🏗️ 技术架构

### 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主要开发语言 |
| FastAPI | 0.115.6 | Web 框架 |
| Uvicorn | 0.32.1 | ASGI 服务器 |
| httpx | 0.28.1 | 异步 HTTP 客户端 |
| Pydantic | 2.10.3 | 数据验证 |

### 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Electron | 33.2.0 | 桌面应用框架 |
| 原生 JavaScript | - | UI 渲染与交互 |
| electron-builder | 25.1.8 | 打包与分发 |

### AI 服务

| 服务 | 模型 | 用途 |
|------|------|------|
| DeepSeek | deepseek-v4-flash | 正文写作、章节导演 |
| DeepSeek | deepseek-v4-pro | 蓝图生成、质量检查 |
| SiliconFlow | BAAI/bge-m3 | 文本 Embedding |

---

## 🤖 Agent 系统

### Agent 列表

| Agent | 职责 | 默认模型 | 温度 |
|-------|------|----------|------|
| **MemoryAgent** | 记忆检索与 Token 预算控制 | flash | 0.1 |
| **ForeshadowAgent** | 伏笔生命周期管理 | flash | 0.2 |
| **ConstraintAgent** | 约束构建（POV、角色分配） | flash | 0.3 |
| **CharacterDirectorAgent** | 角色出场与对话分配 | flash | 0.5 |
| **DirectorAgent** | 章节目标与场景分解 | flash | 0.5 |
| **WriterAgent** | 正文写作 | flash | 0.9 |
| **ReviewAgent** | 质量检查 | pro | 0.2 |
| **StateExtractorAgent** | 状态变化提取 | flash | 0.1 |
| **StateMerger** | 状态合并验证 | - | - |

### 章节生成流水线

```
记忆检索 → 伏笔管理 → 约束构建 → 角色导演 → 章节导演 → 正文写作 → 质量检查 → 状态提取 → 状态合并
```

---

## ⚙️ 配置说明

### 环境变量

```bash
# 数据存储
DATA_DIR=/var/lib/novel-studio

# DeepSeek 配置
USE_DEEPSEEK=true
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MAIN_MODEL=deepseek-v4-flash
DEEPSEEK_PLAN_MODEL=deepseek-v4-flash
DEEPSEEK_FAST_MODEL=deepseek-v4-flash

# Embedding 配置（可选）
SILICONFLOW_API_KEY=sk-xxx
EMBEDDING_MODEL=BAAI/bge-m3
```

### 数据存储

所有数据存储在本地 JSON 文件中：
- **默认路径**：`/var/lib/novel-studio/novel_studio_data.json`
- **可通过 `DATA_DIR` 环境变量自定义**

---

## 🛠️ 开发指南

### 目录结构

```
novel-studio-pro/
├── novel-studio-pro-backend-v1/     # 后端代码
│   ├── app/
│   │   ├── core/                    # 核心模块（配置、存储、工具）
│   │   ├── routers/                 # API 路由
│   │   └── services/
│   │       ├── agents/              # Agent 实现
│   │       ├── ai_orchestrator.py   # 流水线编排
│   │       ├── deepseek_client.py   # DeepSeek 客户端
│   │       └── project_service.py   # 项目服务
│   ├── requirements.txt
│   └── .env
│
└── novel-studio-pro-frontend-v3/    # 前端代码
    ├── main.js                      # Electron 主进程
    ├── preload.js                   # 预加载脚本
    ├── index.html                   # 主页面
    ├── src/
    │   ├── renderer.js              # 渲染逻辑
    │   ├── api.js                   # API 封装
    │   └── styles.css               # 样式
    └── package.json
```

### 添加新 Agent

1. 在 `app/services/agents/` 创建新文件
2. 继承 `BaseAgent` 基类
3. 实现 `build_messages()`、`parse_response()`、`mock_run()` 方法
4. 在 `ai_orchestrator.py` 中引入并调用

---

## 📝 使用技巧

### 1. 控制成本

- 在「模型配置」中将大部分 Agent 切换到 `deepseek-v4-flash`
- 仅保留「蓝图生成」和「质量检查」使用 `deepseek-v4-pro`
- 关闭「Embedding 检索」可进一步降低成本

### 2. 提高质量

- 在「生成设置」中提高「质量阈值」到 90 分以上
- 在「模型配置」中降低「正文写作」的温度到 0.7
- 使用「用户指令」功能提供具体的写作要求

### 3. 保持连贯

- 定期查看「状态面板」，了解角色、伏笔的最新状态
- 使用「事件账本」记录关键剧情节点
- 删除章节时会自动清理关联数据，避免状态混乱

### 4. 处理 503 错误

DeepSeek API 偶尔会出现 503 服务繁忙错误：
- 系统会自动回退到 Mock 模式，输出模板文本
- 等待几分钟后重新生成即可
- 或切换到其他时段使用

---

## 🔧 故障排除

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| 生成内容为空 | 检查字数设置是否过低（建议 3000+），或 DeepSeek API 是否 503 |
| 输出模板文本 | 检查「生成设置」中「Mock 模式」是否关闭 |
| 前端无法连接后端 | 检查后端服务是否启动，端口是否正确 |
| 删除章节后状态异常 | 删除章节会重新编号后续章节，属正常行为 |

### 日志查看

```bash
# 后端日志
tail -f /tmp/novel.log

# 查看错误
grep -i error /tmp/novel.log
```

---

## 📄 许可证

UNLICENSED

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📧 联系

如有问题，请通过 GitHub Issues 联系。
