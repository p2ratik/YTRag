from sentence_transformers import CrossEncoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from backend.models.vector_data import VectorStore
from backend.services.embeddings import embed
from uuid import UUID
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
        conv_uuid = UUID(str(conversation_id))
        stmt = select(VectorStore).where(
            VectorStore.conversation_id == conv_uuid,
            or_(VectorStore.chunk_level == "child", VectorStore.chunk_level.is_(None)),
        )

        # Scope to a specific video if provided
        if video_id:
            stmt = stmt.where(VectorStore.video_id == video_id)

        stmt = stmt.order_by(
            VectorStore.embedding.cosine_distance(query_embed)
        ).limit(top_k)

        results = await db.execute(stmt)
        rows = results.scalars().all()

        # Filter out results with poor similarity
        filtered = []
        for doc in rows:
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


async def _expand_to_unique_parent_chunks(
    conversation_id: str,
    ranked_children: list[VectorStore],
    db: AsyncSession,
    video_id: str | None = None,
) -> list[VectorStore]:
    """
    Expand ranked child chunks with immediate neighbors and return unique parent chunks.
    Ordering: best child relevance rank first, chronological start_time tie-break.
    """
    if not ranked_children:
        return []

    conv_uuid = UUID(str(conversation_id))

    # If hierarchy metadata is missing for all rows, caller should fallback to child chunks.
    if not any(getattr(child, "parent_chunk_id", None) for child in ranked_children):
        return []

    ranked_by_index = {
        child.chunk_index: rank
        for rank, child in enumerate(ranked_children)
        if child.chunk_index is not None
    }

    neighbor_indexes = set()
    for child in ranked_children:
        if child.chunk_index is None:
            continue
        neighbor_indexes.add(child.chunk_index - 1)
        neighbor_indexes.add(child.chunk_index + 1)

    neighbor_indexes = {idx for idx in neighbor_indexes if idx >= 0}
    neighbors = []
    if neighbor_indexes:
        stmt = select(VectorStore).where(
            and_(
                VectorStore.conversation_id == conv_uuid,
                VectorStore.chunk_level == "child",
                VectorStore.chunk_index.in_(neighbor_indexes),
            )
        )
        if video_id:
            stmt = stmt.where(VectorStore.video_id == video_id)
        neighbor_result = await db.execute(stmt)
        neighbors = neighbor_result.scalars().all()

    candidate_children = list(ranked_children) + neighbors

    parent_best_rank = {}
    for child in candidate_children:
        parent_id = getattr(child, "parent_chunk_id", None)
        if not parent_id:
            continue

        base_rank = ranked_by_index.get(child.chunk_index, len(ranked_children) + 1)
        existing_rank = parent_best_rank.get(parent_id)
        if existing_rank is None or base_rank < existing_rank:
            parent_best_rank[parent_id] = base_rank

    if not parent_best_rank:
        return []

    stmt = select(VectorStore).where(VectorStore.id.in_(list(parent_best_rank.keys())))
    parent_result = await db.execute(stmt)
    parents = parent_result.scalars().all()

    parents.sort(
        key=lambda parent: (
            parent_best_rank.get(parent.id, len(ranked_children) + 1),
            float(parent.start_time or 0.0),
        )
    )
    return parents

async def retriver(conversation_id:str, query: str, top_k: int, db: AsyncSession, video_id: str = None):

    results = await retrive_vectors(conversation_id,query, top_k, db, video_id)

    top_children = await rerank_vectors(query, results)

    expanded_parents = await _expand_to_unique_parent_chunks(
        conversation_id=conversation_id,
        ranked_children=top_children,
        db=db,
        video_id=video_id,
    )

    if expanded_parents:
        return expanded_parents

    return top_children

