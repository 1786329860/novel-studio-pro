"""约束生成 Agent。

任务: 根据当前项目状态，生成本章必须遵守的约束条件。
这是流水线的第一步，为后续所有 Agent 提供规则框架。

输出结构:
    - must_happen: 本章必须发生的事件列表
    - must_not_happen: 本章禁止发生的事件列表
    - character_allocation: 角色出场比例分配
    - pov_plan: 视角规划
    - foreshadow_actions: 伏笔处理指令
    - style_constraints: 文风要求
    - continuity_requirements: 连续性要求
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ConstraintAgent(BaseAgent):
    """约束生成 Agent。

    分析当前项目状态（角色、伏笔、主线进度、真相源、事件账本），
    生成本章必须遵守和禁止的约束条件。
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "ConstraintAgent"
        self._description = "根据项目状态生成本章约束条件"

    @property
    def model_route_key(self) -> str:
        return "chapterDirector"

    @property
    def default_temperature(self) -> float:
        return 0.35

    @property
    def default_max_tokens(self) -> int:
        return 4000

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建约束生成的 Prompt。

        Args:
            context: 由 ContextBuilder.build_constraint_context() 构建的上下文

        Returns:
            消息列表
        """
        project = context.get("project", {})

        system_prompt = (
            "你是小说自动化创作系统的【约束生成 Agent】。\n"
            "你的任务是分析当前项目状态，为即将写作的下一章生成精确的约束条件。\n\n"
            "你必须输出严格 JSON，不要写任何解释文字。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "must_happen": ["本章必须发生的事件列表，2-5条"],\n'
            '  "must_not_happen": ["本章禁止发生的事件列表，2-4条"],\n'
            '  "character_allocation": {"角色名": {"min_ratio": 0.1, "max_ratio": 0.4, "scene_type": "主线/支线/过渡"}},\n'
            '  "pov_plan": {"primary": "主视角角色名", "secondary": "次视角角色名", "ratio": "60/30/10"},\n'
            '  "foreshadow_actions": [{"foreshadow_id": "伏笔ID", "action": "轻微回响/推进/回收", "detail": "具体处理方式"}],\n'
            '  "style_constraints": ["文风要求列表"],\n'
            '  "continuity_requirements": ["必须保持的连续性要求"]\n'
            "}\n\n"
            "关键规则：\n"
            "1. must_not_happen 必须包含 forbiddenRules 中的所有禁止项\n"
            "2. 角色分配必须考虑 dropoutRisk 高的角色需要更多出场\n"
            "3. 伏笔处理不能在 plannedPayoffChapter 之前回收\n"
            "4. 视角分配要考虑角色的 knowledgeState，不能让角色知道不该知道的事\n"
            "5. 真相源中标记为禁止的信息绝对不能在本章揭露\n"
            "6. 每章至少推动主线、角色关系或伏笔之一"
        )

        # 构建用户消息，只包含必要的上下文
        user_content = {
            "storyBibleSummary": context.get("storyBibleSummary", {}),
            "currentVolume": context.get("currentVolume", {}),
            "characters": context.get("characters", []),
            "foreshadows": context.get("foreshadows", []),
            "truthSource": context.get("truthSource", {}),
            "recentEvents": context.get("recentEvents", []),
            "recentChapterSummaries": context.get("recentChapterSummaries", []),
            "forbiddenRules": context.get("forbiddenRules", []),
            "status": context.get("status", {}),
            "relationships": context.get("relationships", []),
        }

        user_prompt = (
            "请根据以下项目状态，为下一章生成约束条件：\n\n"
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
        """解析 AI 返回的约束 JSON。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的约束 dict
        """
        data = self._safe_parse_json(content)

        # 确保必要字段存在
        data.setdefault("must_happen", [])
        data.setdefault("must_not_happen", [])
        data.setdefault("character_allocation", {})
        data.setdefault("pov_plan", {})
        data.setdefault("foreshadow_actions", [])
        data.setdefault("style_constraints", [])
        data.setdefault("continuity_requirements", [])

        return data

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式: 根据项目实际状态动态生成约束。

        Args:
            context: 上下文数据

        Returns:
            模拟的约束输出
        """
        project = context.get("project", {})
        characters = project.get("characters", [])
        foreshadows = project.get("foreshadows", [])
        story_bible = project.get("storyBible", {})
        chapters = project.get("chapters", [])
        current_chapter = len(chapters)
        relationships = project.get("relationships", [])

        # --- must_happen: 根据项目状态动态生成 ---
        must_happen = []

        # 主角推进主线
        protagonist = next(
            (c for c in characters if "主角" in c.get("role", "")),
            {"name": "主角"},
        )
        must_happen.append(f"{protagonist.get('name', '主角')}必须在本章推进当前目标。")

        # 高风险伏笔需要回响
        high_risk_fs = [
            fs for fs in foreshadows
            if self._get_risk_value(fs) >= 0.3
        ]
        if high_risk_fs:
            fs = high_risk_fs[0]
            must_happen.append(f"伏笔「{fs.get('name', '未知')}」需要在本章有轻微回响。")

        # dropoutRisk 高的角色需要出场
        high_dropout = [
            c for c in characters
            if self._get_dropout_value(c) >= 0.4
        ]
        if high_dropout:
            char = high_dropout[0]
            must_happen.append(f"{char.get('name', '角色')}需要在本章出场以避免退出风险。")

        # 关系推进
        if relationships:
            rel = relationships[0]
            must_happen.append(
                f"{rel.get('from', '角色A')}与{rel.get('to', '角色B')}的关系需要有微妙变化。"
            )

        # --- must_not_happen: 从 forbiddenRules 提取 ---
        must_not_happen = list(story_bible.get("forbiddenRules", []))

        # 补充通用禁止项
        must_not_happen.append("不得出现与已有设定矛盾的情节。")
        must_not_happen.append("不得让角色突然知道不该知道的信息。")

        # --- character_allocation: 根据角色状态动态分配 ---
        character_allocation = {}
        total_ratio = 0.0
        allocatable = characters[:5]  # 最多分配 5 个角色

        for i, char in enumerate(allocatable):
            name = char.get("name", f"角色{i}")
            role = char.get("role", "")
            agency = self._get_agency_value(char)
            dropout = self._get_dropout_value(char)

            # 主动性高或退出风险高的角色分配更多比例
            if "主角" in role:
                min_r, max_r = 0.3, 0.5
                scene = "主线"
            elif "女主" in role:
                min_r, max_r = 0.2, 0.4
                scene = "主线"
            elif dropout >= 0.4:
                min_r, max_r = 0.1, 0.25
                scene = "支线"
            else:
                min_r, max_r = 0.05, 0.2
                scene = "过渡" if agency < 0.5 else "支线"

            character_allocation[name] = {
                "min_ratio": min_r,
                "max_ratio": max_r,
                "scene_type": scene,
            }
            total_ratio += max_r

        # --- pov_plan: 视角规划 ---
        pov_names = [c.get("name", "") for c in characters[:3]]
        pov_plan = {
            "primary": pov_names[0] if len(pov_names) > 0 else "主角",
            "secondary": pov_names[1] if len(pov_names) > 1 else "配角",
            "ratio": "55/35/10",
        }

        # --- foreshadow_actions: 伏笔处理指令 ---
        foreshadow_actions = []
        for fs in high_risk_fs[:3]:
            risk = self._get_risk_value(fs)
            planned_payoff = fs.get("plannedPayoffChapter", fs.get("plannedPayoff", 999))

            if planned_payoff <= current_chapter + 5:
                action = "推进"
            elif risk >= 0.5:
                action = "轻微回响"
            else:
                action = "轻微回响"

            foreshadow_actions.append({
                "foreshadow_id": fs.get("id", ""),
                "action": action,
                "detail": f"在场景中自然提及「{fs.get('name', '')}」的相关线索。",
            })

        # --- style_constraints: 文风要求 ---
        genre = story_bible.get("genre", "奇幻")
        style_map = {
            "奇幻": ["保持史诗感，场景描写要有想象力", "对话要体现角色个性差异"],
            "玄幻": ["升级爽点要明确", "压迫与反击节奏要紧凑"],
            "科幻": ["技术设定要自洽", "概念清楚不模糊"],
            "都市": ["现实细节要充足", "节奏轻快不拖沓"],
            "悬疑": ["信息不对称要强", "线索布置要自然"],
            "言情": ["情绪浓度要高", "关系拉扯要明确"],
        }
        style_constraints = style_map.get(genre, ["保持文风一致", "节奏适中"])
        style_constraints.append("避免 AI 味重的表达，如'不禁'、'竟然'等过度使用。")

        # --- continuity_requirements: 连续性要求 ---
        continuity_requirements = [
            "角色性格和说话方式必须与前文一致。",
            "时间线不能出现矛盾。",
            "已建立的世界观规则不能随意打破。",
        ]

        if chapters:
            last_ch = chapters[-1]
            continuity_requirements.append(
                f"与上一章「{last_ch.get('title', '')}」的结尾自然衔接。"
            )

        return {
            "must_happen": must_happen,
            "must_not_happen": must_not_happen,
            "character_allocation": character_allocation,
            "pov_plan": pov_plan,
            "foreshadow_actions": foreshadow_actions,
            "style_constraints": style_constraints,
            "continuity_requirements": continuity_requirements,
        }

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _get_risk_value(foreshadow: dict[str, Any]) -> float:
        """获取伏笔的风险值，兼容 0-100 和 0-1 两种格式。"""
        risk = foreshadow.get("risk", 0)
        if risk > 1:
            return risk / 100
        return float(risk)

    @staticmethod
    def _get_dropout_value(character: dict[str, Any]) -> float:
        """获取角色的退出风险值，兼容 0-100 和 0-1 两种格式。"""
        dropout = character.get("dropoutRisk", 0)
        if dropout > 1:
            return dropout / 100
        return float(dropout)

    @staticmethod
    def _get_agency_value(character: dict[str, Any]) -> float:
        """获取角色的主动性分数，兼容 0-100 和 0-1 两种格式。"""
        agency = character.get("agencyScore", 0)
        if agency > 1:
            return agency / 100
        return float(agency)
