from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from app.core.storage import store
from app.core.utils import make_id, now_iso, deep_merge, truncate_text
from app.services import ai_orchestrator
from app.services.agents import StateMerger

logger = logging.getLogger(__name__)


class ProjectService:
    def list_projects(self) -> list[dict[str, Any]]:
        data = store.read()
        projects = list(data.get("projects", {}).values())
        projects.sort(key=lambda item: item.get("updatedAt", ""), reverse=True)
        return projects

    def get_project(self, project_id: str) -> dict[str, Any]:
        project = store.read().get("projects", {}).get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        return project

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = make_id("project")
        title = payload.get("title") or "未命名小说"
        now = now_iso()
        project = {
            "id": project_id,
            "title": title,
            "outline": payload.get("outline", ""),
            "genre": payload.get("genre", "奇幻"),
            "lengthType": payload.get("lengthType", "long"),
            "mode": payload.get("mode", "balanced"),
            "createdAt": now,
            "updatedAt": now,
            "totalTargetChapters": 40 if payload.get("lengthType") == "short" else 80 if payload.get("lengthType") == "medium" else 220 if payload.get("lengthType") == "superlong" else 120,
            "wordCount": 0,
            "currentChapterNumber": 0,
            "storyBible": {},
            "volumePlan": [],
            "stagePlan": [],
            "chapterTitlePreview": [],
            "characters": [],
            "relationships": [],
            "foreshadows": [],
            "truthSource": {},
            "events": [],
            "chapters": [],
            "pendingChapters": {},
            "status": {
                "currentChapter": 0,
                "currentChapterTitle": "尚未开始",
                "mainProgress": 0,
                "qualityScore": 90,
                "deviationRisk": 0.05,
            },
            "memory": {
                "storyBibleMemory": "项目已创建，等待自动构建故事蓝图。",
                "chapterSummaries": [],
                "stateSnapshots": [],
            },
        }

        def mut(data: dict[str, Any]) -> dict[str, Any]:
            data.setdefault("projects", {})[project_id] = project
            return project

        created = store.update(mut)
        return {"project": created}

    async def build_project(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        blueprint = await ai_orchestrator.build_story_blueprint(project)
        blueprint = ai_orchestrator._normalize_blueprint(blueprint)

        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"][project_id]
            current.update(blueprint)
            current["updatedAt"] = now_iso()
            return current

        updated = store.update(mut)
        return {"project": updated, "message": "AI 已完成故事蓝图、分卷规划、角色系统、伏笔与真相源初始化。"}

    async def regenerate_blueprint(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        blueprint = await ai_orchestrator.build_story_blueprint(project, variant="regenerate")

        # 保留已确认章节和事件，避免重写蓝图时丢失进度。
        preserved = {
            "chapters": project.get("chapters", []),
            "events": project.get("events", []),
            "pendingChapters": project.get("pendingChapters", {}),
        }

        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"][project_id]
            current.update(blueprint)
            current.update(preserved)
            current["updatedAt"] = now_iso()
            return current

        updated = store.update(mut)
        return {"project": updated, "message": "已重新扩写蓝图。"}

    async def generate_next_chapter(self, project_id: str, options: dict[str, Any]) -> dict[str, Any]:
        project = self.get_project(project_id)
        # 若项目没有蓝图，自动先构建，避免用户忘记点击。
        if not project.get("storyBible"):
            await self.build_project(project_id)
            project = self.get_project(project_id)

        chapter = await ai_orchestrator.generate_next_chapter(project, options)

        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"][project_id]
            current.setdefault("pendingChapters", {})[chapter["id"]] = chapter
            current["updatedAt"] = now_iso()
            return chapter

        saved_chapter = store.update(mut)
        return {"chapter": saved_chapter}

    def confirm_chapter(self, project_id: str, chapter_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        chapter = project.get("pendingChapters", {}).get(chapter_id)
        if not chapter:
            # 已经确认过时允许幂等返回。
            existing = next((c for c in project.get("chapters", []) if c.get("id") == chapter_id), None)
            if existing:
                return {"project": project, "chapter": existing}
            raise HTTPException(status_code=404, detail="待确认章节不存在")

        chapter = dict(chapter)
        chapter["status"] = "confirmed"
        chapter["confirmedAt"] = now_iso()
        delta = chapter.get("stateDelta", {})

        # ============================================================
        # 任务 1: 用户修改回灌
        # 检查 pendingChapter 的 text 是否与生成时的原始 text 不同
        # 如果不同，调用 analyze_user_edit() 获取新的 state_delta
        # ============================================================
        original_text = chapter.get("_originalText", "")
        current_text = chapter.get("text", "")
        if original_text and current_text and original_text != current_text:
            logger.info(
                "[confirm_chapter] 检测到正文被修改，重新提取状态变化"
            )
            try:
                import asyncio
                from app.services.user_edit_analyzer import analyze_user_edit

                # 在同步方法中运行异步函数
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已经在事件循环中，使用 nest_asyncio 或创建新线程
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        edit_result = pool.submit(
                            asyncio.run,
                            analyze_user_edit(original_text, current_text, project)
                        ).result(timeout=30)
                else:
                    edit_result = loop.run_until_complete(
                        analyze_user_edit(original_text, current_text, project)
                    )

                if edit_result and edit_result.get("action") != "skip":
                    new_delta = edit_result.get("state_delta", {})
                    if new_delta:
                        # 使用 StateMerger 验证新的 state_delta
                        try:
                            merger = StateMerger()
                            _, _ = merger.validate_and_merge(project, new_delta)
                            # 合并新的 delta 到原有 delta
                            delta = _merge_deltas(delta, new_delta)
                            chapter["stateDelta"] = delta
                            chapter["_userEditAnalysis"] = edit_result
                            logger.info(
                                "[confirm_chapter] 用户修改状态变化已合并"
                            )
                        except Exception as exc:
                            logger.warning(
                                "[confirm_chapter] 新 state_delta 验证失败，使用原始 delta: %s",
                                exc,
                            )
            except Exception as exc:
                logger.warning(
                    "[confirm_chapter] 用户修改分析失败，使用原始 delta: %s", exc
                )

        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"][project_id]
            pending = current.setdefault("pendingChapters", {})
            pending.pop(chapter_id, None)
            chapters = current.setdefault("chapters", [])
            if not any(c.get("id") == chapter_id for c in chapters):
                chapters.append(chapter)

            # ============================================================
            # 状态合并: 优先使用 StateMerger 处理新格式 state_delta
            # ============================================================
            _apply_state_delta_via_merger(current, chapter, delta)

            # ============================================================
            # 事件账本更新: 兼容 stateDelta.eventUpdates / new_events
            # ============================================================
            _apply_event_updates(current, chapter, delta)

            # ============================================================
            # 伏笔生命周期更新: 兼容 stateDelta.newForeshadows / foreshadow_changes
            # ============================================================
            _apply_foreshadow_updates(current, chapter, delta)

            # ============================================================
            # 角色活跃状态更新
            # ============================================================
            _apply_character_activity(current, chapter, delta)

            # ============================================================
            # 状态面板更新
            # ============================================================
            _apply_status_update(current, chapter, chapters)

            # ============================================================
            # 记忆更新
            # ============================================================
            _apply_memory_update(current, chapter, chapters)

            current["updatedAt"] = now_iso()
            return {"project": current, "chapter": chapter}

        return store.update(mut)

    def analyze_state(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        report = ai_orchestrator.analyze_project_state(project)

        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"][project_id]
            current.setdefault("status", {})["lastAnalyzedAt"] = report["generatedAt"]
            current.setdefault("status", {})["qualityScore"] = report["score"]
            current["updatedAt"] = now_iso()
            return {"report": report}

        return store.update(mut)

    def patch_character(self, project_id: str, character_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"].get(project_id)
            if not current:
                raise HTTPException(status_code=404, detail="项目不存在")
            for character in current.get("characters", []):
                if character.get("id") == character_id:
                    character.update(patch)
                    current["updatedAt"] = now_iso()
                    return character
            raise HTTPException(status_code=404, detail="角色不存在")
        return store.update(mut)

    def patch_foreshadow(self, project_id: str, foreshadow_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"].get(project_id)
            if not current:
                raise HTTPException(status_code=404, detail="项目不存在")
            for item in current.get("foreshadows", []):
                if item.get("id") == foreshadow_id:
                    item.update(patch)
                    current["updatedAt"] = now_iso()
                    return item
            raise HTTPException(status_code=404, detail="伏笔不存在")
        return store.update(mut)

    def rebuild_memory(self, project_id: str, mode: str = "standard") -> dict[str, Any]:
        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"].get(project_id)
            if not current:
                raise HTTPException(status_code=404, detail="项目不存在")
            chapters = current.get("chapters", [])
            memory = current.setdefault("memory", {})
            memory["storyBibleMemory"] = "已根据当前故事蓝图、章节与事件账本重建全局记忆。"
            memory["chapterSummaries"] = [
                {
                    "chapter": c.get("number"),
                    "title": c.get("title"),
                    "summary": f"第{c.get('number')}章：{c.get('title')}。主要推进主线、关系或伏笔。",
                    "wordCount": c.get("wordCount", 0),
                }
                for c in chapters[-120:]
            ]
            memory["nextContextPack"] = {
                "mode": mode,
                "priority": ["故事蓝图", "真相源", "事件账本", "高风险伏笔", "角色掉线预警", "最近三章摘要"],
                "tokenStrategy": "严格控制输入，必要时只传状态摘要和相关场景。",
            }
            current["updatedAt"] = now_iso()
            return {"memory": memory, "message": "全局记忆已重建。"}
        return store.update(mut)


# ======================================================================
# confirm_chapter 内部辅助函数
# ======================================================================

def _apply_state_delta_via_merger(
    current: dict[str, Any],
    chapter: dict[str, Any],
    delta: dict[str, Any],
) -> None:
    """使用 StateMerger 处理新格式的 state_delta。

    新格式包含: character_changes, relationship_changes, foreshadow_changes,
    new_events, knowledge_updates 等结构化字段。
    如果 state_delta 为空或不包含新格式字段，跳过此步骤。
    """
    # 检查是否为新格式 state_delta（由 StateExtractorAgent 生成）
    new_format_keys = {"character_changes", "relationship_changes", "foreshadow_changes", "new_events"}
    has_new_format = any(delta.get(k) for k in new_format_keys)

    if not has_new_format:
        return

    try:
        merger = StateMerger()
        # StateMerger.merge_delta 会直接修改 current（作为 project 参数传入）
        merger.merge_delta(current, delta)
        logger.info("[confirm_chapter] StateMerger 合并完成")
    except Exception as exc:
        logger.warning("[confirm_chapter] StateMerger 合并失败，回退到原有逻辑: %s", exc)


def _apply_event_updates(
    current: dict[str, Any],
    chapter: dict[str, Any],
    delta: dict[str, Any],
) -> None:
    """更新事件账本。

    兼容两种格式:
    - 旧格式: stateDelta.eventUpdates (字符串或对象列表)
    - 新格式: stateDelta.new_events (由 StateMerger 已处理的结构化事件)

    如果 StateMerger 已经处理了 new_events，这里只处理旧格式的 eventUpdates。
    """
    events = current.setdefault("events", [])

    # 旧格式: eventUpdates
    event_updates = delta.get("eventUpdates", [])
    if not event_updates:
        return

    # 检查是否已被 StateMerger 处理（避免重复添加）
    # StateMerger 处理的事件有 description 字段，旧格式的事件通常是字符串
    for index, event in enumerate(event_updates):
        if isinstance(event, str):
            # Get actual character names from project
            char_names = [c.get("name", "") for c in current.get("characters", []) if c.get("name")]
            characters_str = " / ".join(char_names[:3]) if char_names else "未知角色"
            event = {
                "id": make_id("evt"),
                "chapter": chapter.get("number"),
                "time": f"第{chapter.get('number')}章 0{index}:12",
                "scene": "自动识别场景",
                "characters": characters_str if index % 2 else char_names[0] if char_names else "未知角色",
                "event": event,
                "impact": "推进主线" if index % 2 == 0 else "角色行动",
                "visibility": "主角/读者",
            }
        else:
            event = dict(event)
            if not event.get("id"):
                event["id"] = make_id("evt")
            if isinstance(event.get("characters"), list):
                event["characters"] = "、".join(map(str, event["characters"]))

        # 检查是否已存在（避免 StateMerger 重复添加）
        event_desc = event.get("event") or event.get("description", "")
        already_exists = any(
            e.get("event") == event_desc or e.get("description") == event_desc
            for e in events
        )
        if not already_exists:
            events.append(event)


def _apply_foreshadow_updates(
    current: dict[str, Any],
    chapter: dict[str, Any],
    delta: dict[str, Any],
) -> None:
    """更新伏笔生命周期。

    兼容两种格式:
    - 旧格式: stateDelta.newForeshadows (字符串或对象列表)
    - 新格式: stateDelta.foreshadow_changes (由 StateMerger 已处理)

    如果 StateMerger 已经处理了 foreshadow_changes，这里只处理旧格式的 newForeshadows。
    """
    foreshadows = current.setdefault("foreshadows", [])

    # 旧格式: newForeshadows
    new_foreshadows = delta.get("newForeshadows", [])
    if not new_foreshadows:
        return

    for index, foreshadow in enumerate(new_foreshadows):
        if isinstance(foreshadow, str):
            item = {
                "id": make_id("fb"),
                "name": foreshadow,
                "firstChapter": chapter.get("number"),
                "lastMentioned": chapter.get("number"),
                "lastMentionedChapter": chapter.get("number"),
                "status": "已埋下",
                "importance": "medium",
                "risk": round(0.18 + index * 0.08, 2),
                "plannedPayoff": chapter.get("number", 1) + 10 + index * 4,
                "plannedPayoffChapter": chapter.get("number", 1) + 10 + index * 4,
                "nextAction": "后续章节轻微回响。",
            }
        else:
            item = {
                "id": foreshadow.get("id") or make_id("fb"),
                "name": foreshadow.get("name", "未命名伏笔"),
                "firstChapter": chapter.get("number"),
                "lastMentioned": chapter.get("number"),
                "lastMentionedChapter": chapter.get("number"),
                "status": foreshadow.get("status", "已埋下"),
                "importance": foreshadow.get("importance", "medium"),
                "risk": foreshadow.get("risk", 0.2),
                "plannedPayoff": foreshadow.get("plannedPayoff", foreshadow.get("plannedPayoffChapter", chapter.get("number", 1) + 10)),
                "plannedPayoffChapter": foreshadow.get("plannedPayoffChapter", foreshadow.get("plannedPayoff", chapter.get("number", 1) + 10)),
                "nextAction": foreshadow.get("nextAction", "后续章节轻微回响。"),
            }
        if item.get("risk", 0) > 1:
            item["risk"] = round(item["risk"] / 100, 2)

        # 检查是否已存在（避免 StateMerger 重复添加）
        already_exists = any(
            f.get("name") == item.get("name") for f in foreshadows
        )
        if not already_exists:
            foreshadows.append(item)


def _apply_character_activity(
    current: dict[str, Any],
    chapter: dict[str, Any],
    delta: dict[str, Any],
) -> None:
    """更新角色活跃状态。

    基于事件账本中的角色出场信息，更新 lastAppeared、dropoutRisk、agencyScore。
    如果 StateMerger 已经通过 character_changes 更新了这些字段，这里做补充检查。
    """
    events = current.get("events", [])
    # 获取本章新增的事件
    chapter_events = delta.get("eventUpdates", [])
    if not chapter_events:
        return

    character_names = set()
    for event in events[-len(chapter_events):] if chapter_events else []:
        chars = str(event.get("characters", ""))
        for name in chars.replace("/", "、").split("、"):
            if name.strip():
                character_names.add(name.strip())

    for character in current.get("characters", []):
        current_risk = float(character.get("dropoutRisk", 0.2))
        current_agency = float(character.get("agencyScore", 0.7))
        if current_risk > 1:
            current_risk = current_risk / 100
        if current_agency > 1:
            current_agency = current_agency / 100
        if character.get("name") in character_names:
            character["lastAppeared"] = chapter.get("number")
            character["lastAppearedChapter"] = chapter.get("number")
            character["dropoutRisk"] = round(max(0.05, current_risk - 0.06), 2)
            character["agencyScore"] = round(min(1.0, current_agency + 0.02), 2)
        else:
            character["dropoutRisk"] = round(min(0.95, current_risk + 0.03), 2)
            character["agencyScore"] = round(current_agency, 2)


def _apply_status_update(
    current: dict[str, Any],
    chapter: dict[str, Any],
    chapters: list[dict[str, Any]],
) -> None:
    """更新状态面板。"""
    current_chapter = int(chapter.get("number", len(chapters)))
    status = current.setdefault("status", {})
    total_target = int(current.get("totalTargetChapters", 120) or 120)
    current["currentChapterNumber"] = current_chapter
    current["wordCount"] = int(current.get("wordCount", 0) or 0) + int(chapter.get("wordCount", 0) or 0)
    current["totalTargetChapters"] = total_target
    active_count = len([c for c in current.get("characters", []) if float(c.get("dropoutRisk", 1)) < 0.5])
    old_deviation = float(status.get("deviationRisk", 0.08) or 0.08)
    if old_deviation > 1:
        old_deviation = old_deviation / 100

    # 从 review 中获取质量分数（兼容新旧格式）
    review = chapter.get("review", {})
    quality_score = review.get("totalScore", status.get("qualityScore", 90))
    tests = review.get("tests", [])

    status.update({
        "currentChapter": current_chapter,
        "currentChapterTitle": f"第 {current_chapter} 章 · {chapter.get('title')}",
        "mainProgress": min(100, max(status.get("mainProgress", 0), int(current_chapter / total_target * 100))),
        "foreshadowTotal": len(current.get("foreshadows", [])),
        "foreshadowCount": len(current.get("foreshadows", [])),
        "foreshadowResolved": len([f for f in current.get("foreshadows", []) if f.get("status") in {"已回收", "已解决"}]),
        "activeCharacters": active_count,
        "totalCharacters": len(current.get("characters", [])),
        "deviationRisk": round(max(0.03, min(0.6, old_deviation + 0.01)), 2),
        "qualityScore": quality_score,
        "tests": tests,
        "lastAnalyzedAt": now_iso(),
    })


def _apply_memory_update(
    current: dict[str, Any],
    chapter: dict[str, Any],
    chapters: list[dict[str, Any]],
) -> None:
    """更新记忆系统（章节摘要 + 状态快照）。"""
    current_chapter = int(chapter.get("number", len(chapters)))
    memory = current.setdefault("memory", {})

    # 章节摘要
    summaries = memory.setdefault("chapterSummaries", [])
    ch_title = chapter.get("title", f"第{current_chapter}章")
    # 生成有意义的章节摘要（使用正文前300字 + 导演稿目标）
    chapter_text = chapter.get("text", "")
    director_plan = chapter.get("directorPlan", {})
    chapter_goal = director_plan.get("chapter_goal", "") or director_plan.get("goal", "")
    if chapter_text:
        summary_text = truncate_text(chapter_text, 300)
        if chapter_goal:
            summary_text = f"[目标: {chapter_goal}] {summary_text}"
    else:
        summary_text = f"第{current_chapter}章「{ch_title}」已完成。"
        if chapter_goal:
            summary_text += f" 目标: {chapter_goal}"

    summaries.append({
        "chapter": current_chapter,
        "title": chapter.get("title"),
        "summary": summary_text,
        "wordCount": chapter.get("wordCount", 0),
    })

    # 状态快照
    snapshots = memory.setdefault("stateSnapshots", [])
    snapshots.append({
        "chapter": current_chapter,
        "createdAt": now_iso(),
        "status": dict(current.get("status", {})),
    })

    # 限制历史记录数量
    if len(summaries) > 300:
        del summaries[:-300]
    if len(snapshots) > 300:
        del snapshots[:-300]


project_service = ProjectService()


# ======================================================================
# 任务 1: 用户修改回灌 - delta 合并辅助函数
# ======================================================================

def _merge_deltas(
    original_delta: dict[str, Any],
    new_delta: dict[str, Any],
) -> dict[str, Any]:
    """合并两个 state_delta，新 delta 的内容优先。

    对于列表类型的字段，将新 delta 的项追加到原有列表中（去重）。
    对于标量字段，新 delta 覆盖原有值。

    Args:
        original_delta: 原始 state_delta
        new_delta: 新的 state_delta

    Returns:
        合并后的 state_delta
    """
    merged = dict(original_delta)

    # 列表类型字段: 追加并去重
    list_fields = [
        "character_changes",
        "relationship_changes",
        "foreshadow_changes",
        "new_events",
        "timeline_updates",
        "knowledge_updates",
        "eventUpdates",
        "newForeshadows",
    ]

    for field in list_fields:
        original_list = merged.get(field, [])
        new_list = new_delta.get(field, [])

        if not new_list:
            continue

        if not original_list:
            merged[field] = new_list
            continue

        # 去重追加
        existing_keys = set()
        for item in original_list:
            if isinstance(item, dict):
                key = item.get("id") or item.get("character_id") or item.get("description", "")
                existing_keys.add(key)
            elif isinstance(item, str):
                existing_keys.add(item)

        for item in new_list:
            if isinstance(item, dict):
                key = item.get("id") or item.get("character_id") or item.get("description", "")
                if key not in existing_keys:
                    original_list.append(item)
                    existing_keys.add(key)
            elif isinstance(item, str):
                if item not in existing_keys:
                    original_list.append(item)
                    existing_keys.add(item)

        merged[field] = original_list

    # 标量字段: 新值覆盖
    scalar_fields = ["main_progress_delta"]
    for field in scalar_fields:
        if field in new_delta:
            merged[field] = new_delta[field]

    # relationshipChanges 特殊处理（旧格式）
    if "relationshipChanges" in new_delta:
        original_rel = merged.get("relationshipChanges", [])
        new_rel = new_delta["relationshipChanges"]
        if isinstance(new_rel, list):
            merged["relationshipChanges"] = original_rel + [
                r for r in new_rel if r not in original_rel
            ]
        else:
            merged["relationshipChanges"] = new_rel

    return merged
