from decimal import Decimal
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────

def to_val(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def row_to_dict(row):
    return {k: to_val(row[k]) for k in row.keys()}


def parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="التاريخ غير صحيح")


async def insert_audit(conn, user, action: str, detail: str):
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


def require_access(user):
    require_role(user, "admin", "accountant")


async def get_category_total_profit(pool, category_id: int) -> float:
    """يحسب إجمالي ربح فئة المستودع (نفس منطق warehouse_categories)."""
    try:
        row = await pool.fetchrow(
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
                WHERE p.category_id = $1
            )
            SELECT
                COALESCE(SUM(total_revenue), 0) AS total_sold,
                COALESCE(SUM(total_cost), 0) AS total_cost,
                COALESCE(SUM(total_revenue) - SUM(total_cost), 0) AS total_profit
            FROM product_profit
            """,
            category_id,
        )
        return row_to_dict(row) if row else {"total_sold": 0, "total_cost": 0, "total_profit": 0}
    except Exception:
        return {"total_sold": 0, "total_cost": 0, "total_profit": 0}


# ── Pydantic models ──────────────────────────────────────────

class InvestorIn(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None


class InvestmentIn(BaseModel):
    investor_id: int
    amount: float
    paid_amount: Optional[float] = 0.0
    notes: Optional[str] = None


class DistributionIn(BaseModel):
    distribution_date: Optional[str] = None
    notes: Optional[str] = None


# ── Investors CRUD ───────────────────────────────────────────

@router.get("/investors")
async def list_investors(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT
            wi.*,
            COALESCE(SUM(wci.amount), 0) AS total_invested,
            COUNT(wci.id)::int AS categories_count
        FROM warehouse_investors wi
        LEFT JOIN warehouse_category_investments wci ON wci.investor_id = wi.id
        GROUP BY wi.id
        ORDER BY wi.name ASC
    """)

    return [row_to_dict(r) for r in rows]


