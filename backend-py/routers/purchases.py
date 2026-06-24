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


def parse_purchase_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="تاريخ فاتورة الشراء غير صحيح")


def coerce_id(val):
    """Convert to int if possible, otherwise UUID — matches whatever the live DB uses."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        pass
    return safe_uuid(val) or val


def parse_int_id(val, label="المعرّف"):
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"{label} غير صحيح")


async def insert_audit(conn, user, action: str, entity_id, detail: str):
    audit_entity_id = entity_id if isinstance(entity_id, int) else None
    try:
        await conn.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
            VALUES ($1, $2, $3, 'purchase', $4, $5)
            """,
            user.get("id"),
            user.get("full_name") or user.get("username") or "مستخدم",
            action,
            audit_entity_id,
            detail,
        )
    except Exception:
        pass


class PurchaseItem(BaseModel):
    product_id: str
    quantity: float
    unit_price: float


class PurchaseRequest(BaseModel):
    supplier_id: Optional[str] = None
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    notes: Optional[str] = None
    items: List[PurchaseItem] = Field(default_factory=list)


@router.get("")
async def get_purchases(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch("""
            SELECT p.*, s.name AS supplier_name, u.full_name AS created_by_name
            FROM purchases p
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            LEFT JOIN users u ON p.created_by = u.id
            ORDER BY p.created_at DESC, p.id DESC
            """)

        item_rows = await pool.fetch("""
            SELECT pi.*, pr.name AS product_name, pr.unit AS product_unit
            FROM purchase_items pi
            JOIN products pr ON pi.product_id = pr.id
            ORDER BY pi.purchase_id, pi.id ASC
            """)

        items_by_purchase = {}
        for item in item_rows:
            pid = item["purchase_id"]
            if pid not in items_by_purchase:
                items_by_purchase[pid] = []
            items_by_purchase[pid].append(row_to_dict(item))

        results = []
        for row in rows:
            purchase = row_to_dict(row)
            purchase["items"] = items_by_purchase.get(row["id"], [])
            results.append(purchase)

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_purchase(data: PurchaseRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    if not data.items:
        raise HTTPException(status_code=400, detail="أضف صنفاً واحداً على الأقل")

    invoice_number = (
        clean_text(data.invoice_number)
        or f"PUR-{int(datetime.now().timestamp() * 1000)}"
    )
    purchase_date = parse_purchase_date(data.date)
    notes = clean_text(data.notes)
    supplier_id = coerce_id(data.supplier_id) if data.supplier_id else None

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                if supplier_id is not None:
                    supplier_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM suppliers WHERE id=$1)",
                        supplier_id,
                    )

                    if not supplier_exists:
                        raise HTTPException(status_code=400, detail="المورد غير موجود")

                total = 0.0

                for item in data.items:
                    quantity = float(item.quantity)
                    unit_price = float(item.unit_price)

                    if quantity <= 0:
                        raise HTTPException(
                            status_code=400, detail="كمية الصنف يجب أن تكون أكبر من صفر"
                        )

                    if unit_price < 0:
                        raise HTTPException(
                            status_code=400, detail="سعر الصنف لا يمكن أن يكون سالباً"
                        )

                    product_uuid = safe_uuid(item.product_id)

                    product_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM products WHERE id=$1)",
                        product_uuid,
                    )

                    if not product_exists:
                        raise HTTPException(
                            status_code=400,
                            detail=f"الصنف رقم {item.product_id} غير موجود",
                        )

                    total += quantity * unit_price

                purchase = await conn.fetchrow(
                    """
                    INSERT INTO purchases (supplier_id, invoice_number, date, total, notes, created_by, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                    RETURNING *
                    """,
                    supplier_id,
                    invoice_number,
                    purchase_date,
                    total,
                    notes,
                    user.get("id"),
                )

                for item in data.items:
                    product_uuid = safe_uuid(item.product_id)
                    await conn.execute(
                        """
                        INSERT INTO purchase_items (purchase_id, product_id, quantity, unit_price)
                        VALUES ($1, $2, $3, $4)
                        """,
                        purchase["id"],
                        product_uuid,
                        float(item.quantity),
                        float(item.unit_price),
                    )

                await insert_audit(
                    conn,
                    user,
                    "إنشاء فاتورة شراء",
                    purchase["id"],
                    f"فاتورة شراء #{invoice_number} â€” {total:.2f} د.أ",
                )

                return row_to_dict(purchase)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{purchase_id}/receive")
