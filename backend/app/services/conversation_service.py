from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_title(first_message: str | None) -> str:
    if not first_message:
        return "新会话"
    stripped = first_message.strip().replace("\n", " ")
    return stripped[:50] + ("…" if len(stripped) > 50 else "")


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(self, title: str | None = None) -> Conversation:
        conversation = Conversation(
            title=title or "新会话",
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def list_conversations(self, search_query: str | None = None) -> list[Conversation]:
        stmt = select(Conversation).order_by(Conversation.updated_at.desc())
        if search_query:
            stmt = stmt.where(Conversation.title.ilike(f"%{search_query}%"))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def rename_conversation(self, conversation_id: str, title: str) -> Conversation | None:
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None
        conversation.title = title
        conversation.updated_at = now_utc()
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def delete_conversation(self, conversation_id: str) -> bool:
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False
        await self.db.delete(conversation)
        await self.db.commit()
        return True

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: str | None = None,
        status: str = "done",
        thinking: str = "",
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            thinking=thinking,
            model=model,
            status=status,
            created_at=now_utc(),
        )
        self.db.add(message)

        # Update conversation title from first user message if still default
        if role == "user":
            conversation = await self.get_conversation(conversation_id)
            if conversation and conversation.title == "新会话":
                conversation.title = _generate_title(content)

        # Update conversation updated_at
        conversation = await self.get_conversation(conversation_id)
        if conversation:
            conversation.updated_at = now_utc()

        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def update_message_content(
        self,
        message_id: str,
        content: str,
        status: str | None = None,
        thinking: str | None = None,
    ) -> Message | None:
        result = await self.db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if not message:
            return None

        message.content = content
        if thinking is not None:
            message.thinking = thinking
        if status:
            message.status = status

        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_messages(self, conversation_id: str) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())
