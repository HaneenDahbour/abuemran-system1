import json
import os
import random
import string
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role
from typing import List, Optional

load_dotenv()

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    full_name: str
    role: str
    client_id: Optional[int] = None
    recipient_name: Optional[str] = None
    base_salary: Optional[float] = None
    shop_id: Optional[int] = None
    permissions: Optional[List[str]] = None


def parse_permissions(raw):
    if raw is None:
        return None
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


@router.post("/login")
async def login(data: LoginRequest):
    pool = await get_pool()

    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="اسم المستخدم وكلمة المرور مطلوبان")

    user = await pool.fetchrow("SELECT * FROM users WHERE username = $1", data.username)

    if not user:
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    valid = pwd_context.verify(data.password, user["password_hash"])

    if not valid:
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    permissions = parse_permissions(user["permissions"]) if "permissions" in user.keys() else None

    payload = {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "client_id": user["client_id"],
        "recipient_name": user["recipient_name"],
        "shop_id": user["shop_id"] if "shop_id" in user.keys() else None,
        "permissions": permissions,
        "exp": datetime.utcnow() + timedelta(days=7),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    try:
        await pool.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, detail)
            VALUES ($1, $2, 'تسجيل دخول', $3)
            """,
            user["id"],
            user["full_name"],
            f"دخول من قِبل {user['full_name']}",
        )
    except Exception:
        pass

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "recipient_name": user["recipient_name"],
            "role": user["role"],
            "client_id": user["client_id"],
            "shop_id": user["shop_id"] if "shop_id" in user.keys() else None,
            "permissions": permissions,
        },
    }

@router.get("/employees-list")
async def get_employees_list(user=Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT id, full_name, role, username
        FROM users
        WHERE role IN ('admin', 'accountant', 'employee')
        ORDER BY full_name ASC
    """)
    return [dict(r) for r in rows]
@router.get("/users")
async def get_users(user=Depends(get_current_user)):
    require_role(user, "admin")

    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT
            u.id,
            u.username,
            u.full_name,
            u.role,
            u.client_id,
            u.recipient_name,
            u.shop_id,
            u.permissions,
            COALESCE(u.base_salary, 0) AS base_salary,
            u.created_at,

            COUNT(i.id) AS invoice_count,
            COALESCE(SUM(i.total_amount), 0) AS invoice_total,
            COALESCE(SUM(CASE WHEN i.status = 'approved' THEN i.total_amount ELSE 0 END), 0) AS approved_invoice_total,
            COALESCE(SUM(CASE WHEN i.status = 'pending' THEN i.total_amount ELSE 0 END), 0) AS pending_invoice_total

        FROM users u
        LEFT JOIN invoices i ON i.attributed_employee_id = u.id
        GROUP BY
            u.id,
            u.username,
            u.full_name,
            u.role,
            u.client_id,
            u.recipient_name,
            u.shop_id,
            u.permissions,
            u.base_salary,
            u.created_at
        ORDER BY u.created_at DESC
    """)

    result = []
    for row in rows:
        d = dict(row)
        d["permissions"] = parse_permissions(d.get("permissions"))
        result.append(d)
    return result

@router.post("/users")
async def create_user(data: CreateUserRequest, user=Depends(get_current_user)):
    require_role(user, "admin")

    valid_roles = ["admin", "accountant", "employee", "client", "recipient", "shop_manager", "shop_employee"]

    if data.role not in valid_roles:
        raise HTTPException(status_code=400, detail="الصلاحية المحددة غير صالحة")

    full_name = str(data.full_name or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="الاسم مطلوب")

    if data.role == "client" and not data.client_id:
        raise HTTPException(status_code=400, detail="حساب العميل يحتاج ربطه بعميل رئيسي")

    if data.role == "recipient" and not data.recipient_name:
        raise HTTPException(status_code=400, detail="حساب الزبون يحتاج اسم الزبون كما يظهر في الفواتير")

    if data.role in ("shop_manager", "shop_employee") and not data.shop_id:
        raise HTTPException(status_code=400, detail="حساب موظف المحل يحتاج ربطه بمحل")

    username = (data.username or "").strip()
    if not username:
        username = "emp_" + str(int(datetime.utcnow().timestamp()))

    password = data.password or "Abu@1234"

    pool = await get_pool()

    existing = await pool.fetchrow(
        "SELECT id FROM users WHERE username = $1",
        username,
    )

    if existing:
        raise HTTPException(status_code=409, detail="اسم المستخدم محجوز بالفعل")

    hashed_password = pwd_context.hash(password)

    new_user = await pool.fetchrow(
        """
        INSERT INTO users (username, password_hash, full_name, role, client_id, recipient_name, base_salary, shop_id, permissions)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id, username, full_name, role, client_id, recipient_name, base_salary, shop_id, permissions
        """,
        username,
        hashed_password,
        full_name,
        data.role,
        data.client_id,
        data.recipient_name.strip() if data.recipient_name else None,
        round(float(data.base_salary or 0), 3),
        data.shop_id,
        json.dumps(data.permissions) if data.permissions is not None else None,
    )

    try:
        await pool.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, detail)
            VALUES ($1, $2, 'إنشاء مستخدم', $3)
            """,
            user["id"],
            user["full_name"],
            f"إنشاء مستخدم جديد: {username} ({data.role})",
        )
    except Exception:
        pass

    result = dict(new_user)
    result["permissions"] = parse_permissions(result.get("permissions"))
    result["generated_password"] = password
    return result

