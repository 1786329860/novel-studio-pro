from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import CreateProjectRequest, GenerateChapterRequest
from app.services.project_service import project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects():
    return {"projects": project_service.list_projects()}


@router.post("")
def create_project(payload: CreateProjectRequest):
    return project_service.create_project(payload.model_dump())


@router.get("/{project_id}")
def get_project(project_id: str):
    return {"project": project_service.get_project(project_id)}


@router.post("/{project_id}/build")
async def build_project(project_id: str):
    return await project_service.build_project(project_id)


@router.post("/{project_id}/blueprint/regenerate")
async def regenerate_blueprint(project_id: str):
    return await project_service.regenerate_blueprint(project_id)


@router.post("/{project_id}/chapters/generate-next")
async def generate_next_chapter(project_id: str, payload: GenerateChapterRequest):
    return await project_service.generate_next_chapter(project_id, payload.model_dump())


@router.post("/{project_id}/chapters/{chapter_id}/confirm")
def confirm_chapter(project_id: str, chapter_id: str):
    return project_service.confirm_chapter(project_id, chapter_id)


@router.post("/{project_id}/state/analyze")
def analyze_state(project_id: str):
    return project_service.analyze_state(project_id)
