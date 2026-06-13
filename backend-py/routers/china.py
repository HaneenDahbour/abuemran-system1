from decimal import Decimal
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role

router = APIRouter()


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


def require_china_access(user):
    require_role(user, "admin", "accountant")


CURRENCIES = ("JOD", "USD", "CNY")


def parse_currency(value: Optional[str]) -> str:
    v = (value or "JOD").strip().upper()
    if v not in CURRENCIES:
        raise HTTPException(status_code=400, detail="العملة غير مدعومة")
    return v


def parse_exchange_rate(value, currency: str) -> float:
    if value is None:
        return 1.0
    try:
        rate = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="سعر الصرف غير صحيح")
    if rate <= 0:
        raise HTTPException(status_code=400, detail="سعر الصرف يجب أن يكون أكبر من صفر")
    if currency == "JOD":
        return 1.0
    return rate


# ── Pydantic models ──────────────────────────────────────────

class InvestorIn(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None


class InvestorTransactionIn(BaseModel):
    type: str  # contribution | return | profit_share
    amount: float
    trans_date: Optional[str] = None
    notes: Optional[str] = None


class ChinaSupplierIn(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None


class PaymentIn(BaseModel):
    supplier_name: str
    supplier_id: Optional[int] = None
    amount: float
    currency: Optional[str] = "JOD"
    exchange_rate: Optional[float] = 1
    payment_date: Optional[str] = None
    notes: Optional[str] = None


class PurchaseIn(BaseModel):
    item_name: str
    quantity: Optional[float] = 1
    amount: float
    currency: Optional[str] = "JOD"
    exchange_rate: Optional[float] = 1
    purchase_date: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_id: Optional[int] = None
    notes: Optional[str] = None


class SaleIn(BaseModel):
    item_name: str
    quantity: Optional[float] = 1
    amount: float
    currency: Optional[str] = "JOD"
    exchange_rate: Optional[float] = 1
    sale_date: Optional[str] = None
    buyer_name: Optional[str] = None
    notes: Optional[str] = None


# ── Investors ─────────────────────────────────────────────────

@router.get("/investors")
async def list_investors(user=Depends(get_current_user)):
    require_china_access(user)
    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT
            ci.*,
            COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'contribution'), 0) AS total_contributed,
            COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'return'), 0)       AS total_returned,
            COALESCE(SUM(t.amount) FILTER (WHERE t.type = 'profit_share'), 0) AS total_profit_share
        FROM china_investors ci
        LEFT JOIN china_investor_transactions t ON t.investor_id = ci.id
        GROUP BY ci.id
        ORDER BY ci.name ASC
    """)

    return [row_to_dict(r) for r in rows]


@router.post("/investors")
async def create_investor(data: InvestorIn, user=Depends(get_current_user)):
    require_china_access(user)

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم المستثمر مطلوب")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO china_investors (name, phone, notes, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                name, (data.phone or "").strip() or None, (data.notes or "").strip() or None,
                user.get("id"),
            )
            await insert_audit(conn, user, "إضافة مستثمر صين", f"مستثمر: {name}")
            return row_to_dict(row)


@router.put("/investors/{investor_id}")
async def update_investor(investor_id: int, data: InvestorIn, user=Depends(get_current_user)):
    require_china_access(user)

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم المستثمر مطلوب")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE china_investors
                SET name=$1, phone=$2, notes=$3
                WHERE id=$4
                RETURNING *
                """,
                name, (data.phone or "").strip() or None, (data.notes or "").strip() or None,
                investor_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="المستثمر غير موجود")
            await insert_audit(conn, user, "تعديل مستثمر صين", f"مستثمر: {name}")
            return row_to_dict(row)


