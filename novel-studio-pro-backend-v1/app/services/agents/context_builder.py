"""上下文构建器模块。

负责为每个 Agent 构建精确的上下文包。核心设计原则:
- 智能截断: 控制总 Token 在限制内
- 优先级排序: 故事蓝图 > 当前卷 > 最近章节 > 角色卡 > 伏笔表
- 角色筛选: 只包含相关角色（按出场频率和关联度）
- 伏笔筛选: 只包含活跃伏笔和需要处理的伏笔
- 章节摘要: 最近 3-5 章的摘要，不是全文
- 真相源: 区分作者/读者/角色已知信息
- 事件账本: 最近相关事件

每个 Agent 获取的上下文都是"最小必要集"，避免浪费 Token。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.utils import estimate_tokens, truncate_text

logger = logging.getLogger(__name__)


class ContextBuilder:
    """上下文构建器。

    为流水线中的每个 Agent 构建定制化的上下文包。
    所有方法都是纯函数，不修改原始 project 数据。
    """

    def __init__(self, max_tokens: int = 32000) -> None:
        """初始化上下文构建器。

        Args:
            max_tokens: 上下文包的最大 Token 限制（粗略估算）
        """
        self.max_tokens = max_tokens

    # ------------------------------------------------------------------
    # 公共方法: 为各 Agent 构建上下文
    # ------------------------------------------------------------------

    def build_constraint_context(self, project: dict[str, Any]) -> dict[str, Any]:
        """为约束 Agent 构建上下文。

        包含: 故事蓝图摘要、当前卷信息、角色概览、伏笔概览、
              真相源、事件账本、最近章节摘要、禁止规则。

        Args:
            project: 完整的项目数据

        Returns:
            约束 Agent 所需的上下文包
        """
        context: dict[str, Any] = {}
        budget = self.max_tokens

        # 1. 故事蓝图摘要（最高优先级）
        story_bible = project.get("storyBible", {})
        bible_summary = self._extract_story_bible_summary(story_bible)
        context["storyBibleSummary"] = bible_summary
        budget -= estimate_tokens(json.dumps(bible_summary, ensure_ascii=False))

        # 2. 当前卷信息
        current_volume = self._get_current_volume(project)
        context["currentVolume"] = current_volume
        budget -= estimate_tokens(json.dumps(current_volume, ensure_ascii=False))

        # 3. 角色概览（精简版）
        characters = self._filter_characters(project, max_count=8)
        context["characters"] = characters
        budget -= estimate_tokens(json.dumps(characters, ensure_ascii=False))

        # 4. 伏笔概览（只含活跃和需处理的）
        foreshadows = self._filter_foreshadows(project)
        context["foreshadows"] = foreshadows
        budget -= estimate_tokens(json.dumps(foreshadows, ensure_ascii=False))

        # 5. 真相源
        truth_source = project.get("truthSource", {})
        context["truthSource"] = truth_source
        budget -= estimate_tokens(json.dumps(truth_source, ensure_ascii=False))

        # 6. 事件账本（最近 10 条）
        events = self._get_recent_events(project, max_count=10)
        context["recentEvents"] = events
        budget -= estimate_tokens(json.dumps(events, ensure_ascii=False))

        # 7. 最近章节摘要
        chapter_summaries = self._get_recent_chapter_summaries(project, max_count=5)
        context["recentChapterSummaries"] = chapter_summaries
        budget -= estimate_tokens(json.dumps(chapter_summaries, ensure_ascii=False))

        # 8. 禁止规则
        forbidden_rules = story_bible.get("forbiddenRules", [])
        context["forbiddenRules"] = forbidden_rules

        # 9. 当前状态
        context["status"] = project.get("status", {})

        # 10. 关系概览
        relationships = project.get("relationships", [])[:8]
        context["relationships"] = relationships

        logger.info(
            "[ContextBuilder] 约束上下文构建完成, 剩余预算 token: %d", budget
        )
        return context

    def build_director_context(
        self,
        project: dict[str, Any],
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """为导演 Agent 构建上下文。

        包含: 约束 Agent 的输出 + 项目核心信息。

        Args:
            project: 完整的项目数据
            constraints: 约束 Agent 的输出

        Returns:
            导演 Agent 所需的上下文包
        """
        # 复用约束上下文作为基础
        context = self.build_constraint_context(project)
        context["constraints"] = constraints

        # 补充导演需要的额外信息
        story_bible = project.get("storyBible", {})
        context["styleProfile"] = story_bible.get("styleProfile", "")
        context["mainConflict"] = story_bible.get("mainConflict", "")
        context["endingDirection"] = story_bible.get("endingDirection", "")

        logger.info("[ContextBuilder] 导演上下文构建完成")
        return context

    def build_writer_context(
        self,
        project: dict[str, Any],
        constraints: dict[str, Any],
        director_plan: dict[str, Any],
    ) -> dict[str, Any]:
        """为写作 Agent 构建上下文。

        包含: 约束包 + 导演稿 + 项目写作相关信息。

        Args:
            project: 完整的项目数据
            constraints: 约束 Agent 的输出
            director_plan: 导演 Agent 的输出

        Returns:
            写作 Agent 所需的上下文包
        """
        context: dict[str, Any] = {}

        # 1. 故事蓝图核心
        story_bible = project.get("storyBible", {})
        context["storyBibleSummary"] = self._extract_story_bible_summary(story_bible)
        context["styleProfile"] = story_bible.get("styleProfile", "")
        context["mainTheme"] = story_bible.get("mainTheme", "")

        # 2. 约束包
        context["constraints"] = constraints

        # 3. 导演稿
        context["directorPlan"] = director_plan

        # 4. 角色信息（写作需要更详细的角色卡）
        characters = self._filter_characters(project, max_count=6)
        context["characters"] = characters

        # 5. 最近章节摘要（写作需要更多上下文来保持文风一致）
        chapter_summaries = self._get_recent_chapter_summaries(project, max_count=5)
        context["recentChapterSummaries"] = chapter_summaries

        # 6. 最近一章的结尾段落（用于衔接）
        last_chapter_tail = self._get_last_chapter_tail(project, max_chars=500)
        context["lastChapterTail"] = last_chapter_tail

        # 7. 禁止规则
        context["forbiddenRules"] = story_bible.get("forbiddenRules", [])

        # 8. 伏笔（写作需要知道哪些伏笔可以轻轻提及）
        context["foreshadows"] = self._filter_foreshadows(project)

        # 9. 关系信息
        context["relationships"] = project.get("relationships", [])[:6]

        logger.info("[ContextBuilder] 写作上下文构建完成")
        return context

    def build_review_context(
        self,
        project: dict[str, Any],
        chapter: dict[str, Any],
    ) -> dict[str, Any]:
        """为检查 Agent 构建上下文。

        包含: 正文 + 导演稿 + 约束包 + 项目状态。

        Args:
            project: 完整的项目数据
            chapter: 已生成的章节数据（含正文、导演稿等）

        Returns:
            检查 Agent 所需的上下文包
        """
        context: dict[str, Any] = {}

        # 1. 正文（检查的核心对象）
        context["chapterText"] = chapter.get("text", "")
        context["chapterTitle"] = chapter.get("title", "")
        context["chapterNumber"] = chapter.get("number", 0)
        context["wordCount"] = chapter.get("wordCount", 0)

        # 2. 导演稿（用于对比检查）
        context["directorPlan"] = chapter.get("directorPlan", {})

        # 3. 约束包（用于检查约束遵守情况）
        context["constraints"] = chapter.get("constraints", {})

        # 4. 禁止规则
        story_bible = project.get("storyBible", {})
        context["forbiddenRules"] = story_bible.get("forbiddenRules", [])

        # 5. 角色信息（用于检查角色一致性和主动性）
        context["characters"] = project.get("characters", [])[:8]

        # 6. 伏笔（用于检查伏笔处理）
        context["foreshadows"] = project.get("foreshadows", [])[:10]

        # 7. 真相源（用于检查禁止揭露）
        context["truthSource"] = project.get("truthSource", {})

        # 8. 最近章节摘要（用于连续性检查）
        context["recentChapterSummaries"] = self._get_recent_chapter_summaries(
            project, max_count=3
        )

        # 9. 关系信息（用于检查关系变化合理性）
        context["relationships"] = project.get("relationships", [])[:8]

        logger.info("[ContextBuilder] 检查上下文构建完成")
        return context

    def build_state_extract_context(
        self,
        project: dict[str, Any],
        chapter: dict[str, Any],
    ) -> dict[str, Any]:
        """为状态提取 Agent 构建上下文。

        包含: 正文 + 上一章状态快照 + 当前角色/伏笔/关系状态。

        Args:
            project: 完整的项目数据
            chapter: 已生成的章节数据

        Returns:
            状态提取 Agent 所需的上下文包
        """
        context: dict[str, Any] = {}

        # 1. 正文
        context["chapterText"] = chapter.get("text", "")
        context["chapterNumber"] = chapter.get("number", 0)
        context["chapterTitle"] = chapter.get("title", "")

        # 2. 当前角色状态（用于对比变化）
        context["characters"] = project.get("characters", [])[:8]

        # 3. 当前伏笔状态
        context["foreshadows"] = project.get("foreshadows", [])[:10]

        # 4. 当前关系状态
        context["relationships"] = project.get("relationships", [])[:8]

        # 5. 上一章状态快照（如果有）
        snapshots = project.get("memory", {}).get("stateSnapshots", [])
        context["previousStateSnapshot"] = snapshots[-1] if snapshots else {}

        # 6. 事件账本
        context["recentEvents"] = self._get_recent_events(project, max_count=5)

        # 7. 时间线
        context["timeline"] = project.get("timeline", [])

        logger.info("[ContextBuilder] 状态提取上下文构建完成")
        return context

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _extract_story_bible_summary(self, story_bible: dict[str, Any]) -> dict[str, Any]:
        """从故事蓝图中提取摘要信息。

        只保留对章节生成最关键的元信息，不包含完整大纲。

        Args:
            story_bible: 完整的故事蓝图

        Returns:
            精简的故事蓝图摘要
        """
        if not story_bible:
            return {}
        return {
            "title": story_bible.get("title", ""),
            "genre": story_bible.get("genre", ""),
            "corePremise": story_bible.get("corePremise", ""),
            "mainTheme": story_bible.get("mainTheme", ""),
            "mainConflict": story_bible.get("mainConflict", ""),
            "endingDirection": story_bible.get("endingDirection", ""),
            "forbiddenRules": story_bible.get("forbiddenRules", []),
        }

    def _get_current_volume(self, project: dict[str, Any]) -> dict[str, Any]:
        """获取当前卷信息。

        根据当前章节号判断属于哪一卷。

        Args:
            project: 项目数据

        Returns:
            当前卷的规划信息
        """
        volume_plan = project.get("volumePlan", [])
        current_chapter = len(project.get("chapters", []))

        for volume in volume_plan:
            range_str = volume.get("range", "")
            # 解析 "第1章 - 第30章" 格式
            try:
                parts = range_str.replace("第", "").replace("章", "").split("-")
                start = int(parts[0].strip())
                end = int(parts[1].strip()) if len(parts) > 1 else start + 30
                if start <= current_chapter <= end:
                    return volume
            except (ValueError, IndexError):
                continue

        # 如果找不到匹配的卷，返回第一个或空
        return volume_plan[0] if volume_plan else {}

    def _filter_characters(
        self,
        project: dict[str, Any],
        max_count: int = 8,
    ) -> list[dict[str, Any]]:
        """筛选相关角色。

        按以下优先级排序:
        1. 最近 3 章内出场的角色
        2. 主动性分数高的角色
        3. 主角/女主等核心角色

        Args:
            project: 项目数据
            max_count: 最多返回的角色数量

        Returns:
            筛选后的角色列表
        """
        characters = project.get("characters", [])
        chapters = project.get("chapters", [])
        current_chapter = len(chapters)

        # 计算每个角色的相关性分数
        scored: list[tuple[int, dict[str, Any]]] = []
        for char in characters:
            score = 0
            last_appeared = char.get("lastAppearedChapter", char.get("lastAppeared", 0))

            # 最近出场加分
            chapters_since = current_chapter - last_appeared
            if chapters_since <= 1:
                score += 50
            elif chapters_since <= 3:
                score += 30
            elif chapters_since <= 5:
                score += 15

            # 主动性加分
            agency = char.get("agencyScore", 0)
            if agency > 1:
                agency = agency / 100  # 兼容 0-100 和 0-1 两种格式
            score += int(agency * 30)

            # 核心角色加分
            role = char.get("role", "")
            if "主角" in role:
                score += 40
            elif "女主" in role:
                score += 35
            elif "导师" in role:
                score += 15

            # 退出风险高的角色优先关注
            dropout = char.get("dropoutRisk", 0)
            if dropout > 1:
                dropout = dropout / 100
            score += int(dropout * 20)

            scored.append((score, char))

        # 按分数降序排列
        scored.sort(key=lambda x: x[0], reverse=True)

        # 返回精简版角色信息
        result = []
        for _, char in scored[:max_count]:
            result.append({
                "id": char.get("id", ""),
                "name": char.get("name", ""),
                "role": char.get("role", ""),
                "personality": char.get("personality", ""),
                "currentGoal": char.get("currentGoal", ""),
                "hiddenGoal": char.get("hiddenGoal", ""),
                "emotion": char.get("emotion", ""),
                "agencyScore": char.get("agencyScore", 0),
                "dropoutRisk": char.get("dropoutRisk", 0),
                "knowledgeState": char.get("knowledgeState", []),
            })
        return result

    def _filter_foreshadows(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        """筛选活跃伏笔。

        只包含:
        - 状态为"已埋下"或"待回收"的伏笔
        - 风险值较高的伏笔
        - 计划在近期回收的伏笔

        Args:
            project: 项目数据

        Returns:
            筛选后的伏笔列表
        """
        foreshadows = project.get("foreshadows", [])
        current_chapter = len(project.get("chapters", []))

        result = []
        for fs in foreshadows:
            status = fs.get("status", "")
            # 只保留活跃伏笔
            if status in ("已埋下", "待回收", "进行中", "未触发"):
                risk = fs.get("risk", 0)
                if risk > 1:
                    risk = risk / 100  # 兼容 0-100 和 0-1

                planned_payoff = fs.get("plannedPayoffChapter", fs.get("plannedPayoff", 999))

                # 高风险或近期需要处理的伏笔优先
                if risk >= 0.3 or planned_payoff <= current_chapter + 10:
                    result.append({
                        "id": fs.get("id", ""),
                        "name": fs.get("name", ""),
                        "status": status,
                        "importance": fs.get("importance", "medium"),
                        "risk": risk,
                        "plannedPayoffChapter": planned_payoff,
                        "nextAction": fs.get("nextAction", ""),
                    })

        # 按风险降序排列
        result.sort(key=lambda x: x.get("risk", 0), reverse=True)
        return result[:12]

    def _get_recent_events(
        self,
        project: dict[str, Any],
        max_count: int = 10,
    ) -> list[dict[str, Any]]:
        """获取最近的事件。

        Args:
            project: 项目数据
            max_count: 最多返回的事件数量

        Returns:
            最近的事件列表
        """
        events = project.get("events", [])
        return events[-max_count:] if events else []

    def _get_recent_chapter_summaries(
        self,
        project: dict[str, Any],
        max_count: int = 5,
    ) -> list[dict[str, Any]]:
        """获取最近章节的摘要。

        注意: 返回的是摘要信息，不是正文全文。

        Args:
            project: 项目数据
            max_count: 最多返回的章节数

        Returns:
            最近章节的摘要列表
        """
        chapters = project.get("chapters", [])
        recent = chapters[-max_count:] if chapters else []

        summaries = []
        for ch in recent:
            summary = {
                "number": ch.get("number", 0),
                "title": ch.get("title", ""),
                "wordCount": ch.get("wordCount", 0),
            }
            # 优先使用摘要字段，没有则截取正文前 200 字
            if ch.get("summary"):
                summary["summary"] = ch["summary"]
            elif ch.get("text"):
                summary["summary"] = truncate_text(ch["text"], 200)
            else:
                summary["summary"] = ""

            # 保留导演稿中的目标信息
            director = ch.get("directorPlan", {})
            if director.get("goal"):
                summary["goal"] = director["goal"]

            summaries.append(summary)

        return summaries

    def _get_last_chapter_tail(
        self,
        project: dict[str, Any],
        max_chars: int = 500,
    ) -> str:
        """获取最近一章的结尾段落。

        用于写作 Agent 保持章节间的衔接。

        Args:
            project: 项目数据
            max_chars: 最多返回的字符数

        Returns:
            最后一章的结尾文本
        """
        chapters = project.get("chapters", [])
        if not chapters:
            return ""

        last_chapter = chapters[-1]
        text = last_chapter.get("text", "")
        if not text:
            return ""

        # 取最后 max_chars 个字符
        if len(text) <= max_chars:
            return text
        return text[-max_chars:]
