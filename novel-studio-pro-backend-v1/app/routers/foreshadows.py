from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import ForeshadowPatchRequest
from app.services.project_service import project_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["foreshadows-and-truth"])


@router.get("/foreshadows")
def list_foreshadows(project_id: str):
    project = project_service.get_project(project_id)
    return {"foreshadows": project.get("foreshadows", []), "truthSource": project.get("truthSource", {})}


@router.put("/foreshadows/{foreshadow_id}")
def update_foreshadow(project_id: str, foreshadow_id: str, payload: ForeshadowPatchRequest):
    return {"foreshadow": project_service.patch_foreshadow(project_id, foreshadow_id, payload.patch)}


@router.get("/truth-source")
def get_truth_source(project_id: str):
    project = project_service.get_project(project_id)
    return {"truthSource": project.get("truthSource", {})}
