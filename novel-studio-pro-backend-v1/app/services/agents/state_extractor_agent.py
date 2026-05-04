"""状态提取 Agent。

任务: 从正文中提取状态变化。
这是流水线的第五步，为状态合并器提供变更数据。

输出结构:
    - state_delta: 状态变化包
        - main_progress_delta: 主线进度变化
        - character_changes: 角色状态变化列表
        - relationship_changes: 关系变化列表
        - foreshadow_changes: 伏笔变化列表
        - new_events: 新事件列表
        - timeline_updates: 时间线更新列表
        - knowledge_updates: 角色知识变化列表
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class StateExtractorAgent(BaseAgent):
    """状态提取 Agent。

    从已生成的正文中提取所有状态变化，包括角色状态、关系变化、
    伏笔进展、新事件、时间线更新和角色知识变化。
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "StateExtractorAgent"
        self._description = "从正文中提取状态变化"

    @property
    def model_route_key(self) -> str:
        return "stateExtraction"

    @property
    def default_temperature(self) -> float:
        return 0.1

    @property
    def default_max_tokens(self) -> int:
        return 5000

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建状态提取的 Prompt。

        Args:
            context: 由 ContextBuilder.build_state_extract_context() 构建的上下文

        Returns:
            消息列表
        """
        system_prompt = (
            "你是小说自动化创作系统的【状态提取 Agent】。\n"
            "你的任务是从已生成的章节正文中提取所有状态变化。\n\n"
            "你必须输出严格 JSON，不要写任何解释文字。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "state_delta": {\n'
            '    "main_progress_delta": 2,\n'
            '    "character_changes": [\n'
            '      {"character_id": "角色ID", "character_name": "角色名", "field": "emotion/agencyScore/dropoutRisk/goal", "old": "旧值", "new": "新值", "reason": "变化原因"}\n'
            "    ],\n"
            '    "personality_shifts": [\n'
            '      {"character_id": "角色ID", "character_name": "角色名", "shift": "本章中角色性格/行为模式的微妙变化描述", "trigger": "触发变化的事件或情境"}\n'
            "    ],\n"
            '    "relationship_changes": [\n'
            '      {"from": "角色A", "to": "角色B", "field": "trust/tension", "old_value": 50, "new_value": 45, "delta": -5, "reason": "变化原因"}\n'
            "    ],\n"
            '    "foreshadow_changes": [\n'
            '      {"foreshadow_id": "伏笔ID", "action": "回响/推进/回收", "detail": "具体变化描述"}\n'
            "    ],\n"
            '    "new_events": [\n'
            '      {"description": "事件描述", "impact": "影响描述", "visibility": ["看到了此事件的角色名列表"]}\n'
            "    ],\n"
            '    "small_details": [\n'
            '      {"detail": "可能对后续剧情有用的小细节", "related_character": "相关角色名"}\n'
            "    ],\n"
            '    "timeline_updates": ["时间线更新描述"],\n'
            '    "knowledge_updates": [\n'
            '      {"character": "角色名", "learned": "学到了什么新信息", "forgot": null}\n'
            "    ]\n"
            "  }\n"
            "}\n\n"
            "提取规则：\n"
            "1. main_progress_delta: 主线推进程度（0-10），0表示无推进，10表示重大推进\n"
            "2. character_changes: 只提取明确发生变化的角色属性\n"
            "3. personality_shifts: 提取角色性格/行为模式的微妙变化。例如：冷静的角色开始焦虑、独来独往的角色主动寻求帮助。即使变化很小也要记录。\n"
            "4. relationship_changes: trust 和 tension 的变化范围在 -20 到 +20 之间\n"
            "5. foreshadow_changes: 只记录正文中实际提及或推进的伏笔\n"
            "6. new_events: 只记录对后续剧情有影响的事件\n"
            "7. small_details: 提取正文中看似不起眼但可能对后续有用的小细节（如角色提到的一个地名、一个习惯动作、一个未解释的反应）\n"
            "8. timeline_updates: 记录时间线上的重要节点\n"
            "9. knowledge_updates: 记录角色在本章中获得或失去的知识\n"
            "10. 如果某类变化没有发生，对应列表为空数组即可\n"
            "11. 所有变化必须有 reason 或 detail 说明原因"
        )

        # 构建用户消息
        user_content = {
            "chapterText": context.get("chapterText", ""),
            "chapterNumber": context.get("chapterNumber", 0),
            "chapterTitle": context.get("chapterTitle", ""),
            "characters": context.get("characters", []),
            "foreshadows": context.get("foreshadows", []),
            "relationships": context.get("relationships", []),
            "previousStateSnapshot": context.get("previousStateSnapshot", {}),
            "recentEvents": context.get("recentEvents", []),
            "timeline": context.get("timeline", []),
        }

        user_prompt = (
            "请从以下章节正文中提取所有状态变化：\n\n"
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
        """解析 AI 返回的状态变化 JSON。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的状态变化 dict
        """
        data = self._safe_parse_json(content)

        state_delta = data.get("state_delta", {})
        state_delta.setdefault("main_progress_delta", 0)
        state_delta.setdefault("character_changes", [])
        state_delta.setdefault("personality_shifts", [])
        state_delta.setdefault("relationship_changes", [])
        state_delta.setdefault("foreshadow_changes", [])
        state_delta.setdefault("new_events", [])
        state_delta.setdefault("small_details", [])
        state_delta.setdefault("timeline_updates", [])
        state_delta.setdefault("knowledge_updates", [])

        return {"state_delta": state_delta}

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式: 根据正文和项目状态动态生成状态变化。

        Args:
            context: 上下文数据

        Returns:
            模拟的状态变化输出
        """
        project = context.get("project", {})
        text = context.get("chapterText", "")
        characters = project.get("characters", [])
        foreshadows = project.get("foreshadows", [])
        relationships = project.get("relationships", [])
        chapters = project.get("chapters", [])
        current_chapter = len(chapters)

        state_delta: dict[str, Any] = {}

        # --- main_progress_delta ---
        # 根据正文字数和内容复杂度估算主线推进
        word_count = len(text) if text else 3000
        if word_count >= 5000:
            state_delta["main_progress_delta"] = 3
        elif word_count >= 3000:
            state_delta["main_progress_delta"] = 2
        else:
            state_delta["main_progress_delta"] = 1

        # --- character_changes ---
        character_changes = []
        for char in characters[:4]:
            name = char.get("name", "")
            if not name or not text:
                continue

            # 检查角色是否在正文中出场
            if name not in text:
                # 未出场的角色，增加退出风险
                old_dropout = self._get_value(char, "dropoutRisk")
                new_dropout = min(1.0, old_dropout + 0.05)
                if new_dropout != old_dropout:
                    character_changes.append({
                        "character_id": char.get("id", ""),
                        "character_name": name,
                        "field": "dropoutRisk",
                        "old": old_dropout,
                        "new": round(new_dropout, 2),
                        "reason": f"{name}在本章未出场，退出风险增加。",
                    })
                continue

            # 出场角色的情绪变化
            old_emotion = char.get("emotion", "平静")
            emotion_map = {
                "平静": "警觉",
                "警觉": "紧张",
                "紧张": "压抑",
                "压抑": "坚定",
                "坚定": "平静",
            }
            new_emotion = emotion_map.get(old_emotion, "微变")
            if new_emotion != old_emotion:
                character_changes.append({
                    "character_id": char.get("id", ""),
                    "character_name": name,
                    "field": "emotion",
                    "old": old_emotion,
                    "new": new_emotion,
                    "reason": f"本章事件导致{name}的情绪从{old_emotion}变为{new_emotion}。",
                })

            # 主角的主动性微调
            if "主角" in char.get("role", ""):
                old_agency = self._get_value(char, "agencyScore")
                new_agency = min(1.0, old_agency + 0.02)
                character_changes.append({
                    "character_id": char.get("id", ""),
                    "character_name": name,
                    "field": "agencyScore",
                    "old": old_agency,
                    "new": round(new_agency, 2),
                    "reason": f"{name}在本章展现了主动决策能力。",
                })

        state_delta["character_changes"] = character_changes

        # --- relationship_changes ---
        relationship_changes = []
        for rel in relationships[:4]:
            from_name = rel.get("from", "")
            to_name = rel.get("to", "")

            if not text or (from_name not in text and to_name not in text):
                continue

            # 信任度微调
            old_trust = rel.get("trust", 50)
            trust_delta = -3 if "冲突" in rel.get("type", "") or "敌对" in rel.get("type", "") else 2
            new_trust = max(0, min(100, old_trust + trust_delta))

            # 张力微调
            old_tension = rel.get("tension", 50)
            tension_delta = 5 if trust_delta < 0 else -2
            new_tension = max(0, min(100, old_tension + tension_delta))

            if new_trust != old_trust or new_tension != old_tension:
                relationship_changes.append({
                    "from": from_name,
                    "to": to_name,
                    "field": "trust",
                    "old_value": old_trust,
                    "new_value": new_trust,
                    "delta": trust_delta,
                    "reason": f"本章互动导致{from_name}与{to_name}的关系发生变化。",
                })

        state_delta["relationship_changes"] = relationship_changes

        # --- foreshadow_changes ---
        foreshadow_changes = []
        for fs in foreshadows[:5]:
            fs_name = fs.get("name", "")
            if not fs_name or not text:
                continue

            # 检查伏笔是否在正文中被提及
            if fs_name in text:
                risk = self._get_value(fs, "risk")
                planned_payoff = fs.get("plannedPayoffChapter", fs.get("plannedPayoff", 999))

                if planned_payoff <= current_chapter + 5:
                    action = "推进"
                else:
                    action = "轻微回响"

                foreshadow_changes.append({
                    "foreshadow_id": fs.get("id", ""),
                    "action": action,
                    "detail": f"伏笔「{fs_name}」在本章有{action}。",
                })

        state_delta["foreshadow_changes"] = foreshadow_changes

        # --- new_events ---
        new_events = []
        if text and characters:
            protagonist = next(
                (c for c in characters if "主角" in c.get("role", "")),
                {"name": "主角"},
            )
            new_events.append({
                "description": f"{protagonist.get('name', '主角')}在本章推进了当前调查。",
                "impact": "主线进展，局势进一步复杂化。",
                "visibility": [protagonist.get("name", "主角")],
            })

        state_delta["new_events"] = new_events

        # --- timeline_updates ---
        timeline_updates = []
        if chapters:
            timeline_updates.append(f"第{current_chapter + 1}章事件发生。")
        state_delta["timeline_updates"] = timeline_updates

        # --- knowledge_updates ---
        knowledge_updates = []
        for char in characters[:3]:
            name = char.get("name", "")
            if name and text and name in text:
                # 角色可能在本章学到了新信息
                knowledge_updates.append({
                    "character": name,
                    "learned": f"在本章中获得了与当前事件相关的新信息。",
                    "forgot": None,
                })

        state_delta["knowledge_updates"] = knowledge_updates

        return {"state_delta": state_delta}

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _get_value(obj: dict[str, Any], key: str) -> float:
        """获取数值，兼容 0-100 和 0-1 两种格式。

        Args:
            obj: 数据对象
            key: 键名

        Returns:
            0-1 范围的浮点数
        """
        val = obj.get(key, 0)
        if val > 1:
            return val / 100
        return float(val)
