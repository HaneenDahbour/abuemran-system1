from decimal import Decimal
from datetime import date, datetime
from typing import Optional, List
from uuid import UUID
from utils.telegram import notify_admin

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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


def parse_invoice_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="تاريخ الفاتورة غير صحيح")


def normalize_payment_method(value: Optional[str]) -> str:
    value = clean_text(value) or "credit"
    allowed = {"cash", "credit", "partial", "check", "transfer"}
    if value not in allowed:
        raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")
    return value


def money3(value) -> float:
    return round(float(value or 0), 3)


def calculate_payment(total: float, payment_method: str, paid_amount: Optional[float]) -> tuple[float, float, str]:
    raw_paid = money3(paid_amount)

    if raw_paid < 0:
        raise HTTPException(status_code=400, detail="المبلغ المدفوع لا يمكن أن يكون سالباً")

    if payment_method == "cash":
        paid = total if raw_paid == 0 else raw_paid
    elif payment_method == "credit":
        paid = 0
    else:
        paid = raw_paid

    paid = money3(paid)

    if paid > total:
        raise HTTPException(status_code=400, detail="المبلغ المدفوع أكبر من إجمالي الفاتورة")

    remaining = money3(total - paid)

    if remaining <= 0 and total > 0:
        status = "paid"
    elif paid > 0:
        status = "partial"
    else:
        status = "debt"

    return paid, remaining, status


async def ensure_client_exists(conn, client_id: int):
    exists = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM clients WHERE id=$1)",
        client_id,
    )
    if not exists:
        raise HTTPException(status_code=400, detail="العميل غير موجود")


async def insert_audit(conn, user, action: str, entity_id: int, detail: str):
    try:
        await conn.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
            VALUES ($1, $2, $3, 'invoice', $4, $5)
            """,
            user.get("id"),
            user.get("full_name") or user.get("username") or "مستخدم",
            action,
            entity_id,
            detail,
        )
    except Exception:
        pass


class InvoiceItem(BaseModel):
    product_id: UUID
    description: Optional[str] = None
    quantity: float
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    package_qty: Optional[float] = 12
    package_price: Optional[float] = None
    pricing_note: Optional[str] = None


class InvoiceRequest(BaseModel):
    client_id: int
    invoice_number: Optional[str] = None
    net_amount: Optional[float] = None
    tax_amount: Optional[float] = 0
    total_amount: Optional[float] = None
    invoice_date: Optional[str] = None
    payment_method: Optional[str] = "credit"
    paid_amount: Optional[float] = 0
    notes: Optional[str] = None
    recipient_name: Optional[str] = None
    items: Optional[List[InvoiceItem]] = Field(default_factory=list)

async def fetch_invoice_items(conn, invoice_id: int):
    rows = await conn.fetch(
        """
        SELECT
            ii.*,
            p.name AS product_name,
            p.unit AS product_unit
        FROM invoice_items ii
        LEFT JOIN products p ON p.id = ii.product_id
        WHERE ii.invoice_id = $1
        ORDER BY ii.id
        """,
        invoice_id,
    )
    return [row_to_dict(i) for i in rows]


def enrich_invoice(inv: dict) -> dict:
    total = money3(inv.get("total_amount") or inv.get("net_amount") or inv.get("amount") or 0)
    paid = money3(inv.get("paid_amount") or 0)
    remaining = max(money3(total - paid), 0)

    inv["paid_amount"] = paid
    inv["remaining_amount"] = remaining

    if remaining <= 0 and total > 0:
        inv["payment_status"] = "paid"
    elif paid > 0:
        inv["payment_status"] = "partial"
    else:
        inv["payment_status"] = "debt"

    return inv


def normalize_items(items: List[InvoiceItem]) -> list[dict]:
    normalized = []

    for item in items:
        quantity = money3(item.quantity)

        if quantity <= 0:
            raise HTTPException(status_code=400, detail="كمية الصنف يجب أن تكون أكبر من صفر")

        line_total = item.line_total
        unit_price = item.unit_price

        if line_total is not None and float(line_total) > 0:
            line_total = money3(line_total)
            unit_price = money3(line_total / quantity)
        else:
            unit_price = money3(unit_price or 0)
            if unit_price < 0:
                raise HTTPException(status_code=400, detail="سعر الصنف لا يمكن أن يكون سالباً")
            line_total = money3(quantity * unit_price)

        if line_total < 0:
            raise HTTPException(status_code=400, detail="إجمالي الصنف لا يمكن أن يكون سالباً")

        package_qty = money3(item.package_qty or 12)
        package_price = item.package_price

        if package_price is None and package_qty > 0 and unit_price > 0:
            package_price = money3(unit_price * package_qty)
        else:
            package_price = money3(package_price or 0)

        normalized.append({
            "product_id": item.product_id,
            "description": clean_text(item.description),
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "package_qty": package_qty,
            "package_price": package_price,
            "pricing_note": clean_text(item.pricing_note),
        })

    return normalized

async def delete_auto_payment_for_invoice(conn, invoice_id: int):
    marker = f"%invoice_id:{invoice_id}%"
    await conn.execute(
        """
        DELETE FROM payments
        WHERE invoice_id = $1
           OR COALESCE(notes, '') ILIKE $2
        """,
        invoice_id,
        marker,
    )

async def restore_stock_from_invoice_items(conn, invoice_id: int, user):
    old_items = await conn.fetch(
        """
        SELECT ii.*, p.name AS product_name
        FROM invoice_items ii
        LEFT JOIN products p ON p.id = ii.product_id
        WHERE ii.invoice_id=$1
        """,
        invoice_id,
    )

    for item in old_items:
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
            quantity = money3(item["quantity"] or 0)
            old_stock = money3(product["current_stock"] or 0)
            new_stock = money3(old_stock + quantity)

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
                  ($1, 'in', $2, 'invoice_restore', $3, $4)
                """,
                item["product_id"],
                quantity,
                f"إرجاع مخزون بسبب تعديل/حذف فاتورة",
                safe_uuid(user.get("id")),
            )


