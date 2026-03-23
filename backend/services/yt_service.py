from youtube_transcript_api import YouTubeTranscriptApi


# Algorithm
"""
1 . First group the transcripts into groups of duration ~30 sec . Also add start and end time in metadatas
2 . Use Recursive Text splitter on those
"""


async def group_chunks(conversation_id: str, video_id: str, window: int = 30, overlap: int = 5):
    """Breaks the given video transcripts into groups of ~30 sec each with overlap."""
    api = YouTubeTranscriptApi()
    transcript_list = api.fetch(video_id, languages=["en"])
    snippets = transcript_list.snippets

    groups = []

    current_snippets = []
    current_text = []
    current_start = None
    current_end = None
    current_duration = 0

    print("[DEBUG] Now stared created chunbks for the given yt video ")
    for snippet in snippets:
        snippet_start = snippet.start
        snippet_end = snippet.start + snippet.duration

        if current_start is None:
            current_start = snippet_start

        if current_duration + snippet.duration > window:
            groups.append({
                "conversation_id": conversation_id,
                "video_id": video_id,
                "content": " ".join(current_text).strip(),
                "start_time": current_start,
                "end_time": current_end,
            })

            overlap_snippets = []
            overlap_duration = 0
            for previous in reversed(current_snippets):
                overlap_snippets.insert(0, previous)
                overlap_duration += previous["duration"]
                if overlap_duration >= overlap:
                    break

            current_snippets = overlap_snippets
            current_text = [item["text"] for item in current_snippets]
            current_start = current_snippets[0]["start"] if current_snippets else snippet_start
            current_end = current_snippets[-1]["end"] if current_snippets else None
            current_duration = sum(item["duration"] for item in current_snippets)

        current_snippets.append({
            "text": snippet.text,
            "start": snippet_start,
            "end": snippet_end,
            "duration": snippet.duration,
        })
        current_text.append(snippet.text)
        current_duration += snippet.duration
        current_end = snippet_end

    if current_text:
        groups.append({
            "conversation_id": conversation_id,
            "video_id": video_id,
            "content": " ".join(current_text).strip(),
            "start_time": current_start,
            "end_time": current_end,
        })
    print("[DEBUG] Now finished created chunbks for the given yt video :", len(groups))
    return groups


def _build_parent_chunks(children: list[dict], parent_size: int = 6) -> tuple[list[dict], list[dict]]:
    """
    Build 3-minute parent chunks from ordered child chunks.

    parent_size=6 means 6 x 30s child chunks per parent chunk.
    Returns (parents, children_with_parent_rank).
    """
    parents = []
    children_with_parent_rank = []

    for i in range(0, len(children), parent_size):
        parent_rank = i // parent_size
        child_group = children[i:i + parent_size]
        if not child_group:
            continue

        parent = {
            "conversation_id": child_group[0]["conversation_id"],
            "video_id": child_group[0]["video_id"],
            "content": " ".join(chunk["content"] for chunk in child_group).strip(),
            "start_time": child_group[0]["start_time"],
            "end_time": child_group[-1]["end_time"],
            "chunk_level": "parent",
            "chunk_index": None,
            "parent_rank": parent_rank,
        }
        parents.append(parent)

        for child in child_group:
            updated_child = dict(child)
            updated_child["chunk_level"] = "child"
            updated_child["parent_rank"] = parent_rank
            children_with_parent_rank.append(updated_child)

    return parents, children_with_parent_rank


async def build_parent_child_chunks(
    conversation_id: str,
    video_id: str,
    child_window: int = 30,
    child_overlap: int = 5,
    parent_size: int = 6,
) -> dict:
    """Create ordered child chunks and corresponding parent chunks with linkage metadata."""
    children = await group_chunks(
        conversation_id=conversation_id,
        video_id=video_id,
        window=child_window,
        overlap=child_overlap,
    )

    for idx, chunk in enumerate(children):
        chunk["chunk_level"] = "child"
        chunk["chunk_index"] = idx

    parents, linked_children = _build_parent_chunks(children, parent_size=parent_size)
    return {"parents": parents, "children": linked_children}
