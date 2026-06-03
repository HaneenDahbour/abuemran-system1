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


def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


async def insert_audit(conn, user, action: str, entity_id: Optional[int], detail: str):
    await conn.execute(
        """
        INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
        VALUES ($1, $2, $3, 'supplier', $4, $5)
        """,
        safe_uuid(user.get("id")),
        user.get("full_name") or user.get("username") or "Ù…Ø³ØªØ®Ø¯Ù…",
        action,
        entity_id,
        detail,
    )


class SupplierRequest(BaseModel):
    name: str
    phone: Optional[str] = None


class SupplierPaymentRequest(BaseModel):
    amount: float
    payment_date: Optional[str] = None
    notes: Optional[str] = None
    payment_method: Optional[str] = "cash"


@router.get("")
async def get_suppliers(user=Depends(get_current_user)):
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT s.*,
              COALESCE((SELECT COUNT(*) FROM purchases p WHERE p.supplier_id = s.id), 0) AS purchases_count,
              COALESCE((SELECT SUM(total) FROM purchases p WHERE p.supplier_id = s.id AND p.status = 'received'), 0) AS total_purchased,
              COALESCE((SELECT SUM(amount) FROM supplier_payments sp WHERE sp.supplier_id = s.id), 0) AS total_paid
            FROM suppliers s
            ORDER BY s.name ASC
            """)
        result = []
        for r in rows:
            d = row_to_dict(r)
            d["balance"] = round(
                float(d.get("total_purchased") or 0) - float(d.get("total_paid") or 0),
                3,
            )
            result.append(d)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ø®Ø·Ø£ ÙÙŠ Ø¬Ù„Ø¨ Ø§Ù„Ù…ÙˆØ±Ø¯ÙŠÙ†: {str(e)}")


@router.get("/{supplier_id}/statement")
async def get_supplier_statement(supplier_id: str, user=Depends(get_current_user)):
    pool = await get_pool()
    try:
        supplier = await pool.fetchrow(
            "SELECT * FROM suppliers WHERE id=$1", supplier_id
        )
        if not supplier:
            raise HTTPException(status_code=404, detail="Ø§Ù„Ù…ÙˆØ±Ø¯ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯")

        purchases = await pool.fetch(
            """
            SELECT id, invoice_number, date, total, status, notes
            FROM purchases
            WHERE supplier_id = $1 AND status = 'received'
            ORDER BY date ASC, id ASC
            """,
            supplier_id,
        )

        payments = await pool.fetch(
            """
            SELECT id, amount, payment_date AS date, notes, payment_method
            FROM supplier_payments
            WHERE supplier_id = $1
            ORDER BY payment_date ASC, id ASC
            """,
            supplier_id,
        )

        transactions = []

        for p in purchases:
            d = row_to_dict(p)
            d["type"] = "purchase"
            d["amount"] = float(d.get("total") or 0)
            transactions.append(d)

        for p in payments:
            d = row_to_dict(p)
            d["type"] = "payment"
            d["amount"] = float(d.get("amount") or 0)
            transactions.append(d)

        transactions.sort(key=lambda x: (x.get("date") or "", x.get("id") or 0))

        balance = 0.0
        for t in transactions:
            if t["type"] == "purchase":
                balance += t["amount"]
            else:
                balance -= t["amount"]
            t["running_balance"] = round(balance, 3)

        total_purchased = sum(
            t["amount"] for t in transactions if t["type"] == "purchase"
        )
        total_paid = sum(t["amount"] for t in transactions if t["type"] == "payment")

        return {
            "supplier": row_to_dict(supplier),
            "balance": round(balance, 3),
            "total_purchased": round(total_purchased, 3),
            "total_paid": round(total_paid, 3),
            "transactions": transactions,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{supplier_id}/payments")
async def add_supplier_payment(
    supplier_id: str, data: SupplierPaymentRequest, user=Depends(get_current_user)
):
    require_role(user, "admin", "accountant")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ù…Ø¨Ù„Øº ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø£ÙƒØ¨Ø± Ù…Ù† ØµÙØ±")

    pool = await get_pool()
    try:
        supplier = await pool.fetchrow(
            "SELECT * FROM suppliers WHERE id=$1", supplier_id
        )
        if not supplier:
            raise HTTPException(status_code=404, detail="Ø§Ù„Ù…ÙˆØ±Ø¯ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯")

        pay_date = (
            date.fromisoformat(data.payment_date) if data.payment_date else date.today()
        )

        row = await pool.fetchrow(
            """
            INSERT INTO supplier_payments
              (supplier_id, amount, payment_date, notes, payment_method, created_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            supplier_id,
            round(data.amount, 3),
            pay_date,
            data.notes,
            data.payment_method or "cash",
            safe_uuid(user.get("id")),
        )

        try:
            from utils.telegram import notify_admin

            await notify_admin(
                f"ðŸ’¸ <b>Ø¯ÙØ¹Ø© Ø¬Ø¯ÙŠØ¯Ø© Ù„Ù„Ù…ÙˆØ±Ø¯</b>\n\n"
                f"ðŸª Ø§Ù„Ù…ÙˆØ±Ø¯: {supplier['name']}\n"
                f"ðŸ’µ Ø§Ù„Ù…Ø¨Ù„Øº: {data.amount:.3f} Ø¯.Ø£\n"
                f"ðŸ‘¨â€ðŸ’¼ Ø¯ÙØ¹Ù‡Ø§: {user.get('full_name', '')}"
            )
        except Exception:
            pass

        return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/payments/{payment_id}")
