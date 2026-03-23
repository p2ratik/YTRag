from backend.db.session import AsyncSessionLocal
from backend.services.yt_service import build_parent_child_chunks
from backend.services.embeddings import embed_texts
from backend.services.vector import insert_vectors

async def process_yt_video(conversation_id:str, video_id:str):
    """Injection pipeline"""

    chunk_hierarchy = await build_parent_child_chunks(conversation_id=conversation_id, video_id=video_id)
    parent_chunks = chunk_hierarchy["parents"]
    child_chunks = chunk_hierarchy["children"]

    parent_chunks_embed = await embed_texts(parent_chunks)
    
    async with AsyncSessionLocal() as db:
        inserted_parents = await insert_vectors(parent_chunks_embed, db, return_inserted=True)
        parent_id_by_rank = {parent.parent_rank: parent.id for parent in inserted_parents}

        for child in child_chunks:
            child["parent_chunk_id"] = parent_id_by_rank.get(child.get("parent_rank"))

        child_chunks_embed = await embed_texts(child_chunks)
        await insert_vectors(child_chunks_embed, db)

