import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import engine, Base, AsyncSessionLocal
from app.logging_config import setup_logging
from app.models import Conversation, Message, UploadedFile, ModelConfig  # noqa: F401
from app.routers import chat, conversations, models, skills, upload
from app.seed import seed_models

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed default data
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration: add api_key column to existing model_configs
        # tables (create_all does not alter existing tables). SQLite supports
        # ADD COLUMN; the column may already exist on upgraded DBs, so ignore
        # the duplicate-column error.
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE model_configs ADD COLUMN api_key VARCHAR(500)"
            )
        except Exception:
            pass

        # Lightweight migration: add thinking column to existing messages
        # tables for persisting chain-of-thought / reasoning content. SQLite
        # supports ADD COLUMN; the column may already exist on upgraded DBs,
        # so ignore the duplicate-column error.
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE messages ADD COLUMN thinking TEXT DEFAULT ''"
            )
        except Exception:
            pass

    async with AsyncSessionLocal() as session:
        await seed_models(session)

    yield
    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(
    title="AI Chat Workbench",
    description="Multi-vendor AI chat workbench backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(skills.router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
