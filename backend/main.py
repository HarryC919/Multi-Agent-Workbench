import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import engine, Base, AsyncSessionLocal
from app.logging_config import setup_logging
from app.models import Conversation, Message, UploadedFile, ModelConfig, KnowledgeBase, KnowledgeDoc  # noqa: F401
from app.routers import agent, chat, conversations, knowledge, models, skills, upload
from app.seed import seed_models

_BACKEND_ROOT = Path(__file__).resolve().parent

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

        # Lightweight migration: drop the effort column from messages. The
        # effort (思考强度) feature was removed — models should use their own
        # default temperature/top_p. SQLite >= 3.35 supports DROP COLUMN;
        # ignore the no-such-column error on already-migrated DBs.
        try:
            await conn.exec_driver_sql("ALTER TABLE messages DROP COLUMN effort")
        except Exception:
            pass

        # Lightweight migration: add metadata column to existing messages
        # tables (AgentService phase 2a stores step_count / aborted flag /
        # tool_calls transcript here). SQLite supports ADD COLUMN; the column
        # may already exist on upgraded DBs, so ignore the duplicate error.
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE messages ADD COLUMN metadata TEXT DEFAULT '{}'"
            )
        except Exception:
            pass

        # Lightweight migration: AgentService 2b-i renamed KnowledgeDoc.kb_id →
        # knowledge_base_id. create_all won't alter existing tables, so an old
        # workbench.db still has the kb_id column and inserts using the new name
        # fail with "no column named knowledge_base_id". Rename in place when the
        # legacy column is present (SQLite >= 3.25 supports RENAME COLUMN; the
        # no-such-column error is ignored on already-migrated DBs).
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE knowledge_docs RENAME COLUMN kb_id TO knowledge_base_id"
            )
        except Exception:
            pass

    async with AsyncSessionLocal() as session:
        await seed_models(session)

    # Phase 3: discover markdown-defined skills (.md files in skills_md/).
    from app.config import settings
    from app.skills import discover_markdown_skills
    skills_dir = _BACKEND_ROOT / settings.skills_md_dir
    skills_dir.mkdir(exist_ok=True)
    discover_markdown_skills(skills_dir)

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
app.include_router(agent.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")


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
