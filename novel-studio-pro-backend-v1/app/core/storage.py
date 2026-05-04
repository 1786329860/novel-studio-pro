from __future__ import annotations

import json
import logging
import shutil
import threading
from pathlib import Path
from typing import Any

from app.core.config import config
from app.core.utils import now_iso

logger = logging.getLogger(__name__)


def default_settings() -> dict[str, Any]:
    return {
        "generation": {
            "mockMode": False,
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


class SQLiteStore:
    """SQLite 存储后端。

    实现与 JsonStore 兼容的接口，供上层业务代码无感切换。
    """

    def __init__(self) -> None:
        from app.core.database import Database

        db_path = config.data_dir / config.database_url
        self._db = Database(db_path)
        self._json_store = JsonStore()  # 保留用于数据迁移
        self._migrated = False
        self.lock = threading.RLock()

    def _ensure_migration(self) -> None:
        """确保旧 JSON 数据已迁移到 SQLite。"""
        if self._migrated:
            return
        self._migrated = True

        json_file = config.data_dir / "novel_studio_data.json"
        if not json_file.exists():
            # 没有旧数据，写入默认设置
            self._db.save_settings(default_settings())
            return

        try:
            json_data = self._json_store.read()
            # 检查 SQLite 是否已有数据
            existing_projects = self._db.list_projects()
            if not existing_projects and not self._db.get_settings():
                # SQLite 为空，执行迁移
                self._db.migrate_from_json(json_data)
                logger.info("[SQLiteStore] 已从 JSON 文件迁移数据到 SQLite")
        except Exception as exc:
            logger.warning("[SQLiteStore] 数据迁移失败，继续使用 SQLite: %s", exc)

    def read(self) -> dict[str, Any]:
        """读取完整数据库，返回兼容 JsonStore 的 dict 格式。"""
        self._ensure_migration()

        projects = {}
        for project in self._db.list_projects():
            pid = project.get("id", "")
            if pid:
                projects[pid] = project

        settings = self._db.get_settings()
        if not settings:
            settings = default_settings()

        request_logs = self._db.get_request_logs(200)

        return {
            "version": "1.0.0",
            "projects": projects,
            "settings": settings,
            "requestLogs": request_logs,
            "updatedAt": now_iso(),
        }

    def write(self, data: dict[str, Any]) -> None:
        """写入完整数据库。"""
        self._ensure_migration()

        # 写入所有项目
        projects = data.get("projects", {})
        for project_id, project_data in projects.items():
            if isinstance(project_data, dict):
                self._db.save_project(project_id, project_data)

        # 写入设置
        settings = data.get("settings", {})
        if settings:
            self._db.save_settings(settings)

    def update(self, mutator) -> dict[str, Any]:
        """原子更新：读取 -> 执行 mutator -> 写入。"""
        with self.lock:
            data = self.read()
            result = mutator(data)
            self.write(data)
            return result


def migrate_from_json(json_path: str | Path) -> None:
    """从 JSON 文件导入数据到 SQLite。

    Args:
        json_path: JSON 文件路径
    """
    json_path = Path(json_path)
    if not json_path.exists():
        logger.warning("[migrate_from_json] JSON 文件不存在: %s", json_path)
        return

    from app.core.database import Database

    db_path = config.data_dir / config.database_url
    db = Database(db_path)

    with json_path.open("r", encoding="utf-8") as f:
        json_data = json.load(f)

    db.migrate_from_json(json_data)
    logger.info("[migrate_from_json] 迁移完成: %s -> %s", json_path, db_path)


# ------------------------------------------------------------------
# 全局单例：优先使用 SQLite，回退 JSON
# ------------------------------------------------------------------

def _create_store():
    """根据配置创建存储后端。"""
    if config.use_sqlite:
        try:
            return SQLiteStore()
        except Exception as exc:
            logger.warning("[Storage] SQLite 初始化失败，回退到 JSON: %s", exc)
    return JsonStore()


store = _create_store()

# ---------------------------------------------------------------------------
# 启动时同步 .env 配置到数据存储
# 确保 USE_DEEPSEEK / DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL 等 .env 值
# 能正确同步到 JSON/SQLite 存储中的 settings.deepseek 字段。
# 只在存储中的值为空/False 时才同步，不覆盖用户通过前端手动设置的值。
# ---------------------------------------------------------------------------
def _sync_env_to_store() -> None:
    """将 .env 中的 DeepSeek 配置同步到数据存储（仅在存储中缺失时）。"""
    if not config.use_deepseek or not config.deepseek_api_key:
        return

    try:
        data = store.read()
        ds = data.get("settings", {}).get("deepseek", {})

        needs_sync = False
        if not ds.get("enabled"):
            ds["enabled"] = True
            needs_sync = True
        if not ds.get("apiKey"):
            ds["apiKey"] = config.deepseek_api_key
            needs_sync = True
        if not ds.get("baseUrl") or ds.get("baseUrl") == "https://api.deepseek.com":
            if config.deepseek_base_url and config.deepseek_base_url != "https://api.deepseek.com":
                ds["baseUrl"] = config.deepseek_base_url
                needs_sync = True
        if not ds.get("mainModel"):
            ds["mainModel"] = config.deepseek_main_model
            needs_sync = True
        if not ds.get("fastModel"):
            ds["fastModel"] = config.deepseek_fast_model
            needs_sync = True

        if needs_sync:
            data.setdefault("settings", {})["deepseek"] = ds
            store.write(data)
            logger.info(
                "[Storage] 已从 .env 同步 DeepSeek 配置到存储: enabled=%s, hasApiKey=%s, baseUrl=%s",
                ds.get("enabled"), bool(ds.get("apiKey")), ds.get("baseUrl", "")[:60],
            )
    except Exception as exc:
        logger.warning("[Storage] .env 配置同步失败: %s", exc)


_sync_env_to_store()
