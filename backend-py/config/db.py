import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

pool = None


async def connect_db():
    global pool

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL is missing in .env file")

    pool = await asyncpg.create_pool(
    database_url,
    ssl="require",
    statement_cache_size=0
)

    print("✅ Connected to Supabase PostgreSQL")


async def close_db():
    global pool

    if pool:
        await pool.close()
        print("🔌 Database connection closed")


async def get_pool():
    if pool is None:
        raise Exception("Database pool is not initialized")
    return pool