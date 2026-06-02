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


class CategoryRequest(BaseModel):
    name: str
    icon: Optional[str] = "📦"


@router.get("/")
async def get_categories(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch(
            """
            WITH sold_by_category AS (
                SELECT
                    p.category_id,
                    COALESCE(SUM(s.total), 0) AS total_sold
                FROM products p
                LEFT JOIN (
                    SELECT
                        product_id,
                        COALESCE(line_total, quantity * unit_price, 0) AS total
                    FROM invoice_items

                    UNION ALL

                    SELECT
                        product_id,
                        quantity * unit_price AS total
                    FROM warehouse_invoice_items
                ) s ON s.product_id = p.id
                GROUP BY p.category_id
            )
            SELECT
                wc.id,
                wc.name,
                COALESCE(wc.icon, '📦') AS icon,
                COUNT(p.id)::int AS product_count,
                COALESCE(SUM(p.current_stock), 0) AS total_stock,
                COALESCE(SUM(p.min_stock), 0) AS total_min_stock,
                COUNT(*) FILTER (
                    WHERE p.id IS NOT NULL AND COALESCE(p.current_stock, 0) = 0
                )::int AS out_of_stock_count,
                COUNT(*) FILTER (
                    WHERE p.id IS NOT NULL
                      AND COALESCE(p.current_stock, 0) > 0
                      AND COALESCE(p.min_stock, 0) > 0
                      AND p.current_stock <= p.min_stock
                )::int AS low_stock_count,
                COUNT(*) FILTER (
                    WHERE p.id IS NOT NULL
                      AND COALESCE(p.current_stock, 0) > 0
                      AND (COALESCE(p.min_stock, 0) = 0 OR p.current_stock > p.min_stock)
                )::int AS healthy_count,
                COALESCE(sbc.total_sold, 0) AS total_sold
            FROM warehouse_categories wc
            LEFT JOIN products p ON p.category_id = wc.id
            LEFT JOIN sold_by_category sbc ON sbc.category_id = wc.id
            GROUP BY wc.id, wc.name, wc.icon, sbc.total_sold
            ORDER BY wc.name ASC
            """
        )

        return [row_to_dict(r) for r in rows]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"تعذر تحميل فئات المستودع: {str(e)}"
        )

@router.get("/{category_id}/products")
async def get_category_products(category_id: int, user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch(
            "SELECT * FROM products WHERE category_id = $1 ORDER BY name ASC",
            category_id
        )

        return [row_to_dict(r) for r in rows]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"تعذر تحميل أصناف الفئة: {str(e)}"
        )


@router.post("/")
async def create_category(data: CategoryRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="الاسم مطلوب")

    pool = await get_pool()

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO warehouse_categories (name, icon)
            VALUES ($1, $2)
            RETURNING *
            """,
            data.name.strip(),
            data.icon or "📦"
        )

        try:
            await pool.execute(
                """
                INSERT INTO audit_log (user_id, user_name, action, detail)
                VALUES ($1, $2, 'أضاف فئة مستودع', $3)
                """,
                safe_uuid(user.get("id")),
                user.get("full_name"),
                f"فئة: {data.name.strip()}"
            )
        except Exception:
            pass

        return row_to_dict(row)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{category_id}")
async def update_category(category_id: int, data: CategoryRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="الاسم مطلوب")

    pool = await get_pool()

    try:
        row = await pool.fetchrow(
            """
            UPDATE warehouse_categories
            SET name = $1, icon = $2
            WHERE id = $3
            RETURNING *
            """,
            data.name.strip(),
            data.icon or "📦",
            category_id
        )

        if not row:
            raise HTTPException(status_code=404, detail="الفئة غير موجودة")

        return row_to_dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{category_id}")
async def delete_category(category_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()
    conn = await pool.acquire()

    try:
        async with conn.transaction():
            await conn.execute(
                "UPDATE products SET category_id = NULL WHERE category_id = $1",
                category_id
            )

            deleted = await conn.fetchrow(
                "DELETE FROM warehouse_categories WHERE id = $1 RETURNING id",
                category_id
            )

            if not deleted:
                raise HTTPException(status_code=404, detail="الفئة غير موجودة")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        await pool.release(conn)