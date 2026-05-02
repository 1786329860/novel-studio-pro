"""
Novel Studio Pro - 生产环境启动脚本

用法:
    python start_production.py
    python start_production.py --port 8765 --workers 4
"""

import os
import argparse
import multiprocessing
import uvicorn
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Novel Studio Pro 生产环境启动")
    parser.add_argument("--host", default=os.getenv("APP_HOST", "0.0.0.0"), help="监听地址")
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "8765")), help="监听端口")
    parser.add_argument("--workers", type=int, default=None, help="Worker 进程数（默认为 CPU 核心数，最少 2）")
    args = parser.parse_args()

    # Worker 数量：默认为 CPU 核心数，最少 2
    if args.workers is not None:
        workers = max(1, args.workers)
    else:
        workers = max(2, multiprocessing.cpu_count())

    print(f"启动 Novel Studio Pro 后端 (生产模式)")
    print(f"  地址: {args.host}:{args.port}")
    print(f"  Workers: {workers}")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        workers=workers,
        reload=False,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
