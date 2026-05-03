"""记忆检索 Agent。

独立负责上下文检索和 Token 控制。

输入: 项目状态 + 当前任务描述
输出: 相关记忆、伏笔、事件、角色上下文，以及 Token 预算使用情况。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    """记忆检索 Agent。

    根据当前任务需求，从项目状态中检索最相关的记忆片段，
    并严格控制 Token 预算。
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "memory_retrieval"
        self._description = "记忆检索与 Token 预算控制"

    @property
    def model_route_key(self) -> str:
        return "chapterDirector"

    @property
    def default_temperature(self) -> float:
        return 0.1

    @property
    def default_max_tokens(self) -> int:
        return 4000

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建记忆检索的 Prompt。

        Args:
            context: 包含项目状态和任务描述的上下文

        Returns:
            消息列表
        """
        system_prompt = (
            "你是小说自动化创作系统的【记忆检索 Agent】。\n"
            "你的任务是根据当前任务需求，从项目状态中检索最相关的记忆片段。\n\n"
            "你必须输出严格 JSON，不要写任何解释文字。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "relevant_memories": [\n'
            '    {"type": "chapter_summary", "chapter": 5, "relevance": 0.9, "content": "摘要内容"}\n'
            "  ],\n"
            '  "relevant_foreshadows": [\n'
            '    {"id": "伏笔ID", "name": "伏笔名", "relevance": 0.8, "reason": "相关原因"}\n'
            "  ],\n"
            '  "relevant_events": [\n'
            '    {"id": "事件ID", "description": "事件描述", "relevance": 0.7}\n'
            "  ],\n"
            '  "character_contexts": [\n'
            '    {"name": "角色名", "context": "角色当前状态摘要", "relevance": 0.85}\n'
            "  ],\n"
            '  "token_budget_used": 45000,\n'
            '  "token_budget_total": 64000\n'
            "}\n\n"
            "检索规则：\n"
            "1. 优先检索最近 3-5 章的摘要\n"
            "2. 优先检索高风险伏笔和近期需要处理的伏笔\n"
            "3. 优先检索与当前任务直接相关的角色\n"
            "4. 严格控制 Token 预算，不超过 64000\n"
            "5. 按相关度降序排列"
        )

        project = context.get("project", {})
        user_content = {
            "taskDescription": context.get("taskDescription", "生成下一章"),
            "chapterSummaries": project.get("memory", {}).get("chapterSummaries", [])[-5:],
            "foreshadows": project.get("foreshadows", []),
            "events": project.get("events", [])[-10:],
            "characters": project.get("characters", []),
            "currentChapter": len(project.get("chapters", [])),
        }

        user_prompt = (
            "请根据以下项目状态和任务需求，检索最相关的记忆片段：\n\n"
            f"{json.dumps(user_content, ensure_ascii=False, indent=2)}"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    # ------------------------------------------------------------------
    # 响应解析
    # ------------------------------------------------------------------

    def parse_response(self, content: str) -> dict[str, Any]:
        """解析 AI 返回的记忆检索结果。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的记忆检索结果
        """
        data = self._safe_parse_json(content)

        data.setdefault("relevant_memories", [])
        data.setdefault("relevant_foreshadows", [])
        data.setdefault("relevant_events", [])
        data.setdefault("character_contexts", [])
        data.setdefault("token_budget_used", 0)
        data.setdefault("token_budget_total", 64000)

        return data

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式: 使用 ContextBuilder 的逻辑返回结果。

        Args:
            context: 上下文数据

        Returns:
            模拟的记忆检索结果
        """
        project = context.get("project", {})
        chapters = project.get("chapters", [])
        current_chapter = len(chapters)
        memory = project.get("memory", {})

        # 相关记忆: 最近章节摘要
        relevant_memories = []
        summaries = memory.get("chapterSummaries", [])
        for summary in summaries[-5:]:
            relevant_memories.append({
                "type": "chapter_summary",
                "chapter": summary.get("chapter", 0),
                "relevance": 0.7 + (summary.get("chapter", 0) - current_chapter + 5) * 0.06,
                "content": summary.get("summary", ""),
            })

        # 相关伏笔: 高风险和近期需要处理的
        relevant_foreshadows = []
        for fs in project.get("foreshadows", []):
            risk = fs.get("risk", 0)
            if risk > 1:
                risk = risk / 100
            planned_payoff = fs.get("plannedPayoffChapter", fs.get("plannedPayoff", 999))

            if risk >= 0.3 or planned_payoff <= current_chapter + 10:
                relevant_foreshadows.append({
                    "id": fs.get("id", ""),
                    "name": fs.get("name", ""),
                    "relevance": round(min(1.0, risk + 0.3), 2),
                    "reason": f"风险值 {risk}，计划在第 {planned_payoff} 章处理。",
                })

        # 相关事件: 最近的事件
        relevant_events = []
        for event in project.get("events", [])[-5:]:
            relevant_events.append({
                "id": event.get("id", ""),
                "description": event.get("event") or event.get("description", ""),
                "relevance": 0.7,
            })

        # 角色上下文: 按出场频率排序
        character_contexts = []
        for char in project.get("characters", [])[:5]:
            name = char.get("name", "")
            if not name:
                continue
            character_contexts.append({
                "name": name,
                "context": (
                    f"角色: {name}，{char.get('role', '')}，"
                    f"情绪: {char.get('emotion', '')}，"
                    f"目标: {char.get('currentGoal', '')}"
                ),
                "relevance": 0.8 if "主角" in char.get("role", "") else 0.6,
            })

        # Token 预算估算
        total_tokens = sum(
            len(m.get("content", "")) for m in relevant_memories
        ) * 2  # 粗略估算: 1 字 ≈ 2 token
        total_tokens += len(json.dumps(relevant_foreshadows, ensure_ascii=False))
        total_tokens += len(json.dumps(relevant_events, ensure_ascii=False))
        total_tokens += len(json.dumps(character_contexts, ensure_ascii=False))

        return {
            "relevant_memories": relevant_memories,
            "relevant_foreshadows": relevant_foreshadows,
            "relevant_events": relevant_events,
            "character_contexts": character_contexts,
            "token_budget_used": min(total_tokens, 64000),
            "token_budget_total": 64000,
        }
