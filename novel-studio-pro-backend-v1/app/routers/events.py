from __future__ import annotations

from fastapi import APIRouter

from app.services.project_service import project_service

router = APIRouter(prefix="/api/projects/{project_id}/events", tags=["events"])


@router.get("")
def list_events(project_id: str):
    project = project_service.get_project(project_id)
    return {"events": project.get("events", [])}
