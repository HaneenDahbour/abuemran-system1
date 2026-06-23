"""
روتر الأراضي (Aradi) — نظام إدارة قطع الأراضي والمشترين والمستثمرين.

هذا الوحدة مستقلة تماماً عن المستودع والمحلات.
جميع الجداول تبدأ بـ aradi_
"""

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_permission, require_role

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────

def to_val(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def row_to_dict(row):
    return {k: to_val(row[k]) for k in row.keys()}


def parse_date(value: Optional[str], field_name: str = "التاريخ") -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} غير صحيح")


def parse_date_required(value: Optional[str], field_name: str = "التاريخ") -> date:
    d = parse_date(value, field_name)
    if d is None:
        raise HTTPException(status_code=400, detail=f"{field_name} مطلوب")
    return d


def validate_amount(value, field_name: str = "المبلغ", allow_zero: bool = True) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field_name} غير صحيح")
    if not allow_zero and v <= 0:
        raise HTTPException(status_code=400, detail=f"{field_name} يجب أن يكون أكبر من صفر")
    if v < 0:
        raise HTTPException(status_code=400, detail=f"{field_name} لا يمكن أن يكون سالباً")
    return round(v, 3)


def require_access(user):
    """admin أو accountant لديهم صلاحية كاملة على الأراضي."""
    require_role(user, "admin", "accountant")


