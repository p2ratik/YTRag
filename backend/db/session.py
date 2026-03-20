import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from backend.db.base import Base

load_dotenv()

db_url = os.getenv('DATABASE_URL')

# Render/Heroku provide DATABASE_URL as "postgresql://..." or "postgres://..."
# which defaults to the sync psycopg2 driver. SQLAlchemy's async engine
# requires "postgresql+asyncpg://...", so we rewrite the scheme.
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Strip ?ssl=require from URL — asyncpg ignores it and we pass ssl via connect_args instead
if db_url and "?" in db_url:
    db_url = db_url.split("?")[0]

engine = create_async_engine(
    db_url,
    echo=False,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
        