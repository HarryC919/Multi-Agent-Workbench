import os
import sys
from pathlib import Path

# Ensure the backend directory is on sys.path so `app` can be imported
backend_dir = Path(__file__).parent.parent.resolve()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest_asyncio

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_workbench.db")

from app.database import engine, Base, AsyncSessionLocal
from app.seed import seed_models


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Mirror the production migration in main.py: add api_key column to
        # pre-existing test DBs (create_all won't alter existing tables).
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE model_configs ADD COLUMN api_key VARCHAR(500)"
            )
        except Exception:
            pass

        # Mirror the production migration in main.py: add thinking column to
        # pre-existing messages tables (chain-of-thought persistence).
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE messages ADD COLUMN thinking TEXT DEFAULT ''"
            )
        except Exception:
            pass

        # Mirror the production migration in main.py: drop the effort column
        # (思考强度 feature removed).
        try:
            await conn.exec_driver_sql("ALTER TABLE messages DROP COLUMN effort")
        except Exception:
            pass

        # AgentService phase 2a: add metadata column for agent step / tool
        # call transcript persistence.
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE messages ADD COLUMN metadata TEXT DEFAULT '{}'"
            )
        except Exception:
            pass

        # AgentService phase 2b-i: KnowledgeDoc.kb_id renamed to
        # knowledge_base_id. Mirror the production migration so an old
        # test_workbench.db aligns with the current ORM model.
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE knowledge_docs RENAME COLUMN kb_id TO knowledge_base_id"
            )
        except Exception:
            pass

    async with AsyncSessionLocal() as session:
        await seed_models(session)

    yield
    await engine.dispose()
