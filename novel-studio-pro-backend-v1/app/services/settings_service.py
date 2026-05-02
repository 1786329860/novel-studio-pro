from __future__ import annotations

from typing import Any

from app.core.storage import store, default_settings
from app.core.utils import deep_merge, mask_secret, now_iso


SENSITIVE_KEYS = {"apiKey"}


def _safe_settings(settings: dict[str, Any]) -> dict[str, Any]:
    safe = deep_merge({}, settings)
    deepseek = safe.get("deepseek", {})
    if "apiKey" in deepseek:
        deepseek["apiKeyMasked"] = mask_secret(deepseek.get("apiKey"))
        deepseek["hasApiKey"] = bool(deepseek.get("apiKey"))
        deepseek.pop("apiKey", None)
    return safe


class SettingsService:
    def get_all(self, safe: bool = True) -> dict[str, Any]:
        data = store.read()
        settings = data.get("settings") or default_settings()
        return _safe_settings(settings) if safe else settings

    def get_generation(self) -> dict[str, Any]:
        return self.get_all().get("generation", {})

    def update_generation(self, patch: dict[str, Any]) -> dict[str, Any]:
        def mut(data: dict[str, Any]) -> dict[str, Any]:
            settings = data.setdefault("settings", default_settings())
            settings["generation"] = deep_merge(settings.get("generation", {}), patch)
            settings["updatedAt"] = now_iso()
            return _safe_settings(settings["generation"])
        return store.update(mut)

    def get_model_routes(self) -> dict[str, Any]:
        return self.get_all().get("modelRoutes", {})

    def update_model_routes(self, patch: dict[str, Any]) -> dict[str, Any]:
        def mut(data: dict[str, Any]) -> dict[str, Any]:
            settings = data.setdefault("settings", default_settings())
            settings["modelRoutes"] = deep_merge(settings.get("modelRoutes", {}), patch)
            settings["updatedAt"] = now_iso()
            return settings["modelRoutes"]
        return store.update(mut)

    def get_deepseek(self, safe: bool = True) -> dict[str, Any]:
        settings = self.get_all(safe=safe)
        return settings.get("deepseek", {})

    def update_deepseek(self, patch: dict[str, Any]) -> dict[str, Any]:
        # 如果前端传 apiKeyMasked 或空 apiKey，不覆盖已有真实 key。
        patch = dict(patch)
        patch.pop("apiKeyMasked", None)
        patch.pop("hasApiKey", None)
        if patch.get("apiKey") in {None, "", "********", "****"}:
            patch.pop("apiKey", None)

        def mut(data: dict[str, Any]) -> dict[str, Any]:
            settings = data.setdefault("settings", default_settings())
            settings["deepseek"] = deep_merge(settings.get("deepseek", {}), patch)
            settings["updatedAt"] = now_iso()
            return _safe_settings(settings["deepseek"])
        return store.update(mut)

    def append_request_log(self, item: dict[str, Any]) -> None:
        def mut(data: dict[str, Any]) -> dict[str, Any]:
            logs = data.setdefault("requestLogs", [])
            logs.append({"time": now_iso(), **item})
            if len(logs) > 200:
                del logs[:-200]
            return {}
        store.update(mut)

    def get_request_logs(self) -> list[dict[str, Any]]:
        return store.read().get("requestLogs", [])[-100:]


settings_service = SettingsService()
