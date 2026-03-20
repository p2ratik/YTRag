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

    embedding: List[float] = Field(..., min_length=768, max_length=768)

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v):
        if len(v) != 768:
            raise ValueError("Embedding must be exactly 768 dimensions")
        return v
