from decimal import Decimal
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role

router = APIRouter()

class AdvanceIn(BaseModel):
    employee_user_id: Optional[int] = None
    employee_name: str
    amount: float
    advance_date: Optional[str] = None
    advance_type: Optional[str] = "advance"
    notes: Optional[str] = None

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
        return date.today() if default_today else date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="التاريخ غير صحيح")


class ExpenseIn(BaseModel):
    name: str
    amount: float
    expense_type: Optional[str] = "daily"  # daily / monthly / fixed / other
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


@router.get("")
async def list_expenses(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT e.*, u.full_name AS created_by_name
        FROM cashbox_expenses e
        LEFT JOIN users u ON u.id = e.created_by
        ORDER BY e.expense_date DESC, e.id DESC
    """)

    return [row_to_dict(r) for r in rows]


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

    pool = await get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO cashbox_expenses
          (name, description, amount, expense_type, category, is_fixed,
           expense_date, notes, created_by)
        VALUES
          ($1, $2, $3, $4, $5, $6, $7, $8, $9)
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
        user.get("id"),
    )

    return row_to_dict(row)


@router.delete("/{expense_id}")
async def delete_expense(expense_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    deleted = await pool.fetchrow(
        "DELETE FROM cashbox_expenses WHERE id=$1 RETURNING id",
        expense_id,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")

    return {"success": True}


@router.get("/salaries")
async def list_salaries(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT s.*, u.full_name AS linked_employee_name
        FROM employee_salaries s
        LEFT JOIN users u ON u.id = s.employee_user_id
        ORDER BY s.salary_month DESC, s.id DESC
    """)

    return [row_to_dict(r) for r in rows]


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
    paid_date = parse_date(data.paid_date)

    pool = await get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO employee_salaries
          (employee_user_id, employee_name, salary_amount, salary_month,
           paid_date, status, notes, created_by)
        VALUES
          ($1, $2, $3, $4, $5, $6, $7, $8)
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


@router.delete("/salaries/{salary_id}")
async def delete_salary(salary_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    deleted = await pool.fetchrow(
        "DELETE FROM employee_salaries WHERE id=$1 RETURNING id",
        salary_id,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="الراتب غير موجود")

    return {"success": True}

@router.get("/employees-list")
async def list_employees_for_dropdown(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT id, full_name, role FROM users
        WHERE role IN ('admin','accountant','employee')
        ORDER BY full_name ASC
    """)
    return [dict(r) for r in rows]


@router.get("/advances")
async def list_advances(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT ea.*, u.full_name AS created_by_name
        FROM employee_advances ea
        LEFT JOIN users u ON u.id = ea.created_by
        ORDER BY ea.advance_date DESC, ea.id DESC
    """)
    return [row_to_dict(r) for r in rows]


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
    row = await pool.fetchrow(
        """
        INSERT INTO employee_advances
          (employee_user_id, employee_name, amount, advance_date, advance_type, notes, created_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        RETURNING *
        """,
        data.employee_user_id, employee_name, amount,
        advance_date, data.advance_type or "advance", data.notes, user.get("id"),
    )
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


@router.get("/employee-statement/{employee_name}")
async def employee_statement(employee_name: str, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()

    salaries = await pool.fetch("""
        SELECT id, salary_amount AS amount, salary_month AS date,
               paid_date, status, notes, 'salary' AS record_type
        FROM employee_salaries
        WHERE LOWER(TRIM(employee_name)) = LOWER(TRIM($1))
        ORDER BY salary_month ASC, id ASC
    """, employee_name)

    advances = await pool.fetch("""
        SELECT id, amount, advance_date AS date,
               advance_type, notes, 'advance' AS record_type
        FROM employee_advances
        WHERE LOWER(TRIM(employee_name)) = LOWER(TRIM($1))
        ORDER BY advance_date ASC, id ASC
    """, employee_name)

    total_salary  = sum(float(r["amount"] or 0) for r in salaries)
    total_advances = sum(float(r["amount"] or 0) for r in advances)
    balance = total_salary - total_advances

    txs = [row_to_dict(r) for r in salaries] + [row_to_dict(r) for r in advances]
    txs.sort(key=lambda x: (str(x.get("date") or ""), x.get("id") or 0))

    running = 0.0
    for t in txs:
        if t["record_type"] == "salary":
            running += float(t["amount"] or 0)
        else:
            running -= float(t["amount"] or 0)
        t["running_balance"] = round(running, 3)

    return {
        "employee_name": employee_name,
        "balance": round(balance, 3),
        "total_salary": round(total_salary, 3),
        "total_advances": round(total_advances, 3),
        "transactions": txs,
    }
