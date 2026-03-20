"""
Diagnostic script to pinpoint why the retriever returns empty results.

Usage:
    cd g:/Projects/Rag-01
    python -m backend.tests.diagnose_pipeline

Checks:
  1. What video_ids exist in the database
  2. Total vector count
  3. Whether embedding + cosine search returns results
  4. Whether reranking filters everything out
  5. What the LLM classifier decides
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.db.session import AsyncSessionLocal
from backend.models.vector_data import VectorStore
from backend.services.embeddings import embed
from backend.services.retriver_pipeline import retrive_vectors, rerank_vectors, retriver
from sqlalchemy import select, func, text


async def check_database():
    """Step 1: What's in the database?"""
    print("\n" + "=" * 60)
    print("  STEP 1: Database Contents")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Total count
        result = await db.execute(select(func.count()).select_from(VectorStore))
        total = result.scalar()
        print(f"  Total vectors in DB: {total}")

        if total == 0:
            print("  ❌ DATABASE IS EMPTY — no vectors injected!")
            return None

        # Distinct video_ids
        result = await db.execute(select(VectorStore.video_id).distinct())
        video_ids = [row[0] for row in result.fetchall()]
        print(f"  Distinct video_ids: {video_ids}")

        # Count per video
        for vid in video_ids:
            result = await db.execute(
                select(func.count()).select_from(VectorStore).where(VectorStore.video_id == vid)
            )
            count = result.scalar()
            print(f"    '{vid}' → {count} chunks")

        # Sample a row to check data
        result = await db.execute(select(VectorStore).limit(1))
        sample = result.scalars().first()
        if sample:
            print(f"\n  Sample row:")
            print(f"    id: {sample.id}")
            print(f"    video_id: '{sample.video_id}'")
            print(f"    texts: '{sample.texts[:100]}...'")
            print(f"    start_time: {sample.start_time}")
            print(f"    end_time: {sample.end_time}")
            has_embedding = sample.embedding is not None
            print(f"    has embedding: {has_embedding}")
            if has_embedding:
                emb_len = len(sample.embedding) if hasattr(sample.embedding, '__len__') else 'unknown'
                print(f"    embedding dimension: {emb_len}")

        return video_ids


async def check_embedding():
    """Step 2: Does embedding work?"""
    print("\n" + "=" * 60)
    print("  STEP 2: Embedding Check")
    print("=" * 60)

    query = "What is this video about?"
    try:
        result = await embed(query)
        emb = result.data[0].embedding
        print(f"  ✓ Embedding works. Dimension: {len(emb)}")
        print(f"  First 5 values: {emb[:5]}")
        return True
    except Exception as e:
        print(f"  ❌ Embedding FAILED: {e}")
        return False


async def check_retrieval(video_id=None):
    """Step 3: Does vector search return results?"""
    print("\n" + "=" * 60)
    print(f"  STEP 3: Vector Retrieval (video_id={video_id!r})")
    print("=" * 60)

    query = "What is this video about?"

    async with AsyncSessionLocal() as db:
        # First try without video_id filter
        print(f"\n  3a. Search WITHOUT video_id filter:")
        results_all = await retrive_vectors(query, 10, db)
        print(f"      Results: {len(results_all)}")
        for i, doc in enumerate(results_all[:3]):
            print(f"      {i+1}. video_id='{doc.video_id}' | {doc.texts[:60]}...")

    if video_id:
        async with AsyncSessionLocal() as db:
            print(f"\n  3b. Search WITH video_id='{video_id}':")
            results_filtered = await retrive_vectors(query, 10, db, video_id)
            print(f"      Results: {len(results_filtered)}")
            for i, doc in enumerate(results_filtered[:3]):
                print(f"      {i+1}. video_id='{doc.video_id}' | {doc.texts[:60]}...")

            if len(results_filtered) == 0 and len(results_all) > 0:
                print(f"\n  ⚠️  MISMATCH: Results exist without filter but NOT with video_id='{video_id}'")
                print(f"     The video_id in the DB does not match '{video_id}'.")
                print(f"     DB video_ids: {set(doc.video_id for doc in results_all)}")


async def check_reranking(video_id=None):
    """Step 4: Does reranking filter everything out?"""
    print("\n" + "=" * 60)
    print(f"  STEP 4: Full Pipeline (video_id={video_id!r})")
    print("=" * 60)

    query = "What is this video about?"

    async with AsyncSessionLocal() as db:
        results = await retrive_vectors(query, 10, db, video_id)
        print(f"  Raw retrieval returned: {len(results)} docs")

        if results:
            reranked = await rerank_vectors(query, results)
            print(f"  After reranking: {len(reranked)} docs")

            if len(reranked) == 0:
                print("  ⚠️  Reranker filtered out ALL results (scores too low)")
        else:
            print("  ⚠️  No results to rerank — retrieval returned empty")


async def check_classifier():
    """Step 5: What does the LLM classifier return?"""
    print("\n" + "=" * 60)
    print("  STEP 5: LLM Classifier Check")
    print("=" * 60)

    try:
        from groq import Groq
        import json

        GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
        if not GROQ_API_KEY:
            print("  ⚠️  GROQ_API_KEY not set, skipping classifier test")
            return

        client = Groq(api_key=GROQ_API_KEY)

        test_queries = [
            "What is this video about?",
            "Explain the topic discussed at 2 minutes",
            "Hello, how are you?",
        ]

        for query in test_queries:
            from backend.services.llm_layer.routing_llm import CLASSIFIER_PROMPT
            prompt = CLASSIFIER_PROMPT.format(query=query)

            chat_complete = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=256,
                response_format={"type": "json_object"},
            )

            raw = chat_complete.choices[0].message.content.strip()
            result = json.loads(raw)
            action = result.get("action", "?")
            refined = result.get("prompt", "?")
            print(f"  Query: \"{query}\"")
            print(f"    → action: {action}")
            print(f"    → prompt: \"{refined}\"")
            print()
    except Exception as e:
        print(f"  ❌ Classifier check failed: {e}")


async def main():
    print("=" * 60)
    print("  Pipeline Diagnostic")
    print("=" * 60)

    # Step 1
    video_ids = await check_database()
    if not video_ids:
        print("\n❌ Cannot proceed — database is empty.")
        return

    # Step 2
    emb_ok = await check_embedding()
    if not emb_ok:
        print("\n❌ Cannot proceed — embedding is broken.")
        return

    # Step 3 & 4 — test with first video_id found
    test_vid = video_ids[0]
    await check_retrieval(test_vid)
    await check_reranking(test_vid)

    # Step 5
    await check_classifier()

    print("\n" + "=" * 60)
    print("  Diagnostic complete. Review the output above.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
