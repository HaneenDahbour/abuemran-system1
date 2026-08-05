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


# ── Pydantic Models ───────────────────────────────────────────

class PersonIn(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None


class TransactionIn(BaseModel):
    person_id: int
    amount: float
    transaction_type: str  # give / withdraw
    transaction_date: Optional[str] = None
    notes: Optional[str] = None


# ── People CRUD ──────────────────────────────────────────────

@router.get("/people")
async def list_people(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT p.*,
          COALESCE((SELECT SUM(CASE WHEN t.transaction_type='give' THEN t.amount ELSE 0 END)
                    FROM personal_transactions t WHERE t.person_id = p.id), 0) AS total_given,
          COALESCE((SELECT SUM(CASE WHEN t.transaction_type='withdraw' THEN t.amount ELSE 0 END)
                    FROM personal_transactions t WHERE t.person_id = p.id), 0) AS total_withdrawn,
          COALESCE((SELECT COUNT(*) FROM personal_transactions t WHERE t.person_id = p.id), 0) AS transaction_count
        FROM personal_people p
        ORDER BY p.created_at DESC
    """)
    result = []
    for r in rows:
        d = row_to_dict(r)
        d["balance"] = round(float(d["total_given"]) - float(d["total_withdrawn"]), 3)
        result.append(d)
    return result


@router.post("/people")
async def create_person(data: PersonIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم الشخص مطلوب")
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO personal_people (name, phone, notes, created_by)
        VALUES ($1, $2, $3, $4) RETURNING *
        """,
        name, (data.phone or "").strip() or None,
        (data.notes or "").strip() or None, user.get("id"),
    )
    return row_to_dict(row)


@router.put("/people/{person_id}")
async def update_person(person_id: int, data: PersonIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم الشخص مطلوب")
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE personal_people SET name=$1, phone=$2, notes=$3
        WHERE id=$4 RETURNING *
        """,
        name, (data.phone or "").strip() or None,
        (data.notes or "").strip() or None, person_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="الشخص غير موجود")
    return row_to_dict(row)


@router.delete("/people/{person_id}")
async def delete_person(person_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM personal_people WHERE id=$1 RETURNING id", person_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="الشخص غير موجود")
    return {"success": True}


# ── Transactions CRUD ────────────────────────────────────────

@router.get("/transactions")
async def list_transactions(user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT t.*, p.name AS person_name
        FROM personal_transactions t
        JOIN personal_people p ON p.id = t.person_id
        ORDER BY t.transaction_date DESC, t.id DESC
    """)
    return [row_to_dict(r) for r in rows]


@router.post("/transactions")
async def create_transaction(data: TransactionIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    if data.transaction_type not in ("give", "withdraw"):
        raise HTTPException(status_code=400, detail="نوع العملية غير صحيح")

    amount = round(float(data.amount or 0), 3)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    pool = await get_pool()

    person = await pool.fetchrow(
        "SELECT id FROM personal_people WHERE id=$1", data.person_id
    )
    if not person:
        raise HTTPException(status_code=404, detail="الشخص غير موجود")

    if data.transaction_type == "withdraw":
        balance = await pool.fetchval("""
            SELECT COALESCE(SUM(CASE WHEN transaction_type='give' THEN amount ELSE -amount END), 0)
            FROM personal_transactions WHERE person_id=$1
        """, data.person_id)
        if amount > float(balance):
            raise HTTPException(
                status_code=400,
                detail=f"المبلغ المطلوب سحبه ({amount}) أكبر من الرصيد المتاح ({float(balance):.3f})"
            )

    t_date = date.today()
    if data.transaction_date:
        try:
            t_date = date.fromisoformat(data.transaction_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="التاريخ غير صحيح")

    row = await pool.fetchrow(
        """
        INSERT INTO personal_transactions
          (person_id, amount, transaction_type, transaction_date, notes, created_by)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING *
        """,
        data.person_id, amount, data.transaction_type,
        t_date, (data.notes or "").strip() or None, user.get("id"),
    )
    return row_to_dict(row)


@router.put("/transactions/{transaction_id}")
async def update_transaction(transaction_id: int, data: TransactionIn, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")

    if data.transaction_type not in ("give", "withdraw"):
        raise HTTPException(status_code=400, detail="نوع العملية غير صحيح")

    amount = round(float(data.amount or 0), 3)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    t_date = date.today()
    if data.transaction_date:
        try:
            t_date = date.fromisoformat(data.transaction_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="التاريخ غير صحيح")

    pool = await get_pool()

    if data.transaction_type == "withdraw":
        balance = await pool.fetchval("""
            SELECT COALESCE(SUM(CASE WHEN transaction_type='give' THEN amount ELSE -amount END), 0)
            FROM personal_transactions WHERE person_id=$1 AND id != $2
        """, data.person_id, transaction_id)
        if amount > float(balance):
            raise HTTPException(
                status_code=400,
                detail=f"المبلغ المطلوب سحبه ({amount}) أكبر من الرصيد المتاح ({float(balance):.3f})"
            )

    row = await pool.fetchrow(
        """
        UPDATE personal_transactions
        SET person_id=$1, amount=$2, transaction_type=$3,
            transaction_date=$4, notes=$5
        WHERE id=$6 RETURNING *
        """,
        data.person_id, amount, data.transaction_type,
        t_date, (data.notes or "").strip() or None, transaction_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="العملية غير موجودة")
    return row_to_dict(row)


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()

    txn = await pool.fetchrow(
        "SELECT * FROM personal_transactions WHERE id=$1", transaction_id
    )
    if not txn:
        raise HTTPException(status_code=404, detail="العملية غير موجودة")

    if txn["transaction_type"] == "give":
        balance_after = await pool.fetchval("""
            SELECT COALESCE(SUM(CASE WHEN transaction_type='give' THEN amount ELSE -amount END), 0)
            FROM personal_transactions WHERE person_id=$1 AND id != $2
        """, txn["person_id"], transaction_id)
        if float(balance_after) < 0:
            raise HTTPException(
                status_code=400,
                detail="لا يمكن حذف هذه العملية — الرصيد سيصبح سالباً بسبب عمليات سحب سابقة"
            )

    await pool.execute("DELETE FROM personal_transactions WHERE id=$1", transaction_id)
    return {"success": True}


# ── Person Statement ─────────────────────────────────────────

@router.get("/people/{person_id}/statement")
async def person_statement(person_id: int, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    pool = await get_pool()

    person = await pool.fetchrow(
        "SELECT * FROM personal_people WHERE id=$1", person_id
    )
    if not person:
        raise HTTPException(status_code=404, detail="الشخص غير موجود")

    transactions = await pool.fetch("""
        SELECT * FROM personal_transactions
        WHERE person_id=$1
        ORDER BY transaction_date ASC, id ASC
    """, person_id)

    total_given = sum(float(t["amount"]) for t in transactions if t["transaction_type"] == "give")
    total_withdrawn = sum(float(t["amount"]) for t in transactions if t["transaction_type"] == "withdraw")

    return {
        "person": row_to_dict(person),
        "total_given": round(total_given, 3),
        "total_withdrawn": round(total_withdrawn, 3),
        "balance": round(total_given - total_withdrawn, 3),
        "transactions": [row_to_dict(t) for t in transactions],
    }
