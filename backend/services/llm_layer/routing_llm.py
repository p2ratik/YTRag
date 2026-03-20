from backend.services.llm_layer.retrive_answer import retrive_data_llm, answer_direct_llm
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket
from groq import Groq
import json
import os

GROQ_API_KEY = os.environ['GROQ_API_KEY']
client = Groq(api_key=GROQ_API_KEY)

CLASSIFIER_PROMPT = """You are a query classifier for a YouTube video Q&A assistant. The user has uploaded a video and is asking questions about it.

Your job: decide if the query needs video content retrieval, or can be answered without it.

IMPORTANT: When in doubt, ALWAYS choose "retrieval". The user is here to ask about their video.

Rules:
- action "retrieval": ANY question that could possibly relate to the video content, topic, details, timestamps, summaries, explanations, or anything the video might cover. This includes vague questions like "what is this about?", "summarize this", "explain the main points", etc. Rewrite the query into a concise, descriptive search query optimized for vector similarity search.
- action "direct": ONLY for greetings ("hi", "hello"), thank-yous, or questions clearly unrelated to any video (e.g. "what is 2+2?", "what's the weather?").

You MUST respond with ONLY valid JSON in this exact format (no extra text):
{{"action": "retrieval" or "direct", "prompt": "the prompt text"}}

User query: {query}"""


async def llm_classifier(query: str, websocket: WebSocket, db: AsyncSession, video_id: str = None):
    """Decides whether the query requires a db search or not, then routes accordingly."""

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

    action = result.get("action", "direct").lower()
    refined_prompt = result.get("prompt", query)

    if action == "retrieval":
        await retrive_data_llm(websocket, refined_prompt, db, video_id)
    else:
        await answer_direct_llm(websocket, refined_prompt, db)