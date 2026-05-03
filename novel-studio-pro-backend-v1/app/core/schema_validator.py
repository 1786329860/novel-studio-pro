"""Agent 输出 JSON Schema 校验模块。

为每个 Agent 的输出定义 JSON Schema，验证 AI 返回的数据格式。
使用 Python 标准库实现，不引入 pydantic 或 jsonschema 等外部依赖。

核心功能:
- validate_agent_output(agent_name, data): 验证 Agent 输出格式
- 自动修复常见问题（字段名大小写、缺少默认值等）
- 修复失败时返回详细错误信息，供调用方回退 Mock

设计原则:
- 简单的字段类型检查和必填检查
- 验证失败时返回详细的错误信息
- 验证失败时自动尝试修复
- 修复后仍不合法则回退 Mock
"""

from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ======================================================================
# Schema 定义
# ======================================================================

# 每个 Agent 的 Schema 定义
# 格式: {字段名: (类型, 是否必填, 额外校验函数或默认值)}
# 类型: type 或 tuple[type, ...]
# 额外校验: None 表示无额外校验，callable 表示校验函数，其他值表示默认值

AGENT_SCHEMAS: dict[str, dict[str, tuple]] = {
    # 约束生成 Agent
    "ConstraintAgent": {
        "must_happen": (list, True, None),
        "must_not_happen": (list, True, None),
        "character_allocation": (dict, True, None),
    },
    # 导演稿 Agent
    "DirectorAgent": {
        "scenes": (list, True, _validate_director_scenes),
        "chapter_goal": (str, True, None),
    },
    # 正文写作 Agent
    "WriterAgent": {
        "text": (str, True, _validate_writer_text),
        "word_count": ((int, float), True, _validate_writer_word_count),
    },
    # 质量检查 Agent
    "ReviewAgent": {
        "total_score": ((int, float), True, _validate_review_score),
        "tests": (list, True, _validate_review_tests),
    },
    # 状态提取 Agent
    "StateExtractorAgent": {
        "state_delta": (dict, True, None),
    },
    # 记忆检索 Agent
    "memory_retrieval": {
        "relevant_memories": (list, True, None),
        "token_budget_used": ((int, float), True, None),
    },
    # 角色导演 Agent
    "character_director": {
        "character_plan": (dict, True, None),
    },
    # 伏笔管理 Agent
    "foreshadow_manager": {
        "foreshadow_plan": (list, True, None),
    },
}


# ======================================================================
# 字段级校验函数
# ======================================================================

def _validate_director_scenes(scenes: Any) -> list[str]:
    """校验导演稿的 scenes 列表。

    每个场景必须有 number(int) 和 goal(str)。

    Args:
        scenes: 场景列表

    Returns:
        错误信息列表
    """
    errors: list[str] = []
    if not isinstance(scenes, list):
        return ["scenes 必须是列表"]

    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            errors.append(f"scenes[{i}] 必须是对象")
            continue
        if not isinstance(scene.get("number"), (int, float)):
            errors.append(f"scenes[{i}].number 必须是数字")
        if not isinstance(scene.get("goal"), str) or not scene["goal"].strip():
            errors.append(f"scenes[{i}].goal 必须是非空字符串")

    return errors


def _validate_writer_text(text: Any) -> list[str]:
    """校验正文写作的 text 字段。

    正文必须大于 100 字。

    Args:
        text: 正文内容

    Returns:
        错误信息列表
    """
    if not isinstance(text, str):
        return ["text 必须是字符串"]
    if len(text) < 100:
        return [f"text 长度不足 100 字（当前 {len(text)} 字）"]
    return []


def _validate_writer_word_count(word_count: Any) -> list[str]:
    """校验正文字数。

    字数必须大于 0。

    Args:
        word_count: 字数

    Returns:
        错误信息列表
    """
    if not isinstance(word_count, (int, float)):
        return ["word_count 必须是数字"]
    if int(word_count) <= 0:
        return [f"word_count 必须大于 0（当前 {word_count}）"]
    return []


def _validate_review_score(score: Any) -> list[str]:
    """校验质量评分。

    评分必须在 0-100 之间。

    Args:
        score: 质量评分

    Returns:
        错误信息列表
    """
    if not isinstance(score, (int, float)):
        return ["total_score 必须是数字"]
    s = int(score)
    if s < 0 or s > 100:
        return [f"total_score 必须在 0-100 之间（当前 {s}）"]
    return []


