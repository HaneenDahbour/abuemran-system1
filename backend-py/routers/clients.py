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
        VALUES ($1, $2, $3, 'client', $4, $5)
        """,
        user.get("id"),
        user.get("full_name") or user.get("username") or "مستخدم",
        action,
        entity_id,
        detail,
    )


class ClientRequest(BaseModel):
    name: str
    department: Optional[str] = "porcelain"
    credit_limit: Optional[float] = 0
    risk_level: Optional[str] = "low"
    phone: Optional[str] = None


@router.get("")
async def get_clients(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        if user.get("role") == "client":
            rows = await pool.fetch(
                """
                SELECT c.*,
                       COALESCE((
                         SELECT SUM(i.total_amount)
                         FROM invoices i
                         WHERE i.client_id = c.id
                           AND COALESCE(i.status, 'approved') = 'approved'
                       ), 0)
                       -
                       COALESCE((
                         SELECT SUM(p.amount)
                         FROM payments p
                         WHERE p.client_id = c.id
                           AND p.status = 'approved'
                       ), 0)
                       -
                       COALESCE((
                         SELECT SUM(rp.amount)
                         FROM recipient_payments rp
                         WHERE rp.client_id = c.id
                       ), 0) AS balance
                FROM clients c
                WHERE c.id = $1
                """,
                user.get("client_id"),
            )
        else:
            rows = await pool.fetch("""
                SELECT c.*,
                       COALESCE((
                         SELECT SUM(i.total_amount)
                         FROM invoices i
                         WHERE i.client_id = c.id
                           AND COALESCE(i.status, 'approved') = 'approved'
                       ), 0)
                       -
                       COALESCE((
                         SELECT SUM(p.amount)
                         FROM payments p
                         WHERE p.client_id = c.id
                           AND p.status = 'approved'
                       ), 0)
                       -
                       COALESCE((
                         SELECT SUM(rp.amount)
                         FROM recipient_payments rp
                         WHERE rp.client_id = c.id
                       ), 0) AS balance
                FROM clients c
                ORDER BY c.name ASC
                """)

        return [row_to_dict(r) for r in rows]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{client_id}")
async def get_client(client_id: int, user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        row = await pool.fetchrow(
            """
            SELECT c.*,
                   COALESCE((
                     SELECT SUM(i.total_amount)
                     FROM invoices i
                     WHERE i.client_id = c.id
                       AND COALESCE(i.status, 'approved') = 'approved'
                   ), 0)
                   -
                   COALESCE((
                     SELECT SUM(p.amount)
                     FROM payments p
                     WHERE p.client_id = c.id
                       AND p.status = 'approved'
                   ), 0)
                   -
                   COALESCE((
                     SELECT SUM(rp.amount)
                     FROM recipient_payments rp
                     WHERE rp.client_id = c.id
                   ), 0) AS balance
            FROM clients c
            WHERE c.id = $1
            """,
            client_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail="العميل غير موجود")

        return row_to_dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{client_id}/statement")
async def get_client_statement(client_id: int, user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        client = await pool.fetchrow(
            "SELECT * FROM clients WHERE id=$1",
            client_id,
        )

        if not client:
            raise HTTPException(status_code=404, detail="العميل غير موجود")

        # جلب كل الفواتير مع حساب المدفوع لكل فاتورة
        invoices = await pool.fetch(
            """
            SELECT
                i.id,
                i.invoice_number,
                i.total_amount,
                i.net_amount,
                i.tax_amount,
                i.payment_method,
                i.date,
                i.notes,
                COALESCE((
                    SELECT SUM(rp.amount)
                    FROM recipient_payments rp
                    WHERE rp.invoice_id = i.id
                ), 0) AS paid_from_invoice
            FROM invoices i
            WHERE i.client_id = $1
              AND COALESCE(i.status, 'approved') = 'approved'
            ORDER BY i.date ASC, i.id ASC
            """,
            client_id,
        )

        # جلب كل الدفعات
        payments = await pool.fetch(
            """
            SELECT
                rp.id,
                rp.amount,
                rp.payment_date AS date,
                rp.notes,
                rp.payment_method,
                CASE WHEN rp.invoice_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_invoice_payment
            FROM recipient_payments rp
            WHERE rp.client_id = $1
            ORDER BY rp.payment_date ASC, rp.id ASC
            """,
            client_id,
        )

        # إجماليات
        # المقبوضات المسجّلة من صفحة المقبوضات (جدول payments) — معتمدة فقط
        legacy_payments = await pool.fetch(
            """
            SELECT
                p.id,
                p.amount,
                p.payment_date AS date,
                p.notes,
                p.payment_method
            FROM payments p
            WHERE p.client_id = $1
              AND p.status = 'approved'
            ORDER BY p.payment_date ASC, p.id ASC
            """,
            client_id,
        )

        # الإجماليات تشمل كلا مصدري المقبوضات — لتطابق رصيد صفحة العملاء تماماً
        total_invoiced = sum(float(i["total_amount"] or 0) for i in invoices)
        total_paid = (
            sum(float(p["amount"] or 0) for p in payments)
            + sum(float(p["amount"] or 0) for p in legacy_payments)
        )
        total_remaining = total_invoiced - total_paid

        # إجمالي الذمم (فواتير آجلة غير مسددة بالكامل)
        total_credit_invoices = sum(
            float(i["total_amount"] or 0) - float(i["paid_from_invoice"] or 0)
            for i in invoices
            if float(i["total_amount"] or 0) > float(i["paid_from_invoice"] or 0)
        )

        # إجمالي النقد المدفوع فوراً عند الفواتير
        total_cash_on_invoices = sum(
            float(i["paid_from_invoice"] or 0) for i in invoices
        )

        # الدفعات المستقلة (مش مرتبطة بفاتورة)
        standalone_payments = [p for p in payments if not p["is_invoice_payment"]]
        total_standalone = sum(float(p["amount"] or 0) for p in standalone_payments)

        # بناء قائمة الحركات
        transactions = []

        for inv in invoices:
            total = float(inv["total_amount"] or 0)
            paid_now = float(inv["paid_from_invoice"] or 0)
            remaining = max(total - paid_now, 0)

            transactions.append(
                {
                    "id": inv["id"],
                    "type": "invoice",
                    "amount": total,
                    "paid_amount": paid_now,
                    "remaining_amount": remaining,
                    "date": inv["date"].isoformat() if inv["date"] else None,
                    "description": inv["invoice_number"],
                    "notes": inv["notes"] or "",
                    "payment_method": inv["payment_method"] or "credit",
                }
            )

        for pay in payments:
            transactions.append(
                {
                    "id": pay["id"],
                    "type": "payment",
                    "amount": float(pay["amount"] or 0),
                    "paid_amount": 0,
                    "remaining_amount": 0,
                    "date": pay["date"].isoformat() if pay["date"] else None,
                    "description": pay["notes"] or "مقبوضة",
                    "notes": pay["notes"] or "",
                    "is_invoice_payment": pay["is_invoice_payment"],
                    "payment_method": pay["payment_method"] or "cash",
                }
            )

        # مقبوضات صفحة المقبوضات — تظهر في الكشف مثل أي دفعة أخرى
        for pay in legacy_payments:
            transactions.append(
                {
                    "id": pay["id"],
                    "type": "payment",
                    "amount": float(pay["amount"] or 0),
                    "paid_amount": 0,
                    "remaining_amount": 0,
                    "date": pay["date"].isoformat() if pay["date"] else None,
                    "description": pay["notes"] or "مقبوضة",
                    "notes": pay["notes"] or "",
                    "is_invoice_payment": False,
                    "payment_method": pay["payment_method"] or "cash",
                }
            )

        transactions.sort(key=lambda x: (x["date"] or "", x["id"]))

        # حساب الرصيد الجاري
        running_balance = 0.0
        for tx in transactions:
            if tx["type"] == "invoice":
                running_balance += tx["amount"]
            else:
                running_balance -= tx["amount"]
            tx["running_balance"] = round(running_balance, 3)

        return {
            "client": row_to_dict(client),
            "balance": round(running_balance, 3),
            "credit_limit": float(client["credit_limit"] or 0),
            "summary": {
                "total_invoiced": round(total_invoiced, 3),
                "total_paid": round(total_paid, 3),
                "total_remaining": round(total_remaining, 3),
                "total_credit_invoices": round(total_credit_invoices, 3),
                "total_cash_on_invoices": round(total_cash_on_invoices, 3),
                "total_standalone_payments": round(total_standalone, 3),
            },
            "transactions": transactions,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_client(data: ClientRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    name = clean_text(data.name)
    phone = clean_text(data.phone)

    if not name:
        raise HTTPException(status_code=400, detail="اسم العميل مطلوب")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                duplicate = await conn.fetchrow(
                    "SELECT id FROM clients WHERE LOWER(name) = LOWER($1) LIMIT 1",
                    name,
                )

                if duplicate:
                    raise HTTPException(
                        status_code=400, detail="عميل بهذا الاسم موجود مسبقاً"
                    )

                row = await conn.fetchrow(
                    """
                    INSERT INTO clients (name, department, credit_limit, risk_level, phone)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING *
                    """,
                    name,
                    data.department or "porcelain",
                    float(data.credit_limit or 0),
                    data.risk_level or "low",
                    phone,
                )

                await insert_audit(
                    conn, user, "أضاف عميل", row["id"], f"إضافة عميل: {name}"
                )

                return row_to_dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{client_id}")
async def update_client(
    client_id: int, data: ClientRequest, user=Depends(get_current_user)
):
    require_role(user, "admin", "accountant")

    name = clean_text(data.name)
    phone = clean_text(data.phone)

    if not name:
        raise HTTPException(status_code=400, detail="اسم العميل مطلوب")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    "SELECT id FROM clients WHERE id=$1 FOR UPDATE",
                    client_id,
                )

                if not existing:
                    raise HTTPException(status_code=404, detail="العميل غير موجود")

                row = await conn.fetchrow(
                    """
                    UPDATE clients
                    SET name=$1,
                        department=$2,
                        credit_limit=$3,
                        risk_level=$4,
                        phone=$5
                    WHERE id=$6
                    RETURNING *
                    """,
                    name,
                    data.department or "porcelain",
                    float(data.credit_limit or 0),
                    data.risk_level or "low",
                    phone,
                    client_id,
                )

                await insert_audit(
                    conn, user, "تعديل عميل", client_id, f"تعديل بيانات العميل: {name}"
                )

                return row_to_dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{client_id}")
async def delete_client(client_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                client = await conn.fetchrow(
                    "SELECT id, name FROM clients WHERE id=$1 FOR UPDATE",
                    client_id,
                )

                if not client:
                    raise HTTPException(status_code=404, detail="العميل غير موجود")

                # اجلب فواتير العميل
                invoices = await conn.fetch(
                    """
                    SELECT id, invoice_number
                    FROM invoices
                    WHERE client_id=$1
                    FOR UPDATE
                    """,
                    client_id,
                )

                invoice_ids = [row["id"] for row in invoices]

                # رجّع مخزون أصناف فواتير العميل قبل حذفها
                if invoice_ids:
                    items = await conn.fetch(
                        """
                        SELECT ii.product_id, ii.quantity, i.invoice_number
                        FROM invoice_items ii
                        JOIN invoices i ON i.id = ii.invoice_id
                        WHERE ii.invoice_id = ANY($1::int[])
                        """,
                        invoice_ids,
                    )

                    for item in items:
                        product = await conn.fetchrow(
                            """
                            SELECT id, name, current_stock
                            FROM products
                            WHERE id=$1
                            FOR UPDATE
                            """,
                            item["product_id"],
                        )

                        if product:
                            quantity = float(item["quantity"] or 0)
                            old_stock = float(product["current_stock"] or 0)
                            new_stock = old_stock + quantity

                            await conn.execute(
                                """
                                UPDATE products
                                SET current_stock=$1
                                WHERE id=$2
                                """,
                                new_stock,
                                item["product_id"],
                            )

                            await conn.execute(
                                """
                                INSERT INTO stock_movements
                                  (product_id, type, quantity, source_type, notes, created_by)
                                VALUES
                                  ($1, 'in', $2, 'client_delete', $3, $4)
                                """,
                                item["product_id"],
                                quantity,
                                f"إرجاع مخزون بسبب حذف العميل {client['name']} / فاتورة #{item['invoice_number']}",
                                user.get("id"),
                            )

                    await conn.execute(
                        "DELETE FROM invoice_items WHERE invoice_id = ANY($1::int[])",
                        invoice_ids,
                    )

                # حذف حركات العميل المالية
                await conn.execute("DELETE FROM recipient_payments WHERE client_id=$1", client_id)
                await conn.execute("DELETE FROM payments WHERE client_id=$1", client_id)
                await conn.execute("DELETE FROM checks WHERE client_id=$1", client_id)
                await conn.execute("DELETE FROM invoices WHERE client_id=$1", client_id)

                # فك ربط أي مستخدم مربوط بهذا العميل
                await conn.execute(
                    "UPDATE users SET client_id=NULL WHERE client_id=$1",
                    client_id,
                )

                # حذف العميل نفسه
                await conn.execute("DELETE FROM clients WHERE id=$1", client_id)

                await insert_audit(
                    conn,
                    user,
                    "حذف عميل",
                    client_id,
                    f"حذف العميل وكل حركاته التجريبية: {client['name']}",
                )

                return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

