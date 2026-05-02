# 前端连接后端说明

## 目标架构

```text
Electron 前端
    ↓ 只请求本地接口
FastAPI 本地后端 http://127.0.0.1:8765
    ↓ 可选
DeepSeek API
```

前端不要直接请求 DeepSeek。

## 前端设置建议

在前端 “生成设置 / DeepSeek API 设置” 中：

```text
Mock 模式：关闭
本地后端地址：http://127.0.0.1:8765
请求超时：180000
失败重试次数：2
```

## 核心流程

```text
POST /api/projects
POST /api/projects/{project_id}/build
POST /api/projects/{project_id}/chapters/generate-next
POST /api/projects/{project_id}/chapters/{chapter_id}/confirm
POST /api/projects/{project_id}/state/analyze
```

## 注意

如果前端 v3 暂时没有调用角色、伏笔、模型设置接口，不要着急改前端主流程。后端已经预留了这些接口，后续逐步接即可。
