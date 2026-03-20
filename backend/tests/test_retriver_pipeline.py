"""
Test script for the retriever pipeline.

Verifies the full retrieval flow:
  1. Vector similarity search  (retrive_vectors)
  2. Cross-encoder reranking   (rerank_vectors)
  3. End-to-end pipeline       (retriver)

Usage:
    cd g:/Projects/Rag-01
    python -m backend.tests.test_retriver_pipeline

Requires:
    - DATABASE_URL in .env  (PostgreSQL with pgvector extension)
    - OPENAI_API_KEY in .env (for embedding the query)
    - Vectors already injected (run test_vector_injection first)
"""

import asyncio
import sys
import os
import time

# ── ensure the project root is on sys.path ──────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.db.session import AsyncSessionLocal
from backend.services.retriver_pipeline import retrive_vectors, rerank_vectors, retriver


# ── Test queries ────────────────────────────────────────────────────────
TEST_QUERIES = [
    "What are embeddings and how do they work?",
    "How does vector similarity search work with pgvector?",
    "What is retrieval augmented generation?",
]

# Set to a specific video_id to test filtered retrieval, or None for all
TEST_VIDEO_ID = "test_video_001"


async def test_retrive_vectors(query: str, top_k: int = 10, video_id: str = None):
    """Test 1: Raw vector retrieval via cosine distance."""
    print(f"\n{'─' * 60}")
    print(f"  TEST: retrive_vectors")
    print(f"  Query: \"{query}\"")
    print(f"  top_k: {top_k}, video_id: {video_id or 'ALL'}")
    print(f"{'─' * 60}")

    async with AsyncSessionLocal() as db:
        start = time.perf_counter()
        results = await retrive_vectors(query, top_k, db, video_id)
        elapsed = time.perf_counter() - start

    print(f"  [✓] Retrieved {len(results)} results in {elapsed:.3f}s")

    if not results:
        print("  [⚠] No results found — is the vector_store table populated?")
        return results

    # Display results
    for i, doc in enumerate(results, 1):
        snippet = doc.texts[:80] + "…" if len(doc.texts) > 80 else doc.texts
        print(f"  {i}. [{doc.start_time:.1f}s – {doc.end_time:.1f}s] {snippet}")

    # Basic assertions
    assert isinstance(results, list), "Expected a list of results"
    assert all(hasattr(doc, "texts") for doc in results), "Each result must have a 'texts' attribute"
    assert all(hasattr(doc, "start_time") for doc in results), "Each result must have 'start_time'"
    assert all(hasattr(doc, "end_time") for doc in results), "Each result must have 'end_time'"
    assert len(results) <= top_k, f"Expected at most {top_k} results, got {len(results)}"

    # If video_id was specified, verify all results are from that video
    if video_id:
        for doc in results:
            assert doc.video_id == video_id, f"Expected video_id '{video_id}', got '{doc.video_id}'"
        print(f"  [✓] All results belong to video_id '{video_id}'")

    print("  [✓] All assertions passed")
    return results


async def test_rerank_vectors(query: str, results: list):
    """Test 2: Cross-encoder reranking of retrieved results."""
    print(f"\n{'─' * 60}")
    print(f"  TEST: rerank_vectors")
    print(f"  Query: \"{query}\"")
    print(f"  Input docs: {len(results)}")
    print(f"{'─' * 60}")

    if not results:
        print("  [⚠] Skipping rerank — no results to rerank")
        return []

    start = time.perf_counter()
    top_docs = await rerank_vectors(query, results)
    elapsed = time.perf_counter() - start

    print(f"  [✓] Reranked to {len(top_docs)} docs in {elapsed:.3f}s")
    if len(top_docs) < len(results):
        print(f"  [i] Score cutoff filtered out {len(results) - len(top_docs)} low-confidence results")

    # Display reranked order
    for i, doc in enumerate(top_docs, 1):
        snippet = doc.texts[:80] + "…" if len(doc.texts) > 80 else doc.texts
        print(f"  {i}. [{doc.start_time:.1f}s – {doc.end_time:.1f}s] {snippet}")

    # Basic assertions
    assert isinstance(top_docs, list), "Expected a list"
    assert len(top_docs) <= 5, f"Reranker should return at most 5 docs, got {len(top_docs)}"
    assert len(top_docs) <= len(results), "Reranked results should not exceed input count"

    print("  [✓] All assertions passed")
    return top_docs


async def test_full_pipeline(query: str, top_k: int = 10, video_id: str = None):
    """Test 3: End-to-end retriver pipeline (vector search → rerank)."""
    print(f"\n{'─' * 60}")
    print(f"  TEST: retriver (full pipeline)")
    print(f"  Query: \"{query}\"")
    print(f"  top_k: {top_k}, video_id: {video_id or 'ALL'}")
    print(f"{'─' * 60}")

    async with AsyncSessionLocal() as db:
        start = time.perf_counter()
        top_docs = await retriver(query, top_k, db, video_id)
        elapsed = time.perf_counter() - start

    print(f"  [✓] Pipeline returned {len(top_docs)} docs in {elapsed:.3f}s")

    for i, doc in enumerate(top_docs, 1):
        snippet = doc.texts[:80] + "…" if len(doc.texts) > 80 else doc.texts
        print(f"  {i}. [{doc.start_time:.1f}s – {doc.end_time:.1f}s] {snippet}")

    # Assertions
    assert isinstance(top_docs, list), "Expected a list"
    assert all(hasattr(doc, "texts") for doc in top_docs), "Each doc must have 'texts'"
    assert len(top_docs) <= 5, f"Pipeline should return at most 5 reranked docs, got {len(top_docs)}"

    print("  [✓] All assertions passed")
    return top_docs


async def main():
    print("=" * 60)
    print("  Retriever Pipeline Test")
    print("=" * 60)

    query = TEST_QUERIES[0]

    # ── Step 1: Test raw vector retrieval (with video_id filter) ──
    results = await test_retrive_vectors(query, top_k=10, video_id=TEST_VIDEO_ID)

    # ── Step 2: Test reranking (with score cutoff) ──
    await test_rerank_vectors(query, results)

    # ── Step 3: Test full pipeline with all queries ──
    for q in TEST_QUERIES:
        await test_full_pipeline(q, top_k=10, video_id=TEST_VIDEO_ID)

    print("\n" + "=" * 60)
    print("  ✅  All retriever pipeline tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
