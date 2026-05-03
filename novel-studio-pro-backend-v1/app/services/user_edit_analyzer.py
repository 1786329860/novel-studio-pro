"""用户修改分析器模块。

分析用户对章节正文的修改，提取状态变化。

功能:
- 使用 difflib 找出修改的段落
- 只对有实质性修改的段落调用 AI（忽略格式、空格等无意义修改）
- 修改幅度超过 50% 时，整章重新提取
- 修改幅度小于 10% 时，跳过（视为无意义修改）
- Mock 模式: 返回空的 state_delta
"""

from __future__ import annotations

import difflib
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 修改幅度阈值
MIN_EDIT_RATIO = 0.10  # 低于 10% 视为无意义修改，跳过
FULL_REEXTRACT_RATIO = 0.50  # 超过 50% 整章重新提取


def _split_paragraphs(text: str) -> list[str]:
    """将正文按段落分割。

    Args:
        text: 正文文本

    Returns:
        段落列表（去除空段落）
    """
    lines = text.split("\n")
    paragraphs = []
    current = []

    for line in lines:
        stripped = line.strip()
        if stripped:
            current.append(stripped)
        else:
            if current:
                paragraphs.append(" ".join(current))
                current = []

    if current:
        paragraphs.append(" ".join(current))

    return paragraphs


def _compute_edit_ratio(original: str, modified: str) -> float:
    """计算两段文本的修改比例。

    使用 difflib.SequenceMatcher 计算相似度，返回修改比例（0-1）。

    Args:
        original: 原始文本
        modified: 修改后文本

    Returns:
        修改比例，0 表示无修改，1 表示完全不同
    """
    if not original and not modified:
        return 0.0
    if not original or not modified:
        return 1.0

    ratio = difflib.SequenceMatcher(None, original, modified).ratio()
    return 1.0 - ratio


def _find_modified_paragraphs(
    original_paragraphs: list[str],
    modified_paragraphs: list[str],
) -> list[dict[str, Any]]:
    """使用 diff 算法找出修改的段落。

    Args:
        original_paragraphs: 原始段落列表
        modified_paragraphs: 修改后段落列表

    Returns:
        修改的段落列表，每项包含 type, original, modified, index
    """
    matcher = difflib.SequenceMatcher(
        None, original_paragraphs, modified_paragraphs
    )
    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        change = {
            "type": tag,  # replace / insert / delete
            "original": "\n".join(original_paragraphs[i1:i2]),
            "modified": "\n".join(modified_paragraphs[j1:j2]),
            "original_index": i1,
            "modified_index": j1,
        }
        changes.append(change)

    return changes


def _is_trivial_change(original: str, modified: str) -> bool:
    """判断修改是否为无意义修改（仅格式、空格、标点等）。

    Args:
        original: 原始文本
        modified: 修改后文本

    Returns:
        True 表示无意义修改
    """
    # 去除所有空白和标点后比较
    import re
    clean_original = re.sub(r"[\s，。！？、；：""''（）《》【】\.\,\!\?\;\:\"\'\(\)\[\]]", "", original)
    clean_modified = re.sub(r"[\s，。！？、；：""''（）《》【】\.\,\!\?\;\:\"\'\(\)\[\]]", "", modified)

    if clean_original == clean_modified:
        return True

    # 如果去除空白后差异很小，也视为无意义
    ratio = difflib.SequenceMatcher(None, clean_original, clean_modified).ratio()
    return ratio > 0.95


