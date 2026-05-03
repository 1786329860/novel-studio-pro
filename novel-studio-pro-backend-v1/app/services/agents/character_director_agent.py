"""角色导演 Agent。

独立负责角色戏份分配和主动性管理。

输入: 项目状态 + 约束包 + 导演稿
输出: 角色出场计划、戏份分配、掉线预警。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class CharacterDirectorAgent(BaseAgent):
    """角色导演 Agent。

    分析角色状态，规划本章各角色的出场场景、对话行数、
    内心独白、弧线节拍等，确保角色戏份均衡且合理。
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "character_director"
        self._description = "角色戏份分配与主动性管理"

    @property
    def model_route_key(self) -> str:
        return "chapterDirector"

    @property
    def default_temperature(self) -> float:
        return 0.3

    @property
    def default_max_tokens(self) -> int:
        return 4000

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建角色导演的 Prompt。

        Args:
            context: 包含项目状态、约束包和导演稿的上下文

        Returns:
            消息列表
        """
        system_prompt = (
            "你是小说自动化创作系统的【角色导演 Agent】。\n"
            "你的任务是规划本章各角色的出场戏份和主动性。\n\n"
            "你必须输出严格 JSON，不要写任何解释文字。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "character_plan": {\n'
            '    "角色名": {\n'
            '      "scenes": [1, 2, 3],\n'
            '      "dialogue_lines": 15,\n'
            '      "internal_monologue": true,\n'
            '      "arc_beat": "角色在本章的弧线节拍",\n'
            '      "interaction_targets": ["其他角色"]\n'
            "    }\n"
            "  },\n"
            '  "ensemble_balance": {"主角": 0.4, "配角A": 0.25},\n'
            '  "dropout_warnings": ["角色X已3章未出场，建议安排"]\n'
            "}\n\n"
            "规划规则：\n"
            "1. 主角戏份不超过 50%，确保配角有发挥空间\n"
            "2. dropoutRisk 高的角色必须安排出场\n"
            "3. 每个出场的角色至少有 1 个弧线节拍\n"
            "4. 角色间的互动要合理，基于现有关系\n"
            "5. 内心独白用于展现角色内心变化"
        )

        project = context.get("project", {})
        constraints = context.get("constraints", {})
        director_plan = context.get("directorPlan", {})

        user_content = {
            "characters": project.get("characters", []),
            "relationships": project.get("relationships", []),
            "constraints": constraints,
            "directorPlan": director_plan,
            "currentChapter": len(project.get("chapters", [])),
        }

        user_prompt = (
            "请根据以下信息规划本章的角色戏份：\n\n"
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
        """解析 AI 返回的角色规划结果。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的角色规划结果
        """
        data = self._safe_parse_json(content)

        data.setdefault("character_plan", {})
        data.setdefault("ensemble_balance", {})
        data.setdefault("dropout_warnings", [])

        return data

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式: 根据角色列表和当前章节动态生成。

        Args:
            context: 上下文数据

        Returns:
            模拟的角色规划结果
        """
        project = context.get("project", {})
        characters = project.get("characters", [])
        chapters = project.get("chapters", [])
        current_chapter = len(chapters)
        constraints = context.get("constraints", {})

        character_plan: dict[str, Any] = {}
        ensemble_balance: dict[str, float] = {}
        dropout_warnings: list[str] = []

        # 角色分配比例
        total_ratio = 0.0
        allocatable = characters[:6]

        for i, char in enumerate(allocatable):
            name = char.get("name", f"角色{i}")
            role = char.get("role", "")

            # 获取数值，兼容两种格式
            agency = char.get("agencyScore", 0)
            if agency > 1:
                agency = agency / 100
            dropout = char.get("dropoutRisk", 0)
            if dropout > 1:
                dropout = dropout / 100

            last_appeared = char.get("lastAppearedChapter", char.get("lastAppeared", 0))
            chapters_since = current_chapter - last_appeared

            # 掉线预警
            if chapters_since >= 3 and dropout >= 0.3:
                dropout_warnings.append(
                    f"{name}已 {chapters_since} 章未出场（退出风险 {dropout:.0%}），建议安排出场。"
                )

            # 戏份分配
            if "主角" in role:
                ratio = 0.40
                dialogue_lines = 18
                has_monologue = True
                arc_beat = "在调查中展现决策能力，推进主线。"
            elif "女主" in role:
                ratio = 0.30
                dialogue_lines = 14
                has_monologue = True
                arc_beat = "独立行动段落，展现角色主动性。"
            elif dropout >= 0.4:
                ratio = 0.10
                dialogue_lines = 5
                has_monologue = False
                arc_beat = "重新出场，缓解退出风险。"
            else:
                ratio = 0.08
                dialogue_lines = 4
                has_monologue = False
                arc_beat = "辅助推进当前场景。"

            # 互动目标
            interaction_targets = []
            for other_char in allocatable:
                other_name = other_char.get("name", "")
                if other_name and other_name != name:
                    interaction_targets.append(other_name)

            character_plan[name] = {
                "scenes": [1, 2] if ratio >= 0.2 else [1],
                "dialogue_lines": dialogue_lines,
                "internal_monologue": has_monologue,
                "arc_beat": arc_beat,
                "interaction_targets": interaction_targets[:3],
            }

            ensemble_balance[name] = ratio
            total_ratio += ratio

        # 归一化比例
        if total_ratio > 0:
            for name in ensemble_balance:
                ensemble_balance[name] = round(ensemble_balance[name] / total_ratio, 2)

        # 补充群演比例
        remaining = 1.0 - sum(ensemble_balance.values())
        if remaining > 0.01:
            ensemble_balance["群演"] = round(remaining, 2)

        return {
            "character_plan": character_plan,
            "ensemble_balance": ensemble_balance,
            "dropout_warnings": dropout_warnings,
        }
