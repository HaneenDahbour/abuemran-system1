import os
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config.db import get_pool
from middleware.auth import get_current_user
from middleware.roles import require_role

load_dotenv()

router = APIRouter()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

def to_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def row_to_dict(row):
    return {key: to_json_value(row[key]) for key in row.keys()}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


async def get_system_context(user: dict, pool) -> dict:
    """Build financial context based on user role — mirrors Node ai.js exactly."""
    role = user.get("role")
    context = {}

    try:
        if role != "client":
            stats = await pool.fetchrow(
                """
                SELECT
                    COALESCE(SUM(i.total_amount), 0) AS total_sales,
                    COALESCE(SUM(i.total_amount), 0)
                        - COALESCE((SELECT SUM(amount) FROM payments WHERE status='approved'), 0)
                        AS total_debts,
                    COALESCE((SELECT SUM(amount) FROM payments WHERE status='approved'), 0)
                        AS total_payments,
                    (SELECT COUNT(*) FROM clients) AS client_count,
                    (SELECT COUNT(*) FROM checks WHERE status='pending') AS pending_checks,
                    (SELECT COUNT(*) FROM payments WHERE status='pending') AS pending_payments
                FROM invoices i
                """
            )
            context["stats"] = row_to_dict(stats)

            upcoming_checks = await pool.fetch(
                """
                SELECT c.check_number, cl.name AS client_name, c.amount, c.due_date, c.status
                FROM checks c
                JOIN clients cl ON c.client_id = cl.id
                WHERE c.status = 'pending'
                  AND c.due_date <= NOW() + INTERVAL '14 days'
                ORDER BY c.due_date ASC
                LIMIT 10
                """
            )
            context["upcomingChecks"] = [row_to_dict(r) for r in upcoming_checks]

            top_debts = await pool.fetch(
                """
                SELECT cl.name, cl.risk_level,
                    COALESCE(SUM(i.total_amount), 0)
                        - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id=cl.id AND p.status='approved'), 0)
                        AS balance
                FROM clients cl
                LEFT JOIN invoices i ON i.client_id = cl.id
                GROUP BY cl.id, cl.name, cl.risk_level
                HAVING COALESCE(SUM(i.total_amount), 0)
                    - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id=cl.id AND p.status='approved'), 0) > 0
                ORDER BY balance DESC
                LIMIT 8
                """
            )
            context["topDebts"] = [row_to_dict(r) for r in top_debts]

        if role in ("admin", "accountant"):
            recent_invoices = await pool.fetch(
                """
                SELECT inv.invoice_number, cl.name AS client_name, inv.total_amount, inv.date
                FROM invoices inv
                JOIN clients cl ON inv.client_id = cl.id
                ORDER BY inv.created_at DESC
                LIMIT 5
                """
            )
            context["recentInvoices"] = [row_to_dict(r) for r in recent_invoices]

            pending_payments = await pool.fetch(
                """
                SELECT p.amount, p.payment_date, cl.name AS client_name, u.full_name AS employee_name
                FROM payments p
                JOIN clients cl ON p.client_id = cl.id
                LEFT JOIN users u ON p.submitted_by = u.id
                WHERE p.status = 'pending'
                ORDER BY p.created_at DESC
                LIMIT 5
                """
            )
            context["pendingPayments"] = [row_to_dict(r) for r in pending_payments]

        if role == "admin":
            audit = await pool.fetch(
                """
                SELECT user_name, action, detail, created_at
                FROM audit_log
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
            context["recentAudit"] = [row_to_dict(r) for r in audit]

        if role == "client":
            client_data = await pool.fetchrow(
                """
                SELECT cl.*,
                    COALESCE(SUM(i.total_amount), 0) AS total_invoiced,
                    COALESCE((SELECT SUM(amount) FROM payments p WHERE p.client_id=cl.id AND p.status='approved'), 0)
                        AS total_paid
                FROM clients cl
                LEFT JOIN invoices i ON i.client_id = cl.id
                WHERE cl.id = $1
                GROUP BY cl.id
                """,
                user.get("client_id")
            )
            if client_data:
                r = row_to_dict(client_data)
                context["myBalance"] = float(r.get("total_invoiced", 0)) - float(r.get("total_paid", 0))
                context["myName"] = r.get("name")
                context["creditLimit"] = r.get("credit_limit")

            my_checks = await pool.fetch(
                """
                SELECT check_number, amount, due_date, status, bank_name
                FROM checks
                WHERE client_id = $1 AND status = 'pending'
                ORDER BY due_date ASC
                LIMIT 5
                """,
                user.get("client_id")
            )
            context["myChecks"] = [row_to_dict(r) for r in my_checks]

    except Exception as err:
        context["error"] = f"بعض البيانات غير متاحة: {str(err)}"

    return context


def build_system_prompt(user: dict, context: dict) -> str:
    role = user.get("role", "employee")
    full_name = user.get("full_name", "")

    role_instructions = {
        "admin": f"""أنت مساعد مالي ذكي لنظام أبو عمران التجاري. تتحدث مع المدير العام {full_name}.
لديك صلاحية الوصول الكامل لجميع بيانات النظام: العملاء، الفواتير، المقبوضات، الشيكات، المستخدمين، وسجل العمليات.
يمكنك تحليل الديون، تقييم المخاطر، إعطاء توصيات استراتيجية، وتلخيص الوضع المالي الكامل.""",

        "accountant": f"""أنت مساعد مالي ذكي لنظام أبو عمران التجاري. تتحدث مع المحاسب {full_name}.
لديك صلاحية الوصول لبيانات العملاء، الفواتير، المقبوضات، والشيكات.
ساعد في التحليل المالي، تتبع الديون، ومتابعة الشيكات المستحقة.""",

        "employee": f"""أنت مساعد ذكي لنظام أبو عمران التجاري. تتحدث مع الموظف {full_name}.
يمكنك مساعدته في متابعة المقبوضات التي سجّلها والشيكات المعلّقة.
لا تكشف بيانات مالية تفصيلية لعملاء آخرين.""",

        "client": f"""أنت مساعد خدمة عملاء لنظام أبو عمران التجاري. تتحدث مع العميل {context.get('myName', full_name)}.
أجب فقط عن رصيده وفواتيره وشيكاته الخاصة. لا تذكر أي بيانات لعملاء آخرين مطلقاً.""",
    }

    import json
    context_str = json.dumps(context, ensure_ascii=False, default=str, indent=2)

    return f"""{role_instructions.get(role, role_instructions['employee'])}

بيانات النظام الحالية:
{context_str}

قواعد المساعد:
- أجب دائماً بالعربية بأسلوب مهني ومختصر
- استخدم الأرقام الفعلية من البيانات أعلاه عند الإجابة
- إذا طُلب تقرير أو تحليل، قدّمه بشكل منظّم مع النقاط الرئيسية
- لا تخترع أرقاماً غير موجودة في البيانات
- إذا سُئلت عن شيء خارج صلاحياتك، أخبر المستخدم بذلك بأدب"""


async def call_groq(system_prompt: str, messages: list) -> str:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY مفقود من .env")

    groq_messages = [{"role": "system", "content": system_prompt}]

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role not in ("user", "assistant", "system"):
            role = "user"
        if content:
            groq_messages.append({"role": role, "content": content})

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": groq_messages,
                    "temperature": 0.2,
                    "max_tokens": 700,
                }
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Groq error {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except httpx.ConnectError:
        raise HTTPException(status_code=500, detail="تعذّر الاتصال بـ Groq API")

    


# POST /api/ai/chat
@router.post("/chat")
async def ai_chat(data: ChatRequest, user=Depends(get_current_user)):
    if not data.message:
        raise HTTPException(status_code=400, detail="الرسالة مطلوبة")

    pool = await get_pool()

    try:
        context = await get_system_context(user, pool)
        system_prompt = build_system_prompt(user, context)

        messages = [
            *[{"role": msg.role, "content": msg.content} for msg in (data.history or [])[-10:]],
            {"role": "user", "content": data.message}
        ]

        reply = await call_groq(system_prompt, messages)

        return {"reply": reply}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"خطأ في المساعد الذكي: {str(e)}"
        )


# POST /api/ai/analyze
@router.post("/analyze")
async def ai_analyze(user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    pool = await get_pool()

    try:
        context = await get_system_context(user, pool)
        system_prompt = build_system_prompt(user, context)

        messages = [{
            "role": "user",
            "content": "أعطني ملخصاً سريعاً في 3-4 نقاط عن الوضع المالي الحالي مع أهم التنبيهات التي تستوجب الانتباه الفوري."
        }]

        analysis = await call_groq(system_prompt, messages)

        return {"analysis": analysis}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في التحليل: {str(e)}")


# GET /api/ai/analytics
@router.get("/analytics")
async def ai_analytics(
    period: str = Query(default="weekly"),
    user=Depends(get_current_user)
):
    if user.get("role") not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    intervals = {"daily": "30 days", "weekly": "12 weeks", "monthly": "12 months"}
    trunc_map = {"daily": "day", "weekly": "week", "monthly": "month"}

    interval = intervals.get(period, intervals["weekly"])
    trunc_unit = trunc_map.get(period, "week")

    pool = await get_pool()

    try:
        # Use string interpolation safely — trunc_unit is from a whitelist
        sales_rows = await pool.fetch(
            f"""
            SELECT
                DATE_TRUNC('{trunc_unit}', date) AS period,
                COALESCE(SUM(total_amount), 0) AS total_sales,
                COUNT(*) AS invoice_count
            FROM invoices
            WHERE date >= NOW() - INTERVAL '{interval}'
            GROUP BY 1
            ORDER BY 1 ASC
            """
        )

        payments_rows = await pool.fetch(
            f"""
            SELECT
                DATE_TRUNC('{trunc_unit}', payment_date) AS period,
                COALESCE(SUM(amount), 0) AS total_collected
            FROM payments
            WHERE status = 'approved'
              AND payment_date >= NOW() - INTERVAL '{interval}'
            GROUP BY 1
            ORDER BY 1 ASC
            """
        )

        checks_rows = await pool.fetch(
            f"""
            SELECT
                DATE_TRUNC('{trunc_unit}', due_date) AS period,
                COUNT(*) FILTER (WHERE status='cashed') AS cashed,
                COUNT(*) FILTER (WHERE status='returned') AS returned,
                COUNT(*) FILTER (WHERE status='pending') AS pending
            FROM checks
            WHERE due_date >= NOW() - INTERVAL '{interval}'
            GROUP BY 1
            ORDER BY 1 ASC
            """
        )

        return {
            "period": period,
            "sales": [row_to_dict(r) for r in sales_rows],
            "payments": [row_to_dict(r) for r in payments_rows],
            "checks": [row_to_dict(r) for r in checks_rows],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الإحصائيات: {str(e)}")