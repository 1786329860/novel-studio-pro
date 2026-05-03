"""SQLite 数据库管理模块。

使用 Python 标准库 sqlite3 实现，不引入新依赖。
- WAL 模式支持并发读写
- 线程安全（每个线程独立连接）
- 自动建表与数据迁移
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 线程本地存储，确保每个线程使用独立连接
_thread_local = threading.local()


class Database:
    """SQLite 数据库管理器。

    提供项目、设置、请求日志的 CRUD 操作。
    每个线程维护独立连接，保证线程安全。
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接。"""
        conn: sqlite3.Connection | None = getattr(_thread_local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            _thread_local.conn = conn
        return conn

    def _init_tables(self) -> None:
        """初始化数据库表结构。"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        logger.info("[Database] 数据库初始化完成: %s", self.db_path)

    # ------------------------------------------------------------------
    # 项目 CRUD
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """获取单个项目数据。"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT data FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row:
            return json.loads(row["data"])
        return None

    def save_project(self, project_id: str, data: dict[str, Any]) -> None:
        """保存项目数据（完整 JSON 覆盖）。"""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO projects (id, data, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
            (project_id, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()

    def list_projects(self) -> list[dict[str, Any]]:
        """列出所有项目。"""
        conn = self._get_conn()
        rows = conn.execute("SELECT data FROM projects ORDER BY updated_at DESC").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def delete_project(self, project_id: str) -> bool:
        """删除项目，返回是否成功。"""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # 设置 CRUD
    # ------------------------------------------------------------------

    def get_settings(self) -> dict[str, Any]:
        """获取所有设置（合并为 dict）。"""
        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        result: dict[str, Any] = {}
        for row in rows:
            result[row["key"]] = json.loads(row["value"])
        return result

    def save_settings(self, data: dict[str, Any]) -> None:
        """保存设置（完整覆盖）。"""
        conn = self._get_conn()
        # 先清空旧设置
        conn.execute("DELETE FROM settings")
        # 写入新设置
        for key, value in data.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        conn.commit()

    # ------------------------------------------------------------------
    # 请求日志 CRUD
    # ------------------------------------------------------------------

    def append_request_log(self, log_entry: dict[str, Any]) -> None:
        """追加一条请求日志。"""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO request_logs (data) VALUES (?)",
            (json.dumps(log_entry, ensure_ascii=False),),
        )
        conn.commit()

    def get_request_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最近的请求日志。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT data FROM request_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        # 倒序查询，返回时反转回正序
        return [json.loads(row["data"]) for row in reversed(rows)]

    # ------------------------------------------------------------------
    # 数据迁移
    # ------------------------------------------------------------------

    def migrate_from_json(self, json_data: dict[str, Any]) -> None:
        """从 JSON 数据迁移到 SQLite。

        Args:
            json_data: 原始 JSON 数据，包含 projects, settings, requestLogs
        """
        conn = self._get_conn()

        # 迁移项目
        projects = json_data.get("projects", {})
        for project_id, project_data in projects.items():
            if isinstance(project_data, dict):
                conn.execute(
                    """INSERT OR REPLACE INTO projects (id, data, created_at, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (
                        project_id,
                        json.dumps(project_data, ensure_ascii=False),
                        project_data.get("createdAt", ""),
                        project_data.get("updatedAt", ""),
                    ),
                )

        # 迁移设置
        settings = json_data.get("settings", {})
        if settings:
            conn.execute("DELETE FROM settings")
            for key, value in settings.items():
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, json.dumps(value, ensure_ascii=False)),
                )

        # 迁移请求日志
        logs = json_data.get("requestLogs", [])
        for log_entry in logs:
            if isinstance(log_entry, dict):
                conn.execute(
                    "INSERT INTO request_logs (data, created_at) VALUES (?, ?)",
                    (
                        json.dumps(log_entry, ensure_ascii=False),
                        log_entry.get("time", ""),
                    ),
                )

        conn.commit()
        logger.info(
            "[Database] 数据迁移完成: %d 个项目, %d 条设置, %d 条日志",
            len(projects),
            len(settings),
            len(logs),
        )