def add_months(d: date, months: int) -> date:
    """Add N months to a date, clamping day to last day of month."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


async def audit(conn, user, action: str, entity_type: str, entity_id: Optional[int], detail: str):
    try:
        await conn.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, detail)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user.get("id"),
            user.get("full_name") or user.get("username") or "مستخدم",
            action,
            entity_type,
            entity_id,
            detail,
        )
    except Exception:
        pass  # لا نوقف العملية بسبب الـ audit


# ═══════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_aradi_dashboard(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        row = await pool.fetchrow("""
            WITH plots AS (
                SELECT
                    COUNT(*)                                         AS total_plots,
                    COUNT(*) FILTER (WHERE status = 'available')    AS available_plots,
                    COUNT(*) FILTER (WHERE status = 'sold')         AS sold_plots,
                    COUNT(*) FILTER (WHERE status = 'reserved')     AS reserved_plots,
                    COUNT(*) FILTER (WHERE status = 'invested')     AS invested_plots,
                    COALESCE(SUM(expected_sale_price)
                        FILTER (WHERE status = 'sold'), 0)          AS total_sales_value
                FROM aradi_plots
            ),
            buyer_payments AS (
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM aradi_buyer_payments
                WHERE status = 'confirmed'
            ),
            contracts AS (
                SELECT COALESCE(SUM(sale_price), 0) AS total_sale_price
                FROM aradi_sale_contracts
                WHERE status IN ('active', 'completed')
            ),
            overdue AS (
                SELECT COUNT(*) AS cnt
                FROM aradi_installments i
                WHERE i.due_date < CURRENT_DATE
                  AND COALESCE((
                      SELECT SUM(bp.amount)
                      FROM aradi_buyer_payments bp
                      WHERE bp.installment_id = i.id
                        AND bp.status = 'confirmed'
                  ), 0) < i.amount
            ),
            investments AS (
                SELECT
                    COALESCE(SUM(capital_amount), 0)  AS total_capital,
                    COALESCE(SUM(profit_amount), 0)   AS total_profit,
                    COALESCE(SUM(total_due), 0)       AS total_due
                FROM aradi_investments
                WHERE status != 'cancelled'
            ),
            investor_payments AS (
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM aradi_investor_payments
                WHERE status = 'confirmed'
            ),
            expenses AS (
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM aradi_expenses
                WHERE status = 'confirmed'
            )
            SELECT
                plots.total_plots,
                plots.available_plots,
                plots.sold_plots,
                plots.reserved_plots,
                plots.invested_plots,
                plots.total_sales_value,
                contracts.total_sale_price,
                buyer_payments.total                                            AS total_buyer_payments,
                contracts.total_sale_price - buyer_payments.total               AS total_remaining_from_buyers,
                overdue.cnt                                                     AS overdue_installments_count,
                investments.total_capital                                       AS total_investor_capital,
                investments.total_profit                                        AS total_investor_profit,
                investments.total_due                                           AS total_investor_due,
                investor_payments.total                                         AS total_investor_payments,
                investments.total_due - investor_payments.total                 AS remaining_investor_obligations,
                expenses.total                                                  AS total_expenses,
                buyer_payments.total - investor_payments.total - expenses.total AS net_cash
            FROM plots, buyer_payments, contracts, overdue, investments, investor_payments, expenses
        """)
        return row_to_dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في لوحة التحكم: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# Plots — قطع الأراضي
# ═══════════════════════════════════════════════════════════════

class PlotRequest(BaseModel):
    plot_number: str
    project_name: Optional[str] = None
    location: Optional[str] = None
    area: Optional[float] = None
    purchase_price: Optional[float] = 0
    expected_sale_price: Optional[float] = 0
    status: Optional[str] = "available"
    notes: Optional[str] = None


ALLOWED_PLOT_STATUSES = {"available", "reserved", "sold", "invested", "blocked"}


@router.get("/plots")
async def list_plots(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT p.*,
                   u.full_name AS created_by_name
            FROM aradi_plots p
            LEFT JOIN users u ON u.id = p.created_by
            ORDER BY p.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plots")
async def create_plot(data: PlotRequest, user=Depends(get_current_user)):
    require_access(user)
    if not data.plot_number.strip():
        raise HTTPException(status_code=400, detail="رقم القطعة مطلوب")
    if data.status not in ALLOWED_PLOT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة القطعة غير صحيحة")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_plots
                    (plot_number, project_name, location, area,
                     purchase_price, expected_sale_price, status, notes, created_by)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                RETURNING *
            """,
                data.plot_number.strip(),
                data.project_name,
                data.location,
                data.area,
                round(data.purchase_price or 0, 3),
                round(data.expected_sale_price or 0, 3),
                data.status or "available",
                data.notes,
                user.get("id"),
            )
            await audit(conn, user, "create", "aradi_plot", row["id"],
                        f"إضافة قطعة أرض رقم {row['plot_number']}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        if "aradi_plots_plot_number_key" in str(e):
            raise HTTPException(status_code=400, detail=f"رقم القطعة '{data.plot_number}' مستخدم مسبقاً")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plots/{plot_id}")
async def get_plot(plot_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        row = await pool.fetchrow("""
            SELECT p.*, u.full_name AS created_by_name
            FROM aradi_plots p
            LEFT JOIN users u ON u.id = p.created_by
            WHERE p.id = $1
        """, plot_id)
        if not row:
            raise HTTPException(status_code=404, detail="القطعة غير موجودة")
        return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/plots/{plot_id}")
async def update_plot(plot_id: int, data: PlotRequest, user=Depends(get_current_user)):
    require_access(user)
    if data.status not in ALLOWED_PLOT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة القطعة غير صحيحة")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE aradi_plots
                SET plot_number         = $1,
                    project_name        = $2,
                    location            = $3,
                    area                = $4,
                    purchase_price      = $5,
                    expected_sale_price = $6,
                    status              = $7,
                    notes               = $8,
                    updated_at          = NOW()
                WHERE id = $9
                RETURNING *
            """,
                data.plot_number.strip(),
                data.project_name,
                data.location,
                data.area,
                round(data.purchase_price or 0, 3),
                round(data.expected_sale_price or 0, 3),
                data.status,
                data.notes,
                plot_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="القطعة غير موجودة")
            await audit(conn, user, "update", "aradi_plot", plot_id,
                        f"تعديل قطعة أرض رقم {row['plot_number']}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        if "aradi_plots_plot_number_key" in str(e):
            raise HTTPException(status_code=400, detail=f"رقم القطعة '{data.plot_number}' مستخدم مسبقاً")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/plots/{plot_id}")
async def delete_plot(plot_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            contracts = await conn.fetchval(
                "SELECT COUNT(*) FROM aradi_sale_contracts WHERE plot_id=$1", plot_id
            )
            if contracts > 0:
                raise HTTPException(status_code=400, detail="لا يمكن حذف القطعة لوجود عقود مرتبطة بها")
            investments = await conn.fetchval(
                "SELECT COUNT(*) FROM aradi_investments WHERE plot_id=$1", plot_id
            )
            if investments > 0:
                raise HTTPException(status_code=400, detail="لا يمكن حذف القطعة لوجود استثمارات مرتبطة بها")
            row = await conn.fetchrow(
                "DELETE FROM aradi_plots WHERE id=$1 RETURNING *", plot_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="القطعة غير موجودة")
            await audit(conn, user, "delete", "aradi_plot", plot_id,
                        f"حذف قطعة أرض رقم {row['plot_number']}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Buyers — المشترون
# ═══════════════════════════════════════════════════════════════

class BuyerRequest(BaseModel):
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


@router.get("/buyers")
async def list_buyers(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("SELECT * FROM aradi_buyers ORDER BY id DESC")
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/buyers")
async def create_buyer(data: BuyerRequest, user=Depends(get_current_user)):
    require_access(user)
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="اسم المشتري مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_buyers (name, phone, address, notes)
                VALUES ($1,$2,$3,$4) RETURNING *
            """, data.name.strip(), data.phone, data.address, data.notes)
            await audit(conn, user, "create", "aradi_buyer", row["id"],
                        f"إضافة مشترٍ: {row['name']}")
            return row_to_dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buyers/{buyer_id}")
async def get_buyer(buyer_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        row = await pool.fetchrow("SELECT * FROM aradi_buyers WHERE id = $1", buyer_id)
        if not row:
            raise HTTPException(status_code=404, detail="المشتري غير موجود")
        return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/buyers/{buyer_id}")
async def update_buyer(buyer_id: int, data: BuyerRequest, user=Depends(get_current_user)):
    require_access(user)
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="اسم المشتري مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE aradi_buyers
                SET name=COALESCE($1,name), phone=$2, address=$3, notes=$4, updated_at=NOW()
                WHERE id=$5 RETURNING *
            """, data.name.strip(), data.phone, data.address, data.notes, buyer_id)
            if not row:
                raise HTTPException(status_code=404, detail="المشتري غير موجود")
            await audit(conn, user, "update", "aradi_buyer", buyer_id,
                        f"تعديل بيانات المشتري: {row['name']}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/buyers/{buyer_id}")
async def delete_buyer(buyer_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            contracts = await conn.fetchval(
                "SELECT COUNT(*) FROM aradi_sale_contracts WHERE buyer_id=$1", buyer_id
            )
            if contracts > 0:
                raise HTTPException(status_code=400, detail="لا يمكن حذف المشتري لوجود عقود مرتبطة به")
            row = await conn.fetchrow(
                "DELETE FROM aradi_buyers WHERE id=$1 RETURNING *", buyer_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="المشتري غير موجود")
            await audit(conn, user, "delete", "aradi_buyer", buyer_id,
                        f"حذف المشتري: {row['name']}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Sale Contracts — عقود البيع
# ═══════════════════════════════════════════════════════════════

class ContractRequest(BaseModel):
    plot_id: Optional[int] = None
    buyer_id: int
    contract_number: Optional[str] = None
    sale_price: float
    down_payment: Optional[float] = 0
    installment_amount: Optional[float] = 0
    installment_count: Optional[int] = 0
    first_installment_date: Optional[str] = None
    status: Optional[str] = "active"
    notes: Optional[str] = None


ALLOWED_CONTRACT_STATUSES = {"active", "completed", "cancelled", "defaulted"}


@router.get("/contracts")
async def list_contracts(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT sc.*,
                   b.name  AS buyer_name,
                   p.plot_number
            FROM aradi_sale_contracts sc
            JOIN aradi_buyers b ON b.id = sc.buyer_id
            LEFT JOIN aradi_plots p ON p.id = sc.plot_id
            ORDER BY sc.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contracts")
async def create_contract(data: ContractRequest, user=Depends(get_current_user)):
    require_access(user)

    sale_price = validate_amount(data.sale_price, "سعر البيع")
    down_payment = validate_amount(data.down_payment or 0, "الدفعة الأولى")
    installment_amount = validate_amount(data.installment_amount or 0, "مبلغ القسط")
    installment_count = int(data.installment_count or 0)
    if installment_count < 0:
        raise HTTPException(status_code=400, detail="عدد الأقساط لا يمكن أن يكون سالباً")
    if (data.status or "active") not in ALLOWED_CONTRACT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة العقد غير صحيحة")

    first_date: Optional[date] = parse_date(data.first_installment_date, "تاريخ أول قسط")
    if installment_count > 0 and installment_amount > 0 and first_date is None:
        raise HTTPException(status_code=400,
                            detail="تاريخ أول قسط مطلوب عند تحديد الأقساط")

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # 1. Insert contract
                contract = await conn.fetchrow("""
                    INSERT INTO aradi_sale_contracts
                        (plot_id, buyer_id, contract_number, sale_price,
                         down_payment, installment_amount, installment_count,
                         first_installment_date, status, notes, created_by)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    RETURNING *
                """,
                    data.plot_id,
                    data.buyer_id,
                    data.contract_number,
                    sale_price,
                    down_payment,
                    installment_amount,
                    installment_count,
                    first_date,
                    data.status or "active",
                    data.notes,
                    user.get("id"),
                )
                contract_id = contract["id"]

                # 2. Record down payment if > 0
                if down_payment > 0:
                    await conn.execute("""
                        INSERT INTO aradi_buyer_payments
                            (contract_id, payment_type, amount, payment_date,
                             method, status, notes, created_by)
                        VALUES ($1,'down_payment',$2,CURRENT_DATE,'cash','confirmed',
                                'دفعة أولى عند إنشاء العقد',$3)
                    """, contract_id, down_payment, user.get("id"))

                # 3. Generate installment schedule
                if installment_count > 0 and installment_amount > 0 and first_date:
                    for n in range(1, installment_count + 1):
                        due = add_months(first_date, n - 1)
                        await conn.execute("""
                            INSERT INTO aradi_installments
                                (contract_id, installment_number, due_date, amount)
                            VALUES ($1, $2, $3, $4)
                        """, contract_id, n, due, installment_amount)

                # 4. Update plot status to sold if contract is active
                if data.plot_id and (data.status or "active") == "active":
                    await conn.execute("""
                        UPDATE aradi_plots
                        SET status = 'sold', updated_at = NOW()
                        WHERE id = $1
                    """, data.plot_id)

                await audit(conn, user, "create", "aradi_contract", contract_id,
                            f"إنشاء عقد بيع رقم {contract['contract_number'] or contract_id}")

        return row_to_dict(contract)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء العقد: {str(e)}")


@router.get("/contracts/{contract_id}")
async def get_contract(contract_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        row = await pool.fetchrow("""
            SELECT sc.*,
                   b.name  AS buyer_name,
                   p.plot_number
            FROM aradi_sale_contracts sc
            JOIN aradi_buyers b ON b.id = sc.buyer_id
            LEFT JOIN aradi_plots p ON p.id = sc.plot_id
            WHERE sc.id = $1
        """, contract_id)
        if not row:
            raise HTTPException(status_code=404, detail="العقد غير موجود")
        return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contracts/{contract_id}")
async def update_contract(contract_id: int, data: ContractRequest, user=Depends(get_current_user)):
    require_access(user)
    if (data.status or "active") not in ALLOWED_CONTRACT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة العقد غير صحيحة")
    sale_price = validate_amount(data.sale_price, "سعر البيع")
    down_payment = validate_amount(data.down_payment or 0, "الدفعة الأولى")
    first_date = parse_date(data.first_installment_date, "تاريخ أول قسط")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE aradi_sale_contracts
                SET plot_id                = $1,
                    buyer_id               = $2,
                    contract_number        = $3,
                    sale_price             = $4,
                    down_payment           = $5,
                    installment_amount     = $6,
                    installment_count      = $7,
                    first_installment_date = $8,
                    status                 = $9,
                    notes                  = $10,
                    updated_at             = NOW()
                WHERE id = $11
                RETURNING *
            """,
                data.plot_id,
                data.buyer_id,
                data.contract_number,
                sale_price,
                down_payment,
                round(float(data.installment_amount or 0), 3),
                int(data.installment_count or 0),
                first_date,
                data.status or "active",
                data.notes,
                contract_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="العقد غير موجود")
            await audit(conn, user, "update", "aradi_contract", contract_id,
                        f"تعديل عقد رقم {contract_id}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contracts/{contract_id}")
async def delete_contract(contract_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT * FROM aradi_sale_contracts WHERE id=$1", contract_id
                )
                if not row:
                    raise HTTPException(status_code=404, detail="العقد غير موجود")
                confirmed = await conn.fetchval(
                    "SELECT COUNT(*) FROM aradi_buyer_payments WHERE contract_id=$1 AND status='confirmed'",
                    contract_id,
                )
                if confirmed > 0:
                    raise HTTPException(
                        status_code=400,
                        detail="لا يمكن حذف العقد لوجود دفعات مؤكدة مرتبطة به، قم بإلغائها أولاً",
                    )
                await conn.execute(
                    "DELETE FROM aradi_buyer_payments WHERE contract_id=$1", contract_id
                )
                await conn.execute(
                    "DELETE FROM aradi_installments WHERE contract_id=$1", contract_id
                )
                await conn.execute(
                    "DELETE FROM aradi_sale_contracts WHERE id=$1", contract_id
                )
                if row["plot_id"]:
                    await conn.execute(
                        "UPDATE aradi_plots SET status='available', updated_at=NOW() WHERE id=$1 AND status='sold'",
                        row["plot_id"],
                    )
                await audit(conn, user, "delete", "aradi_contract", contract_id,
                            f"حذف عقد بيع رقم {row['contract_number'] or contract_id}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/{contract_id}/installments")
async def get_contract_installments(contract_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT
                i.*,
                COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    WHERE bp.installment_id = i.id
                      AND bp.status = 'confirmed'
                ), 0) AS paid,
                i.amount - COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    WHERE bp.installment_id = i.id
                      AND bp.status = 'confirmed'
                ), 0) AS remaining,
                CASE
                    WHEN COALESCE((
                        SELECT SUM(bp.amount)
                        FROM aradi_buyer_payments bp
                        WHERE bp.installment_id = i.id
                          AND bp.status = 'confirmed'
                    ), 0) >= i.amount          THEN 'paid'
                    WHEN COALESCE((
                        SELECT SUM(bp.amount)
                        FROM aradi_buyer_payments bp
                        WHERE bp.installment_id = i.id
                          AND bp.status = 'confirmed'
                    ), 0) > 0                  THEN 'partial'
                    WHEN i.due_date < CURRENT_DATE THEN 'overdue'
                    ELSE 'pending'
                END AS computed_status
            FROM aradi_installments i
            WHERE i.contract_id = $1
            ORDER BY i.installment_number
        """, contract_id)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/{contract_id}/payments")
async def get_contract_payments(contract_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT bp.*, i.installment_number, i.due_date AS installment_due_date
            FROM aradi_buyer_payments bp
            LEFT JOIN aradi_installments i ON i.id = bp.installment_id
            WHERE bp.contract_id = $1
            ORDER BY bp.payment_date DESC, bp.id DESC
        """, contract_id)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/{contract_id}/statement")
