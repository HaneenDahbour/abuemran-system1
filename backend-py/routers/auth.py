import os
import random
import string
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role
from typing import Optional

load_dotenv()

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str
    client_id: Optional[int] = None
    recipient_name: Optional[str] = None


@router.post("/login")
async def login(data: LoginRequest):
    pool = await get_pool()

    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Ø§Ø³Ù… Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… ÙˆÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ± Ù…Ø·Ù„ÙˆØ¨Ø§Ù†")

    user = await pool.fetchrow("SELECT * FROM users WHERE username = $1", data.username)

    if not user:
        raise HTTPException(status_code=401, detail="Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø¯Ø®ÙˆÙ„ ØºÙŠØ± ØµØ­ÙŠØ­Ø©")

    valid = pwd_context.verify(data.password, user["password_hash"])

    if not valid:
        raise HTTPException(status_code=401, detail="Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø¯Ø®ÙˆÙ„ ØºÙŠØ± ØµØ­ÙŠØ­Ø©")

    payload = {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "client_id": user["client_id"],
        "recipient_name": user["recipient_name"],
        "exp": datetime.utcnow() + timedelta(days=7),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    try:
        await pool.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, detail)
            VALUES ($1, $2, 'ØªØ³Ø¬ÙŠÙ„ Ø¯Ø®ÙˆÙ„', $3)
            """,
            user["id"],
            user["full_name"],
            f"Ø¯Ø®ÙˆÙ„ Ù…Ù† Ù‚ÙØ¨Ù„ {user['full_name']}",
        )
    except Exception:
        pass

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "recipient_name": user["recipient_name"],
            "role": user["role"],
            "client_id": user["client_id"],
        },
    }


@router.get("/users")
async def get_users(user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT id, username, full_name, role, client_id, recipient_name, created_at
        FROM users
        ORDER BY created_at DESC
        """)

    return [dict(row) for row in rows]


@router.post("/users")
async def create_user(data: CreateUserRequest, user=Depends(get_current_user)):
    require_role(user, "admin")

    valid_roles = ["admin", "accountant", "employee", "client", "recipient"]

    if data.role not in valid_roles:
        raise HTTPException(status_code=400, detail="Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ© Ø§Ù„Ù…Ø­Ø¯Ø¯Ø© ØºÙŠØ± ØµØ§Ù„Ø­Ø©")

    if data.role == "client" and not data.client_id:
        raise HTTPException(
            status_code=400, detail="Ø­Ø³Ø§Ø¨ Ø§Ù„Ø¹Ù…ÙŠÙ„ ÙŠØ­ØªØ§Ø¬ Ø±Ø¨Ø·Ù‡ Ø¨Ø¹Ù…ÙŠÙ„ Ø±Ø¦ÙŠØ³ÙŠ"
        )

    if data.role == "recipient" and not data.recipient_name:
        raise HTTPException(
            status_code=400, detail="Ø­Ø³Ø§Ø¨ Ø§Ù„Ø²Ø¨ÙˆÙ† ÙŠØ­ØªØ§Ø¬ Ø§Ø³Ù… Ø§Ù„Ø²Ø¨ÙˆÙ† ÙƒÙ…Ø§ ÙŠØ¸Ù‡Ø± ÙÙŠ Ø§Ù„ÙÙˆØ§ØªÙŠØ±"
        )

    pool = await get_pool()

    existing = await pool.fetchrow(
        "SELECT id FROM users WHERE username = $1", data.username
    )

    if existing:
        raise HTTPException(status_code=409, detail="Ø§Ø³Ù… Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… Ù…Ø­Ø¬ÙˆØ² Ø¨Ø§Ù„ÙØ¹Ù„")

    hashed_password = pwd_context.hash(data.password)

    new_user = await pool.fetchrow(
        """
        INSERT INTO users (username, password_hash, full_name, role, client_id, recipient_name)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, username, full_name, role, client_id, recipient_name
        """,
        data.username,
        hashed_password,
        data.full_name,
        data.role,
        data.client_id,
        data.recipient_name.strip() if data.recipient_name else None,
    )

    try:
        await pool.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, detail)
            VALUES ($1, $2, 'Ø¥Ù†Ø´Ø§Ø¡ Ù…Ø³ØªØ®Ø¯Ù…', $3)
            """,
            user["id"],
            user["full_name"],
            f"Ø¥Ù†Ø´Ø§Ø¡ Ù…Ø³ØªØ®Ø¯Ù… Ø¬Ø¯ÙŠØ¯: {data.username} ({data.role})",
        )
    except Exception:
        pass

    return dict(new_user)


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    if int(user_id) == int(user["id"]):
        raise HTTPException(status_code=400, detail="Ù„Ø§ ÙŠÙ…ÙƒÙ†Ùƒ Ø­Ø°Ù Ø­Ø³Ø§Ø¨Ùƒ Ø§Ù„Ø®Ø§Øµ")

    pool = await get_pool()

    deleted = await pool.fetchrow(
        "DELETE FROM users WHERE id = $1 RETURNING username", user_id
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯")

    try:
        await pool.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, detail)
            VALUES ($1, $2, 'Ø­Ø°Ù Ù…Ø³ØªØ®Ø¯Ù…', $3)
            """,
            user["id"],
            user["full_name"],
            f"Ø­Ø°Ù Ù…Ø³ØªØ®Ø¯Ù…: {deleted['username']}",
        )
    except Exception:
        pass

    return {"success": True}


@router.get("/telegram-code")
async def telegram_code(user=Depends(get_current_user)):
    pool = await get_pool()

    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    await pool.execute(
        "UPDATE users SET telegram_link_code = $1 WHERE id = $2", code, user["id"]
    )

    return {"code": code}

