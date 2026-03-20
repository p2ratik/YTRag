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
