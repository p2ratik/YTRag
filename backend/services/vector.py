from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.vector_data import VectorStore    # orm model
from backend.schemas.vector_model import VectorModel  #pydantic model
# from app.utils.logger import get_logger

async def insert_vectors(texts, db: AsyncSession, return_inserted: bool = False):
    """Function to insert vectors"""
    # First add then commit
    inserted_rows = []
    for text in texts:
        vector_metadats = VectorModel.model_validate(text)

        db_vector = VectorStore(**vector_metadats.model_dump())
        db.add(db_vector)
        if return_inserted:
            inserted_rows.append(db_vector)
    try:
        await db.commit()
        if return_inserted:
            for row in inserted_rows:
                await db.refresh(row)
        print("Injection done")
        return inserted_rows if return_inserted else None
    except Exception as e:
        await db.rollback()
        print("[DEBUG] Database injection failed", e)
        raise RuntimeError(f"Database injection failed")    
