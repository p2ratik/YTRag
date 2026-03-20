from sqlalchemy import Column, String, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from backend.db.base import Base
import datetime
import uuid


class VectorStore(Base):
    __tablename__ = "vector_store"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    video_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    start_time = Column(Numeric(10, 3), nullable=True)
    end_time = Column(Numeric(10, 3), nullable=True)

    embedding = Column(Vector(768), nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

