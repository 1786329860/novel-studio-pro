# 后端接口契约摘要

默认地址：

```text
http://127.0.0.1:8765
```

## 创建项目

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
  "project": {}
}
```

## 自动构建蓝图

```http
POST /api/projects/{project_id}/build
```

返回：

```json
{
  "project": {},
  "message": "AI 已完成故事蓝图、分卷规划、角色系统、伏笔与真相源初始化。"
}
```

## 生成下一章

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
  "userInstruction": "下一章多写女主"
}
```

返回：

```json
{
  "chapter": {
    "id": "chapter_xxx",
    "number": 1,
    "title": "黑夜中的火光",
    "status": "pending",
    "wordCount": 2856,
    "directorPlan": {},
    "text": "章节正文",
    "review": {},
    "stateDelta": {}
  }
}
```

## 确认章节入库

```http
POST /api/projects/{project_id}/chapters/{chapter_id}/confirm
```

返回：

```json
{
  "project": {},
  "chapter": {}
}
```
