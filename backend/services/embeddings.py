from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
from typing import List, Dict
import asyncio

load_dotenv()

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def embed(texts):
    """Generate embeddings using OpenAI text-embedding-3-small (768 dims)."""
    try:
        result = await asyncio.wait_for(
            client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
                dimensions=768
            ),
            timeout=120,
        )
        return result
    except Exception as e:
        raise

async def embed_texts(texts:List[Dict])->List[Dict]:
    """
    Batch process texts
    """
    batch_size = 66
    batch_texts = []
    temp = []
    print("[DEBUG] Now stared created chunbks for the given yt video ")
    for text in texts:
        temp.append(text.get('content') or text.get('texts') or '')
        if len(temp) == batch_size:
            batch_texts.append(temp)
            temp = []
    if temp:
        batch_texts.append(temp)
    embeddings = []
    try:
        for batch in batch_texts:
            results = await embed(batch)     
            embeddings.append(results)

        all_embeddings = [emb for result in embeddings for emb in result.data]

        for chunk, emb in zip(texts, all_embeddings):
            chunk['embedding'] = emb.embedding

        print("[DEBUG] Now finished created chunbks for the given yt video :", len(texts))
        return texts    
    except Exception as e:
        raise



