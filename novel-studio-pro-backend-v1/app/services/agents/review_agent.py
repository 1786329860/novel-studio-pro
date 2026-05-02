"""质量检查 Agent。

任务: 检查正文质量，确保满足所有约束条件。
这是流水线的第四步，是质量把关的关键 Agent。

输出结构:
    - total_score: 总分（0-100）
    - tests: 检查项列表（连续性、视角稳定性、角色主动性、禁止揭露、伏笔处理、约束遵守、AI味检测）
    - rewrite_suggestions: 修改建议列表
    - passed: 是否通过质量阈值
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# AI 味关键词列表，用于检测
AI_TASTE_KEYWORDS = [
    "不禁", "竟然", "仿佛", "似乎", "宛如", "犹如",
    "心中暗想", "不由得", "情不自禁", "恍然大悟",
    "暗自思忖", "心中一凛", "目光如炬", "嘴角微微上扬",
    "深吸一口气", "缓缓说道", "淡淡地说",
    "一股寒意", "一丝不安", "一抹笑意",
]


class ReviewAgent(BaseAgent):
    """质量检查 Agent。

    对正文进行多维度质量检查，包括连续性、视角稳定性、角色主动性、
    禁止揭露、伏笔处理、约束遵守和 AI 味检测。
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "ReviewAgent"
        self._description = "检查正文质量，多维度评分"

    @property
    def model_route_key(self) -> str:
        return "continuityReview"

    @property
    def default_temperature(self) -> float:
        return 0.2

    @property
    def default_max_tokens(self) -> int:
        return 5000

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建质量检查的 Prompt。

        Args:
            context: 由 ContextBuilder.build_review_context() 构建的上下文

        Returns:
            消息列表
        """
        system_prompt = (
            "你是小说自动化创作系统的【质量检查 Agent】。\n"
            "你的任务是对已生成的正文进行多维度质量检查。\n\n"
            "你必须输出严格 JSON，不要写任何解释文字。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "total_score": 85,\n'
            '  "tests": [\n'
            '    {"name": "连续性检查", "passed": true, "score": 90, "message": "检查结果描述"},\n'
            '    {"name": "视角稳定性", "passed": true, "score": 88, "message": "检查结果描述"},\n'
            '    {"name": "角色主动性", "passed": true, "score": 85, "message": "检查结果描述"},\n'
            '    {"name": "禁止揭露检查", "passed": true, "score": 100, "message": "检查结果描述"},\n'
            '    {"name": "伏笔处理检查", "passed": true, "score": 82, "message": "检查结果描述"},\n'
            '    {"name": "约束遵守检查", "passed": true, "score": 90, "message": "检查结果描述"},\n'
            '    {"name": "AI 味检测", "passed": false, "score": 72, "message": "检查结果描述"}\n'
            "  ],\n"
            '  "rewrite_suggestions": ["修改建议1", "修改建议2"],\n'
            '  "passed": true\n'
            "}\n\n"
            "检查维度说明：\n"
            "1. 连续性检查: 与前文是否有矛盾（时间线、人物位置、已知信息）\n"
            "2. 视角稳定性: 是否按照 pov_plan 切换视角，是否有越界\n"
            "3. 角色主动性: 角色是否有自主行动，是否被动接受安排\n"
            "4. 禁止揭露检查: 是否违反 forbiddenRules，是否提前揭露真相\n"
            "5. 伏笔处理检查: 是否按 foreshadow_actions 处理了伏笔\n"
            "6. 约束遵守检查: 是否满足 must_happen，是否违反 must_not_happen\n"
            "7. AI 味检测: 是否存在模板化表达、过度修辞、不自然的描写\n\n"
            "评分标准：\n"
            "- 90-100: 优秀，无需修改\n"
            "- 80-89: 良好，可有少量修改\n"
            "- 70-79: 及格，建议修改\n"
            "- 60-69: 不及格，需要重写\n"
            "- 60以下: 严重问题，必须重写\n\n"
            "passed 判定: total_score >= 80 且所有关键检查项 passed"
        )

        # 构建用户消息
        user_content = {
            "chapterText": context.get("chapterText", ""),
            "chapterTitle": context.get("chapterTitle", ""),
            "chapterNumber": context.get("chapterNumber", 0),
            "wordCount": context.get("wordCount", 0),
            "directorPlan": context.get("directorPlan", {}),
            "constraints": context.get("constraints", {}),
            "forbiddenRules": context.get("forbiddenRules", []),
            "characters": context.get("characters", []),
            "foreshadows": context.get("foreshadows", []),
            "truthSource": context.get("truthSource", {}),
            "recentChapterSummaries": context.get("recentChapterSummaries", []),
            "relationships": context.get("relationships", []),
        }

        user_prompt = (
            "请对以下章节正文进行质量检查：\n\n"
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
        """解析 AI 返回的检查结果 JSON。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的检查结果 dict
        """
        data = self._safe_parse_json(content)

        data.setdefault("total_score", 0)
        data.setdefault("tests", [])
        data.setdefault("rewrite_suggestions", [])
        data.setdefault("passed", False)

        # 验证 tests 结构
        for test in data["tests"]:
            test.setdefault("name", "")
            test.setdefault("passed", False)
            test.setdefault("score", 0)
            test.setdefault("message", "")

        return data

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式: 根据正文内容进行基础的质量检查。

        使用规则引擎进行本地检查，不依赖 AI。

        Args:
            context: 上下文数据

        Returns:
            模拟的检查结果
        """
        text = context.get("chapterText", "")
        constraints = context.get("constraints", {})
        forbidden_rules = context.get("forbiddenRules", [])
        characters = context.get("characters", [])
        foreshadows = context.get("foreshadows", [])
        director_plan = context.get("directorPlan", {})

        tests = []
        rewrite_suggestions = []

        # 1. 连续性检查
        continuity_score = self._check_continuity(context)
        tests.append({
            "name": "连续性检查",
            "passed": continuity_score >= 70,
            "score": continuity_score,
            "message": "未发现明显的前后矛盾。" if continuity_score >= 80 else "存在轻微的连续性问题，建议检查。",
        })

        # 2. 视角稳定性
        pov_score = self._check_pov_stability(text, constraints)
        tests.append({
            "name": "视角稳定性",
            "passed": pov_score >= 70,
            "score": pov_score,
            "message": "视角切换自然，未发现越界。" if pov_score >= 80 else "视角切换略显突兀。",
        })

        # 3. 角色主动性
        agency_score = self._check_character_agency(text, characters)
        tests.append({
            "name": "角色主动性",
            "passed": agency_score >= 70,
            "score": agency_score,
            "message": "角色有自主行动和决策。" if agency_score >= 80 else "部分角色显得被动。",
        })
        if agency_score < 80:
            rewrite_suggestions.append("增加角色的主动决策和独立行动，减少被动接受安排的描写。")

        # 4. 禁止揭露检查
        forbidden_score = self._check_forbidden_revelation(text, forbidden_rules)
        tests.append({
            "name": "禁止揭露检查",
            "passed": forbidden_score >= 90,
            "score": forbidden_score,
            "message": "未发现违反禁止规则的内容。" if forbidden_score >= 90 else "可能存在提前揭露风险。",
        })
        if forbidden_score < 90:
            rewrite_suggestions.append("检查是否存在提前揭露核心真相的内容，确保遵守 forbiddenRules。")

        # 5. 伏笔处理检查
        foreshadow_score = self._check_foreshadow_handling(text, constraints, foreshadows)
        tests.append({
            "name": "伏笔处理检查",
            "passed": foreshadow_score >= 70,
            "score": foreshadow_score,
            "message": "伏笔处理符合要求。" if foreshadow_score >= 80 else "部分伏笔未按要求处理。",
        })

        # 6. 约束遵守检查
        constraint_score = self._check_constraint_compliance(text, constraints)
        tests.append({
            "name": "约束遵守检查",
            "passed": constraint_score >= 70,
            "score": constraint_score,
            "message": "约束条件基本满足。" if constraint_score >= 80 else "部分约束未满足。",
        })

        # 7. AI 味检测
        ai_taste_score = self._check_ai_taste(text)
        tests.append({
            "name": "AI 味检测",
            "passed": ai_taste_score >= 70,
            "score": ai_taste_score,
            "message": "AI 味较轻，表达自然。" if ai_taste_score >= 80 else "存在一些模板化表达。",
        })
        if ai_taste_score < 80:
            rewrite_suggestions.append("减少'不禁'、'竟然'、'仿佛'等 AI 常用词的使用，用更具体的描写替代。")

        # 计算总分
        total_score = int(sum(t["score"] for t in tests) / len(tests))
        passed = total_score >= 80 and all(t["passed"] for t in tests)

        return {
            "total_score": total_score,
            "tests": tests,
            "rewrite_suggestions": rewrite_suggestions,
            "passed": passed,
        }

    # ------------------------------------------------------------------
    # 本地检查方法（Mock 模式使用）
    # ------------------------------------------------------------------

    def _check_continuity(self, context: dict[str, Any]) -> int:
        """检查连续性。

        基础检查: 正文长度是否合理，是否有最近章节摘要中的矛盾。

        Args:
            context: 上下文数据

        Returns:
            连续性分数（0-100）
        """
        text = context.get("chapterText", "")
        if not text:
            return 60

        score = 85  # 基础分

        # 检查字数是否合理
        word_count = len(text)
        if word_count < 2000:
            score -= 15
        elif word_count < 3000:
            score -= 5

        return max(60, min(100, score))

    def _check_pov_stability(self, text: str, constraints: dict[str, Any]) -> int:
        """检查视角稳定性。

        基础检查: 视角角色是否在约束规定的范围内。

        Args:
            text: 正文内容
            constraints: 约束条件

        Returns:
            视角稳定性分数（0-100）
        """
        score = 88  # 基础分

        pov_plan = constraints.get("pov_plan", {})
        primary = pov_plan.get("primary", "")

        if primary and text:
            # 检查主视角角色是否在正文中有足够的"出场密度"
            # 简单检查: 主角名字出现的频率
            name_count = text.count(primary)
            expected_min = len(text) // 500  # 大约每 500 字出现一次
            if name_count < expected_min * 0.5:
                score -= 10

        return max(60, min(100, score))

    def _check_character_agency(self, text: str, characters: list[dict[str, Any]]) -> int:
        """检查角色主动性。

        基础检查: 角色是否有主动行为的描写。

        Args:
            text: 正文内容
            characters: 角色列表

        Returns:
            角色主动性分数（0-100）
        """
        score = 82  # 基础分

        if not text or not characters:
            return score

        # 检查是否有主动行为的动词
        action_verbs = ["决定", "选择", "转身", "迈步", "开口", "伸手", "握紧", "推开"]
        action_count = sum(text.count(verb) for verb in action_verbs)

        # 检查是否有被动描写的词
        passive_words = ["被迫", "无奈", "只能", "不由", "不由得"]
        passive_count = sum(text.count(word) for word in passive_words)

        if passive_count > action_count:
            score -= 15
        elif passive_count > action_count * 0.7:
            score -= 5

        return max(60, min(100, score))

    def _check_forbidden_revelation(self, text: str, forbidden_rules: list[str]) -> int:
        """检查禁止揭露。

        检查正文是否包含 forbiddenRules 中禁止的内容。

        Args:
            text: 正文内容
            forbidden_rules: 禁止规则列表

        Returns:
            禁止揭露检查分数（0-100）
        """
        if not forbidden_rules:
            return 100

        score = 100
        for rule in forbidden_rules:
            # 从规则中提取关键词
            # 例如 "前30章不得让主角确认夜火计划的最终主谋"
            # 提取 "确认" + "主谋" 等关键词
            keywords = self._extract_keywords_from_rule(rule)
            for keyword in keywords:
                if keyword in text:
                    score -= 15

        return max(60, min(100, score))

    def _check_foreshadow_handling(
        self,
        text: str,
        constraints: dict[str, Any],
        foreshadows: list[dict[str, Any]],
    ) -> int:
        """检查伏笔处理。

        检查约束中要求的伏笔处理是否在正文中有所体现。

        Args:
            text: 正文内容
            constraints: 约束条件
            foreshadows: 伏笔列表

        Returns:
            伏笔处理分数（0-100）
        """
        foreshadow_actions = constraints.get("foreshadow_actions", [])
        if not foreshadow_actions:
            return 85  # 没有伏笔要求，给默认分

        score = 85
        handled = 0

        for action in foreshadow_actions:
            fs_id = action.get("foreshadow_id", "")
            # 查找伏笔名称
            fs_name = ""
            for fs in foreshadows:
                if fs.get("id") == fs_id:
                    fs_name = fs.get("name", "")
                    break

            if fs_name and fs_name in text:
                handled += 1

        total = len(foreshadow_actions)
        if total > 0:
            ratio = handled / total
            if ratio < 0.5:
                score -= 20
            elif ratio < 1.0:
                score -= 5

        return max(60, min(100, score))

    def _check_constraint_compliance(self, text: str, constraints: dict[str, Any]) -> int:
        """检查约束遵守情况。

        检查 must_happen 是否在正文中有所体现。

        Args:
            text: 正文内容
            constraints: 约束条件

        Returns:
            约束遵守分数（0-100）
        """
        must_happen = constraints.get("must_happen", [])
        if not must_happen:
            return 90

        score = 90
        # 从 must_happen 中提取关键词检查
        satisfied = 0
        for item in must_happen:
            # 提取关键词（角色名、事件关键词）
            keywords = self._extract_keywords_from_rule(item)
            for keyword in keywords:
                if keyword in text:
                    satisfied += 1
                    break

        total = len(must_happen)
        if total > 0:
            ratio = satisfied / total
            if ratio < 0.5:
                score -= 20
            elif ratio < 0.8:
                score -= 10

        return max(60, min(100, score))

    def _check_ai_taste(self, text: str) -> int:
        """检测 AI 味。

        统计 AI 常用模板化表达的出现频率。

        Args:
            text: 正文内容

        Returns:
            AI 味检测分数（0-100，越高越好）
        """
        if not text:
            return 80

        total_hits = 0
        for keyword in AI_TASTE_KEYWORDS:
            count = text.count(keyword)
            total_hits += count

        # 计算每千字的 AI 味词数
        word_count = max(len(text), 1)
        hits_per_thousand = (total_hits / word_count) * 1000

        if hits_per_thousand <= 2:
            return 92
        elif hits_per_thousand <= 4:
            return 85
        elif hits_per_thousand <= 6:
            return 78
        elif hits_per_thousand <= 8:
            return 72
        else:
            return max(60, 70 - int(hits_per_thousand))

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords_from_rule(rule: str) -> list[str]:
        """从规则文本中提取关键词。

        过滤掉常见的停用词，保留有意义的名词和动词。

        Args:
            rule: 规则文本

        Returns:
            关键词列表
        """
        # 去除标点
        cleaned = re.sub(r"[，。、；：""''！？（）《》【】\s]", " ", rule)
        words = cleaned.split()

        # 过滤停用词
        stop_words = {
            "的", "了", "在", "是", "有", "和", "与", "或", "不", "也",
            "都", "要", "会", "能", "可以", "应该", "必须", "不得", "不能",
            "不能让", "前", "后", "中", "上", "下", "一", "个", "每",
            "本章", "不得", "禁止", "允许", "需要", "以及", "等",
        }
        keywords = [w for w in words if len(w) >= 2 and w not in stop_words]
        return keywords[:5]  # 最多返回 5 个关键词
