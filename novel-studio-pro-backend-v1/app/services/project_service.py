from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.storage import store
from app.core.utils import make_id, now_iso, deep_merge
from app.services import ai_orchestrator


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

        def mut(data: dict[str, Any]) -> dict[str, Any]:
            current = data["projects"][project_id]
            pending = current.setdefault("pendingChapters", {})
            pending.pop(chapter_id, None)
            chapters = current.setdefault("chapters", [])
            if not any(c.get("id") == chapter_id for c in chapters):
                chapters.append(chapter)

            # 事件账本更新：兼容 stateDelta.eventUpdates 为字符串或对象。
            events = current.setdefault("events", [])
            for index, event in enumerate(delta.get("eventUpdates", [])):
                if isinstance(event, str):
                    event = {
                        "id": make_id("evt"),
                        "chapter": chapter.get("number"),
                        "time": f"第{chapter.get('number')}章 0{index}:12",
                        "scene": "自动识别场景",
                        "characters": "江离 / 沈烬" if index % 2 else "江离",
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
                events.append(event)

            # 伏笔生命周期更新：兼容 stateDelta.newForeshadows 为字符串或对象。
            foreshadows = current.setdefault("foreshadows", [])
            for index, foreshadow in enumerate(delta.get("newForeshadows", [])):
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
                foreshadows.append(item)

            # 角色活跃状态粗更新
            character_names = set()
            for event in events[-len(delta.get("eventUpdates", [])):] if delta.get("eventUpdates") else []:
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

            # 状态面板更新
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
            status.update({
                "currentChapter": current_chapter,
                "currentChapterTitle": f"第 {current_chapter} 章 · {chapter.get('title')}",
                "mainProgress": min(100, max(status.get("mainProgress", 0), int(current_chapter / total_target * 100))),
                "foreshadowTotal": len(foreshadows),
                "foreshadowCount": len(foreshadows),
                "foreshadowResolved": len([f for f in foreshadows if f.get("status") in {"已回收", "已解决"}]),
                "activeCharacters": active_count,
                "totalCharacters": len(current.get("characters", [])),
                "deviationRisk": round(max(0.03, min(0.6, old_deviation + 0.01)), 2),
                "qualityScore": chapter.get("review", {}).get("totalScore", status.get("qualityScore", 90)),
                "tests": chapter.get("review", {}).get("tests", []),
                "lastAnalyzedAt": now_iso(),
            })

            # 记忆更新
            memory = current.setdefault("memory", {})
            summaries = memory.setdefault("chapterSummaries", [])
            summaries.append({
                "chapter": current_chapter,
                "title": chapter.get("title"),
                "summary": f"第{current_chapter}章推进了旧案调查，并更新了角色关系与伏笔。",
                "wordCount": chapter.get("wordCount", 0),
            })
            snapshots = memory.setdefault("stateSnapshots", [])
            snapshots.append({
                "chapter": current_chapter,
                "createdAt": now_iso(),
                "status": dict(status),
            })
            if len(summaries) > 300:
                del summaries[:-300]
            if len(snapshots) > 300:
                del snapshots[:-300]

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


project_service = ProjectService()
