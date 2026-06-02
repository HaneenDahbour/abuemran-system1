import json
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role
from uuid import UUID


def safe_uuid(val):
    try:
        return UUID(str(val))
    except (ValueError, AttributeError, TypeError):
        return None


router = APIRouter()


def to_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def row_to_dict(row):
    return {key: to_json_value(row[key]) for key in row.keys()}


def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def require_warehouse_editor(user):
    require_role(user, "admin", "accountant", "employee")


async def insert_audit(conn, user, action: str, detail: str):
    await conn.execute(
        """
        INSERT INTO audit_log (user_id, user_name, action, detail)
        VALUES ($1, $2, $3, $4)
        """,
        safe_uuid(user.get("id")),
        user.get("full_name") or user.get("username") or "مستخدم",
        action,
        detail,
    )


async def ensure_category_exists(conn, category_id: Optional[int]):
    if category_id is None:
        return

    exists = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM warehouse_categories WHERE id=$1)",
        category_id,
    )

    if not exists:
        raise HTTPException(status_code=400, detail="الفئة المختارة غير موجودة")


async def ensure_sku_unique(conn, sku: Optional[str], exclude_product_id: Optional[UUID] = None):
    sku = clean_text(sku)
    if not sku:
        return

    if exclude_product_id:
        row = await conn.fetchrow(
            """
            SELECT id, name
            FROM products
            WHERE LOWER(sku) = LOWER($1)
              AND id <> $2
            LIMIT 1
            """,
            sku,
            exclude_product_id,
        )
    else:
        row = await conn.fetchrow(
            """
            SELECT id, name
            FROM products
            WHERE LOWER(sku) = LOWER($1)
            LIMIT 1
            """,
            sku,
        )

    if row:
        raise HTTPException(
            status_code=400,
            detail=f"الكود مستخدم مسبقاً في الصنف: {row['name']}"
        )


class ProductRequest(BaseModel):
    name: str
    sku: Optional[str] = None
    category_id: Optional[int] = None
    unit: Optional[str] = "قطعة"
    min_stock: Optional[float] = 0
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    opening_quantity: Optional[float] = 0
    final_stock: Optional[float] = None


class AdjustRequest(BaseModel):
    quantity: float
    notes: Optional[str] = None


@router.get("/")
async def get_products(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch(
            """
            SELECT p.*, wc.name AS category_name, wc.icon AS category_icon
            FROM products p
            LEFT JOIN warehouse_categories wc ON wc.id = p.category_id
            ORDER BY wc.name NULLS LAST, p.name
            """
        )
        return [row_to_dict(r) for r in rows]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_product(data: ProductRequest, user=Depends(get_current_user)):
    require_warehouse_editor(user)

    name = clean_text(data.name)
    sku = clean_text(data.sku)
    unit = clean_text(data.unit) or "قطعة"
    min_stock = float(data.min_stock or 0)
    opening_quantity = float(data.opening_quantity or 0)

    if not name:
        raise HTTPException(status_code=400, detail="اسم الصنف مطلوب")

    if min_stock < 0:
        raise HTTPException(status_code=400, detail="الحد الأدنى لا يمكن أن يكون سالباً")

    if opening_quantity < 0:
        raise HTTPException(status_code=400, detail="الكمية الحالية لا يمكن أن تكون سالبة")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await ensure_category_exists(conn, data.category_id)
                await ensure_sku_unique(conn, sku)

                duplicate = await conn.fetchrow(
                    """
                    SELECT id, name
                    FROM products
                    WHERE LOWER(name) = LOWER($1)
                    AND COALESCE(category_id, 0) = COALESCE($2::int, 0)
                    LIMIT 1
                    """,
                    name,
                    data.category_id,
                )

                if duplicate:
                    raise HTTPException(
                        status_code=409,
                        detail=f"الصنف موجود مسبقاً في هذه الفئة: {duplicate['name']}"
                    )

                props_json = json.dumps(data.properties or {}, ensure_ascii=False)

                row = await conn.fetchrow(
                    """
                    INSERT INTO products
                      (name, sku, category_id, unit, min_stock, current_stock, properties)
                    VALUES
                      ($1, $2, $3, $4, $5, $6, $7::jsonb)
                    RETURNING *
                    """,
                    name,
                    sku,
                    data.category_id,
                    unit,
                    min_stock,
                    opening_quantity,
                    props_json,
                )

                if opening_quantity > 0:
                    await conn.execute(
                        """
                        INSERT INTO stock_movements
                          (product_id, type, quantity, source_type, notes, created_by)
                        VALUES
                          ($1, $2, $3, 'opening', $4, $5)
                        """,
                        row["id"],
                        "in",
                        opening_quantity,
                        f"كمية افتتاحية: {opening_quantity} {unit}",
                        safe_uuid(user.get("id")),
                    )

                await insert_audit(
                    conn,
                    user,
                    "أضاف صنف مستودع",
                    f"{name} — الكمية الافتتاحية: {opening_quantity} {unit}",
                )

                return row_to_dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{product_id}")
async def update_product(product_id: UUID, data: ProductRequest, user=Depends(get_current_user)):
    require_warehouse_editor(user)

    name = clean_text(data.name)
    sku = clean_text(data.sku)
    unit = clean_text(data.unit) or "قطعة"
    min_stock = float(data.min_stock or 0)

    if not name:
        raise HTTPException(status_code=400, detail="اسم الصنف مطلوب")

    if min_stock < 0:
        raise HTTPException(status_code=400, detail="الحد الأدنى لا يمكن أن يكون سالباً")

    if data.final_stock is not None and float(data.final_stock) < 0:
        raise HTTPException(status_code=400, detail="الكمية الحالية لا يمكن أن تكون سالبة")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """
                    SELECT id, name, current_stock
                    FROM products
                    WHERE id=$1
                    FOR UPDATE
                    """,
                    product_id,
                )

                if not current:
                    raise HTTPException(status_code=404, detail="الصنف غير موجود")

                await ensure_category_exists(conn, data.category_id)
                await ensure_sku_unique(conn, sku, exclude_product_id=product_id)

                props_json = json.dumps(data.properties or {}, ensure_ascii=False)
                name = clean_text(data.name)
                sku = clean_text(data.sku)
                unit = clean_text(data.unit) or "قطعة"
                min_stock = float(data.min_stock or 0)
                category_id = int(data.category_id) if data.category_id else None

                row = await conn.fetchrow(
                    """
                    UPDATE products
                    SET name=$1,
                        sku=$2,
                        category_id=$3,
                        unit=$4,
                        min_stock=$5,
                        properties=$6::jsonb
                    WHERE id=$7
                    RETURNING *
                    """,
                    name,
                    sku,
                    category_id,
                    unit,
                    min_stock,
                    props_json,
                    product_id,
                )

                if data.final_stock is not None:
                    old_stock = float(current["current_stock"] or 0)
                    final_stock = float(data.final_stock)
                    diff = final_stock - old_stock

                    if diff != 0:
                        row = await conn.fetchrow(
                            """
                            UPDATE products
                            SET current_stock=$1
                            WHERE id=$2
                            RETURNING *
                            """,
                            final_stock,
                            product_id,
                        )

                        await conn.execute(
                            """
                            INSERT INTO stock_movements
                              (product_id, type, quantity, source_type, notes, created_by)
                            VALUES
                              ($1, $2, $3, 'final_stock_edit', $4, $5)
                            """,
                            product_id,
                            "in" if diff > 0 else "out",
                            abs(diff),
                            f"تعديل الكمية من {old_stock} إلى {final_stock}",
                            safe_uuid(user.get("id")),
                        )

                        await insert_audit(
                            conn,
                            user,
                            "تعديل كمية صنف",
                            f"{name}: من {old_stock} إلى {final_stock}",
                        )

                await insert_audit(
                    conn,
                    user,
                    "تعديل بيانات صنف",
                    f"{name}",
                )

                return row_to_dict(row)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{product_id}/adjust")
