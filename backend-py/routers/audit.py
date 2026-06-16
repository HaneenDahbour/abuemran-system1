from decimal import Decimal
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException


from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role
from uuid import UUID

router = APIRouter()


def to_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def safe_uuid(val):
    try:
        return UUID(str(val))
    except Exception:
        return None


def row_to_dict(row):
    return {key: to_json_value(row[key]) for key in row.keys()}


# GET /api/audit/stats
@router.get("/stats")
async def get_stats(user=Depends(get_current_user)):
    pool = await get_pool()

    try:
        row = await pool.fetchrow("""
                WITH approved_inv AS (
                    SELECT
                        COALESCE(SUM(total_amount), 0) AS total_sales,
                        COALESCE(SUM(COALESCE(initial_paid_amount, 0)), 0) AS invoice_paid,
                        COALESCE(SUM(
                            GREATEST(
                                COALESCE(total_amount, 0) - COALESCE(initial_paid_amount, 0),
                                0
                            )
                        ), 0) AS invoice_remaining
                    FROM invoices
                    WHERE COALESCE(status, '') = 'approved'
                ),
                extra_payments AS (
                    SELECT
                        COALESCE(SUM(amount), 0) AS extra_paid
                    FROM recipient_payments
                )
                SELECT
                    approved_inv.total_sales AS total_sales,

                    GREATEST(
                        approved_inv.invoice_remaining - extra_payments.extra_paid,
                        0
                    ) AS total_debts,

                    approved_inv.invoice_paid + extra_payments.extra_paid AS total_payments,

                    (SELECT COUNT(*) FROM checks WHERE due_date = CURRENT_DATE AND status='pending')
                        AS today_checks,

                    (SELECT COUNT(*) FROM clients)
                        AS active_clients,

                    0 AS pending_payments,

                    (SELECT COALESCE(SUM(cf.total_sold - cf.total_cost), 0)
                     FROM (
                         SELECT
                             p.category_id,
                             COALESCE(SUM(COALESCE(ii.line_total, ii.quantity * ii.unit_price, 0)), 0) AS total_sold,
                             COALESCE(SUM(ii.quantity * COALESCE(NULLIF(p.cost_price,0), NULLIF(p.base_price,0), 0)), 0) AS total_cost
                         FROM invoice_items ii
                         JOIN invoices inv ON inv.id = ii.invoice_id
                         JOIN products p ON p.id = ii.product_id
                         WHERE COALESCE(NULLIF(inv.status,''), 'approved') = 'approved'
                         GROUP BY p.category_id
                     ) cf
                    ) AS total_profit

                FROM approved_inv, extra_payments
            """)
        return row_to_dict(row)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ø®Ø·Ø£ ÙÙŠ Ø­Ø³Ø§Ø¨ Ø§Ù„Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª: {str(e)}")


# GET /api/audit/log
@router.get("/log")
async def get_audit_log(user=Depends(get_current_user)):
    if user.get("role") not in ["admin", "accountant"]:
        raise HTTPException(status_code=403, detail="ØºÙŠØ± Ù…ØµØ±Ø­")

    pool = await get_pool()

    try:
        rows = await pool.fetch("""
            SELECT *
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT 200
            """)

        return [row_to_dict(row) for row in rows]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cashbox")
