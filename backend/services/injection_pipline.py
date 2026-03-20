import tempfile
import os
import json
import asyncio
from backend.db.session import AsyncSessionLocal
from backend.services.yt_service import group_chunks
from backend.services.embeddings import embed_texts
from backend.services.vector import insert_vectors

async def process_yt_video(conversation_id:str, video_id:str):
    """Injection pipeline"""

    yt_transcripts = await group_chunks(conversation_id=conversation_id,video_id=video_id) # Chunked transcripts of time window ~90s

    yt_transcripts_embed = await embed_texts(yt_transcripts) # Embeddings created
    
    async with AsyncSessionLocal() as db:
        await insert_vectors(yt_transcripts_embed, db)