async def adjust_stock(product_id: UUID, data: AdjustRequest, user=Depends(get_current_user)):
    require_warehouse_editor(user)

    qty = float(data.quantity)

    if qty == 0:
        raise HTTPException(status_code=400, detail="الكمية يجب أن تكون رقماً غير صفر")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """
                    SELECT id, name, current_stock
                    FROM products
                    WHERE id=$1
                    FOR UPDATE
                    """,
                    product_id,
                )

                if not current:
                    raise HTTPException(status_code=404, detail="الصنف غير موجود")

                old_stock = float(current["current_stock"] or 0)
                new_stock = old_stock + qty

                if new_stock < 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"لا يمكن خصم {abs(qty)} — المخزون الحالي {old_stock}"
                    )

                updated = await conn.fetchrow(
                    """
                    UPDATE products
                    SET current_stock=$1
                    WHERE id=$2
                    RETURNING *
                    """,
                    new_stock,
                    product_id,
                )

                await conn.execute(
                    """
                    INSERT INTO stock_movements
                      (product_id, type, quantity, source_type, notes, created_by)
                    VALUES
                      ($1, $2, $3, 'manual', $4, $5)
                    """,
                    product_id,
                    "in" if qty > 0 else "out",
                    abs(qty),
                    data.notes or "تعديل يدوي",
                    safe_uuid(user.get("id")),
                )

                await insert_audit(
                    conn,
                    user,
                    "تعديل مخزون",
                    f"{current['name']}: من {old_stock} إلى {new_stock}",
                )

                return row_to_dict(updated)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}/movements")
async def get_movements(product_id: UUID, user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch(
            """
            SELECT sm.*, u.full_name AS user_name
            FROM stock_movements sm
            LEFT JOIN users u ON u.id = sm.created_by
            WHERE sm.product_id = $1
            ORDER BY sm.created_at DESC
            LIMIT 100
            """,
            product_id,
        )

        return [row_to_dict(r) for r in rows]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{product_id}")
async def delete_product(product_id: UUID, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                product = await conn.fetchrow(
                    """
                    SELECT id, name, current_stock
                    FROM products
                    WHERE id=$1
                    FOR UPDATE
                    """,
                    product_id,
                )

                if not product:
                    raise HTTPException(status_code=404, detail="الصنف غير موجود")

                # حذف روابط الصنف التجريبية حتى لا يمنع الحذف
                await conn.execute(
                    "DELETE FROM stock_movements WHERE product_id=$1",
                    product_id,
                )

                await conn.execute(
                    "DELETE FROM warehouse_invoice_items WHERE product_id=$1",
                    product_id,
                )

                await conn.execute(
                    "DELETE FROM purchase_items WHERE product_id=$1",
                    product_id,
                )

                await conn.execute(
                    "DELETE FROM invoice_items WHERE product_id=$1",
                    product_id,
                )

                await conn.execute(
                    "DELETE FROM products WHERE id=$1",
                    product_id,
                )

                await insert_audit(
                    conn,
                    user,
                    "حذف صنف مستودع",
                    f"حذف صنف: {product['name']}",
                )

                return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))