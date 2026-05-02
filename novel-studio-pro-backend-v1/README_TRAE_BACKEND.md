# Novel Studio Pro 后端代码包使用说明（给 Trae）

这个后端是给个人本地 Windows EXE 小说自动化软件使用的。

重要原则：

1. 不做登录注册。
2. 前端不要直接请求 DeepSeek。
3. DeepSeek API Key 只能放在后端 `.env` 或后端本地设置里。
4. 默认使用 Mock 模式，先跑通前后端流程，再接 DeepSeek。
5. 不要删除“生成下一章”与“确认本章入库”两步。
6. 不要把项目改成云端多用户系统。
7. 不要把 JSON 本地存储改得太复杂，第一版先保证能跑。

---

## 一、后端运行步骤

进入后端目录：

```bash
cd novel-studio-pro-backend-v1
```

创建虚拟环境：

```bash
python -m venv .venv
```

Windows 激活：

```bash
.venv\Scripts\activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

复制环境配置：

```bash
copy .env.example .env
```

启动后端：

```bash
python start_backend.py
```

打开浏览器测试：

```text
http://127.0.0.1:8765/api/health
```

看到：

```json
{"ok": true}
```

说明后端启动成功。

也可以打开接口文档：

```text
http://127.0.0.1:8765/docs
```

---

## 二、最简单启动方式

Windows 下也可以双击：

```text
run_backend.bat
```

它会自动创建虚拟环境、安装依赖、启动服务。

---

## 三、和前端连接

⚠️ 重要：先打前端补丁。把本后端包里的 `frontend_patch/api.js` 覆盖到前端项目 `novel-studio-pro-frontend-v3/src/api.js`。否则关闭 Mock 模式后，后端虽然成功返回，前端页面不会刷新。详见 `IMPORTANT_FRONTEND_PATCH.md`。

前端项目是：

```text
novel-studio-pro-frontend-v3
```

先启动本后端，再启动前端。

前端设置页里：

```text
Mock 模式：关闭
本地后端地址：http://127.0.0.1:8765
请求超时：180000 或更高
```

然后测试：

1. 新建项目。
2. 输入小说名。
3. 输入总大纲。
4. 点击“开始自动构建小说”。
5. 进入故事蓝图页检查数据。
6. 进入章节写作页。
7. 点击“生成下一章”。
8. 点击“确认本章入库”。
9. 进入状态面板检查事件账本、伏笔、角色状态。

---

## 四、当前后端已经实现的接口

```text
GET  /api/health
GET  /api/projects
POST /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}/build
POST /api/projects/{project_id}/blueprint/regenerate
POST /api/projects/{project_id}/chapters/generate-next
POST /api/projects/{project_id}/chapters/{chapter_id}/confirm
POST /api/projects/{project_id}/state/analyze
GET  /api/projects/{project_id}/characters
PUT  /api/projects/{project_id}/characters/{character_id}
GET  /api/projects/{project_id}/foreshadows
PUT  /api/projects/{project_id}/foreshadows/{foreshadow_id}
GET  /api/projects/{project_id}/truth-source
GET  /api/projects/{project_id}/memory
POST /api/projects/{project_id}/memory/rebuild
GET  /api/projects/{project_id}/events
GET  /api/settings
GET  /api/settings/generation
PUT  /api/settings/generation
GET  /api/settings/model-routes
PUT  /api/settings/model-routes
GET  /api/settings/deepseek
PUT  /api/settings/deepseek
POST /api/settings/deepseek/test
GET  /api/settings/request-logs
```

---

## 五、默认数据存在哪里

本地数据文件：

```text
data/novel_studio_data.json
```

里面存：

```text
项目
故事蓝图
角色系统
伏笔与真相
事件账本
章节
待确认章节
状态面板
模型设置
DeepSeek 设置
请求日志
```

第一版就用 JSON 文件，简单稳定。后续如果数据量大，再换 SQLite。

---

## 六、DeepSeek 预留位置

DeepSeek 相关代码在：

```text
app/services/deepseek_client.py
app/services/prompt_templates.py
app/services/ai_orchestrator.py
```

默认 `.env`：

```text
USE_DEEPSEEK=false
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MAIN_MODEL=deepseek-chat
DEEPSEEK_FAST_MODEL=deepseek-chat
```

如果要正式测试 DeepSeek：

1. 打开 `.env`。
2. 设置：

```text
USE_DEEPSEEK=true
DEEPSEEK_API_KEY=你的真实key
```

3. 启动后端。
4. 前端设置里关闭 Mock 模式。
5. 调用 `/api/settings/deepseek/test` 测试连接。

注意：不要把真实 API Key 写死在前端代码里。

---

## 七、DeepSeek 超时和上限控制

已经预留：

```text
REQUEST_TIMEOUT_SECONDS=180
RETRY_TIMES=2
MAX_INPUT_TOKENS=64000
MAX_OUTPUT_TOKENS=12000
```

后续细化时 Trae 要做：

1. 长章节分场景生成。
2. JSON 输出失败自动修复。
3. 输入过长时自动压缩上下文。
4. 429 或 5xx 错误自动退避重试。
5. 每次请求记录模型、温度、tokens、耗时、是否成功。
6. 关键章节使用严格模式，普通章节使用标准模式。

当前代码已经有请求重试、超时、日志、Mock 回退框架。

---

## 八、不要让 Trae 做错的事

请不要：

1. 不要让 Electron 前端直接请求 DeepSeek。
2. 不要在前端保存真实 API Key。
3. 不要删除 Mock 模式。
4. 不要把“确认章节入库”省掉。
5. 不要每次生成下一章都把全部正文塞给 DeepSeek。
6. 不要让正文写作 Agent 自己决定全部剧情。
7. 不要把状态更新直接交给模型乱写数据库。
8. 不要让用户修改正文后忘记重新提取状态。

---

## 九、下一步开发建议

第一步：只跑通 Mock 前后端。

第二步：让前端全部页面从后端读取真实本地 JSON 数据。

第三步：接 DeepSeek，只先接“故事蓝图构建”和“生成下一章”。

第四步：拆分多 Agent：

```text
记忆检索 Agent
约束生成 Agent
章节导演 Agent
角色导演 Agent
伏笔管理 Agent
正文写作 Agent
检查修正 Agent
状态更新 Agent
```

第五步：加入任务队列，避免 DeepSeek 长请求让前端等待超时。

---

## 十、如果前端请求失败

优先检查：

1. 后端是否启动。
2. 访问 `http://127.0.0.1:8765/api/health` 是否成功。
3. 前端设置中的后端地址是否是 `http://127.0.0.1:8765`。
4. 前端 Mock 模式是否关闭。
5. 浏览器/终端是否有 CORS 或端口占用错误。
6. Windows 防火墙是否阻止本地端口。