async def get_cashbox(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    try:
        # ÙƒÙ„ Ø§Ù„Ù†Ù‚Ø¯ Ø§Ù„ÙˆØ§ØµÙ„ Ù…Ù† Ø§Ù„Ø¹Ù…Ù„Ø§Ø¡ (Ù…Ø¹ØªÙ…Ø¯)
        cash_in_row = await pool.fetchrow("""
            SELECT COALESCE(SUM(p.amount), 0) AS total
            FROM payments p
            WHERE p.status = 'approved'
              AND (
                COALESCE(p.notes, '') ILIKE '%method:cash%'
                OR COALESCE(p.notes, '') ILIKE '%method:check%'
                OR p.payment_method = 'cash'
                OR p.payment_method = 'check'
              )
            """)

        # ÙƒÙ„ Ø§Ù„Ù…Ø¯ÙÙˆØ¹ Ù„Ù„Ù…ÙˆØ±Ø¯ÙŠÙ†
        cash_out_suppliers = await pool.fetchrow(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM supplier_payments"
        )

        # Ø§Ù„Ù…ØµØ§Ø±ÙŠÙ Ø§Ù„ÙŠØ¯ÙˆÙŠØ©
        cash_out_expenses = await pool.fetchrow(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM cashbox_expenses"
        )

        total_in = float(cash_in_row["total"] or 0)
        total_suppliers = float(cash_out_suppliers["total"] or 0)
        total_expenses = float(cash_out_expenses["total"] or 0)
        balance = total_in - total_suppliers - total_expenses

        # Ø¢Ø®Ø± 50 Ø­Ø±ÙƒØ©
        client_payments = await pool.fetch("""
            SELECT p.id, p.amount, p.payment_date AS date,
                   c.name AS description,
                   'client_payment' AS type,
                   p.notes
            FROM payments p
            JOIN clients c ON c.id = p.client_id
            WHERE p.status = 'approved'
              AND (
                COALESCE(p.notes, '') ILIKE '%method:cash%'
                OR COALESCE(p.notes, '') ILIKE '%method:check%'
                OR p.payment_method = 'cash'
                OR p.payment_method = 'check'
              )
            ORDER BY p.payment_date DESC
            LIMIT 30
            """)

        supplier_payments = await pool.fetch("""
            SELECT sp.id, sp.amount, sp.payment_date AS date,
                   s.name AS description,
                   'supplier_payment' AS type,
                   sp.notes
            FROM supplier_payments sp
            JOIN suppliers s ON s.id = sp.supplier_id
            ORDER BY sp.payment_date DESC
            LIMIT 30
            """)

        expenses = await pool.fetch("""
            SELECT id, amount, expense_date AS date,
                   description, 'expense' AS type, NULL AS notes
            FROM cashbox_expenses
            ORDER BY expense_date DESC
            LIMIT 20
            """)

        def to_val(v):
            if isinstance(v, Decimal):
                return float(v)
            if isinstance(v, (date, datetime)):
                return v.isoformat()
            return v

        def to_d(row):
            return {k: to_val(row[k]) for k in row.keys()}

        transactions = (
            [to_d(r) for r in client_payments]
            + [to_d(r) for r in supplier_payments]
            + [to_d(r) for r in expenses]
        )
        transactions.sort(key=lambda x: x.get("date") or "", reverse=True)

        return {
            "balance": round(balance, 3),
            "total_in": round(total_in, 3),
            "total_out_suppliers": round(total_suppliers, 3),
            "total_out_expenses": round(total_expenses, 3),
            "transactions": transactions[:50],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cashbox/expenses")
async def add_cashbox_expense(data: dict, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    amount = float(data.get("amount") or 0)
    description = str(data.get("description") or "").strip()
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ù…Ø¨Ù„Øº ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø£ÙƒØ¨Ø± Ù…Ù† ØµÙØ±")
    if not description:
        raise HTTPException(status_code=400, detail="Ø§Ù„ÙˆØµÙ Ù…Ø·Ù„ÙˆØ¨")
    pool = await get_pool()
    try:
        exp_date = (
            date.fromisoformat(data["expense_date"])
            if data.get("expense_date")
            else date.today()
        )
        row = await pool.fetchrow(
            """
            INSERT INTO cashbox_expenses (amount, description, expense_date, created_by)
            VALUES ($1, $2, $3, $4) RETURNING *
            """,
            round(amount, 3),
            description,
            exp_date,
            user.get("id") if hasattr(user, "get") else None,
        )
        return {
            k: (
                float(v)
                if isinstance(v, Decimal)
                else v.isoformat() if isinstance(v, (date, datetime)) else v
            )
            for k, v in dict(row).items()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

