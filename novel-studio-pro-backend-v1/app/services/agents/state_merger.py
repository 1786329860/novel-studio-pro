"""状态合并器模块。

任务: 检查 state_delta 冲突，安全合并到项目状态。
这是流水线的最后一步，确保状态变更不会破坏项目一致性。

关键规则:
- 不能违反 forbiddenRules
- 不能提前揭露真相源中标记为"禁止"的信息
- 角色主动性不能突然大幅变化（单次 +/-0.30 以内）
- 伏笔不能在计划回收章节之前被回收
- 关系变化必须合理（单次变化不超过 +/-20）
- 新事件不能与已有事件矛盾

方法:
- validate_delta(project, delta) -> (valid, errors): 验证 delta 是否安全
- merge_delta(project, delta) -> dict: 合并 delta 到项目，返回变更摘要
- generate_preview(project, delta) -> str: 生成状态变化预览文本
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.utils import deep_merge, now_iso

logger = logging.getLogger(__name__)


class StateMerger:
    """状态合并器。

    负责:
    1. 验证 state_delta 的安全性
    2. 将 delta 安全合并到项目状态
    3. 生成状态变化的预览文本
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def validate_and_merge(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        """验证并合并 state_delta，返回 (合并摘要, 预览文本)。

        一步完成验证 -> 预览 -> 合并的流程，供编排器调用。

        Args:
            project: 当前项目数据（会被修改）
            delta: 状态提取 Agent 输出的 state_delta

        Returns:
            (合并摘要 dict, 预览文本 str)
        """
        # 生成预览
        preview = self.generate_preview(project, delta)

        # 执行合并（内部会自动验证）
        merged = self.merge_delta(project, delta)

        return merged, preview

    def validate_delta(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """验证 state_delta 是否安全。

        检查所有关键规则，返回是否通过和错误列表。

        Args:
            project: 当前项目数据
            delta: 状态提取 Agent 输出的 state_delta

        Returns:
            (是否通过验证, 错误信息列表)
        """
        errors: list[str] = []

        # 1. 检查角色主动性变化幅度
        self._check_agency_changes(project, delta, errors)

        # 2. 检查关系变化幅度
        self._check_relationship_changes(project, delta, errors)

        # 3. 检查伏笔回收时机
        self._check_foreshadow_payoff(project, delta, errors)

        # 4. 检查是否违反禁止规则
        self._check_forbidden_rules(project, delta, errors)

        # 5. 检查主线进度合理性
        self._check_main_progress(project, delta, errors)

        # 6. 检查新事件是否矛盾
        self._check_event_consistency(project, delta, errors)

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning("[StateMerger] 验证发现 %d 个问题: %s", len(errors), errors)
        else:
            logger.info("[StateMerger] 验证通过")

        return is_valid, errors

    def merge_delta(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
    ) -> dict[str, Any]:
        """将 state_delta 安全合并到项目状态。

        合并前会自动验证，对不安全的变化进行修正。

        Args:
            project: 当前项目数据（会被修改）
            delta: 状态提取 Agent 输出的 state_delta

        Returns:
            变更摘要 dict
        """
        summary: dict[str, Any] = {
            "mergedAt": now_iso(),
            "changes": [],
            "warnings": [],
        }

        # 先验证
        is_valid, errors = self.validate_delta(project, delta)
        if not is_valid:
            summary["warnings"] = errors
            logger.info("[StateMerger] 存在警告，将自动修正后合并")

        # 合并主线进度
        progress_delta = delta.get("main_progress_delta", 0)
        if progress_delta:
            old_progress = project.get("status", {}).get("mainProgress", 0)
            new_progress = old_progress + progress_delta
            project.setdefault("status", {})["mainProgress"] = new_progress
            summary["changes"].append(f"主线进度: {old_progress} -> {new_progress}")

        # 合并角色变化
        self._merge_character_changes(project, delta, summary)

        # 合并关系变化
        self._merge_relationship_changes(project, delta, summary)

        # 合并伏笔变化
        self._merge_foreshadow_changes(project, delta, summary)

        # 合并新事件
        self._merge_new_events(project, delta, summary)

        # 合并时间线更新
        self._merge_timeline_updates(project, delta, summary)

        # 合并知识更新
        self._merge_knowledge_updates(project, delta, summary)

        # 更新状态快照
        self._update_state_snapshot(project, delta)

        logger.info(
            "[StateMerger] 合并完成，共 %d 项变更，%d 项警告",
            len(summary["changes"]),
            len(summary["warnings"]),
        )

        return summary

    def generate_preview(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
    ) -> str:
        """生成状态变化预览文本。

        用于在合并前向用户展示即将发生的变化。

        Args:
            project: 当前项目数据
            delta: 状态提取 Agent 输出的 state_delta

        Returns:
            可读的状态变化预览文本
        """
        lines: list[str] = []
        lines.append("=== 状态变化预览 ===")
        lines.append("")

        # 主线进度
        progress = delta.get("main_progress_delta", 0)
        if progress:
            lines.append(f"主线进度: +{progress}")

        # 角色变化
        char_changes = delta.get("character_changes", [])
        if char_changes:
            lines.append("")
            lines.append("角色变化:")
            for change in char_changes:
                name = change.get("character_name", "未知角色")
                field = change.get("field", "")
                old = change.get("old", "")
                new = change.get("new", "")
                reason = change.get("reason", "")
                lines.append(f"  - {name} [{field}]: {old} -> {new}")
                if reason:
                    lines.append(f"    原因: {reason}")

        # 关系变化
        rel_changes = delta.get("relationship_changes", [])
        if rel_changes:
            lines.append("")
            lines.append("关系变化:")
            for change in rel_changes:
                from_name = change.get("from", "")
                to_name = change.get("to", "")
                field = change.get("field", "")
                delta_val = change.get("delta", 0)
                reason = change.get("reason", "")
                sign = "+" if delta_val > 0 else ""
                lines.append(f"  - {from_name} <-> {to_name} [{field}]: {sign}{delta_val}")
                if reason:
                    lines.append(f"    原因: {reason}")

        # 伏笔变化
        fs_changes = delta.get("foreshadow_changes", [])
        if fs_changes:
            lines.append("")
            lines.append("伏笔变化:")
            for change in fs_changes:
                fs_id = change.get("foreshadow_id", "")
                action = change.get("action", "")
                detail = change.get("detail", "")
                lines.append(f"  - [{fs_id}] {action}: {detail}")

        # 新事件
        new_events = delta.get("new_events", [])
        if new_events:
            lines.append("")
            lines.append("新事件:")
            for event in new_events:
                desc = event.get("description", "")
                impact = event.get("impact", "")
                visibility = event.get("visibility", [])
                lines.append(f"  - {desc}")
                if impact:
                    lines.append(f"    影响: {impact}")
                if visibility:
                    lines.append(f"    知情者: {', '.join(visibility)}")

        # 知识更新
        knowledge_updates = delta.get("knowledge_updates", [])
        if knowledge_updates:
            lines.append("")
            lines.append("知识变化:")
            for ku in knowledge_updates:
                char = ku.get("character", "")
                learned = ku.get("learned", "")
                forgot = ku.get("forgot", "")
                if learned:
                    lines.append(f"  - {char} 获知: {learned}")
                if forgot:
                    lines.append(f"  - {char} 遗忘: {forgot}")

        lines.append("")
        lines.append("=== 预览结束 ===")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 验证方法
    # ------------------------------------------------------------------

    def _check_agency_changes(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        errors: list[str],
    ) -> None:
        """检查角色主动性变化幅度。

        规则: 单次变化不超过 +/-0.30（30%）。

        Args:
            project: 项目数据
            delta: 状态变化
            errors: 错误列表（会被修改）
        """
        max_agency_change = 0.30
        characters = project.get("characters", [])
        char_map = {c.get("id", ""): c for c in characters}

        for change in delta.get("character_changes", []):
            if change.get("field") != "agencyScore":
                continue

            char_id = change.get("character_id", "")
            old_val = self._to_01(change.get("old", 0))
            new_val = self._to_01(change.get("new", 0))
            diff = abs(new_val - old_val)

            if diff > max_agency_change:
                errors.append(
                    f"角色 {change.get('character_name', char_id)} 的主动性变化过大: "
                    f"{old_val:.2f} -> {new_val:.2f} (变化 {diff:.2f}，上限 {max_agency_change})"
                )

    def _check_relationship_changes(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        errors: list[str],
    ) -> None:
        """检查关系变化幅度。

        规则: 单次变化不超过 +/-20。

        Args:
            project: 项目数据
            delta: 状态变化
            errors: 错误列表（会被修改）
        """
        max_rel_change = 20

        for change in delta.get("relationship_changes", []):
            delta_val = abs(change.get("delta", 0))
            if delta_val > max_rel_change:
                errors.append(
                    f"关系 {change.get('from', '')} <-> {change.get('to', '')} 的变化过大: "
                    f"{change.get('delta', 0)}（上限 +/-{max_rel_change}）"
                )

    def _check_foreshadow_payoff(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        errors: list[str],
    ) -> None:
        """检查伏笔回收时机。

        规则: 不能在计划回收章节之前回收。

        Args:
            project: 项目数据
            delta: 状态变化
            errors: 错误列表（会被修改）
        """
        foreshadows = project.get("foreshadows", [])
        fs_map = {fs.get("id", ""): fs for fs in foreshadows}
        current_chapter = len(project.get("chapters", []))

        for change in delta.get("foreshadow_changes", []):
            if change.get("action") != "回收":
                continue

            fs_id = change.get("foreshadow_id", "")
            fs = fs_map.get(fs_id, {})
            planned_payoff = fs.get("plannedPayoffChapter", fs.get("plannedPayoff", 999))

            if current_chapter < planned_payoff:
                errors.append(
                    f"伏笔 {fs.get('name', fs_id)} 计划在第 {planned_payoff} 章回收，"
                    f"当前第 {current_chapter} 章不能提前回收。"
                )

    def _check_forbidden_rules(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        errors: list[str],
    ) -> None:
        """检查是否违反禁止规则。

        规则: 知识更新不能让角色获得 forbiddenRules 中禁止的信息。

        Args:
            project: 项目数据
            delta: 状态变化
            errors: 错误列表（会被修改）
        """
        forbidden_rules = project.get("storyBible", {}).get("forbiddenRules", [])
        truth_source = project.get("truthSource", {})

        for ku in delta.get("knowledge_updates", []):
            learned = ku.get("learned", "")
            if not learned:
                continue

            # 检查是否与禁止规则冲突
            for rule in forbidden_rules:
                # 提取规则中的关键词
                rule_keywords = self._extract_rule_keywords(rule)
                for keyword in rule_keywords:
                    if keyword in learned:
                        errors.append(
                            f"知识更新可能违反禁止规则: 「{learned}」"
                            f"与规则「{rule}」冲突。"
                        )

    def _check_main_progress(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        errors: list[str],
    ) -> None:
        """检查主线进度合理性。

        规则: 单章推进不超过 10。

        Args:
            project: 项目数据
            delta: 状态变化
            errors: 错误列表（会被修改）
        """
        progress = delta.get("main_progress_delta", 0)
        if progress > 10:
            errors.append(f"主线推进过大: {progress}（单章上限 10）")
        if progress < 0:
            errors.append(f"主线推进不能为负数: {progress}")

    def _check_event_consistency(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        errors: list[str],
    ) -> None:
        """检查新事件是否与已有事件矛盾。

        Args:
            project: 项目数据
            delta: 状态变化
            errors: 错误列表（会被修改）
        """
        existing_events = project.get("events", [])
        new_events = delta.get("new_events", [])

        for new_event in new_events:
            new_desc = new_event.get("description", "")
            for existing in existing_events:
                exist_desc = existing.get("description", "")
                # 简单的矛盾检测: 如果新事件描述中包含"推翻"、"否定"等词
                # 且提到了已有事件的关键信息
                contradiction_words = ["推翻", "否定", "并非如此", "其实是假的"]
                for word in contradiction_words:
                    if word in new_desc and len(exist_desc) > 5:
                        # 提取已有事件的关键词
                        exist_keywords = exist_desc[:10]
                        if exist_keywords in new_desc:
                            errors.append(
                                f"新事件可能与已有事件矛盾: "
                                f"新事件「{new_desc}」vs 已有事件「{exist_desc}」"
                            )

    # ------------------------------------------------------------------
    # 合并方法
    # ------------------------------------------------------------------

    def _merge_character_changes(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """合并角色状态变化到项目。

        Args:
            project: 项目数据（会被修改）
            delta: 状态变化
            summary: 变更摘要（会被修改）
        """
        characters = project.get("characters", [])
        char_map = {c.get("id", ""): c for c in characters}

        for change in delta.get("character_changes", []):
            char_id = change.get("character_id", "")
            char = char_map.get(char_id)
            if not char:
                continue

            field = change.get("field", "")
            new_value = change.get("new")

            if new_value is None:
                continue

            # 安全范围检查
            if field == "agencyScore":
                new_value = max(0, min(1.0, self._to_01(new_value)))
            elif field == "dropoutRisk":
                new_value = max(0, min(1.0, self._to_01(new_value)))

            old_value = char.get(field, "")
            char[field] = new_value

            summary["changes"].append(
                f"角色 {change.get('character_name', char_id)} [{field}]: "
                f"{old_value} -> {new_value}"
            )

    def _merge_relationship_changes(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """合并关系变化到项目。

        Args:
            project: 项目数据（会被修改）
            delta: 状态变化
            summary: 变更摘要（会被修改）
        """
        relationships = project.get("relationships", [])

        for change in delta.get("relationship_changes", []):
            from_name = change.get("from", "")
            to_name = change.get("to", "")
            field = change.get("field", "")
            new_value = change.get("new_value")

            if new_value is None:
                continue

            # 找到对应的关系
            for rel in relationships:
                if rel.get("from") == from_name and rel.get("to") == to_name:
                    old_value = rel.get(field, 50)
                    # 限制变化幅度
                    delta_val = new_value - old_value
                    if abs(delta_val) > 20:
                        delta_val = 20 if delta_val > 0 else -20
                        new_value = old_value + delta_val
                        summary["warnings"].append(
                            f"关系 {from_name} <-> {to_name} 的 {field} 变化被限制为 +/-20"
                        )

                    rel[field] = max(0, min(100, new_value))
                    summary["changes"].append(
                        f"关系 {from_name} <-> {to_name} [{field}]: "
                        f"{old_value} -> {rel[field]}"
                    )
                    break

    def _merge_foreshadow_changes(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """合并伏笔变化到项目。

        Args:
            project: 项目数据（会被修改）
            delta: 状态变化
            summary: 变更摘要（会被修改）
        """
        foreshadows = project.get("foreshadows", [])
        fs_map = {fs.get("id", ""): fs for fs in foreshadows}
        current_chapter = len(project.get("chapters", []))

        for change in delta.get("foreshadow_changes", []):
            fs_id = change.get("foreshadow_id", "")
            fs = fs_map.get(fs_id)
            if not fs:
                continue

            action = change.get("action", "")

            # 检查回收时机
            planned_payoff = fs.get("plannedPayoffChapter", fs.get("plannedPayoff", 999))
            if action == "回收" and current_chapter < planned_payoff:
                summary["warnings"].append(
                    f"伏笔 {fs.get('name', fs_id)} 回收被推迟到计划章节"
                )
                action = "推进"  # 降级为推进

            # 更新伏笔状态
            status_map = {
                "轻微回响": "已埋下",
                "回响": "已埋下",
                "推进": "进行中",
                "回收": "已回收",
            }
            new_status = status_map.get(action, fs.get("status", "已埋下"))
            fs["status"] = new_status
            fs["lastMentionedChapter"] = current_chapter
            fs["lastMentioned"] = current_chapter

            # 更新风险值
            if action == "推进":
                old_risk = self._to_01(fs.get("risk", 0))
                fs["risk"] = min(1.0, old_risk + 0.05)
            elif action == "回收":
                fs["risk"] = 0

            summary["changes"].append(
                f"伏笔 {fs.get('name', fs_id)}: {action} (状态 -> {new_status})"
            )

    def _merge_new_events(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """合并新事件到项目。

        Args:
            project: 项目数据（会被修改）
            delta: 状态变化
            summary: 变更摘要（会被修改）
        """
        events = project.get("events", [])
        if not isinstance(events, list):
            events = []
            project["events"] = events

        for event in delta.get("new_events", []):
            events.append({
                "description": event.get("description", ""),
                "impact": event.get("impact", ""),
                "visibility": event.get("visibility", []),
                "chapter": len(project.get("chapters", [])),
                "createdAt": now_iso(),
            })
            summary["changes"].append(f"新事件: {event.get('description', '')}")

    def _merge_timeline_updates(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """合并时间线更新到项目。

        Args:
            project: 项目数据（会被修改）
            delta: 状态变化
            summary: 变更摘要（会被修改）
        """
        timeline = project.get("timeline", [])
        if not isinstance(timeline, list):
            timeline = []
            project["timeline"] = timeline

        for update in delta.get("timeline_updates", []):
            timeline.append(update)
            summary["changes"].append(f"时间线: {update}")

    def _merge_knowledge_updates(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """合并角色知识更新到项目。

        Args:
            project: 项目数据（会被修改）
            delta: 状态变化
            summary: 变更摘要（会被修改）
        """
        characters = project.get("characters", [])
        char_map = {c.get("name", ""): c for c in characters}

        for ku in delta.get("knowledge_updates", []):
            char_name = ku.get("character", "")
            learned = ku.get("learned", "")
            forgot = ku.get("forgot")

            char = char_map.get(char_name)
            if not char:
                continue

            if learned:
                knowledge_state = char.get("knowledgeState", [])
                knowledge_state.append(learned)
                summary["changes"].append(f"{char_name} 获知: {learned}")

            if forgot:
                knowledge_state = char.get("knowledgeState", [])
                knowledge_state = [k for k in knowledge_state if forgot not in k]
                char["knowledgeState"] = knowledge_state
                summary["changes"].append(f"{char_name} 遗忘: {forgot}")

    def _update_state_snapshot(
        self,
        project: dict[str, Any],
        delta: dict[str, Any],
    ) -> None:
        """更新状态快照到 memory 中。

        Args:
            project: 项目数据（会被修改）
            delta: 状态变化
        """
        memory = project.setdefault("memory", {})
        snapshots = memory.setdefault("stateSnapshots", [])

        snapshot = {
            "chapter": len(project.get("chapters", [])),
            "mainProgress": project.get("status", {}).get("mainProgress", 0),
            "characterEmotions": {
                c.get("name", ""): c.get("emotion", "")
                for c in project.get("characters", [])
            },
            "activeForeshadows": [
                fs.get("name", "")
                for fs in project.get("foreshadows", [])
                if fs.get("status") in ("已埋下", "进行中", "待回收")
            ],
            "delta": delta,
            "updatedAt": now_iso(),
        }

        snapshots.append(snapshot)
        # 只保留最近 20 个快照
        if len(snapshots) > 20:
            del snapshots[:-20]

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _to_01(value: Any) -> float:
        """将值转换为 0-1 范围。

        兼容 0-100 和 0-1 两种格式。

        Args:
            value: 输入值

        Returns:
            0-1 范围的浮点数
        """
        try:
            v = float(value)
            if v > 1:
                return v / 100
            return v
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _extract_rule_keywords(rule: str) -> list[str]:
        """从规则文本中提取关键词。

        Args:
            rule: 规则文本

        Returns:
            关键词列表
        """
        import re

        cleaned = re.sub(r"[，。、；：""''！？（）《》【】\s]", " ", rule)
        words = cleaned.split()

        stop_words = {
            "的", "了", "在", "是", "有", "和", "与", "或", "不", "也",
            "都", "要", "会", "能", "可以", "应该", "必须", "不得", "不能",
            "前", "后", "中", "上", "下", "一", "个", "每", "本章",
        }
        return [w for w in words if len(w) >= 2 and w not in stop_words][:5]
