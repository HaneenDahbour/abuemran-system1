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
    icon: Optional[str] = "ðŸ“¦"


async def insert_category_audit(conn, user, action: str, detail: str):
    try:
        await conn.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, detail)
            VALUES ($1, $2, $3, $4)
            """,
            user.get("id"),
            user.get("full_name") or user.get("username") or "مستخدم",
            action,
            detail,
        )
    except Exception:
        pass


@router.get("")
async def get_categories(user=Depends(get_current_user)):
    pool = await get_pool()
    try:
        # Try profit-enabled query (needs cost_price column from SQL migration)
        rows = await pool.fetch("""
            WITH invoice_sales AS (
                SELECT
                    ii.product_id,
                    COALESCE(SUM(COALESCE(ii.line_total, ii.quantity * ii.unit_price, 0)), 0) AS revenue,
                    COALESCE(SUM(ii.quantity), 0) AS qty_sold
                FROM invoice_items ii
                JOIN invoices i ON i.id = ii.invoice_id
                WHERE COALESCE(NULLIF(i.status, ''), 'approved') = 'approved'
                GROUP BY ii.product_id
            ),
            warehouse_sales AS (
                SELECT
                    product_id,
                    COALESCE(SUM(quantity * unit_price), 0) AS revenue,
                    COALESCE(SUM(quantity), 0)              AS qty_sold
                FROM warehouse_invoice_items
                GROUP BY product_id
            ),
            product_profit AS (
    SELECT
        p.category_id,

        COALESCE(inv.revenue, 0) + COALESCE(wh.revenue, 0) AS total_revenue,

        CASE
            WHEN COALESCE(NULLIF(p.cost_price, 0), NULLIF(p.base_price, 0)) IS NOT NULL
            THEN
                (COALESCE(inv.qty_sold, 0) + COALESCE(wh.qty_sold, 0))
                * COALESCE(NULLIF(p.cost_price, 0), NULLIF(p.base_price, 0))
            ELSE
                COALESCE(inv.revenue, 0) + COALESCE(wh.revenue, 0)
        END AS total_cost

    FROM products p
    LEFT JOIN invoice_sales  inv ON inv.product_id = p.id
    LEFT JOIN warehouse_sales wh ON wh.product_id  = p.id
),
            category_financials AS (
                SELECT
                    category_id,
                    COALESCE(SUM(total_revenue), 0) AS total_sold,
                    COALESCE(SUM(total_cost),    0) AS total_cost
                FROM product_profit
                GROUP BY category_id
            ),
            category_capital AS (
                SELECT
                    p.category_id,
                    COALESCE(SUM(
                        p.current_stock * COALESCE(NULLIF(p.cost_price, 0), NULLIF(p.base_price, 0), 0)
                    ), 0) AS total_capital
                FROM products p
                GROUP BY p.category_id
            ),
            sold_legacy AS (
                SELECT
                    p.category_id,
                    COALESCE(SUM(s.total), 0) AS total_sold
                FROM products p
                LEFT JOIN (
                    SELECT ii.product_id,
                           COALESCE(ii.line_total, ii.quantity * ii.unit_price, 0) AS total
                    FROM invoice_items ii
                    JOIN invoices i ON i.id = ii.invoice_id
                    WHERE COALESCE(NULLIF(i.status, ''), 'approved') = 'approved'
                    UNION ALL
                    SELECT product_id, quantity * unit_price AS total
                    FROM warehouse_invoice_items
                ) s ON s.product_id = p.id
                GROUP BY p.category_id
            )
            SELECT
                wc.id,
                wc.name,
                COALESCE(wc.icon, '📦') AS icon,
                COUNT(p.id)::int  AS product_count,
                COALESCE(SUM(p.current_stock), 0) AS total_stock,
                COALESCE(SUM(p.min_stock),     0) AS total_min_stock,
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
                      AND (COALESCE(p.min_stock, 0) = 0
                           OR p.current_stock > p.min_stock)
                )::int AS healthy_count,
                COALESCE(MAX(cf.total_sold), 0)  AS total_sold,
                COALESCE(MAX(cf.total_cost),  0) AS total_cost,
                COALESCE(MAX(cf.total_sold) - MAX(cf.total_cost), 0) AS total_profit,
                CASE WHEN COALESCE(MAX(cf.total_sold), 0) > 0
                     THEN ROUND(
                         ((COALESCE(MAX(cf.total_sold), 0) - COALESCE(MAX(cf.total_cost), 0))
                          / COALESCE(MAX(cf.total_sold), 1) * 100)::numeric, 1)
                     ELSE 0 END AS profit_margin_pct,
                COALESCE(MAX(cc.total_capital), 0) AS total_capital
            FROM warehouse_categories wc
            LEFT JOIN products           p  ON p.category_id  = wc.id
            LEFT JOIN category_financials cf ON cf.category_id = wc.id
            LEFT JOIN category_capital    cc ON cc.category_id = wc.id
            GROUP BY wc.id, wc.name, wc.icon
            ORDER BY wc.name ASC
        """)
        return [row_to_dict(r) for r in rows]

    except Exception:
        # ── FALLBACK: cost_price column not added yet — use original safe query ──
        try:
            rows = await pool.fetch("""
                WITH sold_by_category AS (
                    SELECT
                        p.category_id,
                        COALESCE(SUM(s.total), 0) AS total_sold
                    FROM products p
                    LEFT JOIN (
                        SELECT ii.product_id,
                               COALESCE(ii.line_total, ii.quantity * ii.unit_price, 0) AS total
                        FROM invoice_items ii
                        JOIN invoices i ON i.id = ii.invoice_id
                        WHERE COALESCE(NULLIF(i.status, ''), 'approved') = 'approved'
                        UNION ALL
                        SELECT product_id, quantity * unit_price AS total
                        FROM warehouse_invoice_items
                    ) s ON s.product_id = p.id
                    GROUP BY p.category_id
                )
                SELECT
                    wc.id,
                    wc.name,
                    COALESCE(wc.icon, '📦') AS icon,
                    COUNT(p.id)::int  AS product_count,
                    COALESCE(SUM(p.current_stock), 0) AS total_stock,
                    COALESCE(SUM(p.min_stock),     0) AS total_min_stock,
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
                          AND (COALESCE(p.min_stock, 0) = 0
                               OR p.current_stock > p.min_stock)
                    )::int AS healthy_count,
                    COALESCE(MAX(sbc.total_sold), 0) AS total_sold,
                    0::numeric AS total_cost,
                    0::numeric AS total_profit,
                    0::numeric AS profit_margin_pct,
                    COALESCE(SUM(p.current_stock * COALESCE(NULLIF(p.cost_price, 0), NULLIF(p.base_price, 0), 0)), 0) AS total_capital
                FROM warehouse_categories wc
                LEFT JOIN products          p   ON p.category_id  = wc.id
                LEFT JOIN sold_by_category  sbc ON sbc.category_id = wc.id
                GROUP BY wc.id, wc.name, wc.icon
                ORDER BY wc.name ASC
            """)
            return [row_to_dict(r) for r in rows]
        except Exception as e2:
            raise HTTPException(
                status_code=500,
                detail=f"تعذر تحميل فئات المستودع: {str(e2)}",
            )
@router.get("/{category_id}/products")
async def get_category_products(category_id: int, user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        rows = await pool.fetch(
            """
            SELECT p.*, wc.name AS category_name, wc.icon AS category_icon
            FROM products p
            LEFT JOIN warehouse_categories wc ON wc.id = p.category_id
            WHERE p.category_id = $1
            ORDER BY p.name ASC
            """,
            category_id,
        )

        return [row_to_dict(r) for r in rows]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ØªØ¹Ø°Ø± ØªØ­Ù…ÙŠÙ„ Ø£ØµÙ†Ø§Ù Ø§Ù„ÙØ¦Ø©: {str(e)}",
        )


@router.get("/{category_id}/analytics")
async def get_category_analytics(category_id: int, user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        category = await pool.fetchrow(
            "SELECT id, name, icon FROM warehouse_categories WHERE id=$1", category_id
        )

        if not category:
            raise HTTPException(status_code=404, detail="الفئة غير موجودة")

        try:
            rows = await pool.fetch(
                """
                WITH invoice_sales AS (
                    SELECT
                        ii.product_id,
                        COALESCE(SUM(COALESCE(ii.line_total, ii.quantity * ii.unit_price, 0)), 0) AS revenue,
                        COALESCE(SUM(ii.quantity), 0) AS qty_sold
                    FROM invoice_items ii
                    JOIN invoices i ON i.id = ii.invoice_id
                    WHERE COALESCE(NULLIF(i.status, ''), 'approved') = 'approved'
                    GROUP BY ii.product_id
                ),
                warehouse_sales AS (
                    SELECT
                        product_id,
                        COALESCE(SUM(quantity * unit_price), 0) AS revenue,
                        COALESCE(SUM(quantity), 0)              AS qty_sold
                    FROM warehouse_invoice_items
                    GROUP BY product_id
                )
                SELECT
                    p.id, p.name, p.sku, p.unit,
                    p.current_stock,
                    COALESCE(NULLIF(p.cost_price, 0), NULLIF(p.base_price, 0), 0) AS cost_price,
                    (p.current_stock * COALESCE(NULLIF(p.cost_price, 0), NULLIF(p.base_price, 0), 0)) AS capital_remaining,
                    COALESCE(inv.qty_sold, 0) + COALESCE(wh.qty_sold, 0) AS qty_sold,
                    COALESCE(inv.revenue, 0)  + COALESCE(wh.revenue, 0)  AS revenue,
                    (COALESCE(inv.revenue, 0) + COALESCE(wh.revenue, 0))
                      - (COALESCE(inv.qty_sold, 0) + COALESCE(wh.qty_sold, 0))
                        * COALESCE(NULLIF(p.cost_price, 0), NULLIF(p.base_price, 0), 0) AS profit
                FROM products p
                LEFT JOIN invoice_sales   inv ON inv.product_id = p.id
                LEFT JOIN warehouse_sales wh  ON wh.product_id  = p.id
                WHERE p.category_id = $1
                ORDER BY profit DESC NULLS LAST, p.name ASC
                """,
                category_id,
            )
        except Exception:
            rows = await pool.fetch(
                """
                SELECT
                    p.id, p.name, p.sku, p.unit,
                    p.current_stock,
                    0::numeric AS cost_price,
                    0::numeric AS capital_remaining,
                    0::numeric AS qty_sold,
                    0::numeric AS revenue,
                    0::numeric AS profit
                FROM products p
                WHERE p.category_id = $1
                ORDER BY p.name ASC
                """,
                category_id,
            )

        products = [row_to_dict(r) for r in rows]

        total_capital = sum(float(p["capital_remaining"] or 0) for p in products)
        total_sold = sum(float(p["revenue"] or 0) for p in products)
        total_profit = sum(float(p["profit"] or 0) for p in products)
        total_qty_sold = sum(float(p["qty_sold"] or 0) for p in products)

        top_product = None
        for p in sorted(products, key=lambda x: float(x["profit"] or 0), reverse=True):
            if float(p["profit"] or 0) > 0:
                top_product = {"name": p["name"], "profit": p["profit"]}
                break

        return {
            "category": row_to_dict(category),
            "summary": {
                "total_capital": total_capital,
                "total_sold": total_sold,
                "total_profit": total_profit,
                "total_qty_sold": total_qty_sold,
                "top_product": top_product,
            },
            "products": products,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر تحميل تحليلات الفئة: {str(e)}")


@router.post("")
async def create_category(data: CategoryRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant", "employee")

    name = (data.name or "").strip()
    icon = (data.icon or "ðŸ“¦").strip() or "ðŸ“¦"

    if not name:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ø§Ø³Ù… Ù…Ø·Ù„ÙˆØ¨")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    """
                    SELECT id
                    FROM warehouse_categories
                    WHERE LOWER(name) = LOWER($1)
                    LIMIT 1
                    """,
                    name,
                )

                if existing:
                    raise HTTPException(
                        status_code=409, detail="Ù‡Ø°Ù‡ Ø§Ù„ÙØ¦Ø© Ù…ÙˆØ¬ÙˆØ¯Ø© Ù…Ø³Ø¨Ù‚Ø§Ù‹"
                    )

                row = await conn.fetchrow(
                    """
                    INSERT INTO warehouse_categories (name, icon)
                    VALUES ($1, $2)
                    RETURNING *
                    """,
                    name,
                    icon,
                )

                await insert_category_audit(
                    conn, user, "Ø£Ø¶Ø§Ù ÙØ¦Ø© Ù…Ø³ØªÙˆØ¯Ø¹", f"ÙØ¦Ø©: {name}"
                )

                return row_to_dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{category_id}")
async def update_category(
    category_id: int, data: CategoryRequest, user=Depends(get_current_user)
):
    require_role(user, "admin", "accountant")

    name = (data.name or "").strip()
    icon = (data.icon or "ðŸ“¦").strip() or "ðŸ“¦"

    if not name:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ø§Ø³Ù… Ù…Ø·Ù„ÙˆØ¨")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                duplicate = await conn.fetchrow(
                    """
                    SELECT id
                    FROM warehouse_categories
                    WHERE LOWER(name) = LOWER($1)
                      AND id <> $2
                    LIMIT 1
                    """,
                    name,
                    category_id,
                )

                if duplicate:
                    raise HTTPException(
                        status_code=409, detail="Ø§Ø³Ù… Ø§Ù„ÙØ¦Ø© Ù…Ø³ØªØ®Ø¯Ù… Ù…Ø³Ø¨Ù‚Ø§Ù‹"
                    )

                row = await conn.fetchrow(
                    """
                    UPDATE warehouse_categories
                    SET name = $1,
                        icon = $2
                    WHERE id = $3
                    RETURNING *
                    """,
                    name,
                    icon,
                    category_id,
                )

                if not row:
                    raise HTTPException(status_code=404, detail="Ø§Ù„ÙØ¦Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø©")

                await conn.execute(
                    """
                    UPDATE products
                    SET category = $1
                    WHERE category_id = $2
                    """,
                    name,
                    category_id,
                )

                await insert_category_audit(
                    conn, user, "ØªØ¹Ø¯ÙŠÙ„ ÙØ¦Ø© Ù…Ø³ØªÙˆØ¯Ø¹", f"ÙØ¦Ø©: {name}"
                )

                return row_to_dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{category_id}")
async def delete_category(category_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                category = await conn.fetchrow(
                    """
                    SELECT id, name
                    FROM warehouse_categories
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    category_id,
                )

                if not category:
                    raise HTTPException(
                        status_code=404,
                        detail="Ø§Ù„ÙØ¦Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø© Ø£Ùˆ ØªÙ… Ø­Ø°ÙÙ‡Ø§ Ù…Ø³Ø¨Ù‚Ø§Ù‹",
                    )

                unlinked_result = await conn.execute(
                    """
                    UPDATE products
                    SET category_id = NULL,
                        category = NULL
                    WHERE category_id = $1
                    """,
                    category_id,
                )

                deleted = await conn.fetchrow(
                    """
                    DELETE FROM warehouse_categories
                    WHERE id = $1
                    RETURNING id
                    """,
                    category_id,
                )

                if not deleted:
                    raise HTTPException(status_code=404, detail="Ø§Ù„ÙØ¦Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø©")

                await insert_category_audit(
                    conn,
                    user,
                    "Ø­Ø°Ù ÙØ¦Ø© Ù…Ø³ØªÙˆØ¯Ø¹",
                    f"Ø­Ø°Ù ÙØ¦Ø©: {category['name']} â€” ØªÙ… Ø¥Ù„ØºØ§Ø¡ Ø±Ø¨Ø· Ø§Ù„Ø£ØµÙ†Ø§Ù Ø§Ù„ØªØ§Ø¨Ø¹Ø© Ø¨Ù‡Ø§",
                )

        return {
            "success": True,
            "message": "ØªÙ… Ø­Ø°Ù Ø§Ù„ÙØ¦Ø© ÙˆØ¥Ù„ØºØ§Ø¡ Ø±Ø¨Ø· Ø§Ù„Ø£ØµÙ†Ø§Ù Ø§Ù„ØªØ§Ø¨Ø¹Ø© Ø¨Ù‡Ø§",
            "deleted_category_id": category_id,
            "unlinked_products": int(unlinked_result.split()[-1]),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

