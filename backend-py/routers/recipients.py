from decimal import Decimal
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_permission, require_role

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
    if user.get("role") != "recipient":
        require_permission(user, "recipients")
    pool = await get_pool()

    try:
        rows = await pool.fetch("""
            WITH inv_sum AS (
                SELECT
                    TRIM(i.recipient_name) AS name,
                    COUNT(i.id) AS invoice_count,
                    COALESCE(SUM(i.total_amount), 0) AS total_invoiced,
                    COALESCE(SUM(COALESCE(i.initial_paid_amount, 0)), 0) AS invoice_paid,
                    MIN(i.client_id) AS client_id,
                    STRING_AGG(DISTINCT c.name, ', ') AS client_name,
                    STRING_AGG(
                        DISTINCT COALESCE(u.full_name, 'غير معروف'),
                        ', '
                    ) AS employee_names
                FROM invoices i
                LEFT JOIN users u ON u.id = COALESCE(i.attributed_employee_id, i.created_by)
                LEFT JOIN clients c ON c.id = i.client_id
                WHERE i.recipient_name IS NOT NULL
                  AND TRIM(i.recipient_name) <> ''
                  AND COALESCE(NULLIF(i.status, ''), 'approved') = 'approved'
                GROUP BY TRIM(i.recipient_name)
            ),
            pay_sum AS (
                SELECT name, COALESCE(SUM(amount), 0) AS extra_paid
                FROM (
                    SELECT TRIM(rp.recipient_name) AS name, rp.amount
                    FROM recipient_payments rp
                    LEFT JOIN invoices i ON i.id = rp.invoice_id
                    WHERE rp.recipient_name IS NOT NULL
                      AND TRIM(rp.recipient_name) <> ''
                      AND (rp.invoice_id IS NULL OR COALESCE(NULLIF(i.status, ''), 'approved') = 'approved')

                    UNION ALL

                    SELECT TRIM(COALESCE(i.recipient_name, c.name)) AS name, p.amount
                    FROM payments p
                    LEFT JOIN invoices i ON i.id = p.invoice_id
                    JOIN clients c ON c.id = p.client_id
                    WHERE p.status = 'approved'
                ) payment_rows
                WHERE name IS NOT NULL AND name <> ''
                GROUP BY name
            )
            SELECT
                inv_sum.name,
                inv_sum.invoice_count,
                inv_sum.total_invoiced,
                inv_sum.employee_names,
                inv_sum.client_id,
                inv_sum.client_name,
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

        if user.get("role") == "recipient":
            own_name = (user.get("recipient_name") or "").strip().lower()
            result = [r for r in result if (r.get("name") or "").strip().lower() == own_name]
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/payments")
async def list_recipient_payments(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    require_permission(user, "payments")

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
    if user.get("role") == "recipient":
        if (user.get("recipient_name") or "").strip().lower() != recipient_name.strip().lower():
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول إلى كشف زبون آخر")
    else:
        require_permission(user, "recipients")
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

        approved_pay_rows = await pool.fetch(
            """
            SELECT p.id, p.amount, p.payment_date AS date, p.notes,
                   p.client_id, p.invoice_id,
                   CASE
                     WHEN COALESCE(p.notes, '') ILIKE '%method:check%' THEN 'check'
                     WHEN COALESCE(p.notes, '') ILIKE '%method:transfer%' THEN 'transfer'
                     ELSE 'cash'
                   END AS payment_method
            FROM payments p
            LEFT JOIN invoices i ON i.id = p.invoice_id
            JOIN clients c ON c.id = p.client_id
            WHERE p.status='approved'
              AND LOWER(TRIM(COALESCE(i.recipient_name, c.name)))=LOWER(TRIM($1))
            ORDER BY p.payment_date ASC, p.id ASC
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

        for r in approved_pay_rows:
            d = row_to_dict(r)
            d["id"] = f"payment-{d['id']}"
            d["type"] = "payment"
            d["source"] = "approved_payment"
            d["amount"] = float(d["amount"] or 0)
            transactions.append(d)

        transactions.sort(key=lambda x: (x.get("date") or "", str(x.get("id") or "")))

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
    require_permission(user, "payments")

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

        if data.invoice_id:
            invoice = await pool.fetchrow(
                """
                SELECT i.total_amount,
                       COALESCE((SELECT SUM(rp.amount) FROM recipient_payments rp WHERE rp.invoice_id=i.id),0)
                       + COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id=i.id AND p.status='approved'),0)
                         AS paid_amount
                FROM invoices i
                WHERE i.id=$1
                  AND ($2::int IS NULL OR i.client_id=$2)
                  AND COALESCE(i.status, 'approved')='approved'
                """,
                data.invoice_id,
                linked_client_id,
            )
            if not invoice:
                raise HTTPException(status_code=400, detail="الفاتورة غير موجودة أو غير معتمدة")
            outstanding = round(float(invoice["total_amount"] or 0) - float(invoice["paid_amount"] or 0), 3)
            if data.amount > outstanding:
                raise HTTPException(status_code=400, detail=f"المبلغ أكبر من باقي الفاتورة ({outstanding:.3f})")

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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    require_permission(user, "payments")
    pool = await get_pool()
    try:
        deleted = await pool.fetchrow(
            "DELETE FROM recipient_payments WHERE id=$1 RETURNING id", payment_id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="المقبوضة غير موجودة")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/payments/{payment_id}")
async def update_payment(payment_id: int, data: PaymentIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    require_permission(user, "payments")

    recipient_name = data.recipient_name.strip()
    if not recipient_name:
        raise HTTPException(status_code=400, detail="اسم الزبون مطلوب")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    if (data.payment_method or "cash") not in ("cash", "check", "transfer"):
        raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")
    try:
        payment_date = date.fromisoformat(data.payment_date) if data.payment_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="تاريخ المقبوضة غير صحيح")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if data.client_id:
                client_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM clients WHERE id=$1)", data.client_id
                )
                if not client_exists:
                    raise HTTPException(status_code=400, detail="العميل غير موجود")
            if data.invoice_id:
                invoice = await conn.fetchrow(
                    """
                    SELECT i.total_amount,
                           COALESCE((SELECT SUM(rp.amount) FROM recipient_payments rp WHERE rp.invoice_id=i.id AND rp.id<>$3),0)
                           + COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id=i.id AND p.status='approved'),0)
                             AS paid_amount
                    FROM invoices i
                    WHERE i.id=$1
                      AND ($2::int IS NULL OR i.client_id=$2)
                      AND COALESCE(i.status, 'approved')='approved'
                    """,
                    data.invoice_id, data.client_id, payment_id,
                )
                if not invoice:
                    raise HTTPException(status_code=400, detail="الفاتورة غير موجودة أو غير معتمدة")
                outstanding = round(float(invoice["total_amount"] or 0) - float(invoice["paid_amount"] or 0), 3)
                if data.amount > outstanding:
                    raise HTTPException(status_code=400, detail=f"المبلغ أكبر من باقي الفاتورة ({outstanding:.3f})")

            row = await conn.fetchrow(
                """
                UPDATE recipient_payments
                SET recipient_name=$1, client_id=$2, invoice_id=$3, amount=$4,
                    payment_method=$5, payment_date=$6, notes=$7
                WHERE id=$8
                RETURNING *
                """,
                recipient_name, data.client_id, data.invoice_id,
                round(data.amount, 3), data.payment_method or "cash",
                payment_date, data.notes, payment_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="المقبوضة غير موجودة")
            return row_to_dict(row)


