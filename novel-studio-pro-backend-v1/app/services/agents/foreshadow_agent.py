"""伏笔管理 Agent。

独立负责伏笔生命周期管理。

输入: 项目状态 + 约束包
输出: 伏笔处理计划、风险评估、真相源检查。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ForeshadowAgent(BaseAgent):
    """伏笔管理 Agent。

    分析当前伏笔状态，规划本章需要处理的伏笔动作，
    评估伏笔风险，检查真相源安全。
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "foreshadow_manager"
        self._description = "伏笔生命周期管理"

    @property
    def model_route_key(self) -> str:
        return "chapterDirector"

    @property
    def default_temperature(self) -> float:
        return 0.2

    @property
    def default_max_tokens(self) -> int:
        return 4000

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建伏笔管理的 Prompt。

        Args:
            context: 包含项目状态和约束包的上下文

        Returns:
            消息列表
        """
        system_prompt = (
            "你是小说自动化创作系统的【伏笔管理 Agent】。\n"
            "你的任务是管理伏笔生命周期，规划本章的伏笔处理。\n\n"
            "你必须输出严格 JSON，不要写任何解释文字。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "foreshadow_plan": [\n'
            '    {"id": "xxx", "action": "轻微回响", "method": "通过角色对话暗示", "intensity": 0.3}\n'
            "  ],\n"
            '  "risk_assessment": [\n'
            '    {"id": "zzz", "risk": "high", "reason": "已15章未推进，读者可能遗忘"}\n'
            "  ],\n"
            '  "truth_source_check": [\n'
            '    {"info": "凶手身份", "can_reveal": false, "reason": "计划在第50章揭露"}\n'
            "  ]\n"
            "}\n\n"
            "管理规则：\n"
            "1. 不能在 plannedPayoffChapter 之前回收伏笔\n"
            "2. 风险高的伏笔必须安排回响或推进\n"
            "3. 真相源中标记为禁止的信息不能在本章揭露\n"
            "4. 每章处理的伏笔数量控制在 2-4 个\n"
            "5. 伏笔回响要自然，不能生硬提及"
        )

        project = context.get("project", {})
        constraints = context.get("constraints", {})

        user_content = {
            "foreshadows": project.get("foreshadows", []),
            "truthSource": project.get("truthSource", {}),
            "currentChapter": len(project.get("chapters", [])),
            "constraints": constraints,
            "forbiddenRules": project.get("storyBible", {}).get("forbiddenRules", []),
        }

        user_prompt = (
            "请根据以下项目状态规划本章的伏笔处理：\n\n"
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
        """解析 AI 返回的伏笔管理结果。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的伏笔管理结果
        """
        data = self._safe_parse_json(content)

        data.setdefault("foreshadow_plan", [])
        data.setdefault("risk_assessment", [])
        data.setdefault("truth_source_check", [])

        return data

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式: 根据伏笔列表和章节进度动态生成。

        Args:
            context: 上下文数据

        Returns:
            模拟的伏笔管理结果
        """
        project = context.get("project", {})
        foreshadows = project.get("foreshadows", [])
        truth_source = project.get("truthSource", {})
        chapters = project.get("chapters", [])
        current_chapter = len(chapters)

        foreshadow_plan: list[dict[str, Any]] = []
        risk_assessment: list[dict[str, Any]] = []
        truth_source_check: list[dict[str, Any]] = []

        for fs in foreshadows:
            fs_id = fs.get("id", "")
            fs_name = fs.get("name", "")
            status = fs.get("status", "")

            # 跳过已回收的伏笔
            if status in ("已回收", "已解决"):
                continue

            # 获取数值，兼容两种格式
            risk = fs.get("risk", 0)
            if risk > 1:
                risk = risk / 100
            planned_payoff = fs.get("plannedPayoffChapter", fs.get("plannedPayoff", 999))

            # 风险评估
            last_mentioned = fs.get("lastMentionedChapter", fs.get("lastMentioned", 0))
            chapters_since_mention = current_chapter - last_mentioned

            if chapters_since_mention >= 10:
                risk_level = "high"
                risk_reason = f"已 {chapters_since_mention} 章未推进，读者可能遗忘。"
            elif chapters_since_mention >= 5:
                risk_level = "medium"
                risk_reason = f"已 {chapters_since_mention} 章未提及，建议安排回响。"
            else:
                risk_level = "low"
                risk_reason = "近期已有提及，风险可控。"

            risk_assessment.append({
                "id": fs_id,
                "name": fs_name,
                "risk": risk_level,
                "reason": risk_reason,
            })

            # 伏笔处理计划
            if planned_payoff <= current_chapter + 5:
                # 即将到回收期，需要推进
                action = "推进"
                method = "揭示部分真相，为回收做铺垫。"
                intensity = 0.6
            elif risk >= 0.4 or risk_level == "high":
                # 高风险，需要回响
                action = "轻微回响"
                method = "通过角色对话或环境描写自然暗示。"
                intensity = 0.3
            elif risk_level == "medium":
                action = "轻微回响"
                method = "在场景中自然提及相关线索。"
                intensity = 0.2
            else:
                # 低风险，暂不处理
                continue

            foreshadow_plan.append({
                "id": fs_id,
                "name": fs_name,
                "action": action,
                "method": method,
                "intensity": intensity,
            })

        # 真相源检查
        author_truth = truth_source.get("authorTruth", {})
        if isinstance(author_truth, dict):
            for info_key, info_value in author_truth.items():
                if isinstance(info_value, dict):
                    can_reveal = info_value.get("canReveal", False)
                    reveal_chapter = info_value.get("revealChapter", 999)
                    reason = (
                        f"计划在第 {reveal_chapter} 章揭露。"
                        if not can_reveal
                        else "可以在本章适当透露。"
                    )
                    truth_source_check.append({
                        "info": info_key,
                        "can_reveal": can_reveal and reveal_chapter <= current_chapter,
                        "reason": reason,
                    })

        # 限制每章处理的伏笔数量
        foreshadow_plan = foreshadow_plan[:4]

        return {
            "foreshadow_plan": foreshadow_plan,
            "risk_assessment": risk_assessment,
            "truth_source_check": truth_source_check,
        }