def _filter_meaningful_changes(
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """过滤掉无意义的修改，只保留实质性修改。

    Args:
        changes: 所有修改列表

    Returns:
        有实质性修改的列表
    """
    meaningful = []
    for change in changes:
        original = change.get("original", "")
        modified = change.get("modified", "")

        # 插入或删除空内容，跳过
        if not original.strip() and not modified.strip():
            continue

        # 无意义修改，跳过
        if original.strip() and modified.strip() and _is_trivial_change(original, modified):
            continue

        meaningful.append(change)

    return meaningful


async def analyze_user_edit(
    original_text: str,
    modified_text: str,
    project: dict[str, Any],
) -> dict[str, Any]:
    """分析用户对章节正文的修改，提取状态变化。

    流程:
    1. 计算整体修改比例
    2. 修改比例 < 10%: 跳过，返回空 state_delta
    3. 修改比例 > 50%: 整章重新提取
    4. 10% <= 修改比例 <= 50%: 只对修改段落提取

    Args:
        original_text: 原始正文
        modified_text: 修改后正文
        project: 项目数据

    Returns:
        分析结果，包含:
        - edit_ratio: 修改比例
        - action: "skip" / "partial" / "full"
        - changes: 修改的段落列表
        - state_delta: 新的状态变化（skip 时为空）
        - summary: 人类可读的摘要
    """
    # 1. 计算整体修改比例
    edit_ratio = _compute_edit_ratio(original_text, modified_text)

    logger.info(
        "[UserEditAnalyzer] 修改比例: %.2f%%", edit_ratio * 100
    )

    # 2. 修改比例过低，跳过
    if edit_ratio < MIN_EDIT_RATIO:
        return {
            "edit_ratio": round(edit_ratio, 4),
            "action": "skip",
            "changes": [],
            "state_delta": {},
            "summary": f"修改幅度仅 {edit_ratio * 100:.1f}%，低于 {MIN_EDIT_RATIO * 100:.0f}% 阈值，视为无意义修改。",
        }

    # 3. 分割段落，找出修改
    original_paragraphs = _split_paragraphs(original_text)
    modified_paragraphs = _split_paragraphs(modified_text)
    all_changes = _find_modified_paragraphs(original_paragraphs, modified_paragraphs)
    meaningful_changes = _filter_meaningful_changes(all_changes)

    if not meaningful_changes:
        return {
            "edit_ratio": round(edit_ratio, 4),
            "action": "skip",
            "changes": [],
            "state_delta": {},
            "summary": "所有修改均为格式调整，无实质性内容变化。",
        }

    # 4. 根据修改幅度决定策略
    if edit_ratio >= FULL_REEXTRACT_RATIO:
        # 整章重新提取
        state_delta = await _full_reextract(modified_text, project)
        return {
            "edit_ratio": round(edit_ratio, 4),
            "action": "full",
            "changes": meaningful_changes,
            "state_delta": state_delta,
            "summary": (
                f"修改幅度 {edit_ratio * 100:.1f}% 超过 {FULL_REEXTRACT_RATIO * 100:.0f}% 阈值，"
                f"整章重新提取状态变化。共检测到 {len(meaningful_changes)} 处修改。"
            ),
        }
    else:
        # 只对修改段落提取
        state_delta = await _partial_reextract(meaningful_changes, project)
        return {
            "edit_ratio": round(edit_ratio, 4),
            "action": "partial",
            "changes": meaningful_changes,
            "state_delta": state_delta,
            "summary": (
                f"修改幅度 {edit_ratio * 100:.1f}%，对 {len(meaningful_changes)} 处实质性修改"
                f"段落重新提取状态变化。"
            ),
        }


async def _full_reextract(
    modified_text: str,
    project: dict[str, Any],
) -> dict[str, Any]:
    """整章重新提取状态变化。

    使用 StateExtractorAgent 对完整修改后正文重新提取。

    Args:
        modified_text: 修改后完整正文
        project: 项目数据

    Returns:
        状态变化 dict
    """
    try:
        from app.services.agents import StateExtractorAgent
        from app.services.agents.context_builder import ContextBuilder

        context_builder = ContextBuilder()
        temp_chapter = {
            "text": modified_text,
            "title": "",
            "number": len(project.get("chapters", [])) + 1,
            "wordCount": len(modified_text),
        }

        ctx = context_builder.build_state_extract_context(project, temp_chapter)
        ctx["project"] = project
        ctx["chapterText"] = modified_text

        result = await StateExtractorAgent().run(ctx)
        return result.get("state_delta", {})
    except Exception as exc:
        logger.warning("[UserEditAnalyzer] 整章重新提取失败，返回空 delta: %s", exc)
        return {}


async def _partial_reextract(
    changes: list[dict[str, Any]],
    project: dict[str, Any],
) -> dict[str, Any]:
    """只对修改段落提取状态变化。

    将修改的段落拼接后发送给 StateExtractorAgent。

    Args:
        changes: 有实质性修改的段落列表
        project: 项目数据

    Returns:
        状态变化 dict
    """
    try:
        from app.services.agents import StateExtractorAgent
        from app.services.agents.context_builder import ContextBuilder

        # 拼接修改的段落
        modified_parts = []
        for change in changes:
            modified = change.get("modified", "")
            if modified.strip():
                modified_parts.append(modified)

        combined_text = "\n\n".join(modified_parts)

        if not combined_text.strip():
            return {}

        context_builder = ContextBuilder()
        temp_chapter = {
            "text": combined_text,
            "title": "",
            "number": len(project.get("chapters", [])) + 1,
            "wordCount": len(combined_text),
        }

        ctx = context_builder.build_state_extract_context(project, temp_chapter)
        ctx["project"] = project
        ctx["chapterText"] = combined_text

        result = await StateExtractorAgent().run(ctx)
        return result.get("state_delta", {})
    except Exception as exc:
        logger.warning("[UserEditAnalyzer] 部分重新提取失败，返回空 delta: %s", exc)
        return {}
