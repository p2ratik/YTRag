from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.vector_data import VectorStore    # orm model
from backend.schemas.vector_model import VectorModel  #pydantic model
# from app.utils.logger import get_logger
from sqlalchemy import select

async def insert_vectors(texts,db:AsyncSession):
    """Function to insert vectors"""
    # First add then commit
    for text in texts:
        vector_metadats = VectorModel.model_validate(text)

        db_vector = VectorStore(**vector_metadats.model_dump())
        db.add(db_vector)
    try:
        await db.commit()
        print("Injection done")
    except Exception as e:
        await db.rollback()
        print("[DEBUG] Database injection failed", e)
        raise RuntimeError(f"Database injection failed")    
