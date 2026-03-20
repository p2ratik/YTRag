# Function which prepares data and sends to LLM for answering
from groq import Groq
from backend.services.retriver_pipeline import retriver
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
import os

GROQ_API_KEY = os.environ['GROQ_API_KEY']
client = Groq(api_key=GROQ_API_KEY)

RETRIEVAL_SYSTEM_PROMPT = """You are a helpful YouTube video assistant. You answer questions about video content using ONLY the provided transcript sections. Do NOT make up information.

Formatting rules — follow these strictly:
1. Start with a short, direct answer (1-2 sentences).
2. Then list the key points as bullet points. Each bullet should start with the timestamp in [MM:SS] format.
3. End with a brief one-line summary if the answer has multiple points.
4. Keep the tone conversational and easy to read.
5. If the provided content doesn't contain enough information to answer, say so honestly.

Example format:
The video discusses [topic].

• [0:15] First key point from the video
• [1:30] Second key point explained clearly
• [3:45] Another relevant detail

In summary, [brief wrap-up]."""

def _build_retrieval_prompt(content, metadatas, query):
    """Build the user prompt with retrieved context."""
    sections = []
    for text, meta in zip(content, metadatas):
        start_m, start_s = divmod(int(meta['start_time']), 60)
        end_m, end_s = divmod(int(meta['end_time']), 60)
        sections.append(f"[{start_m}:{start_s:02d} – {end_m}:{end_s:02d}] {text}")

    context_block = "\n\n".join(sections)

    return f"""Here are the relevant sections from the video transcript:

{context_block}

---
User question: {query}"""

async def retrive_data_llm(websocket:WebSocket, query:str, db:AsyncSession, video_id:str = None):
    """Retrieve context from vector DB, then stream a structured LLM answer."""
    
    data = await retriver(query, 15, db, video_id)
    
    # Preparing data
    content = [doc.content for doc in data]
    metadatas = [{'start_time': doc.start_time, 'end_time': doc.end_time} for doc in data]

    user_prompt = _build_retrieval_prompt(content, metadatas, query)

    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": RETRIEVAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        stream=True
    )    

    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            await websocket.send_text(token)

DIRECT_SYSTEM_PROMPT = """You are a friendly YouTube video assistant. The user is asking a general question that doesn't need video context.

Formatting rules:
1. Be concise and conversational.
2. Use short paragraphs (2-3 sentences max each).
3. Use bullet points for lists.
4. Keep responses brief — no more than a few sentences unless the question requires depth."""

async def answer_direct_llm(websocket:WebSocket, query:str, db:AsyncSession):
    """Answer general questions without video context."""

    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": DIRECT_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.2,
        stream=True
    )  
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            await websocket.send_text(token)
