from decimal import Decimal
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role

router = APIRouter()


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def to_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def row_to_dict(row):
    return {key: to_json_value(row[key]) for key in row.keys()}


def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


async def insert_audit(conn, user, action: str, entity_type: str, entity_id, detail: str):
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
        pass


def check_shop_access(user, shop_id: int):
    """admin/accountant can access any shop. شيوزر له shop_id مرتبط (أي صلاحية) يصل لمحله فقط."""
    role = user.get("role")
    if role in ("admin", "accountant"):
        return
    if user.get("shop_id") and int(user.get("shop_id")) == int(shop_id):
        return
    raise HTTPException(status_code=403, detail="لا تملك صلاحية الوصول لهذا المحل")


def require_shop_role(user):
    """admin/accountant/shop_manager/shop_employee دائماً مسموح، وأي مستخدم آخر مرتبط بمحل (shop_id) مسموح أيضاً."""
    role = user.get("role")
    if role in ("admin", "accountant", "shop_manager", "shop_employee"):
        return
    if user.get("shop_id"):
        return
    raise HTTPException(status_code=403, detail="هذه الصفحة لمستخدمي المحلات فقط — ليس لديك صلاحية")


async def compute_cash_balance(pool, shop_id: int):
    row = await pool.fetchrow(
        """
        SELECT
          COALESCE(SUM(CASE WHEN type='deposit' THEN amount ELSE 0 END), 0) AS total_deposits,
          COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS total_income,
          COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS total_cash_expenses
        FROM shop_cash_transactions
        WHERE shop_id = $1
        """,
        shop_id,
    )
    deposits = float(row["total_deposits"] or 0)
    income = float(row["total_income"] or 0)
    cash_expenses = float(row["total_cash_expenses"] or 0)
    balance = deposits + income - cash_expenses
    return {
        "total_deposits": round(deposits, 3),
        "total_income": round(income, 3),
        "total_cash_expenses": round(cash_expenses, 3),
        "balance": round(balance, 3),
    }


# ──────────────────────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────────────────────

class CategoryRequest(BaseModel):
    name: str
    icon: Optional[str] = "🏬"
    notes: Optional[str] = None


class ShopRequest(BaseModel):
    category_id: int
    name: str
    responsible_employee_id: Optional[int] = None
    responsible_name: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = True


