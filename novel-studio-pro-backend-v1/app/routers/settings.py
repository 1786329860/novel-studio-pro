from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import DeepSeekSettingsRequest, SettingsPatch, TestDeepSeekRequest
from app.services.deepseek_client import deepseek_client
from app.services.settings_service import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_all_settings():
    return {"settings": settings_service.get_all(safe=True)}


@router.get("/generation")
def get_generation_settings():
    return {"generation": settings_service.get_generation()}


@router.put("/generation")
def update_generation_settings(payload: SettingsPatch):
    return {"generation": settings_service.update_generation(payload.data)}


@router.get("/model-routes")
def get_model_routes():
    return {"modelRoutes": settings_service.get_model_routes()}


@router.put("/model-routes")
def update_model_routes(payload: SettingsPatch):
    return {"modelRoutes": settings_service.update_model_routes(payload.data)}


@router.get("/deepseek")
def get_deepseek_settings():
    return {"deepseek": settings_service.get_deepseek(safe=True)}


@router.put("/deepseek")
def update_deepseek_settings(payload: DeepSeekSettingsRequest):
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    return {"deepseek": settings_service.update_deepseek(patch)}


@router.post("/deepseek/test")
async def test_deepseek(payload: TestDeepSeekRequest):
    if not deepseek_client.is_ready():
        return {
            "ok": False,
            "message": "DeepSeek 未启用或 API Key 未配置。当前后端仍可使用 Mock 模式。",
        }
    try:
        result = await deepseek_client.chat(
            messages=[
                {"role": "system", "content": "你是连接测试助手。请简短回答。"},
                {"role": "user", "content": payload.prompt},
            ],
            max_tokens=200,
            temperature=0.1,
            json_mode=False,
            task_name="deepseekTest",
        )
        return {"ok": True, "message": "DeepSeek 连接成功。", "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": str(exc)}


@router.get("/request-logs")
def get_request_logs():
    return {"logs": settings_service.get_request_logs()}