def _validate_review_tests(tests: Any) -> list[str]:
    """校验质量检查的 tests 列表。

    每个测试项必须有 name(str) 和 score(int)。

    Args:
        tests: 测试项列表

    Returns:
        错误信息列表
    """
    errors: list[str] = []
    if not isinstance(tests, list):
        return ["tests 必须是列表"]

    for i, test in enumerate(tests):
        if not isinstance(test, dict):
            errors.append(f"tests[{i}] 必须是对象")
            continue
        if not isinstance(test.get("name"), str) or not test["name"].strip():
            errors.append(f"tests[{i}].name 必须是非空字符串")
        if not isinstance(test.get("score"), (int, float)):
            errors.append(f"tests[{i}].score 必须是数字")

    return errors


# ======================================================================
# 自动修复策略
# ======================================================================

# 字段名大小写映射：常见的 AI 返回字段名变体 -> 标准字段名
_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "ConstraintAgent": {
        "MustHappen": "must_happen",
        "Must_Not_Happen": "must_not_happen",
        "MustNotHappen": "must_not_happen",
        "mustNotHappen": "must_not_happen",
        "MustHappen": "must_happen",
        "CharacterAllocation": "character_allocation",
        "characterAllocation": "character_allocation",
    },
    "DirectorAgent": {
        "Scenes": "scenes",
        "ChapterGoal": "chapter_goal",
        "chapterGoal": "chapter_goal",
        "ChapterArc": "chapter_arc",
        "chapterArc": "chapter_arc",
    },
    "WriterAgent": {
        "Text": "text",
        "WordCount": "word_count",
        "wordCount": "word_count",
        "DialogueRatio": "dialogue_ratio",
        "dialogueRatio": "dialogue_ratio",
        "NarrativeStyle": "narrative_style",
        "narrativeStyle": "narrative_style",
    },
    "ReviewAgent": {
        "TotalScore": "total_score",
        "totalScore": "total_score",
        "Tests": "tests",
        "RewriteSuggestions": "rewrite_suggestions",
        "rewriteSuggestions": "rewrite_suggestions",
    },
    "StateExtractorAgent": {
        "StateDelta": "state_delta",
        "stateDelta": "state_delta",
    },
    "memory_retrieval": {
        "RelevantMemories": "relevant_memories",
        "relevantMemories": "relevant_memories",
        "TokenBudgetUsed": "token_budget_used",
        "tokenBudgetUsed": "token_budget_used",
    },
    "character_director": {
        "CharacterPlan": "character_plan",
        "characterPlan": "character_plan",
    },
    "foreshadow_manager": {
        "ForeshadowPlan": "foreshadow_plan",
        "foreshadowPlan": "foreshadow_plan",
    },
}

# 默认值映射：缺少必填字段时使用的默认值
_DEFAULT_VALUES: dict[str, dict[str, Any]] = {
    "ConstraintAgent": {
        "must_happen": [],
        "must_not_happen": [],
        "character_allocation": {},
    },
    "DirectorAgent": {
        "scenes": [],
        "chapter_goal": "",
    },
    "WriterAgent": {
        "text": "",
        "word_count": 0,
    },
    "ReviewAgent": {
        "total_score": 0,
        "tests": [],
    },
    "StateExtractorAgent": {
        "state_delta": {},
    },
    "memory_retrieval": {
        "relevant_memories": [],
        "token_budget_used": 0,
    },
    "character_director": {
        "character_plan": {},
    },
    "foreshadow_manager": {
        "foreshadow_plan": [],
    },
}


# ======================================================================
# 核心校验函数
# ======================================================================

def validate_agent_output(
    agent_name: str,
    data: dict[str, Any],
) -> tuple[bool, list[str]]:
    """验证 Agent 输出是否符合 JSON Schema。

    Args:
        agent_name: Agent 名称（对应 self.name）
        data: Agent 返回的数据 dict

    Returns:
        (是否有效, 错误列表)
        - 有效时返回 (True, [])
        - 无效时返回 (False, [错误信息列表])
    """
    if not isinstance(data, dict):
        return False, [f"Agent 输出必须是 dict，实际类型: {type(data).__name__}"]

    # 获取该 Agent 的 Schema
    schema = AGENT_SCHEMAS.get(agent_name)
    if schema is None:
        # 未注册的 Agent，跳过校验
        logger.debug("[Schema] Agent '%s' 未注册 Schema，跳过校验", agent_name)
        return True, []

    errors: list[str] = []

    for field_name, (expected_type, required, validator) in schema.items():
        if field_name not in data:
            if required:
                errors.append(f"缺少必填字段: {field_name}")
            continue

        value = data[field_name]

        # 类型检查
        if not isinstance(value, expected_type):
            # 尝试宽松类型转换
            converted = _try_convert_type(value, expected_type)
            if converted is not None:
                data[field_name] = converted
                value = converted
            else:
                errors.append(
                    f"字段 '{field_name}' 类型错误: "
                    f"期望 {expected_type}, 实际 {type(value).__name__}"
                )
                continue

        # 额外校验（如果有校验函数）
        if validator is not None and callable(validator):
            field_errors = validator(value)
            errors.extend(field_errors)

    is_valid = len(errors) == 0
    if not is_valid:
        logger.warning(
            "[Schema] Agent '%s' 输出校验失败: %s",
            agent_name,
            "; ".join(errors),
        )
    else:
        logger.info("[Schema] Agent '%s' 输出校验通过", agent_name)

    return is_valid, errors


