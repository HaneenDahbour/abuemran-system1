from decimal import Decimal
from datetime import date, datetime
from typing import Optional, List
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


class WarehouseInvoiceItem(BaseModel):
    product_id: str
    quantity: float
    unit_price: float


class WarehouseInvoiceRequest(BaseModel):
    invoice_number: Optional[str] = None
    category_id: Optional[int] = None
    buyer_name: Optional[str] = None
    supplier_name: Optional[str] = None
    date: Optional[str] = None
    notes: Optional[str] = None
    items: List[WarehouseInvoiceItem]


@router.get("")
async def get_warehouse_invoices(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch("""
            SELECT
                wi.*,
                wc.name AS category_name,
                u.full_name AS issued_by_name
            FROM warehouse_invoices wi
            LEFT JOIN warehouse_categories wc ON wc.id = wi.category_id
            LEFT JOIN users u ON u.id = wi.issued_by
            ORDER BY wi.date DESC, wi.created_at DESC
            """)

        results = []
        for row in rows:
            item = row_to_dict(row)
            items = await pool.fetch(
                """
                SELECT wii.*, p.name AS product_name,
                       (wii.quantity * wii.unit_price) AS total
                FROM warehouse_invoice_items wii
                JOIN products p ON p.id = wii.product_id
                WHERE wii.warehouse_invoice_id = $1
                """,
                row["id"],
            )
            item["items"] = [row_to_dict(i) for i in items]
            results.append(item)

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"تعذر تحميل فواتير المستودع: {str(e)}"
        )


@router.post("")
async def create_warehouse_invoice(
    data: WarehouseInvoiceRequest, user=Depends(get_current_user)
):
    require_role(user, "admin", "accountant")

    if not data.items:
        raise HTTPException(status_code=400, detail="أضف صنفاً على الأقل")

    for item in data.items:
        if not item.product_id or item.quantity <= 0 or item.unit_price < 0:
            raise HTTPException(status_code=400, detail="بيانات أحد الأصناف غير صحيحة")

    pool = await get_pool()
    conn = await pool.acquire()

    try:
        async with conn.transaction():
            total = sum(item.quantity * item.unit_price for item in data.items)
            invoice_number = (
                data.invoice_number or f"WINV-{int(datetime.now().timestamp() * 1000)}"
            )
            invoice_date = date.fromisoformat(data.date) if data.date else date.today()

            inv = await conn.fetchrow(
                """
                INSERT INTO warehouse_invoices
                    (invoice_number, category_id, buyer_name, supplier_name, date, notes, total, issued_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING *
                """,
                invoice_number,
                data.category_id or None,
                data.buyer_name or None,
                data.supplier_name or None,
                invoice_date,
                data.notes or None,
                total,
                user.get("id"),
            )

            for item in data.items:
                product_uuid = safe_uuid(item.product_id)

                await conn.execute(
                    """
                    INSERT INTO warehouse_invoice_items
                        (warehouse_invoice_id, product_id, quantity, unit_price)
                    VALUES ($1, $2, $3, $4)
                    """,
                    inv["id"],
                    product_uuid,
                    item.quantity,
                    item.unit_price,
                )

                await conn.execute(
                    """
                    UPDATE products
                    SET current_stock = GREATEST(0, current_stock - $1)
                    WHERE id = $2
                    """,
                    item.quantity,
                    product_uuid,
                )

                await conn.execute(
                    """
                    INSERT INTO stock_movements
                        (product_id, type, quantity, source_type, source_id, notes, created_by)
                    VALUES ($1, 'out', $2, 'warehouse_invoice', $3, $4, $5)
                    """,
                    product_uuid,
                    item.quantity,
                    inv["id"],
                    f"فاتورة مستودع #{invoice_number}",
                    user.get("id"),
                )

        try:
            await pool.execute(
                """
                INSERT INTO audit_log (user_id, user_name, action, detail)
                VALUES ($1, $2, 'أضاف فاتورة مستودع', $3)
                """,
                user.get("id"),
                user.get("full_name"),
                f"فاتورة #{invoice_number} â€” {total:.2f} د.أ",
            )
        except Exception:
            pass

        return row_to_dict(inv)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"تعذر إنشاء فاتورة المستودع: {str(e)}"
        )

    finally:
        await pool.release(conn)


@router.delete("/{invoice_id}")
async def delete_warehouse_invoice(invoice_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                invoice = await conn.fetchrow(
                    "SELECT * FROM warehouse_invoices WHERE id=$1 FOR UPDATE",
                    invoice_id,
                )
                if not invoice:
                    raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")

                items = await conn.fetch(
                    "SELECT * FROM warehouse_invoice_items WHERE warehouse_invoice_id=$1",
                    invoice_id,
                )

                for item in items:
                    await conn.execute(
                        "UPDATE products SET current_stock = current_stock + $1 WHERE id = $2",
                        float(item["quantity"] or 0),
                        item["product_id"],
                    )

                await conn.execute(
                    "DELETE FROM stock_movements WHERE source_type='warehouse_invoice' AND source_id=$1",
                    invoice_id,
                )
                await conn.execute(
                    "DELETE FROM warehouse_invoice_items WHERE warehouse_invoice_id=$1",
                    invoice_id,
                )
                await conn.execute(
                    "DELETE FROM warehouse_invoices WHERE id=$1",
                    invoice_id,
                )

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر حذف الفاتورة: {str(e)}")

