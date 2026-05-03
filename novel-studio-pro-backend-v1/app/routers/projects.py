from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import HTTPException
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.schemas import CreateProjectRequest, GenerateChapterRequest
from app.services.project_service import project_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ======================================================================
# 任务 1: 用户修改回灌 - 请求模型
# ======================================================================

class AnalyzeEditRequest(BaseModel):
    originalText: str = Field(..., min_length=1, description="原始正文")
    modifiedText: str = Field(..., min_length=1, description="修改后正文")


# ======================================================================
# 原有接口
# ======================================================================

@router.get("")
def list_projects():
    return {"projects": project_service.list_projects()}


@router.post("")
def create_project(payload: CreateProjectRequest):
    return project_service.create_project(payload.model_dump())


@router.get("/{project_id}")
def get_project(project_id: str):
    return {"project": project_service.get_project(project_id)}


@router.post("/{project_id}/build")
async def build_project(project_id: str):
    return await project_service.build_project(project_id)


@router.post("/{project_id}/blueprint/regenerate")
async def regenerate_blueprint(project_id: str):
    return await project_service.regenerate_blueprint(project_id)


# ======================================================================
# 任务 2: 任务队列 - 章节生成接口改造
# ======================================================================

@router.post("/{project_id}/chapters/generate-next")
async def generate_next_chapter(project_id: str, payload: GenerateChapterRequest, request: Request):
    """生成下一章。

    三种模式:
    1. SSE 流式: 请求头包含 Accept: text/event-stream
    2. 任务队列: 默认模式，立即返回 taskId，后台异步执行
    3. 向后兼容: 非流式请求保持原有行为（返回完整 JSON）
    """
    accept = request.headers.get("accept", "")

    # 模式 1: SSE 流式响应（向后兼容）
    if "text/event-stream" in accept:
        return await _generate_next_chapter_stream(project_id, payload.model_dump(), request)

    # 模式 2: 任务队列模式
    from app.core.task_queue import task_queue

    async def _execute_generate(task) -> dict[str, Any]:
        """后台执行章节生成。"""
        from app.core.task_queue import task_queue as tq

        # 步骤 1: 约束生成
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 5, "正在生成约束...")
        from app.services.ai_orchestrator import _run_full_pipeline
        from app.services.agents import (
            MemoryAgent, ForeshadowAgent, ConstraintAgent,
            CharacterDirectorAgent, DirectorAgent, WriterAgent,
            ReviewAgent, StateExtractorAgent, StateMerger,
            ContextBuilder,
        )
        from app.core.utils import make_id, now_iso
        from app.core.storage import store

        project = project_service.get_project(project_id)

        # 若项目没有蓝图，自动先构建
        if not project.get("storyBible"):
            await tq.update_progress(task.id, 2, "正在构建故事蓝图...")
            await project_service.build_project(project_id)
            project = project_service.get_project(project_id)

        context_builder = ContextBuilder()

        # 步骤 1: 记忆检索
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 5, "正在检索相关记忆...")
        memory_ctx = context_builder.build_constraint_context(project)
        memory_ctx["project"] = project
        memory_ctx["taskDescription"] = "生成下一章"
        memory_result = await MemoryAgent().run(memory_ctx)

        # 步骤 2: 伏笔规划
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 12, "正在规划伏笔处理...")
        foreshadow_ctx = context_builder.build_constraint_context(project)
        foreshadow_ctx["project"] = project
        foreshadow_result = await ForeshadowAgent().run(foreshadow_ctx)

        # 步骤 3: 约束生成（使用伏笔规划结果）
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 20, "正在生成约束条件...")
        constraint_ctx = context_builder.build_constraint_context(project)
        constraint_ctx["project"] = project
        constraint_ctx["foreshadow_plan"] = foreshadow_result.get("foreshadow_plan", [])
        constraints = await ConstraintAgent().run(constraint_ctx)

        # 步骤 4: 角色戏份规划
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 30, "正在规划角色戏份...")
        char_director_ctx = context_builder.build_director_context(project, constraints)
        char_director_ctx["project"] = project
        char_director_ctx["constraints"] = constraints
        char_plan = await CharacterDirectorAgent().run(char_director_ctx)

        # 步骤 5: 导演稿生成（使用角色规划结果）
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 40, "正在生成导演稿...")
        director_ctx = context_builder.build_director_context(project, constraints)
        director_ctx["project"] = project
        director_ctx["character_plan"] = char_plan.get("character_plan", {})
        director_plan = await DirectorAgent().run(director_ctx)

        # 步骤 6: 正文写作
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 55, "正在写作正文...")
        writer_ctx = context_builder.build_writer_context(project, constraints, director_plan)
        writer_ctx["project"] = project
        chapter_text = await WriterAgent().run(writer_ctx)

        # 步骤 7: 质量检查
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 75, "正在进行质量检查...")
        temp_chapter = {
            "text": chapter_text.get("text", ""),
            "title": director_plan.get("chapter_goal", ""),
            "number": len(project.get("chapters", [])) + 1,
            "wordCount": chapter_text.get("word_count", 0),
            "directorPlan": director_plan,
            "constraints": constraints,
        }
        review_ctx = context_builder.build_review_context(project, temp_chapter)
        review = await ReviewAgent().run(review_ctx)

        # 步骤 8: 状态提取
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 88, "正在提取状态变化...")
        state_extract_ctx = context_builder.build_state_extract_context(project, temp_chapter)
        state_extract_ctx["project"] = project
        state_result = await StateExtractorAgent().run(state_extract_ctx)

        # 步骤 9: 状态合并验证
        if task.is_cancelled():
            return None
        await tq.update_progress(task.id, 95, "正在合并验证状态...")
        state_delta = state_result.get("state_delta", {})
        merger = StateMerger()
        merged, preview = merger.validate_and_merge(project, state_delta)

        # 组装完整章节
        chapters = project.get("chapters", [])
        number = len(chapters) + 1
        from app.services.ai_orchestrator import chapter_title
        title = chapter_title(number)
        if project.get("chapterTitlePreview"):
            title = project["chapterTitlePreview"][number - 1].get("title", title)

        chapter = {
            "id": make_id("chapter"),
            "number": number,
            "title": title,
            "status": "pending",
            "wordCount": chapter_text.get("word_count", 0),
            "directorPlan": director_plan,
            "text": chapter_text.get("text", ""),
            "review": review,
            "stateDelta": state_delta,
            "statePreview": preview,
            "constraints": constraints,
            "createdAt": now_iso(),
        }

        # 保存到 pendingChapters
        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"][project_id]
            current.setdefault("pendingChapters", {})[chapter["id"]] = chapter
            current["updatedAt"] = now_iso()
            return chapter

        store.update(mut)

        return {"chapter": chapter}

    task_id = await task_queue.submit(
        task_type="generate_chapter",
        params={"project_id": project_id, "options": payload.model_dump()},
        executor=_execute_generate,
    )

    return {"taskId": task_id, "status": "pending"}