@router.delete("/investors/{investor_id}")
async def delete_investor(investor_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM china_investors WHERE id=$1 RETURNING id, name", investor_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="المستثمر غير موجود")
            await insert_audit(conn, user, "حذف مستثمر صين", f"مستثمر: {row['name']}")
            return {"success": True}


# ── Investor transactions ────────────────────────────────────

@router.get("/investors/{investor_id}/transactions")
async def list_investor_transactions(investor_id: int, user=Depends(get_current_user)):
    require_china_access(user)
    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT t.*, u.full_name AS created_by_name
        FROM china_investor_transactions t
        LEFT JOIN users u ON u.id = t.created_by
        WHERE t.investor_id = $1
        ORDER BY t.trans_date DESC, t.id DESC
        """,
        investor_id,
    )

    return [row_to_dict(r) for r in rows]


@router.post("/investors/{investor_id}/transactions")
async def create_investor_transaction(investor_id: int, data: InvestorTransactionIn, user=Depends(get_current_user)):
    require_china_access(user)

    if data.type not in ("contribution", "return", "profit_share"):
        raise HTTPException(status_code=400, detail="نوع الحركة غير صحيح")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            investor = await conn.fetchrow("SELECT id, name FROM china_investors WHERE id=$1", investor_id)
            if not investor:
                raise HTTPException(status_code=404, detail="المستثمر غير موجود")

            row = await conn.fetchrow(
                """
                INSERT INTO china_investor_transactions (investor_id, type, amount, trans_date, notes, created_by)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                investor_id, data.type, data.amount, parse_date(data.trans_date),
                (data.notes or "").strip() or None, user.get("id"),
            )

            type_label = {
                "contribution": "إضافة رأس مال",
                "return": "استرجاع",
                "profit_share": "حصة من الربح",
            }[data.type]

            await insert_audit(
                conn, user, "حركة مستثمر صين",
                f"{investor['name']} — {type_label}: {data.amount:.2f} د.أ",
            )

            return row_to_dict(row)


@router.delete("/transactions/{transaction_id}")
async def delete_investor_transaction(transaction_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM china_investor_transactions WHERE id=$1 RETURNING id", transaction_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="الحركة غير موجودة")
            await insert_audit(conn, user, "حذف حركة مستثمر صين", f"حركة #{transaction_id}")
            return {"success": True}


# ── Suppliers (موردو الصين) ──────────────────────────────────────

@router.get("/suppliers")
async def list_china_suppliers(user=Depends(get_current_user)):
    require_china_access(user)
    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT
            cs.*,
            COALESCE((SELECT SUM(p.amount_jod) FROM china_payments  p WHERE p.supplier_id = cs.id), 0) AS total_paid_jod,
            COALESCE((SELECT SUM(p.amount_jod) FROM china_purchases p WHERE p.supplier_id = cs.id), 0) AS total_purchased_jod,
            COALESCE((SELECT COUNT(*) FROM china_payments  p WHERE p.supplier_id = cs.id), 0) AS payments_count,
            COALESCE((SELECT COUNT(*) FROM china_purchases p WHERE p.supplier_id = cs.id), 0) AS purchases_count
        FROM china_suppliers cs
        ORDER BY cs.name ASC
    """)

    return [row_to_dict(r) for r in rows]


@router.post("/suppliers")
async def create_china_supplier(data: ChinaSupplierIn, user=Depends(get_current_user)):
    require_china_access(user)

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم المورد مطلوب")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            duplicate = await conn.fetchrow(
                "SELECT id FROM china_suppliers WHERE LOWER(name) = LOWER($1) LIMIT 1", name
            )
            if duplicate:
                raise HTTPException(status_code=400, detail="المورد موجود مسبقاً")

            row = await conn.fetchrow(
                """
                INSERT INTO china_suppliers (name, phone, notes, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                name, (data.phone or "").strip() or None, (data.notes or "").strip() or None,
                user.get("id"),
            )
            await insert_audit(conn, user, "إضافة مورد صين", f"مورد: {name}")
            return row_to_dict(row)


@router.put("/suppliers/{supplier_id}")
async def update_china_supplier(supplier_id: int, data: ChinaSupplierIn, user=Depends(get_current_user)):
    require_china_access(user)

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم المورد مطلوب")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            duplicate = await conn.fetchrow(
                "SELECT id FROM china_suppliers WHERE LOWER(name) = LOWER($1) AND id <> $2 LIMIT 1",
                name, supplier_id,
            )
            if duplicate:
                raise HTTPException(status_code=400, detail="الاسم مستخدم مسبقاً")

            row = await conn.fetchrow(
                """
                UPDATE china_suppliers
                SET name=$1, phone=$2, notes=$3
                WHERE id=$4
                RETURNING *
                """,
                name, (data.phone or "").strip() or None, (data.notes or "").strip() or None,
                supplier_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="المورد غير موجود")
            await insert_audit(conn, user, "تعديل مورد صين", f"مورد: {name}")
            return row_to_dict(row)


