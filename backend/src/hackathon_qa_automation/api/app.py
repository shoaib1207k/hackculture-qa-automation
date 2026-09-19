"""FastAPI app.

    uv run uvicorn hackathon_qa_automation.api.app:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..common.logging_config import setup_logging
from .routes import router

# Origins the demo frontend may call from (comma-separated to override).
DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:5173"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="QA Automation", lifespan=lifespan,
                  description="Score a sale against its retailer's checklist before it ships.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("CORS_ORIGINS", DEFAULT_ORIGINS).split(","),
        allow_methods=["GET", "POST"], allow_headers=["*"])
    app.include_router(router)
    return app


app = create_app()