async def get_contract_statement(contract_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        contract = await pool.fetchrow("""
            SELECT sc.*, b.name AS buyer_name, b.phone AS buyer_phone,
                   p.plot_number, p.location
            FROM aradi_sale_contracts sc
            JOIN aradi_buyers b ON b.id = sc.buyer_id
            LEFT JOIN aradi_plots p ON p.id = sc.plot_id
            WHERE sc.id = $1
        """, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="العقد غير موجود")

        installments = await pool.fetch("""
            SELECT i.*,
                   COALESCE((
                       SELECT SUM(bp.amount)
                       FROM aradi_buyer_payments bp
                       WHERE bp.installment_id = i.id
                         AND bp.status = 'confirmed'
                   ), 0) AS paid,
                   CASE
                       WHEN COALESCE((
                           SELECT SUM(bp.amount)
                           FROM aradi_buyer_payments bp
                           WHERE bp.installment_id = i.id
                             AND bp.status = 'confirmed'
                       ), 0) >= i.amount        THEN 'paid'
                       WHEN COALESCE((
                           SELECT SUM(bp.amount)
                           FROM aradi_buyer_payments bp
                           WHERE bp.installment_id = i.id
                             AND bp.status = 'confirmed'
                       ), 0) > 0               THEN 'partial'
                       WHEN i.due_date < CURRENT_DATE THEN 'overdue'
                       ELSE 'pending'
                   END AS computed_status
            FROM aradi_installments i
            WHERE i.contract_id = $1
            ORDER BY i.installment_number
        """, contract_id)

        payments = await pool.fetch("""
            SELECT * FROM aradi_buyer_payments
            WHERE contract_id = $1
            ORDER BY payment_date, id
        """, contract_id)

        total_paid = sum(
            float(p["amount"]) for p in payments if p["status"] == "confirmed"
        )
        sale_price = float(contract["sale_price"])

        return {
            "contract": row_to_dict(contract),
            "installments": [row_to_dict(r) for r in installments],
            "payments": [row_to_dict(r) for r in payments],
            "summary": {
                "sale_price": sale_price,
                "total_paid": round(total_paid, 3),
                "remaining": round(sale_price - total_paid, 3),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Installments — الأقساط
# ═══════════════════════════════════════════════════════════════

class InstallmentUpdateRequest(BaseModel):
    due_date: Optional[str] = None
    amount: Optional[float] = None
    notes: Optional[str] = None


@router.get("/installments")
async def list_installments(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT i.*,
                   sc.contract_number,
                   b.name AS buyer_name,
                   COALESCE((
                       SELECT SUM(bp.amount)
                       FROM aradi_buyer_payments bp
                       WHERE bp.installment_id = i.id
                         AND bp.status = 'confirmed'
                   ), 0) AS paid,
                   CASE
                       WHEN COALESCE((
                           SELECT SUM(bp.amount)
                           FROM aradi_buyer_payments bp
                           WHERE bp.installment_id = i.id
                             AND bp.status = 'confirmed'
                       ), 0) >= i.amount        THEN 'paid'
                       WHEN COALESCE((
                           SELECT SUM(bp.amount)
                           FROM aradi_buyer_payments bp
                           WHERE bp.installment_id = i.id
                             AND bp.status = 'confirmed'
                       ), 0) > 0               THEN 'partial'
                       WHEN i.due_date < CURRENT_DATE THEN 'overdue'
                       ELSE 'pending'
                   END AS computed_status
            FROM aradi_installments i
            JOIN aradi_sale_contracts sc ON sc.id = i.contract_id
            JOIN aradi_buyers b ON b.id = sc.buyer_id
            ORDER BY i.due_date, i.id
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/installments/{installment_id}")
async def update_installment(
    installment_id: int,
    data: InstallmentUpdateRequest,
    user=Depends(get_current_user),
):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM aradi_installments WHERE id=$1", installment_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="القسط غير موجود")

            new_due = parse_date(data.due_date, "تاريخ الاستحقاق") or existing["due_date"]
            new_amount = (
                round(float(data.amount), 3)
                if data.amount is not None
                else float(existing["amount"])
            )
            if new_amount < 0:
                raise HTTPException(status_code=400, detail="مبلغ القسط لا يمكن أن يكون سالباً")

            row = await conn.fetchrow("""
                UPDATE aradi_installments
                SET due_date=$1, amount=$2, notes=$3, updated_at=NOW()
                WHERE id=$4 RETURNING *
            """, new_due, new_amount, data.notes, installment_id)
            await audit(conn, user, "update", "aradi_installment", installment_id,
                        f"تعديل قسط رقم {existing['installment_number']}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/installments/{installment_id}")
async def delete_installment(installment_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            payments = await conn.fetchval(
                "SELECT COUNT(*) FROM aradi_buyer_payments WHERE installment_id=$1 AND status='confirmed'",
                installment_id,
            )
            if payments > 0:
                raise HTTPException(status_code=400, detail="لا يمكن حذف القسط لوجود دفعات مؤكدة مرتبطة به")
            await conn.execute(
                "UPDATE aradi_buyer_payments SET installment_id=NULL WHERE installment_id=$1",
                installment_id,
            )
            row = await conn.fetchrow(
                "DELETE FROM aradi_installments WHERE id=$1 RETURNING *", installment_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="القسط غير موجود")
            await audit(conn, user, "delete", "aradi_installment", installment_id,
                        f"حذف قسط رقم {row['installment_number']}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Buyer Payments — مقبوضات المشترين
# ═══════════════════════════════════════════════════════════════

ALLOWED_PAYMENT_TYPES = {"down_payment", "installment", "extra", "correction"}
ALLOWED_PAYMENT_METHODS = {"cash", "check", "bank_transfer", "other"}
ALLOWED_PAYMENT_STATUSES = {"pending", "confirmed", "rejected", "void"}


class BuyerPaymentRequest(BaseModel):
    contract_id: int
    installment_id: Optional[int] = None
    payment_type: Optional[str] = "installment"
    amount: float
    payment_date: Optional[str] = None
    method: Optional[str] = "cash"
    status: Optional[str] = "confirmed"
    notes: Optional[str] = None


@router.get("/payments")
async def list_buyer_payments(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT bp.*,
                   b.name AS buyer_name,
                   sc.contract_number
            FROM aradi_buyer_payments bp
            JOIN aradi_sale_contracts sc ON sc.id = bp.contract_id
            JOIN aradi_buyers b ON b.id = sc.buyer_id
            ORDER BY bp.payment_date DESC, bp.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payments")
async def create_buyer_payment(data: BuyerPaymentRequest, user=Depends(get_current_user)):
    require_access(user)

    payment_type = data.payment_type or "installment"
    if payment_type not in ALLOWED_PAYMENT_TYPES:
        raise HTTPException(status_code=400, detail="نوع الدفعة غير صحيح")

    amount = float(data.amount)
    if payment_type != "correction" and amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    method = data.method or "cash"
    if method not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")

    status = data.status or "confirmed"
    if status not in ALLOWED_PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة الدفعة غير صحيحة")

    pay_date = parse_date(data.payment_date, "تاريخ الدفعة") or date.today()

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_buyer_payments
                    (contract_id, installment_id, payment_type, amount,
                     payment_date, method, status, notes, created_by)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                RETURNING *
            """,
                data.contract_id,
                data.installment_id,
                payment_type,
                round(amount, 3),
                pay_date,
                method,
                status,
                data.notes,
                user.get("id"),
            )
            await audit(conn, user, "create", "aradi_buyer_payment", row["id"],
                        f"تسجيل دفعة {amount} للعقد {data.contract_id}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BuyerPaymentUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    payment_date: Optional[str] = None
    method: Optional[str] = None
    amount: Optional[float] = None
    payment_type: Optional[str] = None


@router.put("/payments/{payment_id}")
async def update_buyer_payment(
    payment_id: int,
    data: BuyerPaymentUpdateRequest,
    user=Depends(get_current_user),
):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM aradi_buyer_payments WHERE id=$1", payment_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="الدفعة غير موجودة")

            new_status = data.status or existing["status"]
            if new_status not in ALLOWED_PAYMENT_STATUSES:
                raise HTTPException(status_code=400, detail="حالة الدفعة غير صحيحة")

            new_date = parse_date(data.payment_date, "تاريخ الدفعة") or existing["payment_date"]
            new_method = data.method or existing["method"]
            if new_method not in ALLOWED_PAYMENT_METHODS:
                raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")

            new_amount = round(float(data.amount), 3) if data.amount is not None else float(existing["amount"])
            new_type = data.payment_type or existing["payment_type"]
            if new_type not in ALLOWED_PAYMENT_TYPES:
                raise HTTPException(status_code=400, detail="نوع الدفعة غير صحيح")

            row = await conn.fetchrow("""
                UPDATE aradi_buyer_payments
                SET status=$1, notes=COALESCE($2,notes), payment_date=$3,
                    method=$4, amount=$5, payment_type=$6, updated_at=NOW()
                WHERE id=$7 RETURNING *
            """, new_status, data.notes, new_date, new_method, new_amount, new_type, payment_id)
            await audit(conn, user, "update", "aradi_buyer_payment", payment_id,
                        f"تعديل دفعة رقم {payment_id} → {new_status}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/payments/{payment_id}")
async def delete_buyer_payment(payment_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM aradi_buyer_payments WHERE id=$1 RETURNING *", payment_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="الدفعة غير موجودة")
            await audit(conn, user, "delete", "aradi_buyer_payment", payment_id,
                        f"حذف دفعة مشترٍ بمبلغ {float(row['amount'])}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Investors — المستثمرون
# ═══════════════════════════════════════════════════════════════

class InvestorRequest(BaseModel):
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


@router.get("/investors")
async def list_investors(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("SELECT * FROM aradi_investors ORDER BY id DESC")
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/investors")
async def create_investor(data: InvestorRequest, user=Depends(get_current_user)):
    require_access(user)
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="اسم المستثمر مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_investors (name, phone, address, notes)
                VALUES ($1,$2,$3,$4) RETURNING *
            """, data.name.strip(), data.phone, data.address, data.notes)
            await audit(conn, user, "create", "aradi_investor", row["id"],
                        f"إضافة مستثمر: {row['name']}")
            return row_to_dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/investors/{investor_id}")
async def get_investor(investor_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        row = await pool.fetchrow("SELECT * FROM aradi_investors WHERE id=$1", investor_id)
        if not row:
            raise HTTPException(status_code=404, detail="المستثمر غير موجود")
        return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/investors/{investor_id}")
async def update_investor(investor_id: int, data: InvestorRequest, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE aradi_investors
                SET name=COALESCE($1,name), phone=$2, address=$3, notes=$4, updated_at=NOW()
                WHERE id=$5 RETURNING *
            """, data.name.strip() if data.name else None,
                data.phone, data.address, data.notes, investor_id)
            if not row:
                raise HTTPException(status_code=404, detail="المستثمر غير موجود")
            await audit(conn, user, "update", "aradi_investor", investor_id,
                        f"تعديل بيانات المستثمر: {row['name']}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/investors/{investor_id}")
async def delete_investor(investor_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            investments = await conn.fetchval(
                "SELECT COUNT(*) FROM aradi_investments WHERE investor_id=$1", investor_id
            )
            if investments > 0:
                raise HTTPException(status_code=400, detail="لا يمكن حذف المستثمر لوجود استثمارات مرتبطة به")
            row = await conn.fetchrow(
                "DELETE FROM aradi_investors WHERE id=$1 RETURNING *", investor_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="المستثمر غير موجود")
            await audit(conn, user, "delete", "aradi_investor", investor_id,
                        f"حذف المستثمر: {row['name']}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Investments — الاستثمارات
# ═══════════════════════════════════════════════════════════════

ALLOWED_INVESTMENT_STATUSES = {"active", "closed", "cancelled"}


class InvestmentRequest(BaseModel):
    plot_id: Optional[int] = None
    investor_id: int
    investment_number: Optional[str] = None
    capital_amount: float
    profit_amount: Optional[float] = 0
    status: Optional[str] = "active"
    notes: Optional[str] = None


@router.get("/investments")
async def list_investments(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT inv.*,
                   ir.name  AS investor_name,
                   p.plot_number,
                   COALESCE((
                       SELECT SUM(ip.amount)
                       FROM aradi_investor_payments ip
                       WHERE ip.investment_id = inv.id
                         AND ip.status = 'confirmed'
                   ), 0) AS total_paid_out
            FROM aradi_investments inv
            JOIN aradi_investors ir ON ir.id = inv.investor_id
            LEFT JOIN aradi_plots p ON p.id = inv.plot_id
            ORDER BY inv.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/investments")
async def create_investment(data: InvestmentRequest, user=Depends(get_current_user)):
    require_access(user)
    capital = validate_amount(data.capital_amount, "رأس المال")
    profit = validate_amount(data.profit_amount or 0, "الربح")
    if (data.status or "active") not in ALLOWED_INVESTMENT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة الاستثمار غير صحيحة")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_investments
                    (plot_id, investor_id, investment_number,
                     capital_amount, profit_amount, status, notes, created_by)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                RETURNING *
            """,
                data.plot_id, data.investor_id, data.investment_number,
                capital, profit, data.status or "active",
                data.notes, user.get("id"),
            )
            # Mark plot as invested if provided
            if data.plot_id:
                await conn.execute("""
                    UPDATE aradi_plots SET status='invested', updated_at=NOW()
                    WHERE id=$1 AND status='available'
                """, data.plot_id)
            await audit(conn, user, "create", "aradi_investment", row["id"],
                        f"إضافة استثمار رقم {row['investment_number'] or row['id']}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/investments/{investment_id}")
async def get_investment(investment_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        row = await pool.fetchrow("""
            SELECT inv.*, ir.name AS investor_name, p.plot_number
            FROM aradi_investments inv
            JOIN aradi_investors ir ON ir.id = inv.investor_id
            LEFT JOIN aradi_plots p ON p.id = inv.plot_id
            WHERE inv.id = $1
        """, investment_id)
        if not row:
            raise HTTPException(status_code=404, detail="الاستثمار غير موجود")
        return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/investments/{investment_id}")
async def update_investment(
    investment_id: int, data: InvestmentRequest, user=Depends(get_current_user)
):
    require_access(user)
    if (data.status or "active") not in ALLOWED_INVESTMENT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة الاستثمار غير صحيحة")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE aradi_investments
                SET plot_id=$1, investor_id=$2, investment_number=$3,
                    capital_amount=$4, profit_amount=$5,
                    status=$6, notes=$7, updated_at=NOW()
                WHERE id=$8 RETURNING *
            """,
                data.plot_id,
                data.investor_id,
                data.investment_number,
                round(float(data.capital_amount), 3),
                round(float(data.profit_amount or 0), 3),
                data.status or "active",
                data.notes,
                investment_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="الاستثمار غير موجود")
            await audit(conn, user, "update", "aradi_investment", investment_id,
                        f"تعديل استثمار رقم {investment_id}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/investments/{investment_id}")
async def delete_investment(investment_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT * FROM aradi_investments WHERE id=$1", investment_id
                )
                if not row:
                    raise HTTPException(status_code=404, detail="الاستثمار غير موجود")
                confirmed = await conn.fetchval(
                    "SELECT COUNT(*) FROM aradi_investor_payments WHERE investment_id=$1 AND status='confirmed'",
                    investment_id,
                )
                if confirmed > 0:
                    raise HTTPException(
                        status_code=400,
                        detail="لا يمكن حذف الاستثمار لوجود دفعات مؤكدة مرتبطة به",
                    )
                await conn.execute(
                    "DELETE FROM aradi_investor_payments WHERE investment_id=$1",
                    investment_id,
                )
                await conn.execute(
                    "DELETE FROM aradi_investor_payouts WHERE investment_id=$1",
                    investment_id,
                )
                await conn.execute(
                    "DELETE FROM aradi_investments WHERE id=$1", investment_id
                )
                if row["plot_id"]:
                    remaining = await conn.fetchval(
                        "SELECT COUNT(*) FROM aradi_investments WHERE plot_id=$1 AND id!=$2",
                        row["plot_id"], investment_id,
                    )
                    if remaining == 0:
                        await conn.execute(
                            "UPDATE aradi_plots SET status='available', updated_at=NOW() WHERE id=$1 AND status='invested'",
                            row["plot_id"],
                        )
                await audit(conn, user, "delete", "aradi_investment", investment_id,
                            f"حذف استثمار رقم {row['investment_number'] or investment_id}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/investments/{investment_id}/statement")
async def get_investment_statement(investment_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        inv = await pool.fetchrow("""
            SELECT inv.*, ir.name AS investor_name, ir.phone AS investor_phone,
                   p.plot_number
            FROM aradi_investments inv
            JOIN aradi_investors ir ON ir.id = inv.investor_id
            LEFT JOIN aradi_plots p ON p.id = inv.plot_id
            WHERE inv.id=$1
        """, investment_id)
        if not inv:
            raise HTTPException(status_code=404, detail="الاستثمار غير موجود")

        payouts = await pool.fetch("""
            SELECT * FROM aradi_investor_payouts
            WHERE investment_id=$1 ORDER BY due_date, id
        """, investment_id)

        payments = await pool.fetch("""
            SELECT * FROM aradi_investor_payments
            WHERE investment_id=$1 ORDER BY payment_date, id
        """, investment_id)

        total_paid = sum(
            float(p["amount"]) for p in payments if p["status"] == "confirmed"
        )
        total_due = float(inv["total_due"])

        return {
            "investment": row_to_dict(inv),
            "payouts": [row_to_dict(r) for r in payouts],
            "payments": [row_to_dict(r) for r in payments],
            "summary": {
                "total_due": round(total_due, 3),
                "total_paid_out": round(total_paid, 3),
                "remaining_to_pay": round(total_due - total_paid, 3),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Investor Payouts — جداول الدفع للمستثمرين
# ═══════════════════════════════════════════════════════════════

class InvestorPayoutRequest(BaseModel):
    investment_id: int
    payout_number: Optional[int] = None
    due_date: Optional[str] = None
    amount: float
    notes: Optional[str] = None


@router.get("/investor-payouts")
async def list_investor_payouts(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT ip.*, ir.name AS investor_name
            FROM aradi_investor_payouts ip
            JOIN aradi_investments inv ON inv.id = ip.investment_id
            JOIN aradi_investors ir ON ir.id = inv.investor_id
            ORDER BY ip.due_date, ip.id
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/investor-payouts")
async def create_investor_payout(data: InvestorPayoutRequest, user=Depends(get_current_user)):
    require_access(user)
    amount = validate_amount(data.amount, "المبلغ", allow_zero=False)
    due = parse_date(data.due_date, "تاريخ الاستحقاق")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_investor_payouts
                    (investment_id, payout_number, due_date, amount, notes)
                VALUES ($1,$2,$3,$4,$5) RETURNING *
            """, data.investment_id, data.payout_number, due, amount, data.notes)
            await audit(conn, user, "create", "aradi_investor_payout", row["id"],
                        f"إضافة استحقاق {amount} للاستثمار {data.investment_id}")
            return row_to_dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class InvestorPayoutUpdateRequest(BaseModel):
    due_date: Optional[str] = None
    amount: Optional[float] = None
    notes: Optional[str] = None


@router.put("/investor-payouts/{payout_id}")
async def update_investor_payout(
    payout_id: int,
    data: InvestorPayoutUpdateRequest,
    user=Depends(get_current_user),
):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM aradi_investor_payouts WHERE id=$1", payout_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="الاستحقاق غير موجود")
            new_due = parse_date(data.due_date, "تاريخ الاستحقاق") or existing["due_date"]
            new_amt = round(float(data.amount), 3) if data.amount is not None else float(existing["amount"])
            if new_amt <= 0:
                raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
            row = await conn.fetchrow("""
                UPDATE aradi_investor_payouts
                SET due_date=$1, amount=$2, notes=COALESCE($3,notes), updated_at=NOW()
                WHERE id=$4 RETURNING *
            """, new_due, new_amt, data.notes, payout_id)
            await audit(conn, user, "update", "aradi_investor_payout", payout_id,
                        f"تعديل استحقاق رقم {payout_id}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/investor-payouts/{payout_id}")
async def delete_investor_payout(payout_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE aradi_investor_payments SET payout_id=NULL WHERE payout_id=$1",
                payout_id,
            )
            row = await conn.fetchrow(
                "DELETE FROM aradi_investor_payouts WHERE id=$1 RETURNING *", payout_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="الاستحقاق غير موجود")
            await audit(conn, user, "delete", "aradi_investor_payout", payout_id,
                        f"حذف استحقاق رقم {payout_id}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Investor Payments — مدفوعات للمستثمرين
# ═══════════════════════════════════════════════════════════════

ALLOWED_INVESTOR_PAYMENT_STATUSES = {"pending", "confirmed", "rejected", "void"}


class InvestorPaymentRequest(BaseModel):
    investment_id: int
    payout_id: Optional[int] = None
    amount: float
    payment_date: Optional[str] = None
    method: Optional[str] = "cash"
    status: Optional[str] = "confirmed"
    notes: Optional[str] = None


@router.get("/investor-payments")
async def list_investor_payments(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT ip.*, ir.name AS investor_name
            FROM aradi_investor_payments ip
            JOIN aradi_investments inv ON inv.id = ip.investment_id
            JOIN aradi_investors ir ON ir.id = inv.investor_id
            ORDER BY ip.payment_date DESC, ip.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/investor-payments")
async def create_investor_payment(data: InvestorPaymentRequest, user=Depends(get_current_user)):
    require_access(user)
    amount = validate_amount(data.amount, "المبلغ", allow_zero=False)
    method = data.method or "cash"
    if method not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")
    status = data.status or "confirmed"
    if status not in ALLOWED_INVESTOR_PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="حالة الدفعة غير صحيحة")
    pay_date = parse_date(data.payment_date, "تاريخ الدفع") or date.today()
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_investor_payments
                    (investment_id, payout_id, amount, payment_date,
                     method, status, notes, created_by)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                RETURNING *
            """,
                data.investment_id, data.payout_id, amount, pay_date,
                method, status, data.notes, user.get("id"),
            )
            await audit(conn, user, "create", "aradi_investor_payment", row["id"],
                        f"دفع {amount} للاستثمار {data.investment_id}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class InvestorPaymentUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    payment_date: Optional[str] = None
    method: Optional[str] = None
    amount: Optional[float] = None


@router.put("/investor-payments/{payment_id}")
async def update_investor_payment(
    payment_id: int,
    data: InvestorPaymentUpdateRequest,
    user=Depends(get_current_user),
):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM aradi_investor_payments WHERE id=$1", payment_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="الدفعة غير موجودة")
            new_status = data.status or existing["status"]
            if new_status not in ALLOWED_INVESTOR_PAYMENT_STATUSES:
                raise HTTPException(status_code=400, detail="حالة الدفعة غير صحيحة")
            new_date = parse_date(data.payment_date, "تاريخ الدفع") or existing["payment_date"]
            new_method = data.method or existing["method"]
            if new_method not in ALLOWED_PAYMENT_METHODS:
                raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")
            new_amount = round(float(data.amount), 3) if data.amount is not None else float(existing["amount"])
            if new_amount <= 0:
                raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
            row = await conn.fetchrow("""
                UPDATE aradi_investor_payments
                SET status=$1, notes=COALESCE($2,notes), payment_date=$3,
                    method=$4, amount=$5, updated_at=NOW()
                WHERE id=$6 RETURNING *
            """, new_status, data.notes, new_date, new_method, new_amount, payment_id)
            await audit(conn, user, "update", "aradi_investor_payment", payment_id,
                        f"تعديل دفعة مستثمر رقم {payment_id} → {new_status}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/investor-payments/{payment_id}")
async def delete_investor_payment(payment_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM aradi_investor_payments WHERE id=$1 RETURNING *", payment_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="الدفعة غير موجودة")
            await audit(conn, user, "delete", "aradi_investor_payment", payment_id,
                        f"حذف دفعة مستثمر بمبلغ {float(row['amount'])}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Checks — الشيكات
# ═══════════════════════════════════════════════════════════════

ALLOWED_CHECK_STATUSES = {"received", "deposited", "cleared", "returned", "cancelled"}
ALLOWED_CHECK_RELATED_TYPES = {"buyer_payment", "investor_payment", "expense", "manual"}
ALLOWED_CHECK_DIRECTIONS = {"in", "out"}


class CheckRequest(BaseModel):
    related_type: str
    related_id: Optional[int] = None
    person_name: Optional[str] = None
    check_number: Optional[str] = None
    amount: float
    check_date: Optional[str] = None
    received_date: Optional[str] = None
    bank_name: Optional[str] = None
    status: Optional[str] = "received"
    direction: Optional[str] = "in"
    notes: Optional[str] = None


@router.get("/checks")
async def list_aradi_checks(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT * FROM aradi_checks
            ORDER BY check_date DESC NULLS LAST, id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/checks")
async def create_aradi_check(data: CheckRequest, user=Depends(get_current_user)):
    require_access(user)
    if data.related_type not in ALLOWED_CHECK_RELATED_TYPES:
        raise HTTPException(status_code=400, detail="نوع الشيك غير صحيح")
    direction = data.direction or "in"
    if direction not in ALLOWED_CHECK_DIRECTIONS:
        raise HTTPException(status_code=400, detail="اتجاه الشيك غير صحيح")
    status = data.status or "received"
    if status not in ALLOWED_CHECK_STATUSES:
        raise HTTPException(status_code=400, detail="حالة الشيك غير صحيحة")
    amount = validate_amount(data.amount, "مبلغ الشيك", allow_zero=False)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_checks
                    (related_type, related_id, person_name, check_number,
                     amount, check_date, received_date, bank_name,
                     status, direction, notes)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                RETURNING *
            """,
                data.related_type,
                data.related_id,
                data.person_name,
                data.check_number,
                amount,
                parse_date(data.check_date, "تاريخ الشيك"),
                parse_date(data.received_date, "تاريخ الاستلام"),
                data.bank_name,
                status,
                direction,
                data.notes,
            )
            await audit(conn, user, "create", "aradi_check", row["id"],
                        f"إضافة شيك {direction} بمبلغ {amount}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CheckUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    received_date: Optional[str] = None
    bank_name: Optional[str] = None
    related_type: Optional[str] = None
    person_name: Optional[str] = None
    check_number: Optional[str] = None
    amount: Optional[float] = None
    check_date: Optional[str] = None
    direction: Optional[str] = None


@router.put("/checks/{check_id}")
async def update_aradi_check(
    check_id: int, data: CheckUpdateRequest, user=Depends(get_current_user)
):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM aradi_checks WHERE id=$1", check_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="الشيك غير موجود")
            new_status = data.status or existing["status"]
            if new_status not in ALLOWED_CHECK_STATUSES:
                raise HTTPException(status_code=400, detail="حالة الشيك غير صحيحة")
            new_direction = data.direction or existing["direction"]
            if new_direction not in ALLOWED_CHECK_DIRECTIONS:
                raise HTTPException(status_code=400, detail="اتجاه الشيك غير صحيح")
            new_rtype = data.related_type or existing["related_type"]
            if new_rtype not in ALLOWED_CHECK_RELATED_TYPES:
                raise HTTPException(status_code=400, detail="نوع الشيك غير صحيح")
            new_amount = round(float(data.amount), 3) if data.amount is not None else float(existing["amount"])
            row = await conn.fetchrow("""
                UPDATE aradi_checks
                SET status=$1,
                    notes=COALESCE($2,notes),
                    received_date=COALESCE($3,received_date),
                    bank_name=COALESCE($4,bank_name),
                    person_name=COALESCE($5,person_name),
                    check_number=COALESCE($6,check_number),
                    amount=$7,
                    check_date=COALESCE($8,check_date),
                    direction=$9,
                    related_type=$10,
                    updated_at=NOW()
                WHERE id=$11 RETURNING *
            """,
                new_status,
                data.notes,
                parse_date(data.received_date, "تاريخ الاستلام"),
                data.bank_name,
                data.person_name,
                data.check_number,
                new_amount,
                parse_date(data.check_date, "تاريخ الشيك"),
                new_direction,
                new_rtype,
                check_id,
            )
            await audit(conn, user, "update", "aradi_check", check_id,
                        f"تعديل شيك رقم {check_id} → {new_status}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/checks/{check_id}")
async def delete_aradi_check(check_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM aradi_checks WHERE id=$1 RETURNING *", check_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="الشيك غير موجود")
            await audit(conn, user, "delete", "aradi_check", check_id,
                        f"حذف شيك رقم {row['check_number'] or check_id}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Expenses — المصاريف
# ═══════════════════════════════════════════════════════════════

ALLOWED_EXPENSE_STATUSES = {"pending", "confirmed", "rejected", "void"}


class ExpenseRequest(BaseModel):
    plot_id: Optional[int] = None
    expense_date: str
    category: Optional[str] = None
    amount: float
    method: Optional[str] = "cash"
    status: Optional[str] = "confirmed"
    notes: Optional[str] = None


@router.get("/expenses")
async def list_aradi_expenses(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT e.*, p.plot_number
            FROM aradi_expenses e
            LEFT JOIN aradi_plots p ON p.id = e.plot_id
            ORDER BY e.expense_date DESC, e.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses")
async def create_aradi_expense(data: ExpenseRequest, user=Depends(get_current_user)):
    require_access(user)
    amount = validate_amount(data.amount, "المبلغ", allow_zero=False)
    exp_date = parse_date_required(data.expense_date, "تاريخ المصروف")
    method = data.method or "cash"
    if method not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")
    status = data.status or "confirmed"
    if status not in ALLOWED_EXPENSE_STATUSES:
        raise HTTPException(status_code=400, detail="حالة المصروف غير صحيحة")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aradi_expenses
                    (plot_id, expense_date, category, amount, method, status, notes, created_by)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                RETURNING *
            """,
                data.plot_id, exp_date, data.category, amount,
                method, status, data.notes, user.get("id"),
            )
            await audit(conn, user, "create", "aradi_expense", row["id"],
                        f"مصروف {amount} — {data.category or 'بدون تصنيف'}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExpenseUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    plot_id: Optional[int] = None
    amount: Optional[float] = None
    expense_date: Optional[str] = None
    method: Optional[str] = None


@router.put("/expenses/{expense_id}")
async def update_aradi_expense(
    expense_id: int, data: ExpenseUpdateRequest, user=Depends(get_current_user)
):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM aradi_expenses WHERE id=$1", expense_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail="المصروف غير موجود")
            new_status = data.status or existing["status"]
            if new_status not in ALLOWED_EXPENSE_STATUSES:
                raise HTTPException(status_code=400, detail="حالة المصروف غير صحيحة")
            new_method = data.method or existing["method"]
            if new_method not in ALLOWED_PAYMENT_METHODS:
                raise HTTPException(status_code=400, detail="طريقة الدفع غير صحيحة")
            new_amount = round(float(data.amount), 3) if data.amount is not None else float(existing["amount"])
            new_date = parse_date(data.expense_date, "تاريخ المصروف") or existing["expense_date"]
            new_plot = data.plot_id if data.plot_id is not None else existing["plot_id"]
            row = await conn.fetchrow("""
                UPDATE aradi_expenses
                SET status=$1,
                    notes=COALESCE($2,notes),
                    category=COALESCE($3,category),
                    amount=$4,
                    expense_date=$5,
                    method=$6,
                    plot_id=$7,
                    updated_at=NOW()
                WHERE id=$8 RETURNING *
            """, new_status, data.notes, data.category, new_amount, new_date, new_method, new_plot, expense_id)
            await audit(conn, user, "update", "aradi_expense", expense_id,
                        f"تعديل مصروف رقم {expense_id} → {new_status}")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/expenses/{expense_id}")
async def delete_aradi_expense(expense_id: int, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM aradi_expenses WHERE id=$1 RETURNING *", expense_id
            )
            if not row:
                raise HTTPException(status_code=404, detail="المصروف غير موجود")
            await audit(conn, user, "delete", "aradi_expense", expense_id,
                        f"حذف مصروف بمبلغ {float(row['amount'])}")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Reports — التقارير
# ═══════════════════════════════════════════════════════════════

@router.get("/reports/overdue-installments")
async def report_overdue_installments(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT
                i.id,
                i.contract_id,
                i.installment_number,
                i.due_date,
                i.amount,
                COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    WHERE bp.installment_id = i.id AND bp.status = 'confirmed'
                ), 0) AS paid,
                i.amount - COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    WHERE bp.installment_id = i.id AND bp.status = 'confirmed'
                ), 0) AS remaining,
                b.name AS buyer_name,
                b.phone AS buyer_phone,
                p.plot_number,
                sc.contract_number
            FROM aradi_installments i
            JOIN aradi_sale_contracts sc ON sc.id = i.contract_id
            JOIN aradi_buyers b ON b.id = sc.buyer_id
            LEFT JOIN aradi_plots p ON p.id = sc.plot_id
            WHERE i.due_date < CURRENT_DATE
              AND COALESCE((
                  SELECT SUM(bp.amount)
                  FROM aradi_buyer_payments bp
                  WHERE bp.installment_id = i.id AND bp.status = 'confirmed'
              ), 0) < i.amount
              AND sc.status NOT IN ('cancelled')
            ORDER BY i.due_date
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/upcoming-installments")
async def report_upcoming_installments(days: int = 30, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT
                i.id,
                i.contract_id,
                i.installment_number,
                i.due_date,
                i.amount,
                COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    WHERE bp.installment_id = i.id AND bp.status = 'confirmed'
                ), 0) AS paid,
                b.name AS buyer_name,
                b.phone AS buyer_phone,
                p.plot_number
            FROM aradi_installments i
            JOIN aradi_sale_contracts sc ON sc.id = i.contract_id
            JOIN aradi_buyers b ON b.id = sc.buyer_id
            LEFT JOIN aradi_plots p ON p.id = sc.plot_id
            WHERE i.due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + ($1 || ' days')::INTERVAL
              AND COALESCE((
                  SELECT SUM(bp.amount)
                  FROM aradi_buyer_payments bp
                  WHERE bp.installment_id = i.id AND bp.status = 'confirmed'
              ), 0) < i.amount
              AND sc.status = 'active'
            ORDER BY i.due_date
        """, days)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/upcoming-checks")
async def report_upcoming_checks(days: int = 30, user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT *
            FROM aradi_checks
            WHERE check_date BETWEEN CURRENT_DATE AND CURRENT_DATE + ($1 || ' days')::INTERVAL
              AND status IN ('received','deposited')
            ORDER BY check_date
        """, days)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/buyer-balances")
async def report_buyer_balances(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT
                sc.id           AS contract_id,
                sc.contract_number,
                b.id            AS buyer_id,
                b.name          AS buyer_name,
                b.phone         AS buyer_phone,
                p.plot_number,
                sc.sale_price,
                sc.status       AS contract_status,
                COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    WHERE bp.contract_id = sc.id AND bp.status = 'confirmed'
                ), 0)           AS total_paid,
                sc.sale_price - COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    WHERE bp.contract_id = sc.id AND bp.status = 'confirmed'
                ), 0)           AS remaining
            FROM aradi_sale_contracts sc
            JOIN aradi_buyers b ON b.id = sc.buyer_id
            LEFT JOIN aradi_plots p ON p.id = sc.plot_id
            WHERE sc.status NOT IN ('cancelled')
            ORDER BY remaining DESC, b.name
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/investor-balances")
async def report_investor_balances(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT
                inv.id          AS investment_id,
                inv.investment_number,
                ir.id           AS investor_id,
                ir.name         AS investor_name,
                ir.phone        AS investor_phone,
                p.plot_number,
                inv.capital_amount,
                inv.profit_amount,
                inv.total_due,
                inv.status      AS investment_status,
                COALESCE((
                    SELECT SUM(ip.amount)
                    FROM aradi_investor_payments ip
                    WHERE ip.investment_id = inv.id AND ip.status = 'confirmed'
                ), 0)           AS total_paid_out,
                inv.total_due - COALESCE((
                    SELECT SUM(ip.amount)
                    FROM aradi_investor_payments ip
                    WHERE ip.investment_id = inv.id AND ip.status = 'confirmed'
                ), 0)           AS remaining_to_pay
            FROM aradi_investments inv
            JOIN aradi_investors ir ON ir.id = inv.investor_id
            LEFT JOIN aradi_plots p ON p.id = inv.plot_id
            WHERE inv.status NOT IN ('cancelled')
            ORDER BY remaining_to_pay DESC, ir.name
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/plot-profitability")
async def report_plot_profitability(user=Depends(get_current_user)):
    require_access(user)
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT
                p.id,
                p.plot_number,
                p.project_name,
                p.status,
                p.purchase_price,
                p.expected_sale_price,
                -- Actual confirmed revenue from buyers linked to this plot
                COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    JOIN aradi_sale_contracts sc ON sc.id = bp.contract_id
                    WHERE sc.plot_id = p.id AND bp.status = 'confirmed'
                ), 0) AS total_buyer_payments,
                -- Confirmed expenses on this plot
                COALESCE((
                    SELECT SUM(e.amount)
                    FROM aradi_expenses e
                    WHERE e.plot_id = p.id AND e.status = 'confirmed'
                ), 0) AS total_expenses,
                -- Confirmed payouts to investors linked to this plot
                COALESCE((
                    SELECT SUM(ip.amount)
                    FROM aradi_investor_payments ip
                    JOIN aradi_investments inv ON inv.id = ip.investment_id
                    WHERE inv.plot_id = p.id AND ip.status = 'confirmed'
                ), 0) AS total_investor_payouts,
                -- Net = buyer_payments - expenses - investor_payouts
                COALESCE((
                    SELECT SUM(bp.amount)
                    FROM aradi_buyer_payments bp
                    JOIN aradi_sale_contracts sc ON sc.id = bp.contract_id
                    WHERE sc.plot_id = p.id AND bp.status = 'confirmed'
                ), 0)
                - COALESCE((
                    SELECT SUM(e.amount)
                    FROM aradi_expenses e
                    WHERE e.plot_id = p.id AND e.status = 'confirmed'
                ), 0)
                - COALESCE((
                    SELECT SUM(ip.amount)
                    FROM aradi_investor_payments ip
                    JOIN aradi_investments inv ON inv.id = ip.investment_id
                    WHERE inv.plot_id = p.id AND ip.status = 'confirmed'
                ), 0) AS net_profit
            FROM aradi_plots p
            ORDER BY net_profit DESC NULLS LAST, p.id
        """)
        return [row_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
