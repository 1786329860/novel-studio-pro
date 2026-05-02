from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from typing import Any

from app.core.config import config
from app.core.utils import now_iso


def default_settings() -> dict[str, Any]:
    return {
        "generation": {
            "mockMode": True,
            "generationMode": "standard",
            "qualityThreshold": 85,
            "autoRewriteTimes": 2,
            "chapterMinWords": 3000,
            "chapterMaxWords": 6000,
            "maxInputTokens": config.max_input_tokens,
            "maxOutputTokens": config.max_output_tokens,
            "requestTimeoutSeconds": config.request_timeout_seconds,
            "retryTimes": config.retry_times,
            "agents": {
                "memoryRetrieval": True,
                "constraintBuilder": True,
                "chapterDirector": True,
                "characterDirector": True,
                "foreshadowManager": True,
                "writer": True,
                "reviewer": True,
                "stateUpdater": True,
            },
        },
        "modelRoutes": {
            "outlineExpansion": {
                "model": config.deepseek_main_model,
                "temperature": 0.75,
                "maxOutputTokens": 12000,
                "fallbackModel": config.deepseek_fast_model,
            },
            "chapterDirector": {
                "model": config.deepseek_fast_model,
                "temperature": 0.45,
                "maxOutputTokens": 6000,
                "fallbackModel": config.deepseek_main_model,
            },
            "chapterWriting": {
                "model": config.deepseek_main_model,
                "temperature": 0.9,
                "maxOutputTokens": 12000,
                "fallbackModel": config.deepseek_fast_model,
            },
            "continuityReview": {
                "model": config.deepseek_fast_model,
                "temperature": 0.2,
                "maxOutputTokens": 5000,
                "fallbackModel": config.deepseek_main_model,
            },
            "stateExtraction": {
                "model": config.deepseek_fast_model,
                "temperature": 0.1,
                "maxOutputTokens": 5000,
                "fallbackModel": config.deepseek_main_model,
            },
        },
        "deepseek": {
            "enabled": config.use_deepseek,
            "baseUrl": config.deepseek_base_url,
            "apiKey": config.deepseek_api_key,
            "mainModel": config.deepseek_main_model,
            "fastModel": config.deepseek_fast_model,
            "requestTimeoutSeconds": config.request_timeout_seconds,
            "retryTimes": config.retry_times,
            "stream": False,
            "jsonMode": True,
        },
        "updatedAt": now_iso(),
    }


def empty_database() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "projects": {},
        "settings": default_settings(),
        "requestLogs": [],
    }


class JsonStore:
    """个人本地软件优先简单稳定，第一版使用 JSON 文件持久化。

    后续如果项目变大，Trae 可以把本类替换成 SQLite / PostgreSQL，业务层不用大改。
    """

    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or (config.data_dir / "novel_studio_data.json")
        self.lock = threading.RLock()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.write(empty_database())

    def read(self) -> dict[str, Any]:
        with self.lock:
            try:
                with self.file_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                backup = self.file_path.with_suffix(".broken.json")
                shutil.copy2(self.file_path, backup)
                data = empty_database()
                self.write(data)
            data.setdefault("projects", {})
            data.setdefault("settings", default_settings())
            data.setdefault("requestLogs", [])
            return data

    def write(self, data: dict[str, Any]) -> None:
        with self.lock:
            data["updatedAt"] = now_iso()
            tmp_path = self.file_path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.file_path)

    def update(self, mutator) -> dict[str, Any]:
        with self.lock:
            data = self.read()
            result = mutator(data)
            self.write(data)
            return result


store = JsonStore()
