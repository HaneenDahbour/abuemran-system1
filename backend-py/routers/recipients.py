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
                    COALESCE(SUM(COALESCE(i.initial_paid_amount, 0)), 0) AS invoice_paid,
                    STRING_AGG(
                        DISTINCT COALESCE(u.full_name, 'غير معروف'),
                        ', '
                    ) AS employee_names
                FROM invoices i
LEFT JOIN users u ON u.id = COALESCE(i.attributed_employee_id, i.created_by)                WHERE i.recipient_name IS NOT NULL
                  AND TRIM(i.recipient_name) <> ''
                  AND COALESCE(NULLIF(i.status, ''), 'approved') = 'approved'
                GROUP BY TRIM(i.recipient_name)
            ),
            pay_sum AS (
                SELECT
                    TRIM(rp.recipient_name) AS name,
                    COALESCE(SUM(rp.amount), 0) AS extra_paid
                FROM recipient_payments rp
                LEFT JOIN invoices i ON i.id = rp.invoice_id
                WHERE rp.recipient_name IS NOT NULL
                  AND TRIM(rp.recipient_name) <> ''
                  AND (
                    rp.invoice_id IS NULL
                    OR COALESCE(NULLIF(i.status, ''), 'approved') = 'approved'
                  )
                GROUP BY TRIM(rp.recipient_name)
            )
            SELECT
                inv_sum.name,
                inv_sum.invoice_count,
                inv_sum.total_invoiced,
                inv_sum.employee_names,
                -- المدفوع = سجلات المقبوضات فقط — الدفعة الأولية للفاتورة تُسجَّل
                -- تلقائياً كمقبوضة عند الاعتماد، فجمعها مرتين يضخّم المدفوع
                COALESCE(pay_sum.extra_paid, 0) AS total_paid
            FROM inv_sum
            LEFT JOIN pay_sum
              ON LOWER(TRIM(pay_sum.name)) = LOWER(TRIM(inv_sum.name))
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
                i.created_at,
                i.total_amount,
                i.payment_method,
                i.notes,
                i.recipient_name,
                i.created_by,
i.attributed_employee_id,
u.full_name AS employee_name
FROM invoices i
LEFT JOIN users u ON u.id = COALESCE(i.attributed_employee_id, i.created_by)
            WHERE LOWER(TRIM(i.recipient_name)) = LOWER(TRIM($1))
            AND COALESCE(i.status, 'approved') = 'approved'
            ORDER BY i.date ASC, i.id ASC
            """,
            recipient_name,
        )

        invoice_ids = [r["id"] for r in inv_rows]
        items_by_invoice = {}
        if invoice_ids:
            all_items = await pool.fetch(
                """
                SELECT ii.invoice_id, ii.quantity, ii.unit_price, ii.line_total,
                       ii.description,
                       p.name AS product_name, p.unit AS product_unit
                FROM invoice_items ii
                LEFT JOIN products p ON p.id = ii.product_id
                WHERE ii.invoice_id = ANY($1::int[])
                ORDER BY ii.id
                """,
                invoice_ids,
            )
            for item in all_items:
                iid = item["invoice_id"]
                if iid not in items_by_invoice:
                    items_by_invoice[iid] = []
                items_by_invoice[iid].append({
                    "product_name": item["product_name"] or item["description"] or "",
                    "quantity": float(item["quantity"] or 0),
                    "unit_price": float(item["unit_price"] or 0),
                    "line_total": float(item["line_total"] or 0),
                })

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
        OR COALESCE(NULLIF(i.status, ''), 'approved') = 'approved'
      )
    ORDER BY rp.payment_date ASC, rp.id ASC
    """,
    recipient_name,
    )


        transactions = []

        for r in inv_rows:
            d = row_to_dict(r)

            total = float(d["total_amount"] or 0)

            d["type"] = "invoice"
            d["amount"] = total
            d["items"] = items_by_invoice.get(r["id"], [])
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
        raise HTTPException(status_code=400, detail="اسم الزبون مطلوب")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    pool = await get_pool()
    try:
        pay_date = (
            date.fromisoformat(data.payment_date) if data.payment_date else date.today()
        )

        # ربط تلقائي بالعميل عبر الاسم إذا لم يُمرَّر client_id —
        # حتى يتطابق كشف العميل مع كشف زبائن الفواتير دائماً
        linked_client_id = data.client_id
        if not linked_client_id:
            linked_client_id = await pool.fetchval(
                "SELECT id FROM clients WHERE LOWER(TRIM(name)) = LOWER(TRIM($1)) LIMIT 1",
                data.recipient_name,
            )

        row = await pool.fetchrow(
            """
            INSERT INTO recipient_payments
  (recipient_name, client_id, invoice_id, amount, payment_method, payment_date, notes, created_by)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
        """,
            data.recipient_name.strip(),
            linked_client_id,
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