class ShopSupplierRequest(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None


class ShopPurchaseRequest(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    invoice_number: Optional[str] = None
    description: Optional[str] = None
    amount: float
    purchase_date: Optional[str] = None
    notes: Optional[str] = None
    attachment_url: Optional[str] = None


class ShopCheckRequest(BaseModel):
    check_number: str
    bank_name: Optional[str] = None
    owner_name: Optional[str] = None
    amount: float
    due_date: str
    notes: Optional[str] = None
    image_url: Optional[str] = None


class ShopCheckStatusRequest(BaseModel):
    status: str
    status_notes: Optional[str] = None


class ShopExpenseRequest(BaseModel):
    expense_type: Optional[str] = "other"
    title: str
    employee_name: Optional[str] = None
    amount: float
    expense_date: Optional[str] = None
    notes: Optional[str] = None


class ShopCashRequest(BaseModel):
    type: str  # deposit / income / expense
    amount: float
    trans_date: Optional[str] = None
    notes: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# Categories
# ──────────────────────────────────────────────────────────────

@router.get("/categories")
async def get_categories(user=Depends(get_current_user)):
    require_shop_role(user)
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT c.*,
          COALESCE((SELECT COUNT(*) FROM shops s WHERE s.category_id = c.id), 0) AS shops_count
        FROM shop_categories c
        ORDER BY c.name ASC
        """
    )
    return [row_to_dict(r) for r in rows]


@router.post("/categories")
async def create_category(data: CategoryRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    name = clean_text(data.name)
    if not name:
        raise HTTPException(status_code=400, detail="اسم الفئة مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                duplicate = await conn.fetchrow(
                    "SELECT id, name FROM shop_categories WHERE LOWER(name) = LOWER($1) LIMIT 1",
                    name,
                )
                if duplicate:
                    raise HTTPException(status_code=400, detail=f"الفئة موجودة مسبقاً: {duplicate['name']}")
                row = await conn.fetchrow(
                    "INSERT INTO shop_categories (name, icon, notes, created_by) VALUES ($1, $2, $3, $4) RETURNING *",
                    name, clean_text(data.icon) or "🏬", clean_text(data.notes), user.get("id"),
                )
                await insert_audit(conn, user, "إضافة فئة محلات", "shop_category", row["id"], f"إضافة فئة: {name}")
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/categories/{category_id}")
async def update_category(category_id: int, data: CategoryRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    name = clean_text(data.name)
    if not name:
        raise HTTPException(status_code=400, detail="اسم الفئة مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow("SELECT id FROM shop_categories WHERE id=$1 FOR UPDATE", category_id)
                if not existing:
                    raise HTTPException(status_code=404, detail="الفئة غير موجودة")
                duplicate = await conn.fetchrow(
                    "SELECT id FROM shop_categories WHERE LOWER(name)=LOWER($1) AND id<>$2 LIMIT 1", name, category_id
                )
                if duplicate:
                    raise HTTPException(status_code=400, detail="الاسم مستخدم مسبقاً")
                row = await conn.fetchrow(
                    "UPDATE shop_categories SET name=$1, icon=$2, notes=$3 WHERE id=$4 RETURNING *",
                    name, clean_text(data.icon) or "🏬", clean_text(data.notes), category_id,
                )
                await insert_audit(conn, user, "تعديل فئة محلات", "shop_category", category_id, f"تعديل: {name}")
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/categories/{category_id}")
async def delete_category(category_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                category = await conn.fetchrow("SELECT id, name FROM shop_categories WHERE id=$1 FOR UPDATE", category_id)
                if not category:
                    raise HTTPException(status_code=404, detail="الفئة غير موجودة")
                linked = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM shops WHERE category_id=$1)", category_id)
                if linked:
                    raise HTTPException(status_code=400, detail="لا يمكن حذف الفئة لوجود محلات مرتبطة بها")
                await conn.execute("DELETE FROM shop_categories WHERE id=$1", category_id)
                await insert_audit(conn, user, "حذف فئة محلات", "shop_category", category_id, f"حذف: {category['name']}")
                return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────
# Shops
# ──────────────────────────────────────────────────────────────

@router.get("")
async def get_shops(user=Depends(get_current_user)):
    require_shop_role(user)
    pool = await get_pool()

    role = user.get("role")
    if role in ("shop_manager", "shop_employee"):
        rows = await pool.fetch(
            """
            SELECT s.*, c.name AS category_name, c.icon AS category_icon,
                   u.full_name AS responsible_employee_name
            FROM shops s
            JOIN shop_categories c ON c.id = s.category_id
            LEFT JOIN users u ON u.id = s.responsible_employee_id
            WHERE s.id = $1
            ORDER BY s.name ASC
            """,
            user.get("shop_id") or 0,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT s.*, c.name AS category_name, c.icon AS category_icon,
                   u.full_name AS responsible_employee_name
            FROM shops s
            JOIN shop_categories c ON c.id = s.category_id
            LEFT JOIN users u ON u.id = s.responsible_employee_id
            ORDER BY c.name ASC, s.name ASC
            """
        )

    result = []
    for r in rows:
        d = row_to_dict(r)
        balance = await compute_cash_balance(pool, d["id"])
        purchases_total = await pool.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM shop_purchases WHERE shop_id=$1", d["id"]
        )
        expenses_total = await pool.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM shop_expenses WHERE shop_id=$1", d["id"]
        )
        d["cash"] = balance
        d["total_purchases"] = round(float(purchases_total or 0), 3)
        d["total_expenses"] = round(float(expenses_total or 0), 3)
        result.append(d)
    return result


