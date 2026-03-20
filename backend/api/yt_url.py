from fastapi import APIRouter, Form, HTTPException
from backend.services.injection_pipline import process_yt_video
import re

router = APIRouter(prefix="/api", tags=["urls"])

def extract_video_id(url: str) -> str | None:
    """Extract the YouTube video ID from various URL formats."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/v\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # If it already looks like a raw video ID
    if re.fullmatch(r'[a-zA-Z0-9_-]{11}', url):
        return url
    return None

@router.post("/upload-url", status_code=201)
async def upload_url_query(conversation_id: str = Form(...), url: str = Form(...)):
    """Recieves the url and processes it"""

    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    try:
        await process_yt_video(conversation_id=conversation_id, video_id=video_id)
        return {"message": "Video processed successfully", "video_id": video_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))            
    



