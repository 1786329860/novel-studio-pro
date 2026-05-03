from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

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
