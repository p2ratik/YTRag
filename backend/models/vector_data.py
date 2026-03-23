from sqlalchemy import Column, String, DateTime, Text, Numeric, ForeignKey, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from backend.db.base import Base
import datetime
import uuid


class VectorStore(Base):
    __tablename__ = "vector_store"
    __table_args__ = (
        CheckConstraint("chunk_level IN ('child', 'parent')", name="ck_vector_store_chunk_level"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    video_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    start_time = Column(Numeric(10, 3), nullable=True)
    end_time = Column(Numeric(10, 3), nullable=True)
    chunk_level = Column(String, nullable=False, default="child")
    parent_chunk_id = Column(UUID(as_uuid=True), ForeignKey("vector_store.id", ondelete="SET NULL"), nullable=True)
    chunk_index = Column(Integer, nullable=True)
    parent_rank = Column(Integer, nullable=True)

    embedding = Column(Vector(768), nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    parent = relationship(
        "VectorStore",
        remote_side=[id],
        foreign_keys=[parent_chunk_id],
        back_populates="children",
    )
    children = relationship(
        "VectorStore",
        foreign_keys=[parent_chunk_id],
        back_populates="parent",
    )