@router.get("/{shop_id}")
async def get_shop_detail(shop_id: int, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    pool = await get_pool()

    shop = await pool.fetchrow(
        """
        SELECT s.*, c.name AS category_name, c.icon AS category_icon,
               u.full_name AS responsible_employee_name
        FROM shops s
        JOIN shop_categories c ON c.id = s.category_id
        LEFT JOIN users u ON u.id = s.responsible_employee_id
        WHERE s.id = $1
        """,
        shop_id,
    )
    if not shop:
        raise HTTPException(status_code=404, detail="المحل غير موجود")

    suppliers = await pool.fetch("SELECT * FROM shop_suppliers WHERE shop_id=$1 ORDER BY name ASC", shop_id)
    purchases = await pool.fetch(
        """
        SELECT p.*, sup.name AS supplier_full_name
        FROM shop_purchases p
        LEFT JOIN shop_suppliers sup ON sup.id = p.supplier_id
        WHERE p.shop_id=$1 ORDER BY p.purchase_date DESC, p.id DESC
        """,
        shop_id,
    )
    checks = await pool.fetch("SELECT * FROM shop_checks WHERE shop_id=$1 ORDER BY due_date ASC, id DESC", shop_id)
    expenses = await pool.fetch("SELECT * FROM shop_expenses WHERE shop_id=$1 ORDER BY expense_date DESC, id DESC", shop_id)
    cash = await pool.fetch("SELECT * FROM shop_cash_transactions WHERE shop_id=$1 ORDER BY trans_date DESC, id DESC", shop_id)

    balance = await compute_cash_balance(pool, shop_id)

    return {
        "shop": row_to_dict(shop),
        "cash": balance,
        "suppliers": [row_to_dict(r) for r in suppliers],
        "purchases": [row_to_dict(r) for r in purchases],
        "checks": [row_to_dict(r) for r in checks],
        "expenses": [row_to_dict(r) for r in expenses],
        "cash_transactions": [row_to_dict(r) for r in cash],
        "totals": {
            "total_purchases": round(sum(float(r["amount"] or 0) for r in purchases), 3),
            "total_expenses": round(sum(float(r["amount"] or 0) for r in expenses), 3),
            "total_checks": round(sum(float(r["amount"] or 0) for r in checks), 3),
        },
    }


@router.post("")
async def create_shop(data: ShopRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    name = clean_text(data.name)
    if not name:
        raise HTTPException(status_code=400, detail="اسم المحل مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                category = await conn.fetchrow("SELECT id FROM shop_categories WHERE id=$1", data.category_id)
                if not category:
                    raise HTTPException(status_code=400, detail="الفئة غير موجودة")
                row = await conn.fetchrow(
                    """
                    INSERT INTO shops (category_id, name, responsible_employee_id, responsible_name,
                                       location, phone, notes, is_active, created_by)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *
                    """,
                    data.category_id, name, data.responsible_employee_id,
                    clean_text(data.responsible_name), clean_text(data.location),
                    clean_text(data.phone), clean_text(data.notes),
                    data.is_active if data.is_active is not None else True,
                    user.get("id"),
                )
                await insert_audit(conn, user, "إضافة محل", "shop", row["id"], f"إضافة محل: {name}")
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{shop_id}")
async def update_shop(shop_id: int, data: ShopRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    name = clean_text(data.name)
    if not name:
        raise HTTPException(status_code=400, detail="اسم المحل مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow("SELECT id FROM shops WHERE id=$1 FOR UPDATE", shop_id)
                if not existing:
                    raise HTTPException(status_code=404, detail="المحل غير موجود")
                row = await conn.fetchrow(
                    """
                    UPDATE shops SET category_id=$1, name=$2, responsible_employee_id=$3,
                      responsible_name=$4, location=$5, phone=$6, notes=$7, is_active=$8, updated_at=NOW()
                    WHERE id=$9 RETURNING *
                    """,
                    data.category_id, name, data.responsible_employee_id,
                    clean_text(data.responsible_name), clean_text(data.location),
                    clean_text(data.phone), clean_text(data.notes),
                    data.is_active if data.is_active is not None else True,
                    shop_id,
                )
                await insert_audit(conn, user, "تعديل محل", "shop", shop_id, f"تعديل: {name}")
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{shop_id}")
async def delete_shop(shop_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                shop = await conn.fetchrow("SELECT id, name FROM shops WHERE id=$1 FOR UPDATE", shop_id)
                if not shop:
                    raise HTTPException(status_code=404, detail="المحل غير موجود")
                await conn.execute("UPDATE users SET shop_id=NULL WHERE shop_id=$1", shop_id)
                await conn.execute("DELETE FROM shops WHERE id=$1", shop_id)
                await insert_audit(conn, user, "حذف محل", "shop", shop_id, f"حذف: {shop['name']}")
                return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────
# Suppliers per shop
# ──────────────────────────────────────────────────────────────

@router.post("/{shop_id}/suppliers")
async def add_shop_supplier(shop_id: int, data: ShopSupplierRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    name = clean_text(data.name)
    if not name:
        raise HTTPException(status_code=400, detail="اسم المورد مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                shop = await conn.fetchrow("SELECT id FROM shops WHERE id=$1", shop_id)
                if not shop:
                    raise HTTPException(status_code=404, detail="المحل غير موجود")
                row = await conn.fetchrow(
                    "INSERT INTO shop_suppliers (shop_id, name, phone, notes, created_by) VALUES ($1,$2,$3,$4,$5) RETURNING *",
                    shop_id, name, clean_text(data.phone), clean_text(data.notes), user.get("id"),
                )
                await insert_audit(conn, user, "إضافة مورد محل", "shop_supplier", row["id"], f"محل #{shop_id}: {name}")
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{shop_id}/suppliers/{supplier_id}")
async def update_shop_supplier(shop_id: int, supplier_id: int, data: ShopSupplierRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    name = clean_text(data.name)
    if not name:
        raise HTTPException(status_code=400, detail="اسم المورد مطلوب")
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE shop_suppliers SET name=$1, phone=$2, notes=$3 WHERE id=$4 AND shop_id=$5 RETURNING *",
        name, clean_text(data.phone), clean_text(data.notes), supplier_id, shop_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="المورد غير موجود")
    return row_to_dict(row)


@router.delete("/{shop_id}/suppliers/{supplier_id}")
async def delete_shop_supplier(shop_id: int, supplier_id: int, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM shop_suppliers WHERE id=$1 AND shop_id=$2 RETURNING id", supplier_id, shop_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="المورد غير موجود")
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# Purchases per shop
# ──────────────────────────────────────────────────────────────

@router.post("/{shop_id}/purchases")
async def add_shop_purchase(shop_id: int, data: ShopPurchaseRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                shop = await conn.fetchrow("SELECT id FROM shops WHERE id=$1", shop_id)
                if not shop:
                    raise HTTPException(status_code=404, detail="المحل غير موجود")

                supplier_name = clean_text(data.supplier_name)
                if data.supplier_id:
                    sup = await conn.fetchrow(
                        "SELECT name FROM shop_suppliers WHERE id=$1 AND shop_id=$2", data.supplier_id, shop_id
                    )
                    if not sup:
                        raise HTTPException(status_code=400, detail="المورد غير موجود")
                    supplier_name = supplier_name or sup["name"]

                p_date = date.fromisoformat(data.purchase_date) if data.purchase_date else date.today()

                row = await conn.fetchrow(
                    """
                    INSERT INTO shop_purchases
                      (shop_id, supplier_id, supplier_name, invoice_number, description, amount,
                       purchase_date, notes, attachment_url, created_by)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING *
                    """,
                    shop_id, data.supplier_id, supplier_name, clean_text(data.invoice_number),
                    clean_text(data.description), round(data.amount, 3), p_date,
                    clean_text(data.notes), clean_text(data.attachment_url), user.get("id"),
                )
                await insert_audit(conn, user, "إضافة مشتريات محل", "shop_purchase", row["id"], f"محل #{shop_id}: {data.amount}")
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{shop_id}/purchases/{purchase_id}")
async def update_shop_purchase(shop_id: int, purchase_id: int, data: ShopPurchaseRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    pool = await get_pool()
    p_date = date.fromisoformat(data.purchase_date) if data.purchase_date else date.today()
    row = await pool.fetchrow(
        """
        UPDATE shop_purchases SET supplier_id=$1, supplier_name=$2, invoice_number=$3, description=$4,
          amount=$5, purchase_date=$6, notes=$7, attachment_url=$8
        WHERE id=$9 AND shop_id=$10 RETURNING *
        """,
        data.supplier_id, clean_text(data.supplier_name), clean_text(data.invoice_number),
        clean_text(data.description), round(data.amount, 3), p_date,
        clean_text(data.notes), clean_text(data.attachment_url), purchase_id, shop_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    return row_to_dict(row)


@router.delete("/{shop_id}/purchases/{purchase_id}")
async def delete_shop_purchase(shop_id: int, purchase_id: int, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM shop_purchases WHERE id=$1 AND shop_id=$2 RETURNING id", purchase_id, shop_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# Checks per shop
# ──────────────────────────────────────────────────────────────

@router.post("/{shop_id}/checks")
async def add_shop_check(shop_id: int, data: ShopCheckRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    check_number = clean_text(data.check_number)
    if not check_number:
        raise HTTPException(status_code=400, detail="رقم الشيك مطلوب")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                shop = await conn.fetchrow("SELECT id FROM shops WHERE id=$1", shop_id)
                if not shop:
                    raise HTTPException(status_code=404, detail="المحل غير موجود")
                due = date.fromisoformat(data.due_date)
                row = await conn.fetchrow(
                    """
                    INSERT INTO shop_checks (shop_id, check_number, bank_name, owner_name, amount,
                                              due_date, notes, image_url, created_by)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *
                    """,
                    shop_id, check_number, clean_text(data.bank_name), clean_text(data.owner_name),
                    round(data.amount, 3), due, clean_text(data.notes), clean_text(data.image_url), user.get("id"),
                )
                await insert_audit(conn, user, "إضافة شيك محل", "shop_check", row["id"], f"محل #{shop_id}: شيك {check_number}")
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{shop_id}/checks/{check_id}")
async def update_shop_check(shop_id: int, check_id: int, data: ShopCheckRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    pool = await get_pool()
    due = date.fromisoformat(data.due_date)
    row = await pool.fetchrow(
        """
        UPDATE shop_checks SET check_number=$1, bank_name=$2, owner_name=$3, amount=$4,
          due_date=$5, notes=$6, image_url=$7, updated_at=NOW()
        WHERE id=$8 AND shop_id=$9 RETURNING *
        """,
        clean_text(data.check_number), clean_text(data.bank_name), clean_text(data.owner_name),
        round(data.amount, 3), due, clean_text(data.notes), clean_text(data.image_url), check_id, shop_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="الشيك غير موجود")
    return row_to_dict(row)


@router.put("/{shop_id}/checks/{check_id}/status")
async def update_shop_check_status(shop_id: int, check_id: int, data: ShopCheckStatusRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    if data.status not in ("pending", "cashed", "returned", "cancelled"):
        raise HTTPException(status_code=400, detail="حالة غير صالحة")
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE shop_checks SET status=$1, status_notes=$2, status_updated_by=$3, status_updated_at=NOW(), updated_at=NOW()
        WHERE id=$4 AND shop_id=$5 RETURNING *
        """,
        data.status, clean_text(data.status_notes), user.get("id"), check_id, shop_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="الشيك غير موجود")
    return row_to_dict(row)


@router.delete("/{shop_id}/checks/{check_id}")
async def delete_shop_check(shop_id: int, check_id: int, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant")
    check_shop_access(user, shop_id)
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM shop_checks WHERE id=$1 AND shop_id=$2 RETURNING id", check_id, shop_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="الشيك غير موجود")
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# Expenses (salaries / other) per shop
# ──────────────────────────────────────────────────────────────

@router.post("/{shop_id}/expenses")
async def add_shop_expense(shop_id: int, data: ShopExpenseRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    title = clean_text(data.title)
    if not title:
        raise HTTPException(status_code=400, detail="العنوان مطلوب")
    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    if data.expense_type not in ("salary", "rent", "utility", "other"):
        raise HTTPException(status_code=400, detail="نوع المصروف غير صالح")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                shop = await conn.fetchrow("SELECT id FROM shops WHERE id=$1", shop_id)
                if not shop:
                    raise HTTPException(status_code=404, detail="المحل غير موجود")
                e_date = date.fromisoformat(data.expense_date) if data.expense_date else date.today()
                row = await conn.fetchrow(
                    """
                    INSERT INTO shop_expenses (shop_id, expense_type, title, employee_name, amount, expense_date, notes, created_by)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *
                    """,
                    shop_id, data.expense_type, title, clean_text(data.employee_name),
                    round(data.amount, 3), e_date, clean_text(data.notes), user.get("id"),
                )
                await insert_audit(conn, user, "إضافة مصروف محل", "shop_expense", row["id"], f"محل #{shop_id}: {title} ({data.amount})")
                return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{shop_id}/expenses/{expense_id}")
async def update_shop_expense(shop_id: int, expense_id: int, data: ShopExpenseRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    title = clean_text(data.title)
    if not title:
        raise HTTPException(status_code=400, detail="العنوان مطلوب")
    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    pool = await get_pool()
    e_date = date.fromisoformat(data.expense_date) if data.expense_date else date.today()
    row = await pool.fetchrow(
        """
        UPDATE shop_expenses SET expense_type=$1, title=$2, employee_name=$3, amount=$4, expense_date=$5, notes=$6
        WHERE id=$7 AND shop_id=$8 RETURNING *
        """,
        data.expense_type, title, clean_text(data.employee_name), round(data.amount, 3), e_date,
        clean_text(data.notes), expense_id, shop_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    return row_to_dict(row)


@router.delete("/{shop_id}/expenses/{expense_id}")
async def delete_shop_expense(shop_id: int, expense_id: int, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM shop_expenses WHERE id=$1 AND shop_id=$2 RETURNING id", expense_id, shop_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# Cash transactions (daily float) per shop
# ──────────────────────────────────────────────────────────────

@router.get("/{shop_id}/cash")
async def get_shop_cash(shop_id: int, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM shop_cash_transactions WHERE shop_id=$1 ORDER BY trans_date DESC, id DESC", shop_id
    )
    balance = await compute_cash_balance(pool, shop_id)
    return {"transactions": [row_to_dict(r) for r in rows], **balance}


@router.post("/{shop_id}/cash")
async def add_shop_cash(shop_id: int, data: ShopCashRequest, user=Depends(get_current_user)):
    require_shop_role(user)
    check_shop_access(user, shop_id)
    if data.type not in ("deposit", "income", "expense"):
        raise HTTPException(status_code=400, detail="نوع الحركة غير صالح")
    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    # only admin/accountant/shop_manager can add deposits (capital injections)
    if data.type == "deposit":
        require_role(user, "admin", "accountant", "shop_manager")

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                shop = await conn.fetchrow("SELECT id FROM shops WHERE id=$1", shop_id)
                if not shop:
                    raise HTTPException(status_code=404, detail="المحل غير موجود")
                t_date = date.fromisoformat(data.trans_date) if data.trans_date else date.today()
                row = await conn.fetchrow(
                    """
                    INSERT INTO shop_cash_transactions (shop_id, type, amount, trans_date, notes, created_by)
                    VALUES ($1,$2,$3,$4,$5,$6) RETURNING *
                    """,
                    shop_id, data.type, round(data.amount, 3), t_date, clean_text(data.notes), user.get("id"),
                )
                labels = {"deposit": "إيداع", "income": "مقبوضات", "expense": "مصروف من الصندوق"}
                await insert_audit(conn, user, f"حركة صندوق محل ({labels[data.type]})", "shop_cash", row["id"], f"محل #{shop_id}: {data.amount}")
                balance = await compute_cash_balance(pool, shop_id)
                result = row_to_dict(row)
                result["cash"] = balance
                return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{shop_id}/cash/{trans_id}")
async def update_shop_cash(shop_id: int, trans_id: int, data: ShopCashRequest, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant", "shop_manager")
    check_shop_access(user, shop_id)
    if data.type not in ("deposit", "income", "expense"):
        raise HTTPException(status_code=400, detail="نوع الحركة غير صالح")
    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                t_date = date.fromisoformat(data.trans_date) if data.trans_date else date.today()
                row = await conn.fetchrow(
                    """
                    UPDATE shop_cash_transactions
                    SET type=$1, amount=$2, trans_date=$3, notes=$4
                    WHERE id=$5 AND shop_id=$6
                    RETURNING *
                    """,
                    data.type, round(data.amount, 3), t_date, clean_text(data.notes), trans_id, shop_id,
                )
                if not row:
                    raise HTTPException(status_code=404, detail="السجل غير موجود")
                labels = {"deposit": "إيداع", "income": "مقبوضات", "expense": "مصروف من الصندوق"}
                await insert_audit(conn, user, f"تعديل حركة صندوق محل ({labels[data.type]})", "shop_cash", row["id"], f"محل #{shop_id}: {data.amount}")
                balance = await compute_cash_balance(pool, shop_id)
                result = row_to_dict(row)
                result["cash"] = balance
                return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{shop_id}/cash/{trans_id}")
async def delete_shop_cash(shop_id: int, trans_id: int, user=Depends(get_current_user)):
    require_role(user, "admin", "accountant", "shop_manager")
    check_shop_access(user, shop_id)
    pool = await get_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM shop_cash_transactions WHERE id=$1 AND shop_id=$2 RETURNING id", trans_id, shop_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    return {"success": True}