async def insert_invoice_items_and_deduct_stock(conn, invoice_id: int, invoice_number: str, items: list[dict], user):
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

        if not product:
            raise HTTPException(status_code=400, detail=f"الصنف رقم {item['product_id']} غير موجود")

        current_stock = money3(product["current_stock"] or 0)
        new_stock = money3(current_stock - item["quantity"])

        if new_stock < 0:
            raise HTTPException(
                status_code=400,
                detail=f"المخزون غير كافٍ للصنف {product['name']} — المتوفر {current_stock}",
            )

        await conn.execute(
            """
            INSERT INTO invoice_items
              (invoice_id, product_id, description, quantity, unit_price, line_total,
               package_qty, package_price, pricing_note)
            VALUES
              ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            invoice_id,
            item["product_id"],
            item["description"],
            item["quantity"],
            item["unit_price"],
            item["line_total"],
            item["package_qty"],
            item["package_price"],
            item["pricing_note"],
        )

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
              ($1, 'out', $2, 'invoice', $3, $4)
            """,
            item["product_id"],
            item["quantity"],
            f"خصم بسبب فاتورة مبيعات #{invoice_number}",
            user.get("id"),
        )

async def insert_auto_payment(conn, data: InvoiceRequest, invoice_id: int, invoice_number: str, paid: float, invoice_date: date, payment_method: str, user):
    if paid <= 0:
        return

    await conn.execute(
        """
        INSERT INTO payments
          (client_id, invoice_id, submitted_by, approved_by, amount, status, notes, payment_date, approved_at)
        VALUES
          ($1, $2, $3, $4, $5, 'approved', $6, $7, NOW())
        """,
        data.client_id,
        invoice_id,
        user.get("id"),
        user.get("id"),
        paid,
        f"دفعة تلقائية من فاتورة #{invoice_number} | invoice_id:{invoice_id} | method:{payment_method}",
        invoice_date,
    )

