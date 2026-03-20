from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.yt_url import router as yt_url_router
from backend.db.base import Base
from backend.db.session import engine
import asyncio
import os

app = FastAPI(title="Youtube Rag")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# including routers 
app.include_router(yt_url_router)

from backend.api.login import router as auth_router
app.include_router(auth_router)

from backend.api.chat import router as chat_router
app.include_router(chat_router)

@app.get('/')
def root():
    """Root endpoint"""
    return {"message": "Welcome to Youtube Rag", "version": "1.0.0"}
    