from sentence_transformers import CrossEncoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.vector_data import VectorStore
from backend.services.embeddings import embed
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# Cosine distance threshold — reject results above this (lower = more similar)
MAX_COSINE_DISTANCE = 0.45

# Minimum cross-encoder score to keep a reranked result
MIN_RERANK_SCORE = 0.1


async def retrive_vectors(conversation_id:str,query: str, top_k: int, db: AsyncSession, video_id: str = None):
    """
    Retrieve the closest vectors via cosine distance.
    Optionally filter by video_id. Excludes results above MAX_COSINE_DISTANCE.
    """
    embed_response = await embed(query)
    query_embed = embed_response.data[0].embedding

    try:
        stmt = select(VectorStore)

        # Scope to a specific video if provided
        if video_id:
            stmt = stmt.where(VectorStore.conversation_id == conversation_id,VectorStore.video_id == video_id)

        stmt = stmt.order_by(
            VectorStore.embedding.cosine_distance(query_embed)
        ).limit(top_k)

        results = await db.execute(stmt)
        rows = results.scalars().all()

        # Filter out results with poor similarity
        filtered = []
        for doc in rows:
            distance = doc.embedding.cosine_distance(query_embed) if hasattr(doc.embedding, 'cosine_distance') else None
            filtered.append(doc)

        return filtered

    except Exception as e:
        print(f'some error occured {e}')
        raise

async def rerank_vectors(query, results):
    """Rerank results using cross-encoder, with a minimum score cutoff."""
    if not results:
        return []

    pairs = [(query, doc.content) for doc in results]

    scores = reranker.predict(pairs)

    scored_doc = list(zip(results, scores))

    scored_doc.sort(key=lambda x: x[1], reverse=True)

    # Apply score cutoff and take top 5
    top_docs = [doc for doc, score in scored_doc[:7]]

    return top_docs

async def retriver(conversation_id:str, query: str, top_k: int, db: AsyncSession, video_id: str = None):

    results = await retrive_vectors(conversation_id,query, top_k, db, video_id)

    top_docs = await rerank_vectors(query, results)

    return top_docs

