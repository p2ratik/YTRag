"""
Test script for injecting vectors into the PostgreSQL vector_store table.

Usage:
    cd g:/Projects/Rag-01
    python -m backend.tests.test_vector_injection

Requires:
    - DATABASE_URL in .env (PostgreSQL with pgvector extension)
    - GEMINI_API_KEY in .env
"""

import asyncio
import sys
import os

# ── ensure the project root is on sys.path ──────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.db.session import engine, AsyncSessionLocal
from backend.db.base import Base
from backend.services.embeddings import embed
from backend.services.vector import insert_vectors


# ── Sample data (mimics grouped YouTube transcript chunks) ──────────────
SAMPLE_CHUNKS = [
    {
        "texts": "Welcome to this tutorial on building RAG applications using LangChain and vector databases. Today we will cover the fundamentals of retrieval-augmented generation.",
        "start_time": 0.0,
        "end_time": 15.5,
        "video_id": "test_video_001",
    },
    {
        "texts": "First, let's understand what embeddings are. An embedding is a numerical representation of text that captures its semantic meaning in a high-dimensional vector space.",
        "start_time": 15.5,
        "end_time": 30.0,
        "video_id": "test_video_001",
    },
    {
        "texts": "Vector databases like pgvector allow us to store these embeddings and perform similarity searches efficiently using cosine distance or inner product.",
        "start_time": 30.0,
        "end_time": 45.2,
        "video_id": "test_video_001",
    },
    {
        "texts": "The retrieval step fetches the most relevant chunks from the database based on the user query embedding, and the generation step uses an LLM to synthesize an answer.",
        "start_time": 45.2,
        "end_time": 60.0,
        "video_id": "test_video_001",
    },
    {
        "texts": "Let's now set up our project. We need Python 3.10 or later, FastAPI for the backend, and SQLAlchemy with asyncpg for async database access.",
        "start_time": 60.0,
        "end_time": 75.8,
        "video_id": "test_video_001",
    },
]


async def create_tables():
    """Create all tables (including vector_store) if they don't already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[✓] Tables created / verified.")


async def generate_embeddings(chunks: list[dict]) -> list[dict]:
    """
    Generate embeddings for each chunk using OpenAI text-embedding-3-small
    and attach them under the 'embedding' key.

    embed() returns a CreateEmbeddingResponse whose .data is a list
    of Embedding objects, each with an .embedding (list[float]).
    """
    print(f"[…] Generating embeddings for {len(chunks)} chunks …")
    raw_texts = [chunk["texts"] for chunk in chunks]
    result = await embed(raw_texts)

    for chunk, emb in zip(chunks, result.data):
        chunk["embedding"] = emb.embedding

    print(f"[✓] Embeddings generated.  Dimension = {len(result.data[0].embedding)}")
    return chunks


async def inject_vectors(chunks: list[dict]):
    """Insert embedded chunks into the vector_store table."""
    async with AsyncSessionLocal() as session:
        await insert_vectors(chunks, session)
    print(f"[✓] {len(chunks)} vectors injected into the database.")


async def main():
    print("=" * 60)
    print("  Vector Injection Test")
    print("=" * 60)

    # 1. Ensure tables exist
    await create_tables()

    # 2. Generate embeddings
    embedded_chunks = await generate_embeddings(SAMPLE_CHUNKS)

    # 3. Inject into DB
    await inject_vectors(embedded_chunks)

    print("\n✅  Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
