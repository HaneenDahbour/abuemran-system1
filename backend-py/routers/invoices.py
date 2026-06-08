from decimal import Decimal
from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

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
        raise HTTPException(status_code=400, detail="ØªØ§Ø±ÙŠØ® Ø§Ù„ÙØ§ØªÙˆØ±Ø© ØºÙŠØ± ØµØ­ÙŠØ­")


def normalize_payment_method(value: Optional[str]) -> str:
    value = clean_text(value) or "credit"
    allowed = {"cash", "credit", "partial", "check", "transfer"}
    if value not in allowed:
        raise HTTPException(status_code=400, detail="Ø·Ø±ÙŠÙ‚Ø© Ø§Ù„Ø¯ÙØ¹ ØºÙŠØ± ØµØ­ÙŠØ­Ø©")
    return value


def money3(value) -> float:
    return round(float(value or 0), 3)


def calculate_payment(
    total: float, payment_method: str, paid_amount: Optional[float]
) -> tuple[float, float, str]:
    raw_paid = money3(paid_amount)

    if raw_paid < 0:
        raise HTTPException(
            status_code=400, detail="Ø§Ù„Ù…Ø¨Ù„Øº Ø§Ù„Ù…Ø¯ÙÙˆØ¹ Ù„Ø§ ÙŠÙ…ÙƒÙ† Ø£Ù† ÙŠÙƒÙˆÙ† Ø³Ø§Ù„Ø¨Ø§Ù‹"
        )

    if payment_method == "cash":
        paid = total if raw_paid == 0 else raw_paid
    elif payment_method == "credit":
        paid = 0
    else:
        paid = raw_paid

    paid = money3(paid)

    if paid > total:
        raise HTTPException(
            status_code=400, detail="Ø§Ù„Ù…Ø¨Ù„Øº Ø§Ù„Ù…Ø¯ÙÙˆØ¹ Ø£ÙƒØ¨Ø± Ù…Ù† Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ÙØ§ØªÙˆØ±Ø©"
        )

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
        raise HTTPException(status_code=400, detail="Ø§Ù„Ø¹Ù…ÙŠÙ„ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯")