@router.post("/investors")
async def create_investor(data: InvestorIn, user=Depends(get_current_user)):
    require_access(user)

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم المستثمر مطلوب")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT id FROM warehouse_investors WHERE LOWER(name) = LOWER($1)", name
            )
            if existing:
                raise HTTPException(status_code=409, detail="هذا المستثمر موجود مسبقاً")

            row = await conn.fetchrow(
                """
                INSERT INTO warehouse_investors (name, phone, notes, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                name, (data.phone or "").strip() or None, (data.notes or "").strip() or None,
                user.get("id"),
            )
            await insert_audit(conn, user, "إضافة مستثمر مستودع", f"مستثمر: {name}")
            return row_to_dict(row)


@router.put("/investors/{investor_id}")
async def update_investor(investor_id: int, data: InvestorIn, user=Depends(get_current_user)):
    require_access(user)

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم المستثمر مطلوب")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            duplicate = await conn.fetchrow(
                "SELECT id FROM warehouse_investors WHERE LOWER(name) = LOWER($1) AND id <> $2", name, investor_id
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="اسم المستثمر مستخدم مسبقاً")

            row = await conn.fetchrow(
                """
                UPDATE warehouse_investors
                SET name=$1, phone=$2, notes=$3
                WHERE id=$4
                RETURNING *
                """,
                name, (data.phone or "").strip() or None, (data.notes or "").strip() or None,
                investor_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="المستثمر غير موجود")
            await insert_audit(conn, user, "تعديل مستثمر مستودع", f"مستثمر: {name}")
            return row_to_dict(row)


@router.delete("/investors/{investor_id}")
async def delete_investor(investor_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM warehouse_investors WHERE id=$1 RETURNING id, name", investor_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="المستثمر غير موجود")
            await insert_audit(conn, user, "حذف مستثمر مستودع", f"مستثمر: {row['name']}")
            return {"success": True}


@router.get("/investors/{investor_id}")
async def get_investor(investor_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()

    investor = await pool.fetchrow("SELECT * FROM warehouse_investors WHERE id=$1", investor_id)
    if not investor:
        raise HTTPException(status_code=404, detail="المستثمر غير موجود")

    investments = await pool.fetch(
        """
        SELECT wci.*, wc.name AS category_name, wc.icon AS category_icon
        FROM warehouse_category_investments wci
        JOIN warehouse_categories wc ON wc.id = wci.category_id
        WHERE wci.investor_id = $1
        ORDER BY wc.name ASC
        """,
        investor_id,
    )

    return {
        "investor": row_to_dict(investor),
        "investments": [row_to_dict(r) for r in investments],
    }


# ── Investments per category ──────────────────────────────────

@router.get("/categories/{category_id}/investments")
async def get_category_investments(category_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()

    category = await pool.fetchrow("SELECT id, name, icon FROM warehouse_categories WHERE id=$1", category_id)
    if not category:
        raise HTTPException(status_code=404, detail="الفئة غير موجودة")

    rows = await pool.fetch(
        """
        SELECT wci.*, wi.name AS investor_name, wi.phone AS investor_phone
        FROM warehouse_category_investments wci
        JOIN warehouse_investors wi ON wi.id = wci.investor_id
        WHERE wci.category_id = $1
        ORDER BY wci.amount DESC, wi.name ASC
        """,
        category_id,
    )

    investments = [row_to_dict(r) for r in rows]
    total_invested = sum(float(i["amount"] or 0) for i in investments)
    for inv in investments:
        inv["contribution_pct"] = round((float(inv["amount"] or 0) / total_invested * 100), 3) if total_invested > 0 else 0

    return {
        "category": row_to_dict(category),
        "total_invested": total_invested,
        "investments": investments,
    }


@router.post("/categories/{category_id}/investments")
async def set_category_investment(category_id: int, data: InvestmentIn, user=Depends(get_current_user)):
    require_access(user)

    if data.amount < 0:
        raise HTTPException(status_code=400, detail="المبلغ لا يمكن أن يكون سالباً")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            category = await conn.fetchrow("SELECT id, name FROM warehouse_categories WHERE id=$1", category_id)
            if not category:
                raise HTTPException(status_code=404, detail="الفئة غير موجودة")

            investor = await conn.fetchrow("SELECT id, name FROM warehouse_investors WHERE id=$1", data.investor_id)
            if not investor:
                raise HTTPException(status_code=404, detail="المستثمر غير موجود")

            row = await conn.fetchrow(
                """
                INSERT INTO warehouse_category_investments (category_id, investor_id, amount, paid_amount, notes, created_by)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (category_id, investor_id)
                DO UPDATE SET amount = EXCLUDED.amount, paid_amount = EXCLUDED.paid_amount,
                              notes = EXCLUDED.notes, updated_at = NOW()
                RETURNING *
                """,
                category_id, data.investor_id, data.amount,
                data.paid_amount or 0.0,
                (data.notes or "").strip() or None,
                user.get("id"),
            )

            await insert_audit(
                conn, user, "تحديث مساهمة مستثمر",
                f"{investor['name']} — فئة: {category['name']} — المبلغ: {data.amount:.3f} د.أ",
            )

            return row_to_dict(row)


@router.delete("/categories/{category_id}/investments/{investment_id}")
async def delete_category_investment(category_id: int, investment_id: int, user=Depends(get_current_user)):
    require_access(user)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                DELETE FROM warehouse_category_investments
                WHERE id=$1 AND category_id=$2
                RETURNING id, investor_id
                """,
                investment_id, category_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="المساهمة غير موجودة")

            await insert_audit(conn, user, "حذف مساهمة مستثمر", f"مساهمة #{investment_id} — فئة #{category_id}")
            return {"success": True}


# ── Profit-sharing calculation ─────────────────────────────────

OWNER_SHARE_PCT = 0.5  # 50% للمالك، 50% للمستثمرين


