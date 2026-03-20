import json
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.db.session import AsyncSessionLocal, get_db
from backend.models.user import User
from backend.auth.dependencies import get_current_user
from backend.auth.security import verify_access_token
from backend.schemas.chat_model import ConversationCreate, ChatRequest
from backend.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new conversation session for the current user."""
    conv = await chat_service.create_conversation(current_user.id, req.title, db)
    return {"conversation_id": str(conv.id), "title": conv.title}


@router.get("/conversations")
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Gets all conversations for the current user."""
    convs = await chat_service.get_user_conversations(current_user.id, db)
    return [{"id": str(c.id), "title": c.title, "created_at": c.created_at} for c in convs]


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns persisted messages for a conversation if it belongs to the current user."""
    conv = await chat_service.get_conversation_for_user(conversation_id, current_user.id, db)
    if not conv:
        return []

    messages = await chat_service.fetch_conversation_messages(conversation_id, db)
    return [
        {"id": str(m.id), "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in messages
    ]


@router.post("/message")
async def send_message(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Receives a user message, runs the RAG + LLM pipeline, returns the reply."""
    reply = await chat_service.process_chat_message(
        conversation_id=req.conversation_id,
        user_message=req.message,
        video_id=req.video_id,
        db=db
    )
    return {"reply": reply}


def _extract_token_from_websocket(websocket: WebSocket) -> str | None:
    """Extracts JWT from Authorization header, query params, or cookies."""
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    query_token = websocket.query_params.get("token") or websocket.query_params.get("access_token")
    if query_token:
        return query_token

    cookie_token = websocket.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    return None


async def _authenticate_websocket_user(websocket: WebSocket, db: AsyncSession) -> User | None:
    token = _extract_token_from_websocket(websocket)
    if not token:
        return None

    payload = verify_access_token(token)
    if not payload or "sub" not in payload:
        return None

    try:
        user_id = UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket):
    """JWT-authenticated WebSocket chat endpoint for message exchange + streamed AI replies."""
    async with AsyncSessionLocal() as db:
        user = await _authenticate_websocket_user(websocket, db)
        if not user:
            await websocket.close(code=4401, reason="Unauthorized")
            return

        await websocket.accept()
        await websocket.send_json({"type": "ready"})

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
                    continue

                event_type = payload.get("type", "chat_message")
                if event_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if event_type != "chat_message":
                    await websocket.send_json({"type": "error", "message": "Unsupported event type."})
                    continue

                conversation_id = str(payload.get("conversation_id", "")).strip()
                user_message = str(payload.get("message", "")).strip()
                video_id = payload.get("video_id")

                if not conversation_id or not user_message:
                    await websocket.send_json({"type": "error", "message": "conversation_id and message are required."})
                    continue

                conv = await chat_service.get_conversation_for_user(conversation_id, user.id, db)
                if not conv:
                    await websocket.send_json({"type": "error", "message": "Conversation not found."})
                    continue

                await websocket.send_json({"type": "assistant_start"})
                async for token in chat_service.process_chat_message_stream(
                    conversation_id=conversation_id,
                    user_message=user_message,
                    video_id=video_id,
                    db=db
                ):
                    await websocket.send_json({"type": "assistant_chunk", "delta": token})
                await websocket.send_json({"type": "assistant_end"})
        except WebSocketDisconnect:
            return
