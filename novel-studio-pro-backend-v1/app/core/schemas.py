from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    outline: str = Field(default="", max_length=50000)
    genre: str = Field(default="奇幻")
    lengthType: str = Field(default="long")
    mode: str = Field(default="balanced")


class GenerateChapterRequest(BaseModel):
    mode: str = "standard"
    qualityThreshold: int = 85
    maxInputTokens: int = 64000
    maxOutputTokens: int = 12000
    userInstruction: str = ""


class StateAnalyzeResponse(BaseModel):
    report: dict[str, Any]


class SettingsPatch(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class DeepSeekSettingsRequest(BaseModel):
    enabled: bool | None = None
    baseUrl: str | None = None
    apiKey: str | None = None
    mainModel: str | None = None
    fastModel: str | None = None
    requestTimeoutSeconds: int | None = None
    retryTimes: int | None = None
    stream: bool | None = None
    jsonMode: bool | None = None


class TestDeepSeekRequest(BaseModel):
    prompt: str = "请只返回 JSON：{\"ok\": true, \"message\": \"连接成功\"}"


class CharacterPatchRequest(BaseModel):
    patch: dict[str, Any]


class ForeshadowPatchRequest(BaseModel):
    patch: dict[str, Any]


class MemoryRebuildRequest(BaseModel):
    mode: Literal["light", "standard", "strict"] = "standard"