@router.get("/categories/{category_id}/profit-share")
async def get_category_profit_share(category_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()

    category = await pool.fetchrow("SELECT id, name, icon FROM warehouse_categories WHERE id=$1", category_id)
    if not category:
        raise HTTPException(status_code=404, detail="الفئة غير موجودة")

    financials = await get_category_total_profit(pool, category_id)
    total_profit = float(financials.get("total_profit") or 0)

    rows = await pool.fetch(
        """
        SELECT wci.*, wi.name AS investor_name, wi.phone AS investor_phone
        FROM warehouse_category_investments wci
        JOIN warehouse_investors wi ON wi.id = wci.investor_id
        WHERE wci.category_id = $1
        ORDER BY wci.amount DESC, wi.name ASC
        """,
        category_id,
    )
    investments = [row_to_dict(r) for r in rows]
    total_invested = sum(float(i["amount"] or 0) for i in investments)

    # إذا كان الربح سالباً أو صفراً، لا يوجد توزيع
    distributable_profit = max(total_profit, 0)

    owner_share = round(distributable_profit * OWNER_SHARE_PCT, 3)
    investors_pool = round(distributable_profit - owner_share, 3)

    shares = []
    for inv in investments:
        amount = float(inv["amount"] or 0)
        pct = (amount / total_invested) if total_invested > 0 else 0
        share = round(investors_pool * pct, 3)
        shares.append({
            "investor_id": inv["investor_id"],
            "investor_name": inv["investor_name"],
            "contribution_amount": amount,
            "contribution_pct": round(pct * 100, 3),
            "profit_share": share,
        })

    return {
        "category": row_to_dict(category),
        "total_sold": financials.get("total_sold", 0),
        "total_cost": financials.get("total_cost", 0),
        "total_profit": total_profit,
        "total_invested": total_invested,
        "owner_share_pct": OWNER_SHARE_PCT * 100,
        "owner_share": owner_share,
        "investors_pool": investors_pool,
        "investor_shares": shares,
        "has_loss": total_profit < 0,
    }


@router.get("/summary")
async def get_investors_summary(user=Depends(get_current_user)):
    """ملخص شامل: كل فئة + إجمالي ربحها + توزيع المستثمرين فيها."""
    require_access(user)
    pool = await get_pool()

    categories = await pool.fetch("SELECT id, name, icon FROM warehouse_categories ORDER BY name ASC")

    result = []
    grand_total_profit = 0.0
    grand_owner_share = 0.0
    grand_investors_pool = 0.0

    for cat in categories:
        cat_dict = row_to_dict(cat)
        financials = await get_category_total_profit(pool, cat["id"])
        total_profit = float(financials.get("total_profit") or 0)

        inv_rows = await pool.fetch(
            """
            SELECT wci.amount, wi.id AS investor_id, wi.name AS investor_name
            FROM warehouse_category_investments wci
            JOIN warehouse_investors wi ON wi.id = wci.investor_id
            WHERE wci.category_id = $1
            ORDER BY wci.amount DESC
            """,
            cat["id"],
        )
        investments = [row_to_dict(r) for r in inv_rows]
        total_invested = sum(float(i["amount"] or 0) for i in investments)

        distributable_profit = max(total_profit, 0)
        owner_share = round(distributable_profit * OWNER_SHARE_PCT, 3)
        investors_pool = round(distributable_profit - owner_share, 3)

        if total_profit > 0:
            grand_total_profit += total_profit
            grand_owner_share += owner_share
            grand_investors_pool += investors_pool

        cat_dict.update({
            "total_profit": total_profit,
            "total_invested": total_invested,
            "investors_count": len(investments),
            "owner_share": owner_share,
            "investors_pool": investors_pool,
        })
        result.append(cat_dict)

    return {
        "categories": result,
        "totals": {
            "total_profit": grand_total_profit,
            "owner_share": round(grand_owner_share, 3),
            "investors_pool": round(grand_investors_pool, 3),
        },
    }