@router.delete("/suppliers/{supplier_id}")
async def delete_china_supplier(supplier_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM china_suppliers WHERE id=$1 RETURNING id, name", supplier_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="المورد غير موجود")
            await insert_audit(conn, user, "حذف مورد صين", f"مورد: {row['name']}")
            return {"success": True}


@router.get("/suppliers/{supplier_id}/statement")
async def china_supplier_statement(supplier_id: int, user=Depends(get_current_user)):
    require_china_access(user)
    pool = await get_pool()

    supplier = await pool.fetchrow("SELECT * FROM china_suppliers WHERE id=$1", supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="المورد غير موجود")

    payments = await pool.fetch(
        """
        SELECT p.*, u.full_name AS created_by_name
        FROM china_payments p
        LEFT JOIN users u ON u.id = p.created_by
        WHERE p.supplier_id = $1
        ORDER BY p.payment_date DESC, p.id DESC
        """,
        supplier_id,
    )

    purchases = await pool.fetch(
        """
        SELECT p.*, u.full_name AS created_by_name
        FROM china_purchases p
        LEFT JOIN users u ON u.id = p.created_by
        WHERE p.supplier_id = $1
        ORDER BY p.purchase_date DESC, p.id DESC
        """,
        supplier_id,
    )

    totals_by_currency = {}
    for p in list(payments) + list(purchases):
        cur = p["currency"] or "JOD"
        totals_by_currency.setdefault(cur, {"payments": 0.0, "purchases": 0.0})

    for p in payments:
        cur = p["currency"] or "JOD"
        totals_by_currency[cur]["payments"] += float(p["amount"] or 0)

    for p in purchases:
        cur = p["currency"] or "JOD"
        totals_by_currency[cur]["purchases"] += float(p["amount"] or 0)

    total_paid_jod = sum(float(p["amount_jod"] or 0) for p in payments)
    total_purchased_jod = sum(float(p["amount_jod"] or 0) for p in purchases)

    return {
        "supplier": row_to_dict(supplier),
        "payments": [row_to_dict(r) for r in payments],
        "purchases": [row_to_dict(r) for r in purchases],
        "totals_by_currency": totals_by_currency,
        "total_paid_jod": round(total_paid_jod, 3),
        "total_purchased_jod": round(total_purchased_jod, 3),
        "balance_jod": round(total_purchased_jod - total_paid_jod, 3),
    }


# ── Supplier payments (دفعات للموردين) ──────────────────────────

@router.get("/payments")
async def list_payments(user=Depends(get_current_user)):
    require_china_access(user)
    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT p.*, u.full_name AS created_by_name
        FROM china_payments p
        LEFT JOIN users u ON u.id = p.created_by
        ORDER BY p.payment_date DESC, p.id DESC
    """)

    return [row_to_dict(r) for r in rows]


@router.post("/payments")
async def create_payment(data: PaymentIn, user=Depends(get_current_user)):
    require_china_access(user)

    supplier_name = (data.supplier_name or "").strip()
    if not supplier_name:
        raise HTTPException(status_code=400, detail="اسم المورد مطلوب")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    currency = parse_currency(data.currency)
    exchange_rate = parse_exchange_rate(data.exchange_rate, currency)
    amount_jod = round(data.amount * exchange_rate, 3)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO china_payments
                  (supplier_name, supplier_id, amount, currency, exchange_rate, amount_jod,
                   payment_date, notes, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
                """,
                supplier_name, data.supplier_id, data.amount, currency, exchange_rate, amount_jod,
                parse_date(data.payment_date),
                (data.notes or "").strip() or None, user.get("id"),
            )
            await insert_audit(
                conn, user, "دفعة لمورد صين",
                f"{supplier_name} — {data.amount:.2f} {currency}",
            )
            return row_to_dict(row)


