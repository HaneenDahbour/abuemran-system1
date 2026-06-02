from decimal import Decimal
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException

from config.db import get_pool
from middleware.auth import get_current_user

router = APIRouter()


def to_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def row_to_dict(row):
    return {key: to_json_value(row[key]) for key in row.keys()}


# GET /api/notifications/
@router.get("/")
async def get_notifications(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch(
            """
            SELECT *
            FROM notifications
            WHERE user_id = $1 OR role = $2
            ORDER BY created_at DESC
            LIMIT 50
            """,
            user.get("id"),
            user.get("role")
        )

        return [row_to_dict(row) for row in rows]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"خطأ في السيرفر: {str(e)}"
        )


# PUT /api/notifications/read
@router.put("/read")
async def mark_notifications_read(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        await pool.execute(
            """
            UPDATE notifications
            SET is_read = TRUE
            WHERE user_id = $1 OR role = $2
            """,
            user.get("id"),
            user.get("role")
        )

        return {"message": "تم تعليم الكل مقروءاً"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"خطأ في السيرفر: {str(e)}"
        )