@router.put("/users/{user_id}")
async def update_user(user_id: int, data: CreateUserRequest, user=Depends(get_current_user)):
    require_role(user, "admin")
    full_name = str(data.full_name or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="الاسم مطلوب")
    valid_roles = ["admin", "accountant", "employee", "client", "recipient", "shop_manager", "shop_employee"]
    if data.role not in valid_roles:
        raise HTTPException(status_code=400, detail="الصلاحية غير صالحة")
    pool = await get_pool()
    current = await pool.fetchrow(
        "SELECT client_id, recipient_name, shop_id, permissions FROM users WHERE id=$1",
        user_id,
    )
    if not current:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    fields_set = getattr(data, "model_fields_set", getattr(data, "__fields_set__", set()))
    client_id = data.client_id if "client_id" in fields_set else current["client_id"]
    recipient_name = data.recipient_name if "recipient_name" in fields_set else current["recipient_name"]
    shop_id = data.shop_id if "shop_id" in fields_set else current["shop_id"]
    if "permissions" in fields_set:
        permissions = json.dumps(data.permissions) if data.permissions is not None else None
    else:
        permissions = current["permissions"]

    if data.role == "client" and not client_id:
        raise HTTPException(status_code=400, detail="حساب العميل يحتاج ربطه بعميل رئيسي")
    if data.role == "recipient" and not recipient_name:
        raise HTTPException(status_code=400, detail="حساب الزبون يحتاج اسم الزبون")
    if data.role in ("shop_manager", "shop_employee") and not shop_id:
        raise HTTPException(status_code=400, detail="حساب موظف المحل يحتاج ربطه بمحل")

    updates = ["full_name=$1", "role=$2", "client_id=$3", "recipient_name=$4",
               "base_salary=COALESCE($5, base_salary)", "shop_id=$6"]
    params = [full_name, data.role, client_id, recipient_name,
              round(float(data.base_salary), 3) if data.base_salary is not None else None,
              shop_id]
    updates.append(f"permissions=${len(params)+1}")
    params.append(permissions)
    if data.password:
        hashed = pwd_context.hash(data.password)
        updates.append(f"password_hash=${len(params)+1}")
        params.append(hashed)
    params.append(user_id)
    row = await pool.fetchrow(
        f"UPDATE users SET {', '.join(updates)} WHERE id=${len(params)} RETURNING id, username, full_name, role, client_id, recipient_name, base_salary, shop_id, permissions",
        *params
    )
    result = dict(row)
    result["permissions"] = parse_permissions(result.get("permissions"))
    return result


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, user=Depends(get_current_user)):
    require_role(user, "admin")

    if int(user_id) == int(user["id"]):
        raise HTTPException(status_code=400, detail="لا يمكنك حذف حسابك الخاص")

    pool = await get_pool()

    deleted = await pool.fetchrow(
        "DELETE FROM users WHERE id = $1 RETURNING username", user_id
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    try:
        await pool.execute(
            """
            INSERT INTO audit_log (user_id, user_name, action, detail)
            VALUES ($1, $2, 'حذف مستخدم', $3)
            """,
            user["id"],
            user["full_name"],
            f"حذف مستخدم: {deleted['username']}",
        )
    except Exception:
        pass

    return {"success": True}


@router.get("/telegram-code")
async def telegram_code(user=Depends(get_current_user)):
    pool = await get_pool()

    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    await pool.execute(
        "UPDATE users SET telegram_link_code = $1 WHERE id = $2", code, user["id"]
    )

    return {"code": code}

