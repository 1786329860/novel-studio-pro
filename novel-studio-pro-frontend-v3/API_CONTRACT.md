# Novel Studio Pro 前端需要的后端接口契约

前端只调用本地后端，不直接调用 DeepSeek。默认后端地址：

```text
http://127.0.0.1:8765
```

## 1. 创建项目

```http
POST /api/projects
```

请求：

```json
{
  "title": "夜火长明",
  "outline": "用户输入的大纲",
  "genre": "奇幻",
  "lengthType": "long",
  "mode": "balanced"
}
```

返回：

```json
{
  "project": {
    "id": "project_xxx",
    "title": "夜火长明",
    "storyBible": {},
    "characters": [],
    "foreshadows": [],
    "truthSource": {},
    "events": [],
    "chapters": [],
    "status": {}
  }
}
```

## 2. 自动构建项目蓝图

```http
POST /api/projects/{project_id}/build
```

职责：

- 分析总大纲。
- 自动补全写作风格。
- 自动生成分卷规划。
- 自动生成每卷走向。
- 自动生成角色系统。
- 自动生成伏笔与真相源。
- 自动生成章节标题预览。

返回：

```json
{
  "project": {},
  "message": "AI 已完成故事蓝图、分卷规划、角色系统、伏笔与真相源初始化。"
}
```

## 3. 重新扩写蓝图

```http
POST /api/projects/{project_id}/blueprint/regenerate
```

返回：

```json
{
  "project": {},
  "message": "已重新扩写蓝图。"
}
```

## 4. 生成下一章

```http
POST /api/projects/{project_id}/chapters/generate-next
```

请求：

```json
{
  "mode": "standard",
  "qualityThreshold": 85,
  "maxInputTokens": 64000,
  "maxOutputTokens": 12000,
  "userInstruction": ""
}
```

返回：

```json
{
  "chapter": {
    "id": "chapter_xxx",
    "number": 14,
    "title": "旧账与夜火",
    "status": "pending",
    "wordCount": 2856,
    "directorPlan": {
      "goal": "本章目标",
      "pov": "视角安排",
      "roleFocus": {},
      "forbidden": []
    },
    "text": "章节正文",
    "review": {
      "totalScore": 92,
      "tests": []
    },
    "stateDelta": {
      "newForeshadows": [],
      "relationshipChanges": [],
      "eventUpdates": [],
      "timeline": []
    }
  }
}
```

## 5. 确认章节入库

```http
POST /api/projects/{project_id}/chapters/{chapter_id}/confirm
```

职责：

- 将 pending 章节变成 confirmed。
- 更新章节表。
- 更新事件账本。
- 更新角色状态。
- 更新伏笔生命周期。
- 更新真相源。
- 更新状态快照。

返回：

```json
{
  "project": {},
  "chapter": {}
}
```

## 6. 分析状态

```http
POST /api/projects/{project_id}/state/analyze
```

返回：

```json
{
  "report": {
    "generatedAt": "2026-05-01T00:00:00.000Z",
    "summary": "状态良好。主线推进稳定，伏笔风险可控。",
    "score": 92
  }
}
```

## 7. 后续建议补充接口

这些接口当前 UI 已有入口，后端可以第二阶段实现：

```http
GET /api/projects/{project_id}/characters
PUT /api/projects/{project_id}/characters/{character_id}
GET /api/projects/{project_id}/foreshadows
PUT /api/projects/{project_id}/foreshadows/{foreshadow_id}
GET /api/projects/{project_id}/memory
POST /api/projects/{project_id}/memory/rebuild
GET /api/settings/model-routes
PUT /api/settings/model-routes
GET /api/settings/deepseek
PUT /api/settings/deepseek
POST /api/settings/deepseek/test
```

## DeepSeek 超时与输入输出上限要求

后端必须处理：

1. 请求超时。
2. 动态重试。
3. 流式输出或任务队列。
4. JSON 输出解析失败时自动修复。
5. 输入上下文过长时自动压缩。
6. 输出过长时分场景生成。
7. 每次请求记录模型、温度、输入长度、输出长度和耗时。

前端只负责展示和触发，不负责直接保存 API Key 到源码里。
