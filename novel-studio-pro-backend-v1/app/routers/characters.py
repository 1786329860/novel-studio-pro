from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import CharacterPatchRequest
from app.services.project_service import project_service

router = APIRouter(prefix="/api/projects/{project_id}/characters", tags=["characters"])


@router.get("")
def list_characters(project_id: str):
    project = project_service.get_project(project_id)
    return {"characters": project.get("characters", []), "relationships": project.get("relationships", [])}


@router.put("/{character_id}")
def update_character(project_id: str, character_id: str, payload: CharacterPatchRequest):
    return {"character": project_service.patch_character(project_id, character_id, payload.patch)}
