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


def parse_date(value: Optional[str], default_today: bool = True) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="التاريخ غير صحيح")


# ── Pydantic Models ───────────────────────────────────────────

class ExpenseIn(BaseModel):
    name: str
    amount: float
    expense_type: Optional[str] = "daily"
    category: Optional[str] = None
    expense_date: Optional[str] = None
    notes: Optional[str] = None
    is_fixed: Optional[bool] = False


class SalaryIn(BaseModel):
    employee_user_id: Optional[int] = None
    employee_name: str
    salary_amount: float
    salary_month: str
    paid_date: Optional[str] = None
    status: Optional[str] = "paid"
    notes: Optional[str] = None


class AdvanceIn(BaseModel):
    user_id: Optional[int] = None
    employee_name: str
    amount: float
    advance_date: Optional[str] = None
    advance_type: Optional[str] = "advance"
    notes: Optional[str] = None


# ── Expenses ──────────────────────────────────────────────────

@router.get("")
async def list_expenses(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT e.*, u.full_name AS created_by_name
            FROM cashbox_expenses e
            LEFT JOIN users u ON u.id = e.created_by
            ORDER BY e.expense_date DESC, e.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception:
        return []


@router.post("")
async def create_expense(data: ExpenseIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    name = str(data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم المصروف مطلوب")

    amount = round(float(data.amount or 0), 3)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    expense_date = parse_date(data.expense_date)

    created_by = None
    try:
        if user.get("id") is not None:
            created_by = int(user.get("id"))
    except Exception:
        created_by = None

    pool = await get_pool()

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO cashbox_expenses
              (name, description, amount, expense_type, category, is_fixed,
               expense_date, notes, created_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            RETURNING *
            """,
            name,
            name,
            amount,
            data.expense_type or "daily",
            data.category,
            bool(data.is_fixed),
            expense_date,
            data.notes,
            created_by,
        )

        return row_to_dict(row)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر حفظ المصروف: {str(e)}")


@router.put("/{expense_id}")
async def update_expense(expense_id: int, data: ExpenseIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    name = str(data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم المصروف مطلوب")
    amount = round(float(data.amount or 0), 3)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    expense_date = parse_date(data.expense_date)
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE cashbox_expenses
        SET name=$1, description=$1, amount=$2, expense_type=$3,
            category=$4, is_fixed=$5, expense_date=$6, notes=$7
        WHERE id=$8 RETURNING *
        """,
        name, amount, data.expense_type or "daily",
        data.category, bool(data.is_fixed), expense_date, data.notes, expense_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    return row_to_dict(row)

@router.delete("/{expense_id}")
async def delete_expense(expense_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM cashbox_expenses WHERE id=$1 RETURNING id", expense_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    return {"success": True}


# ── Salaries ──────────────────────────────────────────────────

@router.get("/salaries")
async def list_salaries(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT s.*, u.full_name AS linked_employee_name
            FROM employee_salaries s
            LEFT JOIN users u ON u.id = s.employee_user_id
            ORDER BY s.salary_month DESC, s.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception:
        return []


@router.post("/salaries")
async def create_salary(data: SalaryIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    employee_name = str(data.employee_name or "").strip()
    if not employee_name:
        raise HTTPException(status_code=400, detail="اسم الموظف مطلوب")

    amount = round(float(data.salary_amount or 0), 3)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="قيمة الراتب يجب أن تكون أكبر من صفر")

    salary_month = parse_date(data.salary_month)
    paid_date    = parse_date(data.paid_date)
    pool = await get_pool()

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO employee_salaries
              (employee_user_id, employee_name, salary_amount, salary_month,
               paid_date, status, notes, created_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            RETURNING *
            """,
            data.employee_user_id,
            employee_name,
            amount,
            salary_month,
            paid_date,
            data.status or "paid",
            data.notes,
            user.get("id"),
        )
        return row_to_dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر حفظ الراتب: {str(e)}")




@router.put("/salaries/{salary_id}")
async def update_salary(salary_id: int, data: SalaryIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    employee_name = str(data.employee_name or "").strip()
    if not employee_name:
        raise HTTPException(status_code=400, detail="اسم الموظف مطلوب")
    amount = round(float(data.salary_amount or 0), 3)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="قيمة الراتب يجب أن تكون أكبر من صفر")
    salary_month = parse_date(data.salary_month)
    paid_date = parse_date(data.paid_date)
    pool = await get_pool()
    try:
        row = await pool.fetchrow(
            """
            UPDATE employee_salaries
            SET employee_user_id=$1, employee_name=$2, salary_amount=$3,
                salary_month=$4, paid_date=$5, status=$6, notes=$7
            WHERE id=$8 RETURNING *
            """,
            data.employee_user_id, employee_name, amount,
            salary_month, paid_date, data.status or "paid", data.notes, salary_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر تعديل الراتب: {str(e)}")
    if not row:
        raise HTTPException(status_code=404, detail="الراتب غير موجود")
    return row_to_dict(row)

@router.delete("/salaries/{salary_id}")
async def delete_salary(salary_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM employee_salaries WHERE id=$1 RETURNING id", salary_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="الراتب غير موجود")
    return {"success": True}


# ── Advances ──────────────────────────────────────────────────

@router.get("/advances")
async def list_advances(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    try:
        rows = await pool.fetch("""
            SELECT ea.*, u.full_name AS linked_employee_name
            FROM employee_advances ea
            LEFT JOIN users u ON u.id = ea.user_id
            ORDER BY ea.advance_date DESC, ea.id DESC
        """)
        return [row_to_dict(r) for r in rows]
    except Exception:
        return []


@router.post("/advances")
async def create_advance(data: AdvanceIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    employee_name = str(data.employee_name or "").strip()
    if not employee_name:
        raise HTTPException(status_code=400, detail="اسم الموظف مطلوب")

    amount = round(float(data.amount or 0), 3)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    advance_date = parse_date(data.advance_date)
    pool = await get_pool()

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO employee_advances
              (user_id, employee_name, amount, advance_date, advance_type, notes, created_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            RETURNING *
            """,
            data.user_id,
            employee_name,
            amount,
            advance_date,
            data.advance_type or "advance",
            data.notes,
            user.get("id"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر حفظ السلفة: {str(e)}")

    out = row_to_dict(row)
    out["settlement"] = await settle_advance_against_salary(
        pool, data.user_id, employee_name, amount, advance_date, user
    )
    return out


async def settle_advance_against_salary(pool, user_id, employee_name, amount, advance_date, user):
    """
    تسوية السلفة مع الراتب الشهري الأساسي:
    - يُجمع كل سلف الشهر ويُقارن بالراتب الأساسي (users.base_salary)
    - عند اكتمال الراتب عبر السلف → يُسجَّل راتب الشهر تلقائياً كمدفوع بملاحظة توضيحية
    - إذا كان راتب الشهر مدفوعاً مسبقاً → تُعتبر السلفة ديناً إضافياً ويُنبَّه المستخدم
    """
    result = {
        "auto_settled": False,
        "already_paid": False,
        "base_salary": 0.0,
        "month_advances": 0.0,
        "remaining_salary": None,
    }
    if not user_id:
        return result

    try:
        month_start = advance_date.replace(day=1)
        next_month = (
            month_start.replace(year=month_start.year + 1, month=1)
            if month_start.month == 12
            else month_start.replace(month=month_start.month + 1)
        )

        salary_row = await pool.fetchrow(
            """
            SELECT id, status, salary_amount FROM employee_salaries
            WHERE employee_user_id=$1 AND salary_month >= $2 AND salary_month < $3
            ORDER BY id LIMIT 1
            """,
            user_id, month_start, next_month,
        )

        base_salary = float(
            await pool.fetchval(
                "SELECT COALESCE(base_salary, 0) FROM users WHERE id=$1", user_id
            ) or 0
        )

        # لا راتب أساسي في ملف الموظف؟ استخدمي راتب الشهر المسجَّل يدوياً كهدف للتسوية
        if base_salary <= 0 and salary_row:
            base_salary = float(salary_row["salary_amount"] or 0)

        if base_salary <= 0:
            return result  # لا راتب أساسي ولا راتب شهري مسجَّل — لا تسوية

        month_advances = float(
            await pool.fetchval(
                """
                SELECT COALESCE(SUM(amount), 0) FROM employee_advances
                WHERE user_id=$1 AND advance_date >= $2 AND advance_date < $3
                """,
                user_id, month_start, next_month,
            ) or 0
        )

        result["base_salary"] = round(base_salary, 3)
        result["month_advances"] = round(month_advances, 3)
        month_label = month_start.strftime("%m/%Y")

        if salary_row and salary_row["status"] == "paid":
            # الراتب مدفوع مسبقاً — لا شيء يُخصم منه
            result["already_paid"] = True
            result["remaining_salary"] = 0.0
            return result

        if month_advances >= base_salary:
            excess = round(month_advances - base_salary, 3)
            note = (
                f"🔒 إقفال تلقائي — راتب شهر {month_label} ({base_salary:.3f} د.أ) "
                f"اكتمل سداده بالكامل عبر السلف (إجمالي سلف الشهر: {month_advances:.3f} د.أ)."
            )
            if excess > 0:
                note += f" ⚠️ فائض {excess:.3f} د.أ يُحتسب ديناً إضافياً على الموظف."
            note += f" آخر سلفة: {amount:.3f} د.أ بتاريخ {advance_date.isoformat()}."

            if salary_row:
                # سجل راتب موجود (غير مدفوع) — تحديثه إلى مدفوع
                await pool.execute(
                    """
                    UPDATE employee_salaries
                    SET status='paid', paid_date=$1,
                        notes=COALESCE(notes,'') || ' | ' || $2
                    WHERE id=$3
                    """,
                    advance_date, note, salary_row["id"],
                )
            else:
                await pool.execute(
                    """
                    INSERT INTO employee_salaries
                      (employee_user_id, employee_name, salary_amount, salary_month,
                       paid_date, status, notes, created_by)
                    VALUES ($1,$2,$3,$4,$5,'paid',$6,$7)
                    """,
                    user_id, employee_name, base_salary, month_start,
                    advance_date, note, user.get("id"),
                )

            result["auto_settled"] = True
            result["remaining_salary"] = 0.0
        else:
            result["remaining_salary"] = round(base_salary - month_advances, 3)

    except Exception:
        pass  # التسوية إضافة تحسينية — لا توقف تسجيل السلفة

    return result




@router.put("/advances/{advance_id}")
async def update_advance(advance_id: int, data: AdvanceIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    employee_name = str(data.employee_name or "").strip()
    if not employee_name:
        raise HTTPException(status_code=400, detail="اسم الموظف مطلوب")
    amount = round(float(data.amount or 0), 3)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    advance_date = parse_date(data.advance_date)
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE employee_advances
        SET user_id=$1, employee_name=$2, amount=$3,
            advance_date=$4, advance_type=$5, notes=$6
        WHERE id=$7 RETURNING *
        """,
        data.user_id, employee_name, amount,
        advance_date, data.advance_type or "advance", data.notes, advance_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="السلفة غير موجودة")
    return row_to_dict(row)

@router.delete("/advances/{advance_id}")
async def delete_advance(advance_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM employee_advances WHERE id=$1 RETURNING id", advance_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="السلفة غير موجودة")
    return {"success": True}


# ── Employee Statement ────────────────────────────────────────

@router.get("/employee/{user_id}/statement")
async def employee_financial_statement(
    user_id: int, user=Depends(get_current_user)
):
    require_role(user, "admin", "accountant")
    pool = await get_pool()

    employee = await pool.fetchrow(
        "SELECT id, full_name, username, role FROM users WHERE id=$1", user_id
    )
    if not employee:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    try:
        salaries = await pool.fetch("""
            SELECT id, employee_user_id, employee_name,
                   salary_amount, salary_month, paid_date, status, notes
            FROM employee_salaries
            WHERE employee_user_id = $1
            ORDER BY salary_month ASC
        """, user_id)
    except Exception:
        salaries = []

    try:
        advances = await pool.fetch("""
            SELECT id, user_id, employee_name,
                   amount, advance_date, advance_type, notes
            FROM employee_advances
            WHERE user_id = $1
            ORDER BY advance_date ASC
        """, user_id)
    except Exception:
        advances = []

    total_salary   = sum(float(s["salary_amount"]) for s in salaries)
    total_advances = sum(float(a["amount"])         for a in advances)

    return {
        "employee":       dict(employee),
        "total_salary":   round(total_salary,   3),
        "total_advances": round(total_advances, 3),
        "net_balance":    round(total_salary - total_advances, 3),
        "salaries":       [row_to_dict(r) for r in salaries],
        "advances":       [row_to_dict(r) for r in advances],
    }


# ── Employees list for dropdowns (all staff) ─────────────────

@router.get("/employees-list")
async def get_employees_for_dropdown(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT id, full_name, role FROM users
        WHERE role IN ('admin','accountant','employee')
        ORDER BY full_name ASC
    """)
    return [dict(r) for r in rows]