async def receive_purchase(purchase_id: str, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    purchase_id = coerce_id(purchase_id)

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                purchase = await conn.fetchrow(
                    "SELECT * FROM purchases WHERE id=$1 FOR UPDATE",
                    purchase_id,
                )

                if not purchase:
                    raise HTTPException(
                        status_code=404, detail="فاتورة الشراء غير موجودة"
                    )

                if purchase["status"] != "pending":
                    raise HTTPException(
                        status_code=400,
                        detail="لا يمكن استلام هذه الفاتورة لأنها ليست معلّقة أو تم استلامها مسبقاً",
                    )

                await conn.execute(
                    "DELETE FROM stock_movements WHERE source_type='purchase' AND source_id::text = $1",
                    str(purchase_id),
                )

                items = await conn.fetch(
                    "SELECT * FROM purchase_items WHERE purchase_id=$1 ORDER BY id ASC",
                    purchase_id,
                )

                if not items:
                    raise HTTPException(
                        status_code=400, detail="لا توجد أصناف في فاتورة الشراء"
                    )

                for item in items:
                    product = await conn.fetchrow(
                        "SELECT id, name, current_stock FROM products WHERE id=$1 FOR UPDATE",
                        item["product_id"],
                    )

                    if not product:
                        raise HTTPException(
                            status_code=400,
                            detail=f"الصنف رقم {item['product_id']} غير موجود",
                        )

                    quantity = float(item["quantity"] or 0)

                    if quantity <= 0:
                        raise HTTPException(
                            status_code=400, detail="كمية غير صحيحة داخل فاتورة الشراء"
                        )

                    old_stock = float(product["current_stock"] or 0)
                    new_stock = old_stock + quantity
                    new_cost_price = float(item["unit_price"] or 0)

                    if new_cost_price > 0:
                        await conn.execute(
                            """
                            UPDATE products
                            SET current_stock=$1, cost_price=$2, base_price=$2
                            WHERE id=$3
                            """,
                            new_stock,
                            new_cost_price,
                            item["product_id"],
                        )
                    else:
                        await conn.execute(
                            "UPDATE products SET current_stock=$1 WHERE id=$2",
                            new_stock,
                            item["product_id"],
                        )

                    await conn.execute(
                        """
                        INSERT INTO stock_movements
                          (product_id, type, quantity, source_type, source_id, notes, created_by)
                        VALUES
                          ($1, 'in', $2, 'purchase', $3, $4, $5)
                        """,
                        item["product_id"],
                        quantity,
                        purchase_id,
                        f"استلام مشتريات #{purchase['invoice_number']}",
                        user.get("id"),
                    )

                updated_purchase = await conn.fetchrow(
                    "UPDATE purchases SET status='received' WHERE id=$1 RETURNING *",
                    purchase_id,
                )

                await insert_audit(
                    conn,
                    user,
                    "استلام مشتريات",
                    purchase_id,
                    f"استلام فاتورة شراء #{purchase['invoice_number']}",
                )

                return row_to_dict(updated_purchase)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{purchase_id}")
async def update_purchase(purchase_id: str, data: PurchaseRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    purchase_id = coerce_id(purchase_id)

    if not data.items:
        raise HTTPException(status_code=400, detail="أضف صنفاً واحداً على الأقل")

    pool = await get_pool()
    supplier_id = coerce_id(data.supplier_id) if data.supplier_id else None

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                purchase = await conn.fetchrow(
                    "SELECT * FROM purchases WHERE id=$1 FOR UPDATE",
                    purchase_id,
                )

                if not purchase:
                    raise HTTPException(
                        status_code=404, detail="فاتورة الشراء غير موجودة"
                    )

                if supplier_id is not None:
                    supplier_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM suppliers WHERE id=$1)",
                        supplier_id,
                    )
                    if not supplier_exists:
                        raise HTTPException(status_code=400, detail="المورد غير موجود")

                if purchase["status"] == "received":
                    actual_movements = await conn.fetch(
                        """SELECT product_id, SUM(quantity) AS total_qty
                           FROM stock_movements
                           WHERE source_type='purchase' AND source_id::text = $1
                           GROUP BY product_id""",
                        str(purchase_id),
                    )
                    for mov in actual_movements:
                        await conn.execute(
                            "UPDATE products SET current_stock = GREATEST(0, current_stock - $1) WHERE id = $2",
                            float(mov["total_qty"] or 0),
                            mov["product_id"],
                        )
                    await conn.execute(
                        "DELETE FROM stock_movements WHERE source_type='purchase' AND source_id::text = $1",
                        str(purchase_id),
                    )

                await conn.execute(
                    "DELETE FROM purchase_items WHERE purchase_id=$1", purchase_id
                )

                total = 0.0
                for item in data.items:
                    quantity = float(item.quantity)
                    unit_price = float(item.unit_price)

                    if quantity <= 0:
                        raise HTTPException(
                            status_code=400, detail="كمية الصنف يجب أن تكون أكبر من صفر"
                        )
                    if unit_price < 0:
                        raise HTTPException(
                            status_code=400, detail="سعر الصنف لا يمكن أن يكون سالباً"
                        )

                    product_uuid = safe_uuid(item.product_id)
                    product_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM products WHERE id=$1)",
                        product_uuid,
                    )
                    if not product_exists:
                        raise HTTPException(
                            status_code=400,
                            detail=f"الصنف رقم {item.product_id} غير موجود",
                        )

                    total += quantity * unit_price

                    await conn.execute(
                        """
                        INSERT INTO purchase_items (purchase_id, product_id, quantity, unit_price)
                        VALUES ($1, $2, $3, $4)
                        """,
                        purchase_id,
                        product_uuid,
                        quantity,
                        unit_price,
                    )

                    if purchase["status"] == "received":
                        new_cost = unit_price
                        await conn.execute(
                            """
                            UPDATE products
                            SET current_stock = current_stock + $1
                            """ + (", cost_price = $3, base_price = $3" if new_cost > 0 else "") + """
                            WHERE id = $2
                            """,
                            quantity,
                            product_uuid,
                            *([new_cost] if new_cost > 0 else []),
                        )
                        await conn.execute(
                            """
                            INSERT INTO stock_movements
                              (product_id, type, quantity, source_type, source_id, notes, created_by)
                            VALUES ($1, 'in', $2, 'purchase', $3, $4, $5)
                            """,
                            product_uuid,
                            quantity,
                            purchase_id,
                            f"تعديل مشتريات #{purchase['invoice_number']}",
                            user.get("id"),
                        )

                invoice_number = (
                    clean_text(data.invoice_number) or purchase["invoice_number"]
                )
                purchase_date = parse_purchase_date(data.date) if data.date else purchase["date"]

                updated = await conn.fetchrow(
                    """
                    UPDATE purchases
                    SET supplier_id=$1, invoice_number=$2, date=$3, total=$4, notes=$5
                    WHERE id=$6
                    RETURNING *
                    """,
                    supplier_id,
                    invoice_number,
                    purchase_date,
                    total,
                    clean_text(data.notes),
                    purchase_id,
                )

                await insert_audit(
                    conn,
                    user,
                    "تعديل فاتورة شراء",
                    purchase_id,
                    f"تعديل فاتورة #{invoice_number} — {total:.2f} د.أ",
                )

                return row_to_dict(updated)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{purchase_id}")
