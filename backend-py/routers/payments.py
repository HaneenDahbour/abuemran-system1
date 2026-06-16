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


def parse_payment_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="تاريخ المقبوضة غير صحيح")


def normalize_payment_method(value: Optional[str]) -> str:
    value = clean_text(value) or "cash"
    allowed = {"cash", "check", "transfer"}
    if value not in allowed:
        raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")
    return value


class PaymentRequest(BaseModel):
    client_id: int
    invoice_id: Optional[int] = None
    amount: float
    payment_method: Optional[str] = "cash"
    payment_date: Optional[str] = None
    notes: Optional[str] = None


class RejectPaymentRequest(BaseModel):
    reason: str


PAYMENT_SELECT = """
SELECT p.*,
       c.name AS client_name,
       e.full_name AS employee_name,
       a.full_name AS approver_name,
       CASE
         WHEN COALESCE(p.notes, '') ILIKE '%method:check%' THEN 'check'
         WHEN COALESCE(p.notes, '') ILIKE '%method:transfer%' THEN 'transfer'
         ELSE 'cash'
       END AS payment_method
FROM payments p
JOIN clients c ON p.client_id = c.id
LEFT JOIN users e ON p.submitted_by = e.id
LEFT JOIN users a ON p.approved_by = a.id
"""


@router.get("")
async def get_payments(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        if user.get("role") == "client":
            rows = await pool.fetch(
                PAYMENT_SELECT + """
                WHERE p.client_id = $1
                ORDER BY p.created_at DESC
                """,
                user.get("client_id"),
            )

        elif user.get("role") == "employee":
            rows = await pool.fetch(
                PAYMENT_SELECT + """
                WHERE p.submitted_by = $1
                ORDER BY p.created_at DESC
                """,
                user.get("id"),
            )

        else:
            rows = await pool.fetch(PAYMENT_SELECT + """
                ORDER BY p.created_at DESC
                """)

        return [row_to_dict(row) for row in rows]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في السيرفر: {str(e)}")


@router.post("")
async def create_payment(data: PaymentRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant", "employee")

    if not data.client_id:
        raise HTTPException(status_code=400, detail="العميل مطلوب")

    amount = float(data.amount or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    method = normalize_payment_method(data.payment_method)
    payment_date = parse_payment_date(data.payment_date)

    status = "pending" if user.get("role") == "employee" else "approved"
    approved_by = None if status == "pending" else user.get("id")
    approved_at = None if status == "pending" else datetime.now()

    base_notes = clean_text(data.notes) or ""

    notes_parts = []
    if base_notes:
        notes_parts.append(base_notes)
    if data.invoice_id:
        notes_parts.append(f"invoice_id:{data.invoice_id}")
    notes_parts.append(f"method:{method}")
    notes = " | ".join(notes_parts)

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                client_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM clients WHERE id=$1)",
                    data.client_id,
                )
                if not client_exists:
                    raise HTTPException(status_code=400, detail="العميل غير موجود")

                if data.invoice_id:
                    invoice_exists = await conn.fetchval(
                        """
                        SELECT EXISTS(
                          SELECT 1
                          FROM invoices
                          WHERE id=$1 AND client_id=$2
                        )
                        """,
                        data.invoice_id,
                        data.client_id,
                    )

                    if not invoice_exists:
                        raise HTTPException(
                            status_code=400,
                            detail="الفاتورة غير موجودة أو لا تتبع هذا العميل",
                        )

                new_payment = await conn.fetchrow(
                    """
                    INSERT INTO payments
                      (client_id, invoice_id, submitted_by, approved_by, amount, status, notes, payment_date, approved_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    RETURNING *
                    """,
                    data.client_id,
                    data.invoice_id,
                    user.get("id"),
                    approved_by,
                    amount,
                    status,
                    notes,
                    payment_date,
                    approved_at,
                )

                if status == "pending":
                    try:
                        await conn.execute(
                            """
                            INSERT INTO notifications (role, message, type)
                            VALUES ('admin', $1, 'pending')
                            """,
                            f"â³ دفعة جديدة {amount} د.أ تنتظر موافقتك",
                        )
                    except Exception:
                        pass

                try:
                    await conn.execute(
                        """
                        INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
                        VALUES ($1,$2,$3,'payment',$4,$5)
                        """,
                        user.get("id"),
                        user.get("full_name") or user.get("username") or "مستخدم",
                        (
                            "سجّل دفعة مباشرة"
                            if status == "approved"
                            else "أرسل دفعة للموافقة"
                        ),
                        new_payment["id"],
                        f"{amount:.3f} د.أ â€” client_id:{data.client_id} â€” invoice_id:{data.invoice_id or 'none'} â€” method:{method}",
                    )
                except Exception:
                    pass

                out = row_to_dict(new_payment)
                out["payment_method"] = method
                return out

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في السيرفر: {str(e)}")


@router.post("/{payment_id}/approve")
async def approve_payment(payment_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        payment = await pool.fetchrow(
            """
            UPDATE payments
            SET status='approved',
                approved_by=$1,
                approved_at=NOW()
            WHERE id=$2 AND status='pending'
            RETURNING *
            """,
            user.get("id"),
            payment_id,
        )

        if not payment:
            raise HTTPException(
                status_code=404, detail="الدفعة غير موجودة أو تمت معالجتها مسبقاً"
            )

        try:
            await pool.execute(
                """
                INSERT INTO notifications (user_id, message, type)
                VALUES ($1, $2, 'approved')
                """,
                payment["submitted_by"],
                f"âœ“ اعتمد المدير دفعتك بقيمة {payment['amount']} د.أ",
            )
        except Exception:
            pass

        return row_to_dict(payment)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="خطأ في السيرفر")


@router.post("/{payment_id}/reject")
async def reject_payment(
    payment_id: int, data: RejectPaymentRequest, user=Depends(get_current_user)
):
    require_role(user, "admin")

    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="سبب الرفض مطلوب")

    pool = await get_pool()

    try:
        payment = await pool.fetchrow(
            """
            UPDATE payments
            SET status='rejected',
                rejection_reason=$1,
                approved_by=$2,
                approved_at=NOW()
            WHERE id=$3 AND status='pending'
            RETURNING *
            """,
            data.reason.strip(),
            user.get("id"),
            payment_id,
        )

        if not payment:
            raise HTTPException(
                status_code=404, detail="الدفعة غير موجودة أو تمت معالجتها مسبقاً"
            )

        try:
            await pool.execute(
                """
                INSERT INTO notifications (user_id, message, type)
                VALUES ($1, $2, 'rejected')
                """,
                payment["submitted_by"],
                f"âœ— رُفضت دفعتك {payment['amount']} د.أ â€” السبب: {data.reason}",
            )
        except Exception:
            pass

        return row_to_dict(payment)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="خطأ في السيرفر")


@router.delete("/{payment_id}")
async def delete_payment(payment_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        deleted = await pool.fetchrow(
            "DELETE FROM payments WHERE id=$1 RETURNING id",
            payment_id,
        )

        if not deleted:
            raise HTTPException(status_code=404, detail="الدفعة غير موجودة")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

