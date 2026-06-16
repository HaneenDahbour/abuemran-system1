from decimal import Decimal
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role

router = APIRouter()


def safe_uuid(val):
    try:
        return UUID(str(val))
    except (ValueError, AttributeError, TypeError):
        return None


def to_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def row_to_dict(row):
    return {key: to_json_value(row[key]) for key in row.keys()}


class CheckRequest(BaseModel):
    client_id: int
    check_number: str
    bank_name: Optional[str] = None
    owner_name: Optional[str] = None
    amount: float
    due_date: str
    notes: Optional[str] = None


class CheckStatusRequest(BaseModel):
    status: str


@router.get("")
async def get_checks(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        if user.get("role") == "client":
            rows = await pool.fetch(
                """
                SELECT ch.*, c.name AS client_name
                FROM checks ch
                JOIN clients c ON ch.client_id = c.id
                WHERE ch.client_id = $1
                ORDER BY ch.due_date ASC
                """,
                user.get("client_id"),
            )
        else:
            rows = await pool.fetch("""
                SELECT ch.*, c.name AS client_name, u.full_name AS employee_name
                FROM checks ch
                JOIN clients c ON ch.client_id = c.id
                LEFT JOIN users u ON ch.created_by = u.id
                ORDER BY ch.due_date ASC
                """)

        return [row_to_dict(row) for row in rows]

    except Exception:
        raise HTTPException(status_code=500, detail="Ø®Ø·Ø£ ÙÙŠ Ø§Ù„Ø³ÙŠØ±ÙØ±")


@router.post("")
async def create_check(data: CheckRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant", "employee")

    if (
        not data.client_id
        or not data.check_number
        or not data.amount
        or not data.due_date
    ):
        raise HTTPException(
            status_code=400, detail="Ø§Ù„Ø¹Ù…ÙŠÙ„ØŒ Ø±Ù‚Ù… Ø§Ù„Ø´ÙŠÙƒØŒ Ø§Ù„Ù‚ÙŠÙ…Ø©ØŒ ÙˆØªØ§Ø±ÙŠØ® Ø§Ù„Ø§Ø³ØªØ­Ù‚Ø§Ù‚ Ù…Ø·Ù„ÙˆØ¨Ø©"
        )

    pool = await get_pool()

    try:
        try:
            due_date_value = date.fromisoformat(data.due_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="ØªØ§Ø±ÙŠØ® Ø§Ù„Ø§Ø³ØªØ­Ù‚Ø§Ù‚ ØºÙŠØ± ØµØ§Ù„Ø­. Ø§Ø³ØªØ®Ø¯Ù…ÙŠ Ø§Ù„Ø´ÙƒÙ„ YYYY-MM-DD",
            )

        new_check = await pool.fetchrow(
            """
            INSERT INTO checks
              (client_id, created_by, check_number, bank_name, owner_name, amount, due_date, notes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            RETURNING *
            """,
            data.client_id,
            user.get("id"),
            data.check_number,
            data.bank_name,
            data.owner_name,
            float(data.amount),
            due_date_value,
            data.notes,
        )

        try:
            await pool.execute(
                """
                INSERT INTO notifications (role, message, type)
                VALUES ('admin', $1, 'check')
                """,
                f"ðŸ¦ {user.get('full_name')} Ø£Ø¶Ø§Ù Ø´ÙŠÙƒ #{data.check_number} Ù‚ÙŠÙ…ØªÙ‡ {data.amount} Ø¯.Ø£ ÙŠØ³ØªØ­Ù‚ {data.due_date}",
            )
        except Exception:
            pass

        try:
            await pool.execute(
                """
                INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
                VALUES ($1,$2,'Ø£Ø¶Ø§Ù Ø´ÙŠÙƒ','check',$3,$4)
                """,
                user.get("id"),
                user.get("full_name"),
                new_check["id"],
                f"Ø´ÙŠÙƒ #{data.check_number} â€” {data.amount} Ø¯.Ø£",
            )
        except Exception:
            pass

        return row_to_dict(new_check)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ø®Ø·Ø£ ÙÙŠ Ø§Ù„Ø³ÙŠØ±ÙØ±: {str(e)}")


@router.put("/{check_id}/status")
async def update_check_status(
    check_id: int, data: CheckStatusRequest, user=Depends(get_current_user)
):
    require_role(user, "admin", "accountant")

    allowed_statuses = ["cashed", "returned", "cancelled"]

    if data.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Ø§Ù„Ø­Ø§Ù„Ø© ÙŠØ¬Ø¨ Ø£Ù† ØªÙƒÙˆÙ†: cashed Ø£Ùˆ returned Ø£Ùˆ cancelled",
        )

    pool = await get_pool()

    try:
        updated = await pool.fetchrow(
            """
            UPDATE checks
            SET status=$1,
                status_updated_at=NOW(),
                status_updated_by=$2
            WHERE id=$3
            RETURNING *
            """,
            data.status,
            user.get("id"),
            check_id,
        )

        if not updated:
            raise HTTPException(status_code=404, detail="Ø§Ù„Ø´ÙŠÙƒ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯")

        if data.status == "returned":
            try:
                await pool.execute(
                    """
                    INSERT INTO notifications (role, message, type)
                    VALUES ('admin', $1, 'rejected')
                    """,
                    f"â†© Ø´ÙŠÙƒ #{updated['check_number']} Ù…Ø±ØªØ¬Ø¹ â€” {updated['amount']} Ø¯.Ø£",
                )
            except Exception:
                pass

        action = (
            "ØµØ±Ù Ø´ÙŠÙƒ"
            if data.status == "cashed"
            else ("Ø³Ø¬Ù‘Ù„ Ø´ÙŠÙƒ Ù…Ø±ØªØ¬Ø¹" if data.status == "returned" else "Ø£Ù„ØºÙ‰ Ø´ÙŠÙƒ")
        )

        try:
            await pool.execute(
                """
                INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
                VALUES ($1,$2,$3,'check',$4,$5)
                """,
                user.get("id"),
                user.get("full_name"),
                action,
                check_id,
                f"Ø´ÙŠÙƒ #{updated['check_number']}",
            )
        except Exception:
            pass

        return row_to_dict(updated)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Ø®Ø·Ø£ ÙÙŠ Ø§Ù„Ø³ÙŠØ±ÙØ±")


@router.delete("/{check_id}")
async def delete_check(check_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        deleted = await pool.fetchrow(
            "DELETE FROM checks WHERE id=$1 RETURNING check_number", check_id
        )

        if not deleted:
            raise HTTPException(status_code=404, detail="Ø§Ù„Ø´ÙŠÙƒ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯")

        try:
            await pool.execute(
                """
                INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
                VALUES ($1,$2,'Ø­Ø°Ù Ø´ÙŠÙƒ','check',$3,$4)
                """,
                user.get("id"),
                user.get("full_name"),
                check_id,
                f"Ø­Ø°Ù Ø´ÙŠÙƒ #{deleted['check_number']}",
            )
        except Exception:
            pass

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

