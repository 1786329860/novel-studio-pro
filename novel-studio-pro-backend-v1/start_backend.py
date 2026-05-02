import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("APP_HOST", "127.0.0.1")
port = int(os.getenv("APP_PORT", "8765"))
debug = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
workers = int(os.getenv("WORKERS", "1"))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=host, port=port, reload=debug, workers=workers)
