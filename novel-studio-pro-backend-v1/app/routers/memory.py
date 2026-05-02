from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import MemoryRebuildRequest
from app.services.project_service import project_service

router = APIRouter(prefix="/api/projects/{project_id}/memory", tags=["memory"])


@router.get("")
def get_memory(project_id: str):
    project = project_service.get_project(project_id)
    return {"memory": project.get("memory", {})}


@router.post("/rebuild")
def rebuild_memory(project_id: str, payload: MemoryRebuildRequest):
    return project_service.rebuild_memory(project_id, payload.mode)
