from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from app.services.settings_service import settings_service


class DeepSeekClient:
    """DeepSeek API 适配层。

    当前后端默认不启用 DeepSeek。启用条件：
    1. 设置 deepseek.enabled = true；
    2. 填写 apiKey；
    3. 在生成设置里关闭 mockMode。

    这层只负责请求、超时、重试、日志，不负责小说业务逻辑。
    """

    def __init__(self) -> None:
        pass

    def is_ready(self) -> bool:
        settings = settings_service.get_deepseek(safe=False)
        return bool(settings.get("enabled") and settings.get("apiKey"))

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        json_mode: bool = False,
        task_name: str = "unknown",
    ) -> str:
        settings = settings_service.get_deepseek(safe=False)
        if not settings.get("enabled"):
            raise RuntimeError("DeepSeek 未启用，当前应使用 Mock 生成。")
        api_key = settings.get("apiKey")
        if not api_key:
            raise RuntimeError("DeepSeek API Key 未配置。")

        base_url = str(settings.get("baseUrl") or "https://api.deepseek.com").rstrip("/")
        url = f"{base_url}/chat/completions"
        model_name = model or settings.get("mainModel") or "deepseek-chat"
        retry_times = int(settings.get("retryTimes") or 2)
        timeout_seconds = int(settings.get("requestTimeoutSeconds") or 180)

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        started = time.perf_counter()
        for attempt in range(retry_times + 1):
            try:
                timeout = httpx.Timeout(connect=15.0, read=timeout_seconds, write=30.0, pool=15.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 429 or response.status_code >= 500:
                    raise RuntimeError(f"DeepSeek 临时错误 HTTP {response.status_code}: {response.text[:300]}")
                if response.status_code >= 400:
                    raise RuntimeError(f"DeepSeek 请求失败 HTTP {response.status_code}: {response.text[:500]}")

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                settings_service.append_request_log({
                    "task": task_name,
                    "model": model_name,
                    "temperature": temperature,
                    "maxTokens": max_tokens,
                    "elapsedMs": elapsed_ms,
                    "status": "ok",
                    "attempt": attempt + 1,
                })
                return content
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retry_times:
                    await asyncio.sleep(1.2 + attempt * 1.8)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        settings_service.append_request_log({
            "task": task_name,
            "model": model_name,
            "temperature": temperature,
            "maxTokens": max_tokens,
            "elapsedMs": elapsed_ms,
            "status": "error",
            "error": str(last_error),
        })
        raise last_error or RuntimeError("DeepSeek 请求失败。")

    async def chat_json(self, **kwargs: Any) -> dict[str, Any]:
        content = await self.chat(json_mode=True, **kwargs)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 简单兜底：提取第一个 JSON 对象。
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                return json.loads(content[start : end + 1])
            raise


deepseek_client = DeepSeekClient()