async def insert_audit(conn, user, action: str, entity_id: int, detail: str):
    try:
        await conn.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
            VALUES ($1, $2, $3, 'invoice', $4, $5)
            """,
            safe_uuid(user.get("id")),
            user.get("full_name") or user.get("username") or "Ù…Ø³ØªØ®Ø¯Ù…",
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
    client_id: Optional[int] = None
    invoice_number: Optional[str] = None
    net_amount: Optional[float] = None
    tax_amount: Optional[float] = 0
    total_amount: Optional[float] = None
    invoice_date: Optional[str] = None
    payment_method: Optional[str] = "credit"
    paid_amount: Optional[float] = 0
    notes: Optional[str] = None
    recipient_name: str
    attributed_employee_id: Optional[int] = None
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
    total = money3(
        inv.get("total_amount") or inv.get("net_amount") or inv.get("amount") or 0
    )
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
            raise HTTPException(
                status_code=400, detail="ÙƒÙ…ÙŠØ© Ø§Ù„ØµÙ†Ù ÙŠØ¬Ø¨ Ø£Ù† ØªÙƒÙˆÙ† Ø£ÙƒØ¨Ø± Ù…Ù† ØµÙØ±"
            )

        line_total = item.line_total
        unit_price = item.unit_price

        if line_total is not None and float(line_total) > 0:
            line_total = money3(line_total)
            unit_price = money3(line_total / quantity)
        else:
            unit_price = money3(unit_price or 0)
            if unit_price < 0:
                raise HTTPException(
                    status_code=400, detail="Ø³Ø¹Ø± Ø§Ù„ØµÙ†Ù Ù„Ø§ ÙŠÙ…ÙƒÙ† Ø£Ù† ÙŠÙƒÙˆÙ† Ø³Ø§Ù„Ø¨Ø§Ù‹"
                )
            line_total = money3(quantity * unit_price)

        if line_total < 0:
            raise HTTPException(
                status_code=400, detail="Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ØµÙ†Ù Ù„Ø§ ÙŠÙ…ÙƒÙ† Ø£Ù† ÙŠÙƒÙˆÙ† Ø³Ø§Ù„Ø¨Ø§Ù‹"
            )

        package_qty = money3(item.package_qty or 12)
        package_price = item.package_price

        if package_price is None and package_qty > 0 and unit_price > 0:
            package_price = money3(unit_price * package_qty)
        else:
            package_price = money3(package_price or 0)

        normalized.append(
            {
                "product_id": item.product_id,
                "description": clean_text(item.description),
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
                "package_qty": package_qty,
                "package_price": package_price,
                "pricing_note": clean_text(item.pricing_note),
            }
        )

    return normalized


async def delete_auto_payment_for_invoice(conn, invoice_id: int):
    marker = f"%invoice_id:{invoice_id}%"

    await conn.execute(
        """
        DELETE FROM recipient_payments
        WHERE invoice_id = $1
           OR COALESCE(notes, '') ILIKE $2
        """,
        invoice_id,
        marker,
    )

    # legacy cleanup from old client-based payments
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
                "Ø¥Ø±Ø¬Ø§Ø¹ Ù…Ø®Ø²ÙˆÙ† Ø¨Ø³Ø¨Ø¨ ØªØ¹Ø¯ÙŠÙ„/Ø­Ø°Ù ÙØ§ØªÙˆØ±Ø©",
                safe_uuid(user.get("id")),
            )


async def insert_invoice_items_and_deduct_stock(
    conn, invoice_id: int, invoice_number: str, items: list[dict], user
):
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
            raise HTTPException(
                status_code=400,
                detail=f"الصنف رقم {item['product_id']} غير موجود",
            )

        quantity = money3(item["quantity"] or 0)
        current_stock = money3(product["current_stock"] or 0)
        new_stock = money3(current_stock - quantity)

        if new_stock < 0:
            raise HTTPException(
                status_code=400,
                detail=f"المخزون غير كافٍ للصنف {product['name']} — المتوفر {current_stock}",
            )

        # ✅ Important: actually deduct from live product quantity
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
            INSERT INTO invoice_items
              (invoice_id, product_id, description, quantity, unit_price, line_total,
               package_qty, package_price, pricing_note)
            VALUES
              ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            invoice_id,
            item["product_id"],
            item["description"],
            quantity,
            item["unit_price"],
            item["line_total"],
            item["package_qty"],
            item["package_price"],
            item["pricing_note"],
        )

        await conn.execute(
            """
            INSERT INTO stock_movements
              (product_id, type, quantity, source_type, notes, created_by)
            VALUES
              ($1, 'out', $2, 'invoice', $3, $4)
            """,
            item["product_id"],
            quantity,
            f"خصم بسبب فاتورة مبيعات #{invoice_number}",
            safe_uuid(user.get("id")),
        )
async def insert_auto_payment(
    conn,
    data: InvoiceRequest,
    invoice_id: int,
    invoice_number: str,
    paid: float,
    invoice_date: date,
    payment_method: str,
    user,
):
    if paid <= 0:
        return

    recipient_name = clean_text(data.recipient_name)
    if not recipient_name:
        raise HTTPException(status_code=400, detail="اسم الزبون / مطلوب من السادة مطلوب")

    await conn.execute(
        """
        INSERT INTO recipient_payments
          (recipient_name, client_id, invoice_id, amount, payment_method,
           payment_date, notes, created_by)
        VALUES
          ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        recipient_name,
        data.client_id,
        invoice_id,
        money3(paid),
        payment_method,
        invoice_date,
        f"دفعة تلقائية من فاتورة #{invoice_number} | invoice_id:{invoice_id} | method:{payment_method}",
        user.get("id"),
    )