async def _generate_next_chapter_stream(
    project_id: str,
    options: dict,
    request: Request,
) -> StreamingResponse:
    """SSE 流式生成下一章。"""

    async def event_generator() -> AsyncGenerator[str, None]:
        from app.services.ai_orchestrator import generate_next_chapter_stream as gen_stream

        try:
            async for event in gen_stream(project_id, options):
                if await request.is_disconnected():
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("[Stream] 章节生成流式错误: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ======================================================================
# 任务 1: 用户修改回灌 - 分析修改接口
# ======================================================================

@router.post("/{project_id}/chapters/{chapter_id}/analyze-edit")
async def analyze_edit(
    project_id: str,
    chapter_id: str,
    payload: AnalyzeEditRequest,
):
    """分析用户对章节正文的修改，返回新的 state_delta 预览。

    不自动应用，让用户确认。
    """
    from app.services.user_edit_analyzer import analyze_user_edit

    project = project_service.get_project(project_id)

    result = await analyze_user_edit(
        original_text=payload.originalText,
        modified_text=payload.modifiedText,
        project=project,
    )

    return {
        "projectId": project_id,
        "chapterId": chapter_id,
        "analysis": result,
    }


# ======================================================================
# 确认章节接口（原有）
# ======================================================================

@router.post("/{project_id}/chapters/{chapter_id}/confirm")
def confirm_chapter(project_id: str, chapter_id: str):
    return project_service.confirm_chapter(project_id, chapter_id)


@router.post("/{project_id}/state/analyze")
def analyze_state(project_id: str):
    return project_service.analyze_state(project_id)


# ======================================================================
# 任务 2: 任务队列 - 任务管理接口
# ======================================================================

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态和进度。"""
    from app.core.task_queue import task_queue

    status = await task_queue.get_status(task_id)
    if not status:
        return JSONResponse(status_code=404, content={"detail": "任务不存在"})
    return status


@router.get("/tasks")
async def list_tasks():
    """列出所有任务。"""
    from app.core.task_queue import task_queue

    tasks = await task_queue.list_tasks()
    return {"tasks": tasks}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务。"""
    from app.core.task_queue import task_queue

    success = await task_queue.cancel(task_id)
    if not success:
        return JSONResponse(status_code=400, content={"detail": "任务不存在或已完成，无法取消"})
    return {"taskId": task_id, "status": "cancelled", "message": "任务已取消"}


# ======================================================================
# 连接测试 & 系统诊断接口
# ======================================================================

@router.get("/test-connection")
async def test_connection():
    """测试后端与 DeepSeek 的连通性"""
    from app.core.config import config
    from app.services.deepseek_client import DeepSeekClient

    if not config.use_deepseek:
        return {"ok": False, "message": "DeepSeek 未启用（USE_DEEPSEEK=false）"}
    if not config.deepseek_api_key:
        return {"ok": False, "message": "API Key 未配置"}

    client = DeepSeekClient()
    try:
        result = await client.chat(
            messages=[{"role": "user", "content": "你好，请回复\"连接正常\""}],
            max_tokens=20,
            temperature=0.1
        )
        return {"ok": True, "message": "连接成功", "response": result[:50] if result else ""}
    except Exception as e:
        return {"ok": False, "message": f"连接失败: {str(e)[:200]}"}


@router.post("/test-model")
async def test_model(body: dict = Body(...)):
    """测试指定模型的连通性"""
    from app.core.config import config
    from app.services.deepseek_client import DeepSeekClient

    model = body.get("model", config.deepseek_main_model)
    client = DeepSeekClient()
    try:
        result = await client.chat(
            messages=[{"role": "user", "content": "测试"}],
            max_tokens=10,
            temperature=0.1,
            model=model
        )
        return {"ok": True, "model": model, "message": "模型可用", "response": result[:50] if result else ""}
    except Exception as e:
        return {"ok": False, "model": model, "message": f"模型不可用: {str(e)[:200]}"}


@router.get("/test-embedding")
async def test_embedding():
    """测试 Embedding 服务连通性"""
    from app.services.embedding_client import embedding_client

    if not embedding_client.api_key:
        return {"ok": False, "message": "硅基流动 API Key 未配置"}

    try:
        vec = embedding_client.embed_query("测试文本")
        dim = len(vec) if vec else 0
        return {"ok": True, "message": "Embedding 服务正常", "dimension": dim, "model": embedding_client.model}
    except Exception as e:
        return {"ok": False, "message": f"Embedding 服务异常: {str(e)[:200]}"}


@router.get("/request-logs")
async def get_request_logs(limit: int = 50):
    """获取最近的 API 请求日志"""
    from app.core.storage import store
    data = store.read()
    logs = data.get("requestLogs", [])
    return {"logs": logs[-limit:]}


# ======================================================================
# 导出接口
# ======================================================================

@router.get("/{project_id}/export-characters")
async def export_characters(project_id: str):
    """导出项目角色表为 JSON"""
    from app.core.storage import store
    data = store.read()
    project = data.get("projects", {}).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    characters = project.get("characters", [])
    return {"characters": characters, "exported_at": datetime.now().isoformat()}


@router.get("/{project_id}/export-events")
async def export_events(project_id: str):
    """导出事件账本"""
    from app.core.storage import store
    data = store.read()
    project = data.get("projects", {}).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    events = project.get("events", [])
    return {"events": events, "total": len(events)}


# ======================================================================
# 语义搜索 & 记忆管理接口
# ======================================================================

@router.post("/{project_id}/semantic-search")
async def semantic_search(project_id: str, body: dict = Body(...)):
    """语义搜索相关章节/事件"""
    from app.core.storage import store
    from app.services.embedding_client import embedding_client

    query = body.get("query", "")
    search_type = body.get("type", "chapters")  # chapters, events, foreshadows
    top_k = body.get("top_k", 5)

    data = store.read()
    project = data.get("projects", {}).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if search_type == "chapters":
        docs = [
            {"id": ch.get("number", i), "text": f"第{ch.get('number','')}章 {ch.get('title','')} {ch.get('content','')[:500]}", "embedding": ch.get("embedding")}
            for i, ch in enumerate(project.get("chapters", []))
        ]
    elif search_type == "events":
        docs = [
            {"id": ev.get("id", i), "text": f"{ev.get('description','')} {ev.get('impact','')}", "embedding": ev.get("embedding")}
            for i, ev in enumerate(project.get("events", []))
        ]
    elif search_type == "foreshadows":
        docs = [
            {"id": fs.get("id", i), "text": f"{fs.get('content','')} {fs.get('expectedPayoff','')}", "embedding": fs.get("embedding")}
            for i, fs in enumerate(project.get("foreshadows", []))
        ]
    else:
        docs = []

    results = embedding_client.search_similar(query, docs, top_k=top_k)
    return {"query": query, "type": search_type, "results": results}


@router.post("/{project_id}/rebuild-memory")
async def rebuild_memory(project_id: str):
    """重建全局记忆：为所有章节生成 Embedding 向量"""
    from app.core.storage import store
    from app.services.embedding_client import embedding_client

    data = store.read()
    project = data.get("projects", {}).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not embedding_client.api_key:
        return {"ok": False, "message": "硅基流动 API Key 未配置，无法生成 Embedding"}

    chapters = project.get("chapters", [])
    if not chapters:
        return {"ok": False, "message": "没有章节可以处理"}

    # 收集需要生成 embedding 的章节
    texts = []
    indices = []
    for i, ch in enumerate(chapters):
        if not ch.get("embedding"):
            text = f"第{ch.get('number','')}章 {ch.get('title','')}\n{ch.get('content','')[:1000]}"
            texts.append(text)
            indices.append(i)

    if not texts:
        return {"ok": True, "message": "所有章节已有 Embedding，无需重建", "processed": 0}

    # 批量生成
    try:
        embeddings = embedding_client.embed_texts(texts)
        for idx, emb in zip(indices, embeddings):
            chapters[idx]["embedding"] = emb

        # 保存
        data["projects"][project_id]["chapters"] = chapters
        store.write(data)

        return {"ok": True, "message": f"已为 {len(embeddings)} 个章节生成 Embedding", "processed": len(embeddings)}
    except Exception as e:
        return {"ok": False, "message": f"生成失败: {str(e)[:200]}"}


@router.post("/{project_id}/compress-history")
async def compress_history(project_id: str):
    """压缩历史章节正文（保留摘要，删除完整正文以节省 token）"""
    from app.core.storage import store

    data = store.read()
    project = data.get("projects", {}).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    chapters = project.get("chapters", [])
    compressed_count = 0

    for ch in chapters:
        content = ch.get("content", "")
        if content and len(content) > 200 and not ch.get("compressed"):
            # 保留前200字作为摘要
            ch["content"] = content[:200] + "\n\n[... 已压缩，原文 " + str(len(content)) + " 字 ...]"
            ch["compressed"] = True
            ch["original_length"] = len(content)
            compressed_count += 1

    if compressed_count > 0:
        data["projects"][project_id]["chapters"] = chapters
        store.write(data)

    return {"ok": True, "compressed": compressed_count, "message": f"已压缩 {compressed_count} 个章节的正文"}


@router.post("/{project_id}/rebuild-ledger")
async def rebuild_ledger(project_id: str):
    """从所有章节中重建事件账本"""
    from app.core.storage import store

    data = store.read()
    project = data.get("projects", {}).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    events = []
    for ch in project.get("chapters", []):
        state_delta = ch.get("stateDelta", {})
        if state_delta:
            for evt in state_delta.get("new_events", state_delta.get("newEvents", [])):
                events.append({
                    "id": f"ch{ch.get('number','?')}-{len(events)}",
                    "chapter": ch.get("number", "?"),
                    "description": evt if isinstance(evt, str) else evt.get("description", str(evt)),
                    "type": "plot"
                })

    data["projects"][project_id]["events"] = events
    store.write(data)

    return {"ok": True, "rebuilt": len(events), "message": f"已从章节中重建 {len(events)} 条事件"}
