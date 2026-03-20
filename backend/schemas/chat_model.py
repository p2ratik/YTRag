from pydantic import BaseModel
from typing import Optional

class ConversationCreate(BaseModel):
    title: str = "New Conversation"

class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    video_id: Optional[str] = None
