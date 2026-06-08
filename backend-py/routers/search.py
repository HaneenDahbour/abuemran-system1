from decimal import Decimal
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from config.db import get_pool
from middleware.auth import get_current_user

router = APIRouter()


def to_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def row_to_dict(row):
    return {key: to_json_value(row[key]) for key in row.keys()}


# GET /api/search?q=term
@router.get("")
async def search(q: str = Query(default=""), user=Depends(get_current_user)):
    raw = q.strip()

    if len(raw) < 2:
        return {"clients": [], "invoices": [], "checks": [], "products": []}

    pattern = f"%{raw}%"
    pool = await get_pool()

    try:
        clients_rows, invoices_rows, checks_rows, products_rows = (
            await _run_parallel_search(pool, pattern)
        )

        return {
            "clients": [row_to_dict(r) for r in clients_rows],
            "invoices": [row_to_dict(r) for r in invoices_rows],
            "checks": [row_to_dict(r) for r in checks_rows],
            "products": [row_to_dict(r) for r in products_rows],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _run_parallel_search(pool, pattern: str):
    import asyncio

    async def fetch_clients():
        return await pool.fetch(
            """
            SELECT id, name, phone, risk_level,
                   COALESCE((SELECT SUM(net_amount) FROM invoices WHERE client_id=c.id), 0)
                   - COALESCE((SELECT SUM(amount) FROM payments WHERE client_id=c.id AND status='approved'), 0)
                   AS balance
            FROM clients c
            WHERE name ILIKE $1 OR phone ILIKE $1
            LIMIT 6
            """,
            pattern,
        )

    async def fetch_invoices():
        return await pool.fetch(
            """
            SELECT inv.id, inv.invoice_number, inv.total_amount, inv.date,
                   COALESCE(c.name,            '') AS client_name,
                   COALESCE(inv.recipient_name,'') AS recipient_name,
                   COALESCE(ae.full_name,      '') AS attributed_employee_name,
                   COALESCE(u.full_name,       '') AS created_by_name
            FROM invoices inv
            LEFT JOIN clients c ON c.id  = inv.client_id
            LEFT JOIN users ae  ON ae.id = inv.attributed_employee_id
            LEFT JOIN users u   ON u.id  = inv.created_by
            WHERE COALESCE(NULLIF(inv.status,''), 'approved') != 'rejected'
              AND (
                   inv.invoice_number               ILIKE $1
                OR COALESCE(c.name,           '') ILIKE $1
                OR COALESCE(inv.recipient_name,'') ILIKE $1
                OR COALESCE(ae.full_name,     '') ILIKE $1
                OR COALESCE(u.full_name,      '') ILIKE $1
              )
            ORDER BY inv.date DESC
            LIMIT 8
            """,
            pattern,
        )

    async def fetch_checks():
        return await pool.fetch(
            """
            SELECT ch.id, ch.check_number, ch.amount, ch.due_date, ch.status,
                   c.name AS client_name
            FROM checks ch
            JOIN clients c ON c.id = ch.client_id
            WHERE ch.check_number ILIKE $1 OR c.name ILIKE $1
            ORDER BY ch.due_date DESC
            LIMIT 6
            """,
            pattern,
        )

    async def fetch_products():
        return await pool.fetch(
            """
            SELECT p.id, p.name, p.sku, p.current_stock, p.unit,
                   wc.name AS category_name
            FROM products p
            LEFT JOIN warehouse_categories wc ON wc.id = p.category_id
            WHERE p.name ILIKE $1 OR p.sku ILIKE $1
            LIMIT 6
            """,
            pattern,
        )

    return await asyncio.gather(
        fetch_clients(), fetch_invoices(), fetch_checks(), fetch_products()
    )