def try_fix_agent_output(
    agent_name: str,
    data: dict[str, Any],
) -> tuple[dict[str, Any], bool, list[str]]:
    """尝试自动修复 Agent 输出。

    修复策略:
    1. 字段名大小写/别名映射
    2. 缺少必填字段时填充默认值
    3. 类型转换（如 str -> int）

    Args:
        agent_name: Agent 名称
        data: Agent 返回的数据 dict

    Returns:
        (修复后的数据, 是否修复成功, 修复日志列表)
    """
    if not isinstance(data, dict):
        return data, False, ["数据不是 dict，无法修复"]

    fixed = copy.deepcopy(data)
    fix_log: list[str] = []

    # 获取该 Agent 的别名映射和默认值
    aliases = _FIELD_ALIASES.get(agent_name, {})
    defaults = _DEFAULT_VALUES.get(agent_name, {})

    # 步骤 1: 字段名别名映射
    for alias, standard_name in aliases.items():
        if alias in fixed and standard_name not in fixed:
            fixed[standard_name] = fixed.pop(alias)
            fix_log.append(f"字段名修复: '{alias}' -> '{standard_name}'")

    # 步骤 2: 缺少必填字段时填充默认值
    schema = AGENT_SCHEMAS.get(agent_name, {})
    for field_name, (expected_type, required, _) in schema.items():
        if field_name not in fixed and required and field_name in defaults:
            fixed[field_name] = defaults[field_name]
            fix_log.append(f"填充默认值: '{field_name}' = {defaults[field_name]!r}")

    # 步骤 3: 类型转换
    for field_name, (expected_type, _, _) in schema.items():
        if field_name in fixed:
            value = fixed[field_name]
            if not isinstance(value, expected_type):
                converted = _try_convert_type(value, expected_type)
                if converted is not None:
                    fixed[field_name] = converted
                    fix_log.append(
                        f"类型转换: '{field_name}' "
                        f"{type(value).__name__} -> {type(converted).__name__}"
                    )

    # 步骤 4: WriterAgent 特殊修复 - 从 text 重新计算 word_count
    if agent_name == "WriterAgent":
        text = fixed.get("text", "")
        word_count = fixed.get("word_count", 0)
        if text and (not isinstance(word_count, (int, float)) or int(word_count) <= 0):
            fixed["word_count"] = len(text)
            fix_log.append(f"重新计算 word_count: {len(text)}")

    # 步骤 5: ReviewAgent 特殊修复 - 从 tests 重新计算 total_score
    if agent_name == "ReviewAgent":
        total_score = fixed.get("total_score", 0)
        tests = fixed.get("tests", [])
        if not isinstance(total_score, (int, float)) or int(total_score) <= 0:
            if tests and all(isinstance(t.get("score"), (int, float)) for t in tests):
                fixed["total_score"] = int(
                    sum(t["score"] for t in tests) / len(tests)
                )
                fix_log.append(f"从 tests 重新计算 total_score: {fixed['total_score']}")

    success = len(fix_log) > 0
    if success:
        logger.info(
            "[Schema] Agent '%s' 自动修复: %s",
            agent_name,
            "; ".join(fix_log),
        )

    return fixed, success, fix_log


def _try_convert_type(value: Any, expected_type: type | tuple[type, ...]) -> Any:
    """尝试将值转换为目标类型。

    Args:
        value: 原始值
        expected_type: 目标类型

    Returns:
        转换后的值，无法转换时返回 None
    """
    if isinstance(expected_type, tuple):
        # 多种类型，逐一尝试
        for t in expected_type:
            result = _try_convert_type(value, t)
            if result is not None:
                return result
        return None

    try:
        if expected_type is int and isinstance(value, (int, float)):
            return int(value)
        if expected_type is float and isinstance(value, (int, float, str)):
            return float(value)
        if expected_type is str:
            return str(value)
        if expected_type is list and isinstance(value, (list, tuple)):
            return list(value)
        if expected_type is dict and isinstance(value, dict):
            return dict(value)
    except (ValueError, TypeError):
        pass

    return None
