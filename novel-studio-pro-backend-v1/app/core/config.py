from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = _int(os.getenv("APP_PORT"), 8765)
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data")).resolve()

    # 部署配置
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    static_dir: str = os.getenv("STATIC_DIR", "../novel-studio-pro-frontend-v3")
    debug: bool = _bool(os.getenv("DEBUG"), False)

    use_deepseek: bool = _bool(os.getenv("USE_DEEPSEEK"), False)
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_main_model: str = os.getenv("DEEPSEEK_MAIN_MODEL", "deepseek-v4-flash")
    deepseek_plan_model: str = os.getenv("DEEPSEEK_PLAN_MODEL", "deepseek-v4-pro")
    deepseek_fast_model: str = os.getenv("DEEPSEEK_FAST_MODEL", "deepseek-v4-flash")

    request_timeout_seconds: int = _int(os.getenv("REQUEST_TIMEOUT_SECONDS"), 180)
    retry_times: int = _int(os.getenv("RETRY_TIMES"), 2)
    max_input_tokens: int = _int(os.getenv("MAX_INPUT_TOKENS"), 64000)
    max_output_tokens: int = _int(os.getenv("MAX_OUTPUT_TOKENS"), 12000)

    # SQLite 数据库配置
    use_sqlite: bool = _bool(os.getenv("USE_SQLITE"), True)
    database_url: str = os.getenv("DATABASE_URL", "data/novel_studio.db")


config = AppConfig()
config.data_dir.mkdir(parents=True, exist_ok=True)
