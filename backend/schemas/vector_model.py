from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Pydantic Model
class VectorModel(BaseModel):
    """
    Vector Embeddings
    """

    conversation_id: Optional[UUID] = None
    video_id: str
    content: str

    start_time: Optional[float] = None
    end_time: Optional[float] = None
    chunk_level: str = "child"
    parent_chunk_id: Optional[UUID] = None
    chunk_index: Optional[int] = None
    parent_rank: Optional[int] = None

    embedding: List[float] = Field(..., min_length=768, max_length=768)

    @field_validator("chunk_level")
    @classmethod
    def validate_chunk_level(cls, v):
        if v not in {"child", "parent"}:
            raise ValueError("chunk_level must be either 'child' or 'parent'")
        return v

    @field_validator("chunk_index", "parent_rank")
    @classmethod
    def validate_non_negative_int(cls, v):
        if v is not None and v < 0:
            raise ValueError("chunk index values must be non-negative")
        return v

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v):
        if len(v) != 768:
            raise ValueError("Embedding must be exactly 768 dimensions")
        return v
