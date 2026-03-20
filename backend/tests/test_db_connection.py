"""
Test script to verify SQLAlchemy database connection and table access.
Run from the project root:
    python -m backend.tests.test_db_connection
"""
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# ── 1. Build the engine (same logic as db/session.py) ──────────────────
db_url = os.getenv("DATABASE_URL")

if not db_url:
    raise RuntimeError("❌  DATABASE_URL is not set in .env")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

print(f"🔌 Connecting to: {db_url[:60]}...")  # truncated for safety

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


# ── 2. Tests ───────────────────────────────────────────────────────────
async def test_raw_connection():
    """Check that we can open a raw connection to the DB."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        row = result.fetchone()
        assert row[0] == 1
        print("✅  Raw connection OK  →  SELECT 1 passed")


async def test_tables_exist():
    """Check that core application tables exist."""
    expected_tables = ["users", "conversations", "messages", "vector_store"]
    async with engine.connect() as conn:
        for table in expected_tables:
            result = await conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.tables"
                    "  WHERE table_schema = 'public'"
                    f"  AND table_name = '{table}'"
                    ")"
                )
            )
            exists = result.scalar()
            status = "✅ " if exists else "❌ "
            print(f"{status} Table '{table}' {'found' if exists else 'NOT FOUND'}")


async def test_session_query():
    """Check that we can run a query through SQLAlchemy ORM session."""
    from backend.models.user import User
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            print(f"✅  ORM session OK  →  Found user: {user.user_name}")
        else:
            print("✅  ORM session OK  →  users table is empty (no users yet)")


# ── 3. Runner ──────────────────────────────────────────────────────────
async def main():
    print("\n" + "═" * 50)
    print("  DB Connection Test")
    print("═" * 50 + "\n")

    try:
        await test_raw_connection()
    except Exception as e:
        print(f"❌  Raw connection FAILED: {e}")
        print("\n💡 Check your DATABASE_URL in .env and your network connection.")
        return

    try:
        await test_tables_exist()
    except Exception as e:
        print(f"❌  Table check FAILED: {e}")

    try:
        await test_session_query()
    except Exception as e:
        print(f"❌  ORM session FAILED: {e}")

    print("\n" + "═" * 50)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
