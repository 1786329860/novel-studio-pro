from __future__ import annotations

import logging
import sys
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import config
from app.routers import characters, events, foreshadows, memory, projects, settings

# ---------------------------------------------------------------------------
# 日志配置：确保所有 INFO 级别日志输出到 stdout
# nohup 模式下只有 stdout/stderr 被捕获到日志文件
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Novel Studio Pro Backend",
    description="Novel Studio Pro 后端服务。Electron 桌面客户端通过此 API 进行数据交互。",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS 配置
# Electron 桌面应用的 origin 为 "file://" 或 "null"，
# 部署到服务器后需要允许任意来源（因为用户从本地 EXE 连接远程服务器）。
# ---------------------------------------------------------------------------
_origins_raw: str = config.cors_origins
if _origins_raw.strip() == "*":
    allow_origins_list: list[str] = ["*"]
else:
    allow_origins_list = [o.strip() for o in _origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API 路由
# ---------------------------------------------------------------------------
app.include_router(projects.router)
app.include_router(characters.router)
app.include_router(foreshadows.router)
app.include_router(memory.router)
app.include_router(events.router)
app.include_router(settings.router)


@app.get("/")
def root():
    return {
        "name": "Novel Studio Pro Backend",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health():
    result: dict[str, Any] = {
        "ok": True,
        "host": config.app_host,
        "port": config.app_port,
        "message": "后端运行正常。",
    }
    if config.debug:
        result["dataDir"] = str(config.data_dir)
    return result


@app.on_event("startup")
async def startup_diagnostic():
    """启动时输出关键配置诊断信息，便于排查 Mock 模式问题。"""
    from app.services.settings_service import settings_service
    from app.services.deepseek_client import deepseek_client

    ds = settings_service.get_deepseek(safe=False)
    gen = settings_service.get_generation()
    logger.info("=" * 60)
    logger.info("[启动诊断] Novel Studio Pro 后端启动")
    logger.info("[启动诊断] DATA_DIR = %s", config.data_dir)
    logger.info("[启动诊断] USE_DEEPSEEK(env) = %s", config.use_deepseek)
    logger.info("[启动诊断] DEEPSEEK_API_KEY(env) = %s", "***" if config.deepseek_api_key else "(空)")
    logger.info("[启动诊断] DEEPSEEK_BASE_URL(env) = %s", config.deepseek_base_url)
    logger.info("[启动诊断] deepseek.enabled(存储) = %s", ds.get("enabled"))
    logger.info("[启动诊断] deepseek.apiKey(存储) = %s", "***" if ds.get("apiKey") else "(空)")
    logger.info("[启动诊断] deepseek.baseUrl(存储) = %s", ds.get("baseUrl"))
    logger.info("[启动诊断] generation.mockMode = %s", gen.get("mockMode"))
    logger.info("[启动诊断] deepseek_client.is_ready() = %s", deepseek_client.is_ready())
    logger.info("=" * 60)
