from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import config
from app.routers import characters, events, foreshadows, memory, projects, settings

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
    allow_origin_regex=r".*",
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
    return {
        "ok": True,
        "host": config.app_host,
        "port": config.app_port,
        "dataDir": str(config.data_dir),
        "message": "后端运行正常。",
    }
