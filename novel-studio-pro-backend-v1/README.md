# Novel Studio Pro Backend v1

这是 Novel Studio Pro 个人本地小说自动化软件的 FastAPI 后端骨架。

特点：

- 本地运行，无登录。
- 默认 Mock 模式，不需要 DeepSeek 也能跑完整流程。
- 预留 DeepSeek API 接入位置。
- 使用 JSON 文件做本地持久化，适合第一版个人使用。
- 已实现项目创建、蓝图构建、下一章生成、确认入库、状态分析、角色、伏笔、真相源、全局记忆、模型配置、DeepSeek 设置等接口。

快速启动：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python start_backend.py
```

访问：

```text
http://127.0.0.1:8765/docs
```

详细说明请看：

```text
README_TRAE_BACKEND.md
FRONTEND_CONNECTION_GUIDE.md
API_CONTRACT_BACKEND.md
```