async def delete_supplier_payment(payment_id: str, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    try:
        deleted = await pool.fetchrow(
            "DELETE FROM supplier_payments WHERE id=$1 RETURNING id", payment_id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Ø§Ù„Ø¯ÙØ¹Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø©")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_supplier(data: SupplierRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    name = clean_text(data.name)
    phone = clean_text(data.phone)
    if not name:
        raise HTTPException(status_code=400, detail="Ø§Ø³Ù… Ø§Ù„Ù…ÙˆØ±Ø¯ Ù…Ø·Ù„ÙˆØ¨")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                duplicate = await conn.fetchrow(
                    "SELECT id, name FROM suppliers WHERE LOWER(name) = LOWER($1) LIMIT 1",
                    name,
                )
                if duplicate:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Ø§Ù„Ù…ÙˆØ±Ø¯ Ù…ÙˆØ¬ÙˆØ¯ Ù…Ø³Ø¨Ù‚Ø§Ù‹: {duplicate['name']}",
                    )
                row = await conn.fetchrow(
                    "INSERT INTO suppliers (name, phone) VALUES ($1, $2) RETURNING *",
                    name,
                    phone,
                )
                await insert_audit(
                    conn, user, "Ø£Ø¶Ø§Ù Ù…ÙˆØ±Ø¯", row["id"], f"Ø¥Ø¶Ø§ÙØ© Ù…ÙˆØ±Ø¯: {name}"
                )
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{supplier_id}")
async def update_supplier(
    supplier_id: str, data: SupplierRequest, user=Depends(get_current_user)
):
    require_role(user, "admin", "accountant")
    name = clean_text(data.name)
    phone = clean_text(data.phone)
    if not name:
        raise HTTPException(status_code=400, detail="Ø§Ø³Ù… Ø§Ù„Ù…ÙˆØ±Ø¯ Ù…Ø·Ù„ÙˆØ¨")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    "SELECT id, name FROM suppliers WHERE id=$1 FOR UPDATE", supplier_id
                )
                if not existing:
                    raise HTTPException(status_code=404, detail="Ø§Ù„Ù…ÙˆØ±Ø¯ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯")
                duplicate = await conn.fetchrow(
                    "SELECT id FROM suppliers WHERE LOWER(name) = LOWER($1) AND id <> $2 LIMIT 1",
                    name,
                    supplier_id,
                )
                if duplicate:
                    raise HTTPException(status_code=400, detail="Ø§Ù„Ø§Ø³Ù… Ù…Ø³ØªØ®Ø¯Ù… Ù…Ø³Ø¨Ù‚Ø§Ù‹")
                row = await conn.fetchrow(
                    "UPDATE suppliers SET name=$1, phone=$2, updated_at=NOW() WHERE id=$3 RETURNING *",
                    name,
                    phone,
                    supplier_id,
                )
                await insert_audit(
                    conn, user, "ØªØ¹Ø¯ÙŠÙ„ Ù…ÙˆØ±Ø¯", supplier_id, f"ØªØ¹Ø¯ÙŠÙ„: {name}"
                )
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: str, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                supplier = await conn.fetchrow(
                    "SELECT id, name FROM suppliers WHERE id=$1 FOR UPDATE", supplier_id
                )
                if not supplier:
                    raise HTTPException(status_code=404, detail="Ø§Ù„Ù…ÙˆØ±Ø¯ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯")
                linked = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM purchases WHERE supplier_id=$1)",
                    supplier_id,
                )
                if linked:
                    raise HTTPException(
                        status_code=400,
                        detail="Ù„Ø§ ÙŠÙ…ÙƒÙ† Ø­Ø°Ù Ø§Ù„Ù…ÙˆØ±Ø¯ Ù„Ø£Ù†Ù‡ Ù…Ø±ØªØ¨Ø· Ø¨ÙÙˆØ§ØªÙŠØ± Ø´Ø±Ø§Ø¡",
                    )
                await conn.execute("DELETE FROM suppliers WHERE id=$1", supplier_id)
                await insert_audit(
                    conn, user, "Ø­Ø°Ù Ù…ÙˆØ±Ø¯", supplier_id, f"Ø­Ø°Ù: {supplier['name']}"
                )
                return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