async def delete_purchase(purchase_id: str, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    purchase_id = coerce_id(purchase_id)

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                purchase = await conn.fetchrow(
                    "SELECT * FROM purchases WHERE id=$1 FOR UPDATE",
                    purchase_id,
                )

                if not purchase:
                    raise HTTPException(
                        status_code=404, detail="فاتورة الشراء غير موجودة"
                    )

                if purchase["status"] == "received":
                    actual_movements = await conn.fetch(
                        """SELECT product_id, SUM(quantity) AS total_qty
                           FROM stock_movements
                           WHERE source_type='purchase' AND source_id::text = $1
                           GROUP BY product_id""",
                        str(purchase_id),
                    )
                    for mov in actual_movements:
                        await conn.execute(
                            "UPDATE products SET current_stock = GREATEST(0, current_stock - $1) WHERE id = $2",
                            float(mov["total_qty"] or 0),
                            mov["product_id"],
                        )
                    await conn.execute(
                        "DELETE FROM stock_movements WHERE source_type='purchase' AND source_id::text = $1",
                        str(purchase_id),
                    )

                await conn.execute(
                    "DELETE FROM purchase_items WHERE purchase_id=$1", purchase_id
                )
                await conn.execute("DELETE FROM purchases WHERE id=$1", purchase_id)

                await insert_audit(
                    conn,
                    user,
                    "حذف فاتورة شراء",
                    None,
                    f"حذف فاتورة شراء #{purchase['invoice_number']}",
                )

            return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



