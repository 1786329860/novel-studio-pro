"""Agent 基类模块。

所有 Agent 的抽象基类，定义了统一的执行接口和通用能力：
- name / description: Agent 身份标识
- run(context): 执行入口，自动判断 Mock/真实 AI 模式
- run_stream(context): 流式执行入口，默认调用 run() 后一次性 yield
- build_messages(context): 子类实现，构建 Prompt
- parse_response(content): 子类实现，解析 AI 返回
- mock_run(context): 子类实现，Mock 模式下的逻辑

设计原则:
- 失败自动回退 Mock，不中断创作流程
- 所有 Agent 统一使用 deepseek_client 发送请求
- 子类只需实现 build_messages / parse_response / mock_run 三个方法
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from app.services.deepseek_client import deepseek_client
from app.services.settings_service import settings_service

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """所有 Agent 的基类。

    子类必须实现:
        - build_messages(context): 构建发送给 AI 的消息列表
        - parse_response(content): 解析 AI 返回的原始文本为结构化 dict
        - mock_run(context): Mock 模式下生成合理的模拟输出

    子类可选覆盖:
        - model_route_key: 对应 settings.modelRoutes 中的路由键名
        - default_temperature: 默认温度参数
        - default_max_tokens: 默认最大输出 token 数
    """

    def __init__(self) -> None:
        self._name: str = "BaseAgent"
        self._description: str = "Agent 基类"

    # ------------------------------------------------------------------
    # 子类可覆盖的属性
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Agent 名称，子类应覆盖。"""
        return self._name

    @property
    def description(self) -> str:
        """Agent 功能描述，子类应覆盖。"""
        return self._description

    @property
    def model_route_key(self) -> str:
        """对应 settings.modelRoutes 中的路由键名。

        子类可覆盖以指定不同的模型路由配置。
        """
        return "chapterWriting"

    @property
    def default_temperature(self) -> float:
        """默认温度参数，子类可覆盖。"""
        return 0.7

    @property
    def default_max_tokens(self) -> int:
        """默认最大输出 token 数，子类可覆盖。"""
        return 8000

    # ------------------------------------------------------------------
    # 核心执行流程
    # ------------------------------------------------------------------

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """执行 Agent 任务。

        流程:
        1. 检查是否为 Mock 模式或 DeepSeek 未就绪
        2. Mock 模式: 调用 mock_run
        3. 真实 AI 模式: 调用 _ai_run，失败自动回退 Mock

        Args:
            context: 上下文数据，包含项目状态、前序 Agent 输出等

        Returns:
            Agent 的结构化输出 dict
        """
        generation = settings_service.get_generation()
        is_mock = generation.get("mockMode", False) or not deepseek_client.is_ready()
        is_ready = deepseek_client.is_ready()

        logger.info(
            "[Agent] %s 执行判断: mockMode=%s, is_ready=%s, is_mock=%s",
            self.name, generation.get("mockMode"), is_ready, is_mock,
        )

        if is_mock or not is_ready:
            logger.info("[Mock] %s 使用 Mock 模式执行 (mockMode=%s, is_ready=%s)", self.name, generation.get("mockMode"), is_ready)
            try:
                return await self.mock_run(context)
            except Exception as exc:
                logger.error("[Mock] %s Mock 执行失败: %s", self.name, exc)
                return self._fallback_mock(context)

        # 真实 AI 模式
        try:
            result = await self._ai_run(context)
            logger.info("[AI] %s 执行成功", self.name)
            return result
        except Exception as exc:
            logger.warning(
                "[AI] %s AI 执行失败，自动回退 Mock: %s", self.name, exc
            )
            try:
                return await self.mock_run(context)
            except Exception:
                return self._fallback_mock(context)

    async def run_stream(self, context: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        """流式执行 Agent 任务。

        默认实现：调用 run() 后一次性 yield 完整结果。
        子类（如 WriterAgent）可覆盖实现真正的流式输出。

        Yields:
            dict，格式为 {"type": "progress", "text": "..."} 或 {"type": "result", "data": {...}}
        """
        result = await self.run(context)
        yield {"type": "result", "data": result}

    # ------------------------------------------------------------------
    # AI 调用
    # ------------------------------------------------------------------

    async def _ai_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """使用 DeepSeek AI 执行任务。

        构建 messages -> 发送请求 -> 解析响应 -> Schema 校验。
        校验失败时自动尝试修复，修复后仍失败则回退 Mock。
        """
        messages = self.build_messages(context)

        # 从 modelRoutes 读取路由配置
        routes = settings_service.get_all(safe=False).get("modelRoutes", {})
        route = routes.get(self.model_route_key, {})

        content = await deepseek_client.chat(
            messages=messages,
            model=route.get("model"),
            temperature=float(route.get("temperature", self.default_temperature)),
            max_tokens=int(route.get("maxOutputTokens", self.default_max_tokens)),
            json_mode=True,
            task_name=self.name,
        )

        result = self.parse_response(content)

        # Schema 校验
        from app.core.schema_validator import (
            validate_agent_output,
            try_fix_agent_output,
        )

        is_valid, errors = validate_agent_output(self.name, result)
        if is_valid:
            logger.info("[AI] %s 执行成功，Schema 校验通过", self.name)
            return result

        # 校验失败，尝试自动修复
        logger.warning(
            "[Schema] %s 输出校验失败，尝试自动修复: %s",
            self.name,
            "; ".join(errors),
        )
        fixed_result, fix_success, fix_log = try_fix_agent_output(self.name, result)

        if fix_success:
            # 修复后重新校验
            is_valid_after_fix, fix_errors = validate_agent_output(
                self.name, fixed_result
            )
            if is_valid_after_fix:
                logger.info(
                    "[Schema] %s 自动修复成功: %s",
                    self.name,
                    "; ".join(fix_log),
                )
                return fixed_result
            else:
                logger.warning(
                    "[Schema] %s 修复后仍不合法: %s，回退 Mock",
                    self.name,
                    "; ".join(fix_errors),
                )
        else:
            logger.warning(
                "[Schema] %s 无法自动修复，回退 Mock",
                self.name,
            )

        # 修复失败，回退 Mock
        try:
            return await self.mock_run(context)
        except Exception:
            return self._fallback_mock(context)

    # ------------------------------------------------------------------
    # 子类必须实现的抽象方法
    # ------------------------------------------------------------------

    @abstractmethod
    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建发送给 AI 的消息列表。

        Args:
            context: 上下文数据

        Returns:
            包含 system 和 user 消息的列表
        """
        ...

    @abstractmethod
    def parse_response(self, content: str) -> dict[str, Any]:
        """解析 AI 返回的原始文本为结构化 dict。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的结果 dict
        """
        ...

    @abstractmethod
    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式下生成合理的模拟输出。

        必须根据 context 中的实际项目状态动态生成，不能硬编码。

        Args:
            context: 上下文数据

        Returns:
            与真实 AI 输出格式一致的结构化 dict
        """
        ...

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _fallback_mock(self, context: dict[str, Any]) -> dict[str, Any]:
        """最终兜底 Mock，当 mock_run 也失败时使用。

        返回一个最基本的安全默认值，确保流程不中断。
        """
        logger.error("[Fallback] %s 使用兜底 Mock", self.name)
        return {"_mock": True, "_agent": self.name, "_fallback": True}

    def _safe_parse_json(self, content: str) -> dict[str, Any]:
        """安全解析 JSON 字符串，提取第一个 JSON 对象。

        Args:
            content: 可能包含非 JSON 内容的字符串

        Returns:
            解析后的 dict
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    pass
        return {"_raw": content, "_parse_error": True}

    def _get_project_value(self, context: dict[str, Any], key: str, default: Any = None) -> Any:
        """从 context 中安全获取项目属性。

        Args:
            context: 上下文数据
            key: 属性键名
            default: 默认值

        Returns:
            对应的值或默认值
        """
        project = context.get("project", {})
        return project.get(key, default)
