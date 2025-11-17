from pathlib import Path

import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.config import settings
from backend.logging_config import configure_logging

logger = logging.getLogger(__name__)

configure_logging()

app = FastAPI(title="Nova Reel Local Video Generator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

frontend_path = Path("frontend")
videos_path = Path(settings.output_local_dir)
frontend_path.mkdir(parents=True, exist_ok=True)
videos_path.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
app.mount("/videos", StaticFiles(directory=str(videos_path)), name="videos")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = frontend_path / "index.html"
    return FileResponse(index_file)