@router.get("/")
async def get_invoices(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        if user.get("role") == "client":
            rows = await pool.fetch(
                """
                SELECT inv.*, c.name AS client_name,
                       COALESCE((
                         SELECT SUM(p.amount)
                         FROM payments p
                         WHERE p.client_id = inv.client_id
                           AND p.status = 'approved'
                           AND (
                             p.invoice_id = inv.id
                             OR COALESCE(p.notes, '') ILIKE ('%invoice_id:' || inv.id::text || '%')
                           )
                       ), 0) AS paid_amount
                FROM invoices inv
                JOIN clients c ON inv.client_id = c.id
                WHERE inv.client_id = $1
                ORDER BY inv.date DESC, inv.id DESC
                """,
                user.get("client_id"),
            )
        else:
            rows = await pool.fetch(
                """
                SELECT inv.*, c.name AS client_name, u.full_name AS created_by_name,
                       COALESCE((
                         SELECT SUM(p.amount)
                         FROM payments p
                         WHERE p.client_id = inv.client_id
                           AND p.status = 'approved'
                           AND (
                             p.invoice_id = inv.id
                             OR COALESCE(p.notes, '') ILIKE ('%invoice_id:' || inv.id::text || '%')
                           )
                       ), 0) AS paid_amount
                FROM invoices inv
                JOIN clients c ON inv.client_id = c.id
                LEFT JOIN users u ON inv.created_by = u.id
                ORDER BY inv.date DESC, inv.id DESC
                """
            )

        result = []
        async with pool.acquire() as conn:
            for row in rows:
                inv = enrich_invoice(row_to_dict(row))
                inv["items"] = await fetch_invoice_items(conn, row["id"])
                result.append(inv)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الفواتير: {str(e)}")

@router.post("/")
async def create_invoice(data: InvoiceRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant", "employee")

    if not data.client_id:
        raise HTTPException(status_code=400, detail="العميل مطلوب")

    items = normalize_items(data.items or [])

    if items:
        net = money3(sum(item["line_total"] for item in items))
    else:
        net = money3(data.net_amount or 0)

    tax = money3(data.tax_amount or 0)
    total = money3(data.total_amount) if data.total_amount is not None else money3(net + tax)

    if net <= 0:
        raise HTTPException(status_code=400, detail="المبلغ الصافي يجب أن يكون أكبر من صفر")
    if tax < 0:
        raise HTTPException(status_code=400, detail="الضريبة لا يمكن أن تكون سالبة")
    if total <= 0:
        raise HTTPException(status_code=400, detail="إجمالي الفاتورة غير صحيح")

    payment_method = normalize_payment_method(data.payment_method)
    paid, remaining, payment_status = calculate_payment(total, payment_method, data.paid_amount)

    invoice_number = clean_text(data.invoice_number) or f"INV-{int(datetime.now().timestamp() * 1000)}"
    invoice_date = parse_invoice_date(data.invoice_date)

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await ensure_client_exists(conn, data.client_id)

                inv = await conn.fetchrow(
                    """
                    INSERT INTO invoices
                      (client_id, invoice_number, amount, net_amount, tax_amount, total_amount,
                       date, payment_method, notes, recipient_name, created_by)
                    VALUES
                      ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING *
                    """,
                    data.client_id,
                    invoice_number,
                    net,
                    net,
                    tax,
                    total,
                    invoice_date,
                    payment_method,
                    clean_text(data.notes),
                    clean_text(data.recipient_name),
                    user.get("id"),
                )

                await insert_invoice_items_and_deduct_stock(conn, inv["id"], invoice_number, items, user)
                await insert_auto_payment(conn, data, inv["id"], invoice_number, paid, invoice_date, payment_method, user)

                await insert_audit(
                    conn,
                    user,
                    "أضاف فاتورة",
                    inv["id"],
                    f"فاتورة #{invoice_number} — الإجمالي {total:.3f} — المدفوع {paid:.3f} — الباقي {remaining:.3f}",
                )

                out = enrich_invoice(row_to_dict(inv))
                out["paid_amount"] = paid
                out["remaining_amount"] = remaining
                out["payment_status"] = payment_status
                out["items"] = await fetch_invoice_items(conn, inv["id"])
                return out

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{invoice_id}")
async def update_invoice(invoice_id: int, data: InvoiceRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    if not data.client_id:
        raise HTTPException(status_code=400, detail="العميل مطلوب")

    items = normalize_items(data.items or [])

    if items:
        net = money3(sum(item["line_total"] for item in items))
    else:
        net = money3(data.net_amount or 0)

    tax = money3(data.tax_amount or 0)
    total = money3(data.total_amount) if data.total_amount is not None else money3(net + tax)

    if net <= 0:
        raise HTTPException(status_code=400, detail="المبلغ الصافي يجب أن يكون أكبر من صفر")
    if total <= 0:
        raise HTTPException(status_code=400, detail="إجمالي الفاتورة غير صحيح")

    payment_method = normalize_payment_method(data.payment_method)
    paid, remaining, payment_status = calculate_payment(total, payment_method, data.paid_amount)

    invoice_number = clean_text(data.invoice_number) or f"INV-{invoice_id}"
    invoice_date = parse_invoice_date(data.invoice_date)

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                invoice = await conn.fetchrow(
                    """
                    SELECT id, invoice_number
                    FROM invoices
                    WHERE id=$1
                    FOR UPDATE
                    """,
                    invoice_id,
                )

                if not invoice:
                    raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")

                await ensure_client_exists(conn, data.client_id)

                await restore_stock_from_invoice_items(conn, invoice_id, user)
                await delete_auto_payment_for_invoice(conn, invoice_id)
                await conn.execute("DELETE FROM invoice_items WHERE invoice_id=$1", invoice_id)

                updated = await conn.fetchrow(
                    """
                    UPDATE invoices
                    SET client_id=$1,
                        invoice_number=$2,
                        amount=$3,
                        net_amount=$4,
                        tax_amount=$5,
                        total_amount=$6,
                        date=$7,
                        payment_method=$8,
                        notes=$9,
                        recipient_name=$10
                    WHERE id=$11
                    RETURNING *
                    """,
                    data.client_id,
                    invoice_number,
                    net,
                    net,
                    tax,
                    total,
                    invoice_date,
                    payment_method,
                    clean_text(data.notes),
                    clean_text(data.recipient_name),
                    invoice_id,
                )

                await insert_invoice_items_and_deduct_stock(conn, invoice_id, invoice_number, items, user)
                await insert_auto_payment(conn, data, invoice_id, invoice_number, paid, invoice_date, payment_method, user)

                await insert_audit(
                    conn,
                    user,
                    "تعديل فاتورة",
                    invoice_id,
                    f"تعديل فاتورة #{invoice_number} — الإجمالي {total:.3f} — المدفوع {paid:.3f} — الباقي {remaining:.3f}",
                )

                out = enrich_invoice(row_to_dict(updated))
                out["paid_amount"] = paid
                out["remaining_amount"] = remaining
                out["payment_status"] = payment_status
                out["items"] = await fetch_invoice_items(conn, invoice_id)
                return out

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{invoice_id}")
async def delete_invoice(invoice_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                invoice = await conn.fetchrow(
                    """
                    SELECT id, invoice_number
                    FROM invoices
                    WHERE id=$1
                    FOR UPDATE
                    """,
                    invoice_id,
                )

                if not invoice:
                    raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")

                await restore_stock_from_invoice_items(conn, invoice_id, user)
                await delete_auto_payment_for_invoice(conn, invoice_id)

                await conn.execute("DELETE FROM invoice_items WHERE invoice_id=$1", invoice_id)
                await conn.execute("DELETE FROM invoices WHERE id=$1", invoice_id)

                await insert_audit(
                    conn,
                    user,
                    "حذف فاتورة",
                    invoice_id,
                    f"حذف فاتورة #{invoice['invoice_number']} وإرجاع مخزونها وحذف دفعتها التلقائية إن وجدت",
                )

                return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))