async def insert_invoice_items_only(conn, invoice_id: int, items: list[dict]):
    """Save invoice items WITHOUT touching stock â€” for pending invoices."""
    for item in items:
        product_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM products WHERE id=$1)",
            item["product_id"],
        )
        if not product_exists:
            raise HTTPException(
                status_code=400,
                detail=f"Ø§Ù„ØµÙ†Ù Ø±Ù‚Ù… {item['product_id']} ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯",
            )
        await conn.execute(
            """
            INSERT INTO invoice_items
              (invoice_id, product_id, description, quantity, unit_price, line_total,
               package_qty, package_price, pricing_note)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            """,
            invoice_id, item["product_id"], item["description"],
            item["quantity"], item["unit_price"], item["line_total"],
            item["package_qty"], item["package_price"], item["pricing_note"],
        )


async def deduct_stock_for_approved_invoice(conn, invoice_id: int, invoice_number: str, user):
    """Deduct stock for an already-saved invoice's items â€” called on admin approval."""
    items = await conn.fetch(
        """
        SELECT ii.product_id, ii.quantity, p.name AS product_name, p.current_stock
        FROM invoice_items ii
        LEFT JOIN products p ON p.id = ii.product_id
        WHERE ii.invoice_id = $1
        """,
        invoice_id,
    )

    for item in items:
        product = await conn.fetchrow(
            "SELECT id, name, current_stock FROM products WHERE id=$1 FOR UPDATE",
            item["product_id"],
        )
        if not product:
            raise HTTPException(
                status_code=400,
                detail=f"Ø§Ù„ØµÙ†Ù '{item.get('product_name', item['product_id'])}' ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯",
            )

        current = money3(product["current_stock"] or 0)
        qty = money3(item["quantity"] or 0)
        new_stock = money3(current - qty)

        if new_stock < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Ø§Ù„Ù…Ø®Ø²ÙˆÙ† ØºÙŠØ± ÙƒØ§ÙÙ Ù„Ù„ØµÙ†Ù '{product['name']}' â€” Ø§Ù„Ù…ØªÙˆÙØ±: {current:.0f}",
            )

        await conn.execute(
            "UPDATE products SET current_stock=$1 WHERE id=$2",
            new_stock, item["product_id"],
        )
        await conn.execute(
            """
            INSERT INTO stock_movements
              (product_id, type, quantity, source_type, notes, created_by)
            VALUES ($1,'out',$2,'invoice',$3,$4)
            """,
            item["product_id"], qty,
            f"Ø®ØµÙ… Ø¨Ø³Ø¨Ø¨ Ø§Ø¹ØªÙ…Ø§Ø¯ ÙØ§ØªÙˆØ±Ø© #{invoice_number}",
            safe_uuid(user.get("id")),
        )
@router.get("")
async def get_invoices(user=Depends(get_current_user)):
    pool = await get_pool()
    try:
        role = user.get("role")
        paid_sq = """COALESCE((
            SELECT SUM(rp.amount) FROM recipient_payments rp
            WHERE rp.invoice_id = inv.id
        ), 0)"""

        base_select = f"""
            SELECT
                inv.*,
                c.name AS client_name,
                ae.full_name AS attributed_employee_name,
                cb.full_name AS created_by_name,
                {paid_sq} AS paid_amount
            FROM invoices inv
            LEFT JOIN clients c ON inv.client_id = c.id
            LEFT JOIN users ae ON ae.id = inv.attributed_employee_id
            LEFT JOIN users cb ON cb.id = inv.created_by
        """

        if role == "client":
            rows = await pool.fetch(f"""
                {base_select}
                WHERE inv.client_id = $1
                  AND COALESCE(inv.status,'approved') = 'approved'
                ORDER BY inv.date DESC, inv.id DESC
            """, user.get("client_id"))

        elif role == "employee":
            rows = await pool.fetch(f"""
                {base_select}
                WHERE inv.attributed_employee_id = $1
                   OR inv.created_by = $1
                ORDER BY inv.date DESC, inv.id DESC
            """, user.get("id"))

        else:
            rows = await pool.fetch(f"""
                {base_select}
                ORDER BY
                  CASE COALESCE(inv.status,'approved')
                    WHEN 'pending' THEN 0
                    WHEN 'approved' THEN 1
                    ELSE 2
                  END,
                  inv.date DESC,
                  inv.id DESC
            """)

        result = []
        async with pool.acquire() as conn:
            for row in rows:
                inv = enrich_invoice(row_to_dict(row))
                inv["items"] = await fetch_invoice_items(conn, row["id"])
                result.append(inv)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الفواتير: {str(e)}")
