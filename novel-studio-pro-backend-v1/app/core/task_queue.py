"""内存任务队列模块。

简单的内存任务队列，支持异步任务管理。
重启后清空，可接受。

功能:
- 提交任务，返回 task_id
- 查询任务状态和进度
- 取消任务
- 列出所有任务
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class Task:
    """任务对象。

    Attributes:
        id: 任务唯一标识
        type: 任务类型（如 "generate_chapter"）
        status: 任务状态 (pending/running/done/failed/cancelled)
        progress: 进度百分比 (0-100)
        current_step: 当前步骤描述
        result: 任务结果
        error: 错误信息
        created_at: 创建时间 (ISO 格式)
        started_at: 开始执行时间 (ISO 格式)
        finished_at: 完成时间 (ISO 格式)
        params: 任务参数
        _cancel_event: 取消事件
    """

    def __init__(
        self,
        task_type: str,
        params: dict[str, Any],
    ) -> None:
        self.id: str = f"task_{uuid.uuid4().hex[:12]}"
        self.type: str = task_type
        self.status: str = "pending"
        self.progress: float = 0.0
        self.current_step: str = "等待执行"
        self.result: Any = None
        self.error: str = ""
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.started_at: str = ""
        self.finished_at: str = ""
        self.params: dict[str, Any] = params
        self._cancel_event: asyncio.Event = asyncio.Event()

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的 dict。

        Returns:
            任务信息的 dict 表示
        """
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "progress": self.progress,
            "current_step": self.current_step,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    def is_cancelled(self) -> bool:
        """检查任务是否已被取消。

        Returns:
            True 表示已取消
        """
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """标记任务为已取消。"""
        self._cancel_event.set()


class TaskQueue:
    """内存任务队列。

    支持异步任务提交、状态查询、取消和列表。
    使用内存存储，重启后清空。
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def submit(
        self,
        task_type: str,
        params: dict[str, Any],
        executor: Callable[[Task], Coroutine[Any, Any, Any]] | None = None,
    ) -> str:
        """提交任务。

        Args:
            task_type: 任务类型
            params: 任务参数
            executor: 可选的异步执行函数，接收 Task 对象

        Returns:
            task_id
        """
        task = Task(task_type, params)

        async with self._lock:
            self._tasks[task.id] = task

        # 如果提供了执行函数，在后台启动
        if executor:
            asyncio.create_task(self._run_task(task, executor))

        logger.info(
            "[TaskQueue] 任务已提交: id=%s, type=%s", task.id, task_type
        )
        return task.id

    async def _run_task(
        self,
        task: Task,
        executor: Callable[[Task], Coroutine[Any, Any, Any]],
    ) -> None:
        """在后台执行任务。

        Args:
            task: 任务对象
            executor: 异步执行函数
        """
        task.status = "running"
        task.started_at = datetime.now(timezone.utc).isoformat()

        try:
            result = await executor(task)
            if task.is_cancelled():
                task.status = "cancelled"
                task.finished_at = datetime.now(timezone.utc).isoformat()
                logger.info("[TaskQueue] 任务已取消: id=%s", task.id)
            else:
                task.status = "done"
                task.result = result
                task.progress = 100.0
                task.current_step = "完成"
                task.finished_at = datetime.now(timezone.utc).isoformat()
                logger.info("[TaskQueue] 任务完成: id=%s", task.id)
        except asyncio.CancelledError:
            task.status = "cancelled"
            task.finished_at = datetime.now(timezone.utc).isoformat()
            logger.info("[TaskQueue] 任务被中断: id=%s", task.id)
        except Exception as exc:
            if task.is_cancelled():
                task.status = "cancelled"
            else:
                task.status = "failed"
                task.error = str(exc)
            task.finished_at = datetime.now(timezone.utc).isoformat()
            logger.error(
                "[TaskQueue] 任务失败: id=%s, error=%s", task.id, exc
            )

    async def get_status(self, task_id: str) -> dict[str, Any] | None:
        """获取任务状态。

        Args:
            task_id: 任务 ID

        Returns:
            任务状态 dict，不存在返回 None
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                return task.to_dict()
        return None

    async def cancel(self, task_id: str) -> bool:
        """取消任务。

        Args:
            task_id: 任务 ID

        Returns:
            True 表示取消成功，False 表示任务不存在或已完成
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if task.status in ("done", "failed", "cancelled"):
                return False

            task.cancel()

            if task.status == "pending":
                task.status = "cancelled"
                task.finished_at = datetime.now(timezone.utc).isoformat()
                logger.info("[TaskQueue] 已取消待执行任务: id=%s", task_id)
                return True

            # running 状态的任务，标记取消，由 executor 检查
            logger.info("[TaskQueue] 已标记运行中任务为取消: id=%s", task_id)
            return True

    async def list_tasks(self) -> list[dict[str, Any]]:
        """列出所有任务。

        Returns:
            所有任务的信息列表，按创建时间倒序
        """
        async with self._lock:
            tasks = [task.to_dict() for task in self._tasks.values()]

        # 按创建时间倒序
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return tasks

    async def update_progress(
        self,
        task_id: str,
        progress: float,
        step: str = "",
    ) -> None:
        """更新任务进度。

        Args:
            task_id: 任务 ID
            progress: 进度百分比 (0-100)
            step: 当前步骤描述
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == "running":
                task.progress = min(100.0, max(0.0, progress))
                if step:
                    task.current_step = step


# 全局单例
task_queue = TaskQueue()