@router.put("/payments/{payment_id}")
async def update_payment(payment_id: int, data: PaymentIn, user=Depends(get_current_user)):
    require_china_access(user)

    supplier_name = (data.supplier_name or "").strip()
    if not supplier_name:
        raise HTTPException(status_code=400, detail="اسم المورد مطلوب")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    currency = parse_currency(data.currency)
    exchange_rate = parse_exchange_rate(data.exchange_rate, currency)
    amount_jod = round(data.amount * exchange_rate, 3)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE china_payments
                SET supplier_name=$1, supplier_id=$2, amount=$3, currency=$4,
                    exchange_rate=$5, amount_jod=$6, payment_date=$7, notes=$8
                WHERE id=$9
                RETURNING *
                """,
                supplier_name, data.supplier_id, data.amount, currency, exchange_rate, amount_jod,
                parse_date(data.payment_date), (data.notes or "").strip() or None,
                payment_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="الدفعة غير موجودة")
            await insert_audit(
                conn, user, "تعديل دفعة مورد صين",
                f"{supplier_name} — {data.amount:.2f} {currency}",
            )
            return row_to_dict(row)


@router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM china_payments WHERE id=$1 RETURNING id", payment_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="الدفعة غير موجودة")
            await insert_audit(conn, user, "حذف دفعة مورد صين", f"دفعة #{payment_id}")
            return {"success": True}


# ── Purchases (مشتريات الصين) ────────────────────────────────────

@router.get("/purchases")
async def list_purchases(user=Depends(get_current_user)):
    require_china_access(user)
    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT p.*, u.full_name AS created_by_name
        FROM china_purchases p
        LEFT JOIN users u ON u.id = p.created_by
        ORDER BY p.purchase_date DESC, p.id DESC
    """)

    return [row_to_dict(r) for r in rows]


@router.post("/purchases")
async def create_purchase(data: PurchaseIn, user=Depends(get_current_user)):
    require_china_access(user)

    item_name = (data.item_name or "").strip()
    if not item_name:
        raise HTTPException(status_code=400, detail="اسم البضاعة مطلوب")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    currency = parse_currency(data.currency)
    exchange_rate = parse_exchange_rate(data.exchange_rate, currency)
    amount_jod = round(data.amount * exchange_rate, 3)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO china_purchases
                  (item_name, quantity, amount, currency, exchange_rate, amount_jod,
                   purchase_date, supplier_name, supplier_id, notes, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
                """,
                item_name, data.quantity or 1, data.amount, currency, exchange_rate, amount_jod,
                parse_date(data.purchase_date),
                (data.supplier_name or "").strip() or None, data.supplier_id,
                (data.notes or "").strip() or None,
                user.get("id"),
            )
            await insert_audit(
                conn, user, "مشتريات صين",
                f"{item_name} — {data.amount:.2f} {currency}",
            )
            return row_to_dict(row)


@router.put("/purchases/{purchase_id}")
async def update_purchase(purchase_id: int, data: PurchaseIn, user=Depends(get_current_user)):
    require_china_access(user)

    item_name = (data.item_name or "").strip()
    if not item_name:
        raise HTTPException(status_code=400, detail="اسم البضاعة مطلوب")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    currency = parse_currency(data.currency)
    exchange_rate = parse_exchange_rate(data.exchange_rate, currency)
    amount_jod = round(data.amount * exchange_rate, 3)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE china_purchases
                SET item_name=$1, quantity=$2, amount=$3, currency=$4, exchange_rate=$5,
                    amount_jod=$6, purchase_date=$7, supplier_name=$8, supplier_id=$9, notes=$10
                WHERE id=$11
                RETURNING *
                """,
                item_name, data.quantity or 1, data.amount, currency, exchange_rate, amount_jod,
                parse_date(data.purchase_date),
                (data.supplier_name or "").strip() or None, data.supplier_id,
                (data.notes or "").strip() or None,
                purchase_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="عملية الشراء غير موجودة")
            await insert_audit(
                conn, user, "تعديل مشتريات صين",
                f"{item_name} — {data.amount:.2f} {currency}",
            )
            return row_to_dict(row)