@router.post("")
async def create_invoice(data: InvoiceRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant", "employee")

    recipient_name = clean_text(data.recipient_name)
    if not recipient_name:
     raise HTTPException(status_code=400, detail="اسم الزبون / مطلوب من السادة مطلوب")

    items = normalize_items(data.items or [])

    if items:
        net = money3(sum(item["line_total"] for item in items))
    else:
        net = money3(data.net_amount or 0)

    tax = money3(data.tax_amount or 0)
    total = (
        money3(data.total_amount)
        if data.total_amount is not None
        else money3(net + tax)
    )

    if net <= 0:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ù…Ø¨Ù„Øº Ø§Ù„ØµØ§ÙÙŠ ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø£ÙƒØ¨Ø± Ù…Ù† ØµÙØ±")
    if tax < 0:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ø¶Ø±ÙŠØ¨Ø© Ù„Ø§ ÙŠÙ…ÙƒÙ† Ø£Ù† ØªÙƒÙˆÙ† Ø³Ø§Ù„Ø¨Ø©")
    if total <= 0:
        raise HTTPException(status_code=400, detail="Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ÙØ§ØªÙˆØ±Ø© ØºÙŠØ± ØµØ­ÙŠØ­")

    payment_method = normalize_payment_method(data.payment_method)
    paid, remaining, payment_status = calculate_payment(total, payment_method, data.paid_amount)

    invoice_number = (
        clean_text(data.invoice_number)
        or f"INV-{int(datetime.now().timestamp() * 1000)}"
    )
    invoice_date = parse_invoice_date(data.invoice_date)

    # Employees create pending invoices; admin/accountant approve immediately
    role = user.get("role", "employee")
    invoice_status = "pending"

    if role == "employee":
        attributed_employee_id = user.get("id")
    else:
        attributed_employee_id = data.attributed_employee_id or user.get("id")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                if data.client_id:
                    await ensure_client_exists(conn, data.client_id)

                inv = await conn.fetchrow(
                    """
                    INSERT INTO invoices
                    (client_id, invoice_number, amount, net_amount, tax_amount, total_amount,
                    date, payment_method, notes, recipient_name, created_by,
                    attributed_employee_id, status, approved_by, approved_at,
                    initial_paid_amount, invoice_writer_name)
                    VALUES
                    ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
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
                    recipient_name,
                    user.get("id"),
                    attributed_employee_id,
                    invoice_status,
                    user.get("id") if invoice_status == "approved" else None,
                    datetime.now() if invoice_status == "approved" else None,
                    paid,
                    None,
                )

                if invoice_status == "approved":
                    # Immediate: deduct stock + auto-payment (existing behaviour)
                    await insert_invoice_items_and_deduct_stock(
                        conn, inv["id"], invoice_number, items, user
                    )
                    await insert_auto_payment(
                        conn, data, inv["id"], invoice_number, paid,
                        invoice_date, payment_method, user,
                    )
                else:
                    # Pending: save items only, stock untouched until approval
                    await insert_invoice_items_only(conn, inv["id"], items)
                    try:
                        await conn.execute(
                            """
                            INSERT INTO notifications (role, message, type)
                            VALUES ('admin', $1, 'pending')
                            """,
                            f"ðŸ“‹ ÙØ§ØªÙˆØ±Ø© Ø¬Ø¯ÙŠØ¯Ø© Ø¨Ø§Ù†ØªØ¸Ø§Ø± Ù…ÙˆØ§ÙÙ‚ØªÙƒ | #{invoice_number} | {user.get('full_name')} | {total:.3f} Ø¯.Ø£",
                        )
                    except Exception:
                        pass

                await insert_audit(
                    conn, user, "Ø£Ø¶Ø§Ù ÙØ§ØªÙˆØ±Ø©", inv["id"],
                    f"ÙØ§ØªÙˆØ±Ø© #{invoice_number} â€” {total:.3f} â€” Ø§Ù„Ø­Ø§Ù„Ø©: {invoice_status}",
                )

                out = enrich_invoice(row_to_dict(inv))
                out["paid_amount"] = paid if invoice_status == "approved" else 0
                out["remaining_amount"] = remaining if invoice_status == "approved" else total
                out["payment_status"] = payment_status if invoice_status == "approved" else "debt"
                out["items"] = await fetch_invoice_items(conn, inv["id"])
                emp_name = await conn.fetchval(
                    "SELECT full_name FROM users WHERE id=$1",
                    attributed_employee_id,
                )

                out["attributed_employee_id"] = attributed_employee_id
                out["attributed_employee_name"] = emp_name or user.get("full_name")
                out["created_by_name"] = user.get("full_name")
                return out

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{invoice_id}")
async def update_invoice(
    invoice_id: int, data: InvoiceRequest, user=Depends(get_current_user)
):
    require_role(user, "admin", "accountant")

    recipient_name = clean_text(data.recipient_name)
    if not recipient_name:
        raise HTTPException(status_code=400, detail="اسم الزبون / مطلوب من السادة مطلوب")

    items = normalize_items(data.items or [])

    if items:
        net = money3(sum(item["line_total"] for item in items))
    else:
        net = money3(data.net_amount or 0)

    tax = money3(data.tax_amount or 0)
    total = (
        money3(data.total_amount)
        if data.total_amount is not None
        else money3(net + tax)
    )

    if net <= 0:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ù…Ø¨Ù„Øº Ø§Ù„ØµØ§ÙÙŠ ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø£ÙƒØ¨Ø± Ù…Ù† ØµÙØ±")
    if total <= 0:
        raise HTTPException(status_code=400, detail="Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ÙØ§ØªÙˆØ±Ø© ØºÙŠØ± ØµØ­ÙŠØ­")

    payment_method = normalize_payment_method(data.payment_method)
    paid, remaining, payment_status = calculate_payment(total, payment_method, data.paid_amount)

    invoice_number = clean_text(data.invoice_number) or f"INV-{invoice_id}"
    invoice_date = parse_invoice_date(data.invoice_date)

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                invoice = await conn.fetchrow(
                    "SELECT id, invoice_number, status FROM invoices WHERE id=$1 FOR UPDATE",
                    invoice_id,
                )
                if not invoice:
                    raise HTTPException(status_code=404, detail="Ø§Ù„ÙØ§ØªÙˆØ±Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø©")

                current_status = invoice.get("status") or "approved"
                if current_status == "rejected":
                    raise HTTPException(status_code=400, detail="Ù„Ø§ ÙŠÙ…ÙƒÙ† ØªØ¹Ø¯ÙŠÙ„ ÙØ§ØªÙˆØ±Ø© Ù…Ø±ÙÙˆØ¶Ø©")

                await ensure_client_exists(conn, data.client_id)

                # Handle items based on current status
                if current_status == "approved":
                    # Restore old stock, delete old payment, then re-insert with new stock
                    await restore_stock_from_invoice_items(conn, invoice_id, user)
                    await delete_auto_payment_for_invoice(conn, invoice_id)

                await conn.execute("DELETE FROM invoice_items WHERE invoice_id=$1", invoice_id)

                updated = await conn.fetchrow(
                    """
                    UPDATE invoices
                    SET client_id=$1, invoice_number=$2, amount=$3, net_amount=$4,
                        tax_amount=$5, total_amount=$6, date=$7, payment_method=$8,
                        notes=$9, recipient_name=$10, initial_paid_amount=$11,
attributed_employee_id=$12                    WHERE id=$13
                    RETURNING *
                    """,
                    data.client_id,
                    invoice_number,
                    net, net, tax, total,
                    invoice_date,
                    payment_method,
                    clean_text(data.notes),
                    recipient_name,
                    paid,
                    data.attributed_employee_id or user.get("id"),                    invoice_id,
                )

                if current_status == "approved":
                    await insert_invoice_items_and_deduct_stock(
                        conn, invoice_id, invoice_number, items, user
                    )
                    await insert_auto_payment(
                        conn, data, invoice_id, invoice_number, paid,
                        invoice_date, payment_method, user,
                    )
                else:
                    # Still pending: just update items, no stock touch
                    await insert_invoice_items_only(conn, invoice_id, items)

                await insert_audit(
                    conn, user, "ØªØ¹Ø¯ÙŠÙ„ ÙØ§ØªÙˆØ±Ø©", invoice_id,
                    f"ØªØ¹Ø¯ÙŠÙ„ ÙØ§ØªÙˆØ±Ø© #{invoice_number} â€” {total:.3f}",
                )

                out = enrich_invoice(row_to_dict(updated))
                out["paid_amount"] = paid if current_status == "approved" else 0
                out["remaining_amount"] = remaining if current_status == "approved" else total
                out["payment_status"] = payment_status if current_status == "approved" else "debt"
                out["items"] = await fetch_invoice_items(conn, invoice_id)
                return out

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# POST /api/invoices/{invoice_id}/approve
@router.post("/{invoice_id}/approve")
async def approve_invoice(invoice_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                invoice = await conn.fetchrow(
                    """
                    SELECT inv.*, c.name AS client_name
                    FROM invoices inv
                    JOIN clients c ON c.id = inv.client_id
                    WHERE inv.id=$1
                    FOR UPDATE
                    """,
                    invoice_id,
                )

                if not invoice:
                    raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")

                if (invoice["status"] or "approved") != "pending":
                    raise HTTPException(
                        status_code=400,
                        detail="يمكن اعتماد الفواتير المعلّقة فقط",
                    )

                invoice_number = invoice["invoice_number"]
                invoice_date = invoice["date"] or date.today()
                payment_method = normalize_payment_method(invoice["payment_method"])
                total = money3(invoice["total_amount"] or invoice["net_amount"] or 0)

                # For pending invoices, stock is deducted only now
                await deduct_stock_for_approved_invoice(
                    conn,
                    invoice_id,
                    invoice_number,
                    user,
                )

                # Calculate payment after approval
                # cash = fully paid, credit = 0, others need manual payment unless stored later
                if payment_method == "cash":
                    paid = total
                else:
                    paid = 0

                paid = money3(paid)
                remaining = money3(total - paid)

                # Create approved automatic payment for cash invoices
                if paid > 0:
                                    await conn.execute(
                                        """
                                        INSERT INTO recipient_payments
                                        (recipient_name, client_id, invoice_id, amount, payment_method,
                                        payment_date, notes, created_by)
                                        VALUES
                                        ($1, $2, $3, $4, $5, $6, $7, $8)
                                        """,
                                        invoice["recipient_name"],
                                        invoice["client_id"],
                                        invoice_id,
                                        paid,
                                        payment_method,
                                        invoice_date,
                                        f"دفعة تلقائية عند اعتماد فاتورة #{invoice_number}",
                                        safe_uuid(user.get("id")),
                                    )

                updated = await conn.fetchrow(
                    """
                    UPDATE invoices
                    SET status='approved',
                        approved_by=$1,
                        approved_at=NOW()
                    WHERE id=$2
                    RETURNING *
                    """,
                    safe_uuid(user.get("id")),
                    invoice_id,
                )

                try:
                    await conn.execute(
                        """
                        INSERT INTO notifications (user_id, message, type)
                        VALUES ($1, $2, 'approved')
                        """,
                        invoice["created_by"],
                        f"✅ تمت الموافقة على فاتورتك #{invoice_number} — تم خصم المخزون",
                    )
                except Exception:
                    pass

                await insert_audit(
                    conn,
                    user,
                    "اعتمد فاتورة",
                    invoice_id,
                    f"اعتماد فاتورة #{invoice_number} — تم خصم المخزون",
                )

                out = enrich_invoice(row_to_dict(updated))
                out["client_name"] = invoice["client_name"]
                out["paid_amount"] = paid
                out["remaining_amount"] = remaining

                if remaining <= 0 and total > 0:
                    out["payment_status"] = "paid"
                elif paid > 0:
                    out["payment_status"] = "partial"
                else:
                    out["payment_status"] = "debt"

                out["items"] = await fetch_invoice_items(conn, invoice_id)
                return out

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# POST /api/invoices/{invoice_id}/reject
@router.post("/{invoice_id}/reject")
async def reject_invoice(invoice_id: int, data: dict, user=Depends(get_current_user)):
    require_role(user, "admin")

    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="سبب الرفض مطلوب")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                invoice = await conn.fetchrow(
                    "SELECT * FROM invoices WHERE id=$1 FOR UPDATE",
                    invoice_id,
                )

                if not invoice:
                    raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")

                current_status = invoice["status"] or "approved"

                if current_status != "pending":
                    raise HTTPException(
                        status_code=400,
                        detail="يمكن رفض وحذف الفواتير المعلّقة فقط",
                    )

                # Pending invoice did not touch stock, so safe delete
                await conn.execute(
                    "DELETE FROM invoice_items WHERE invoice_id=$1",
                    invoice_id,
                )

                await conn.execute(
                    "DELETE FROM invoices WHERE id=$1",
                    invoice_id,
                )

                try:
                    await conn.execute(
                        """
                        INSERT INTO notifications (user_id, message, type)
                        VALUES ($1, $2, 'rejected')
                        """,
                        invoice["created_by"],
                        f"✗ رُفضت فاتورتك #{invoice['invoice_number']} وتم حذفها — السبب: {reason}",
                    )
                except Exception:
                    pass

                await insert_audit(
                    conn,
                    user,
                    "رفض وحذف فاتورة",
                    invoice_id,
                    f"رفض وحذف فاتورة #{invoice['invoice_number']} — السبب: {reason}",
                )

                return {
                    "success": True,
                    "deleted": True,
                    "message": "تم رفض الفاتورة وحذفها لأنها كانت معلّقة",
                }

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
                    "SELECT id, invoice_number, status FROM invoices WHERE id=$1 FOR UPDATE",
                    invoice_id,
                )
                if not invoice:
                    raise HTTPException(status_code=404, detail="Ø§Ù„ÙØ§ØªÙˆØ±Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø©")

                current_status = invoice.get("status") or "approved"

                # Only restore stock for approved invoices (stock was actually deducted)
                if current_status == "approved":
                    await restore_stock_from_invoice_items(conn, invoice_id, user)
                    await delete_auto_payment_for_invoice(conn, invoice_id)

                await conn.execute("DELETE FROM invoice_items WHERE invoice_id=$1", invoice_id)
                await conn.execute("DELETE FROM invoices WHERE id=$1", invoice_id)

                await insert_audit(
                    conn, user, "Ø­Ø°Ù ÙØ§ØªÙˆØ±Ø©", invoice_id,
                    f"Ø­Ø°Ù ÙØ§ØªÙˆØ±Ø© #{invoice['invoice_number']} (ÙƒØ§Ù†Øª: {current_status})",
                )

                return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

