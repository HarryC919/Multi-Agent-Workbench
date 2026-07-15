import pytest

from app.database import AsyncSessionLocal
from app.models import Conversation, Message
from app.services.conversation_service import ConversationService


@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session
        # Rollback any changes after test
        await session.rollback()


@pytest.fixture
async def service(db):
    return ConversationService(db)


async def test_create_conversation(service):
    conv = await service.create_conversation()
    assert conv.title == "新会话"
    assert conv.id is not None


async def test_create_conversation_with_title(service):
    conv = await service.create_conversation(title="Custom Title")
    assert conv.title == "Custom Title"


async def test_list_and_search_conversations(service):
    await service.create_conversation(title="Python project")
    await service.create_conversation(title="JavaScript notes")

    all_convs = await service.list_conversations()
    assert len(all_convs) >= 2

    filtered = await service.list_conversations(search_query="Python")
    assert len(filtered) >= 1
    assert all("Python" in c.title for c in filtered)


async def test_rename_conversation(service):
    conv = await service.create_conversation()
    updated = await service.rename_conversation(conv.id, "Renamed")
    assert updated.title == "Renamed"


async def test_delete_conversation(service):
    conv = await service.create_conversation()
    deleted = await service.delete_conversation(conv.id)
    assert deleted is True
    assert await service.get_conversation(conv.id) is None


async def test_add_message_and_auto_title(service):
    conv = await service.create_conversation()
    msg = await service.add_message(
        conversation_id=conv.id,
        role="user",
        content="Tell me about FastAPI design patterns",
        model="gpt-5.5",
    )

    assert msg.role == "user"
    assert msg.model == "gpt-5.5"

    # Conversation title should be auto-generated from first user message
    await service.db.refresh(conv)
    assert conv.title == "Tell me about FastAPI design patterns"


async def test_get_messages(service):
    conv = await service.create_conversation()
    await service.add_message(conv.id, "user", "Hi")
    await service.add_message(conv.id, "assistant", "Hello!")

    messages = await service.get_messages(conv.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


async def test_update_message_content(service):
    conv = await service.create_conversation()
    msg = await service.add_message(conv.id, "assistant", "", status="streaming")

    updated = await service.update_message_content(msg.id, "Complete answer", status="done")
    assert updated.content == "Complete answer"
    assert updated.status == "done"
