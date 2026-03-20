from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.chat import Conversation, Message
from backend.services.retriver_pipeline import retriver
from groq import Groq
import os
from uuid import UUID

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def _to_uuid(value: str):
    return UUID(str(value))


async def create_conversation(user_id, title: str, db: AsyncSession) -> Conversation:
    """Creates and persists a new conversation for a given user."""
    new_conv = Conversation(user_id=user_id, title=title)
    db.add(new_conv)
    await db.commit()
    await db.refresh(new_conv)
    return new_conv


async def get_user_conversations(user_id, db: AsyncSession) -> list[Conversation]:
    """Returns all conversations for a user, newest first."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


async def get_conversation_for_user(conversation_id: str, user_id: str, db: AsyncSession) -> Conversation | None:
    """Returns a conversation only if it belongs to the given user."""
    try:
        conv_uuid = UUID(str(conversation_id))
        user_uuid = UUID(str(user_id))
    except ValueError:
        return None

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid,
            Conversation.user_id == user_uuid,
        )
    )
    return result.scalar_one_or_none()


async def store_message(conversation_id: str, role: str, content: str, db: AsyncSession) -> Message:
    """Persists a single message to the DB."""
    msg = Message(conversation_id=_to_uuid(conversation_id), role=role, content=content)
    db.add(msg)
    await db.commit()
    return msg


async def fetch_recent_history(conversation_id: str, db: AsyncSession, limit: int = 10) -> list[Message]:
    """Fetches the last N messages for a conversation in chronological order."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == _to_uuid(conversation_id))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    messages.reverse()
    return messages


async def fetch_conversation_messages(conversation_id: str, db: AsyncSession, limit: int = 200) -> list[Message]:
    """Fetches full conversation messages in chronological order (capped by limit)."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == _to_uuid(conversation_id))
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def build_rag_context(conversation_id: str, query: str, db: AsyncSession, video_id: str | None) -> str:
    """Retrieves and formats RAG context from the vector store."""
    try:
        data = await retriver(conversation_id, query, 10, db, video_id)
        if data:
            sections = [
                f"[{int(doc.start_time)//60}:{int(doc.start_time)%60:02d}] {doc.content}"
                for doc in data
            ]
            return "\n\n".join(sections)
    except Exception as e:
        print(f"RAG retrieval error: {e}")
        await db.rollback()
    return ""



async def stream_llm_response(query: str, history: list[dict], rag_context: str):
    """Streams token chunks from the LLM based on chat history and RAG context."""
    if not _client:
        yield "Sorry, LLM is not configured."
        return

    system_prompt = "You are a helpful assistant."
    if rag_context:
        system_prompt += f"\n\nContext from video:\n{rag_context}\n\nUse this context to answer the user if relevant."

    messages_for_llm = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages_for_llm.append({"role": msg["role"], "content": msg["content"]})

    try:
        stream = _client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_for_llm,
            temperature=0.3,
            max_tokens=512,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token
    except Exception as e:
        print(f"LLM Stream Error: {e}")
        yield "Error generating response."


async def process_chat_message_stream(
    conversation_id: str,
    user_message: str,
    video_id: str | None,
    db: AsyncSession
):
    """
    Streaming pipeline for a single chat turn.
    Yields assistant token deltas and persists the final assistant message.
    """
    await store_message(conversation_id, "user", user_message, db)
    print("user message stored")
    history_orm = await fetch_recent_history(conversation_id, db)
    # Convert ORM objects to plain dicts immediately so SQLAlchemy does not
    # attempt a lazy-load inside the async streaming generator.
    history = [{"role": m.role, "content": m.content} for m in history_orm]
    print("history fetched")
    rag_context = await build_rag_context(conversation_id, user_message, db, video_id)
    print("rag context built")

    chunks = []
    async for token in stream_llm_response(user_message, history, rag_context):
        chunks.append(token)
        yield token

    reply = "".join(chunks).strip()
    if not reply:
        reply = "I could not generate a response."
    await store_message(conversation_id, "assistant", reply, db)
