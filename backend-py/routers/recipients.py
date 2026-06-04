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
    except Exception:
        return None


def to_val(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    return v


def row_to_dict(row):
    return {k: to_val(row[k]) for k in row.keys()}


class PaymentIn(BaseModel):
    recipient_name: str
    client_id: Optional[int] = None
    invoice_id: Optional[int] = None
    amount: float
    payment_method: Optional[str] = "cash"
    payment_date: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def list_recipients(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch("""
            WITH inv_sum AS (
                SELECT
                    TRIM(i.recipient_name) AS name,
                    COUNT(i.id) AS invoice_count,
                    COALESCE(SUM(i.total_amount), 0) AS total_invoiced,
                    STRING_AGG(
                        DISTINCT COALESCE(u.full_name, 'غير معروف'),
                        ', '
                    ) AS employee_names
                FROM invoices i
                LEFT JOIN users u ON u.id = i.created_by
                WHERE i.recipient_name IS NOT NULL
                  AND TRIM(i.recipient_name) <> ''
                  AND COALESCE(i.status, '') = 'approved'
                GROUP BY TRIM(i.recipient_name)
            )
            SELECT
                inv_sum.name,
                inv_sum.invoice_count,
                inv_sum.total_invoiced,
                inv_sum.employee_names,
                COALESCE((
                    SELECT SUM(rp.amount)
                    FROM recipient_payments rp
                    LEFT JOIN invoices i2 ON i2.id = rp.invoice_id
                    WHERE LOWER(TRIM(rp.recipient_name)) = LOWER(TRIM(inv_sum.name))
                      AND (
                        rp.invoice_id IS NULL
                        OR COALESCE(i2.status, '') = 'approved'
                      )
                ), 0) AS total_paid
            FROM inv_sum
            ORDER BY inv_sum.total_invoiced DESC
        """)

        result = []
        for r in rows:
            d = row_to_dict(r)
            d["balance"] = round(
                float(d["total_invoiced"] or 0) - float(d["total_paid"] or 0),
                3,
            )
            result.append(d)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/payments")
async def list_recipient_payments(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    pool = await get_pool()

    try:
        rows = await pool.fetch("""
            SELECT
                rp.*,
                u.full_name AS employee_name,
                i.invoice_number
            FROM recipient_payments rp
            LEFT JOIN users u ON u.id = rp.created_by
            LEFT JOIN invoices i ON i.id = rp.invoice_id
            ORDER BY rp.payment_date DESC, rp.id DESC
        """)

        return [row_to_dict(row) for row in rows]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/{recipient_name}/statement")
async def recipient_statement(recipient_name: str, user=Depends(get_current_user)):
    pool = await get_pool()
    try:
        inv_rows = await pool.fetch(
            """
                    SELECT
                i.id,
                i.invoice_number,
                i.date,
                i.total_amount,
                i.payment_method,
                i.notes,
                i.recipient_name,
                i.created_by,
                u.full_name AS employee_name
            FROM invoices i
            LEFT JOIN users u ON u.id = i.created_by
            WHERE LOWER(TRIM(i.recipient_name)) = LOWER(TRIM($1))
            AND COALESCE(i.status, 'approved') = 'approved'
            ORDER BY i.date ASC, i.id ASC
            """,
            recipient_name,
        )

        manual_pay_rows = await pool.fetch(
    """
    SELECT
        rp.id,
        rp.amount,
        rp.payment_date AS date,
        rp.notes,
        rp.created_at,
        rp.client_id,
        rp.invoice_id,
        rp.payment_method
    FROM recipient_payments rp
    LEFT JOIN invoices i ON i.id = rp.invoice_id
    WHERE LOWER(TRIM(rp.recipient_name)) = LOWER(TRIM($1))
      AND (
        rp.invoice_id IS NULL
        OR COALESCE(i.status, '') = 'approved'
      )
    ORDER BY rp.payment_date ASC, rp.id ASC
    """,
    recipient_name,
)


        transactions = []

        for r in inv_rows:
            d = row_to_dict(r)
            d["type"] = "invoice"
            d["amount"] = float(d["total_amount"] or 0)
            transactions.append(d)



        for r in manual_pay_rows:
            d = row_to_dict(r)
            d["type"] = "payment"
            d["source"] = "manual_recipient_payment"
            d["amount"] = float(d["amount"] or 0)
            transactions.append(d)

        transactions.sort(key=lambda x: (x.get("date") or "", x.get("id") or 0))

        balance = 0.0
        for t in transactions:
            if t["type"] == "invoice":
                balance += t["amount"]
            else:
                balance -= t["amount"]
            t["running_balance"] = round(balance, 3)

        total_invoiced = sum(
            t["amount"] for t in transactions if t["type"] == "invoice"
        )
        total_paid = sum(t["amount"] for t in transactions if t["type"] == "payment")

        return {
            "recipient_name": recipient_name,
            "balance": round(balance, 3),
            "total_invoiced": round(total_invoiced, 3),
            "total_paid": round(total_paid, 3),
            "transactions": transactions,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payments")
async def add_payment(data: PaymentIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    if not data.recipient_name.strip():
        raise HTTPException(status_code=400, detail="Ø§Ø³Ù… Ø§Ù„Ø²Ø¨ÙˆÙ† Ù…Ø·Ù„ÙˆØ¨")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ù…Ø¨Ù„Øº ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø£ÙƒØ¨Ø± Ù…Ù† ØµÙØ±")

    pool = await get_pool()
    try:
        pay_date = (
            date.fromisoformat(data.payment_date) if data.payment_date else date.today()
        )

        row = await pool.fetchrow(
            """
            INSERT INTO recipient_payments
  (recipient_name, client_id, invoice_id, amount, payment_method, payment_date, notes, created_by)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
        """,
            data.recipient_name.strip(),
            data.client_id,
            data.invoice_id,
            round(data.amount, 3),
            data.payment_method or "cash",
            pay_date,
            data.notes,
            user.get("id"),
        )
        return row_to_dict(row)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    try:
        await pool.execute("DELETE FROM recipient_payments WHERE id=$1", payment_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