@router.delete("/purchases/{purchase_id}")
async def delete_purchase(purchase_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM china_purchases WHERE id=$1 RETURNING id", purchase_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="عملية الشراء غير موجودة")
            await insert_audit(conn, user, "حذف مشتريات صين", f"عملية #{purchase_id}")
            return {"success": True}


# ── Sales (مبيعات بضاعة الصين) ───────────────────────────────────

@router.get("/sales")
async def list_sales(user=Depends(get_current_user)):
    require_china_access(user)
    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT s.*, u.full_name AS created_by_name
        FROM china_sales s
        LEFT JOIN users u ON u.id = s.created_by
        ORDER BY s.sale_date DESC, s.id DESC
    """)

    return [row_to_dict(r) for r in rows]


@router.post("/sales")
async def create_sale(data: SaleIn, user=Depends(get_current_user)):
    require_china_access(user)

    item_name = (data.item_name or "").strip()
    if not item_name:
        raise HTTPException(status_code=400, detail="اسم البضاعة مطلوب")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    currency = parse_currency(data.currency)
    exchange_rate = parse_exchange_rate(data.exchange_rate, currency)
    amount_jod = round(data.amount * exchange_rate, 3)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO china_sales
                  (item_name, quantity, amount, currency, exchange_rate, amount_jod,
                   sale_date, buyer_name, notes, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
                """,
                item_name, data.quantity or 1, data.amount, currency, exchange_rate, amount_jod,
                parse_date(data.sale_date),
                (data.buyer_name or "").strip() or None, (data.notes or "").strip() or None,
                user.get("id"),
            )
            await insert_audit(
                conn, user, "مبيعات صين",
                f"{item_name} — {data.amount:.2f} {currency}",
            )
            return row_to_dict(row)


@router.put("/sales/{sale_id}")
async def update_sale(sale_id: int, data: SaleIn, user=Depends(get_current_user)):
    require_china_access(user)

    item_name = (data.item_name or "").strip()
    if not item_name:
        raise HTTPException(status_code=400, detail="اسم البضاعة مطلوب")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    currency = parse_currency(data.currency)
    exchange_rate = parse_exchange_rate(data.exchange_rate, currency)
    amount_jod = round(data.amount * exchange_rate, 3)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE china_sales
                SET item_name=$1, quantity=$2, amount=$3, currency=$4, exchange_rate=$5,
                    amount_jod=$6, sale_date=$7, buyer_name=$8, notes=$9
                WHERE id=$10
                RETURNING *
                """,
                item_name, data.quantity or 1, data.amount, currency, exchange_rate, amount_jod,
                parse_date(data.sale_date),
                (data.buyer_name or "").strip() or None, (data.notes or "").strip() or None,
                sale_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="عملية البيع غير موجودة")
            await insert_audit(
                conn, user, "تعديل مبيعات صين",
                f"{item_name} — {data.amount:.2f} {currency}",
            )
            return row_to_dict(row)


@router.delete("/sales/{sale_id}")
async def delete_sale(sale_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM china_sales WHERE id=$1 RETURNING id", sale_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="عملية البيع غير موجودة")
            await insert_audit(conn, user, "حذف مبيعات صين", f"عملية #{sale_id}")
            return {"success": True}


# ── Summary / Dashboard ──────────────────────────────────────────

@router.get("/summary")
async def get_summary(user=Depends(get_current_user)):
    require_china_access(user)
    pool = await get_pool()

    contributions = await pool.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM china_investor_transactions WHERE type='contribution'"
    )
    returns = await pool.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM china_investor_transactions WHERE type='return'"
    )
    profit_shares_paid = await pool.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM china_investor_transactions WHERE type='profit_share'"
    )
    total_payments = await pool.fetchval(
        "SELECT COALESCE(SUM(amount_jod),0) FROM china_payments"
    )
    total_purchases = await pool.fetchval(
        "SELECT COALESCE(SUM(amount_jod),0) FROM china_purchases"
    )
    total_sales = await pool.fetchval(
        "SELECT COALESCE(SUM(amount_jod),0) FROM china_sales"
    )

    contributions = float(contributions or 0)
    returns = float(returns or 0)
    profit_shares_paid = float(profit_shares_paid or 0)
    total_payments = float(total_payments or 0)
    total_purchases = float(total_purchases or 0)
    total_sales = float(total_sales or 0)

    net_capital = contributions - returns - profit_shares_paid
    gross_profit = total_sales - total_purchases
    remaining_capital = net_capital - total_purchases - total_payments + total_sales

    return {
        "total_contributions": contributions,
        "total_returns": returns,
        "total_profit_shares_paid": profit_shares_paid,
        "net_capital": net_capital,
        "total_payments_to_suppliers": total_payments,
        "total_purchases": total_purchases,
        "total_sales": total_sales,
        "gross_profit": gross_profit,
        "remaining_capital": remaining_capital,
    }
