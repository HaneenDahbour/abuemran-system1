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
    """Build financial context based on user role â€” mirrors Node ai.js exactly."""
    role = user.get("role")
    context = {}

    try:
        if role != "client":
            stats = await pool.fetchrow("""
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
                WHERE COALESCE(i.status, 'approved') = 'approved'
                """)
            context["stats"] = row_to_dict(stats)

            upcoming_checks = await pool.fetch("""
                SELECT c.check_number, cl.name AS client_name, c.amount, c.due_date, c.status
                FROM checks c
                JOIN clients cl ON c.client_id = cl.id
                WHERE c.status = 'pending'
                  AND c.due_date <= NOW() + INTERVAL '14 days'
                ORDER BY c.due_date ASC
                LIMIT 10
                """)
            context["upcomingChecks"] = [row_to_dict(r) for r in upcoming_checks]

            top_debts = await pool.fetch("""
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
                """)
            context["topDebts"] = [row_to_dict(r) for r in top_debts]

        if role in ("admin", "accountant"):
            recent_invoices = await pool.fetch("""
                SELECT inv.invoice_number, cl.name AS client_name, inv.total_amount, inv.date
                FROM invoices inv
                JOIN clients cl ON inv.client_id = cl.id
                ORDER BY inv.created_at DESC
                LIMIT 5
                """)
            context["recentInvoices"] = [row_to_dict(r) for r in recent_invoices]

            pending_payments = await pool.fetch("""
                SELECT p.amount, p.payment_date, cl.name AS client_name, u.full_name AS employee_name
                FROM payments p
                JOIN clients cl ON p.client_id = cl.id
                LEFT JOIN users u ON p.submitted_by = u.id
                WHERE p.status = 'pending'
                ORDER BY p.created_at DESC
                LIMIT 5
                """)
            context["pendingPayments"] = [row_to_dict(r) for r in pending_payments]

        if role == "admin":
            audit = await pool.fetch("""
                SELECT user_name, action, detail, created_at
                FROM audit_log
                ORDER BY created_at DESC
                LIMIT 10
                """)
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
                user.get("client_id"),
            )
            if client_data:
                r = row_to_dict(client_data)
                context["myBalance"] = float(r.get("total_invoiced", 0)) - float(
                    r.get("total_paid", 0)
                )
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
                user.get("client_id"),
            )
            context["myChecks"] = [row_to_dict(r) for r in my_checks]

    except Exception as err:
        context["error"] = f"Ø¨Ø¹Ø¶ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª ØºÙŠØ± Ù…ØªØ§Ø­Ø©: {str(err)}"

    return context


def build_system_prompt(user: dict, context: dict) -> str:
    role = user.get("role", "employee")
    full_name = user.get("full_name", "")

    role_instructions = {
        "admin": f"""Ø£Ù†Øª Ù…Ø³Ø§Ø¹Ø¯ Ù…Ø§Ù„ÙŠ Ø°ÙƒÙŠ Ù„Ù†Ø¸Ø§Ù… Ø£Ø¨Ùˆ Ø¹Ù…Ø±Ø§Ù† Ø§Ù„ØªØ¬Ø§Ø±ÙŠ. ØªØªØ­Ø¯Ø« Ù…Ø¹ Ø§Ù„Ù…Ø¯ÙŠØ± Ø§Ù„Ø¹Ø§Ù… {full_name}.
Ù„Ø¯ÙŠÙƒ ØµÙ„Ø§Ø­ÙŠØ© Ø§Ù„ÙˆØµÙˆÙ„ Ø§Ù„ÙƒØ§Ù…Ù„ Ù„Ø¬Ù…ÙŠØ¹ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù†Ø¸Ø§Ù…: Ø§Ù„Ø¹Ù…Ù„Ø§Ø¡ØŒ Ø§Ù„ÙÙˆØ§ØªÙŠØ±ØŒ Ø§Ù„Ù…Ù‚Ø¨ÙˆØ¶Ø§ØªØŒ Ø§Ù„Ø´ÙŠÙƒØ§ØªØŒ Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù…ÙŠÙ†ØŒ ÙˆØ³Ø¬Ù„ Ø§Ù„Ø¹Ù…Ù„ÙŠØ§Øª.
ÙŠÙ…ÙƒÙ†Ùƒ ØªØ­Ù„ÙŠÙ„ Ø§Ù„Ø¯ÙŠÙˆÙ†ØŒ ØªÙ‚ÙŠÙŠÙ… Ø§Ù„Ù…Ø®Ø§Ø·Ø±ØŒ Ø¥Ø¹Ø·Ø§Ø¡ ØªÙˆØµÙŠØ§Øª Ø§Ø³ØªØ±Ø§ØªÙŠØ¬ÙŠØ©ØŒ ÙˆØªÙ„Ø®ÙŠØµ Ø§Ù„ÙˆØ¶Ø¹ Ø§Ù„Ù…Ø§Ù„ÙŠ Ø§Ù„ÙƒØ§Ù…Ù„.""",
        "accountant": f"""Ø£Ù†Øª Ù…Ø³Ø§Ø¹Ø¯ Ù…Ø§Ù„ÙŠ Ø°ÙƒÙŠ Ù„Ù†Ø¸Ø§Ù… Ø£Ø¨Ùˆ Ø¹Ù…Ø±Ø§Ù† Ø§Ù„ØªØ¬Ø§Ø±ÙŠ. ØªØªØ­Ø¯Ø« Ù…Ø¹ Ø§Ù„Ù…Ø­Ø§Ø³Ø¨ {full_name}.
Ù„Ø¯ÙŠÙƒ ØµÙ„Ø§Ø­ÙŠØ© Ø§Ù„ÙˆØµÙˆÙ„ Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø¹Ù…Ù„Ø§Ø¡ØŒ Ø§Ù„ÙÙˆØ§ØªÙŠØ±ØŒ Ø§Ù„Ù…Ù‚Ø¨ÙˆØ¶Ø§ØªØŒ ÙˆØ§Ù„Ø´ÙŠÙƒØ§Øª.
Ø³Ø§Ø¹Ø¯ ÙÙŠ Ø§Ù„ØªØ­Ù„ÙŠÙ„ Ø§Ù„Ù…Ø§Ù„ÙŠØŒ ØªØªØ¨Ø¹ Ø§Ù„Ø¯ÙŠÙˆÙ†ØŒ ÙˆÙ…ØªØ§Ø¨Ø¹Ø© Ø§Ù„Ø´ÙŠÙƒØ§Øª Ø§Ù„Ù…Ø³ØªØ­Ù‚Ø©.""",
        "employee": f"""Ø£Ù†Øª Ù…Ø³Ø§Ø¹Ø¯ Ø°ÙƒÙŠ Ù„Ù†Ø¸Ø§Ù… Ø£Ø¨Ùˆ Ø¹Ù…Ø±Ø§Ù† Ø§Ù„ØªØ¬Ø§Ø±ÙŠ. ØªØªØ­Ø¯Ø« Ù…Ø¹ Ø§Ù„Ù…ÙˆØ¸Ù {full_name}.
ÙŠÙ…ÙƒÙ†Ùƒ Ù…Ø³Ø§Ø¹Ø¯ØªÙ‡ ÙÙŠ Ù…ØªØ§Ø¨Ø¹Ø© Ø§Ù„Ù…Ù‚Ø¨ÙˆØ¶Ø§Øª Ø§Ù„ØªÙŠ Ø³Ø¬Ù‘Ù„Ù‡Ø§ ÙˆØ§Ù„Ø´ÙŠÙƒØ§Øª Ø§Ù„Ù…Ø¹Ù„Ù‘Ù‚Ø©.
Ù„Ø§ ØªÙƒØ´Ù Ø¨ÙŠØ§Ù†Ø§Øª Ù…Ø§Ù„ÙŠØ© ØªÙØµÙŠÙ„ÙŠØ© Ù„Ø¹Ù…Ù„Ø§Ø¡ Ø¢Ø®Ø±ÙŠÙ†.""",
        "client": f"""Ø£Ù†Øª Ù…Ø³Ø§Ø¹Ø¯ Ø®Ø¯Ù…Ø© Ø¹Ù…Ù„Ø§Ø¡ Ù„Ù†Ø¸Ø§Ù… Ø£Ø¨Ùˆ Ø¹Ù…Ø±Ø§Ù† Ø§Ù„ØªØ¬Ø§Ø±ÙŠ. ØªØªØ­Ø¯Ø« Ù…Ø¹ Ø§Ù„Ø¹Ù…ÙŠÙ„ {context.get('myName', full_name)}.
Ø£Ø¬Ø¨ ÙÙ‚Ø· Ø¹Ù† Ø±ØµÙŠØ¯Ù‡ ÙˆÙÙˆØ§ØªÙŠØ±Ù‡ ÙˆØ´ÙŠÙƒØ§ØªÙ‡ Ø§Ù„Ø®Ø§ØµØ©. Ù„Ø§ ØªØ°ÙƒØ± Ø£ÙŠ Ø¨ÙŠØ§Ù†Ø§Øª Ù„Ø¹Ù…Ù„Ø§Ø¡ Ø¢Ø®Ø±ÙŠÙ† Ù…Ø·Ù„Ù‚Ø§Ù‹.""",
    }

    import json

    context_str = json.dumps(context, ensure_ascii=False, default=str, indent=2)

    return f"""{role_instructions.get(role, role_instructions['employee'])}

Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù†Ø¸Ø§Ù… Ø§Ù„Ø­Ø§Ù„ÙŠØ©:
{context_str}

Ù‚ÙˆØ§Ø¹Ø¯ Ø§Ù„Ù…Ø³Ø§Ø¹Ø¯:
- Ø£Ø¬Ø¨ Ø¯Ø§Ø¦Ù…Ø§Ù‹ Ø¨Ø§Ù„Ø¹Ø±Ø¨ÙŠØ© Ø¨Ø£Ø³Ù„ÙˆØ¨ Ù…Ù‡Ù†ÙŠ ÙˆÙ…Ø®ØªØµØ±
- Ø§Ø³ØªØ®Ø¯Ù… Ø§Ù„Ø£Ø±Ù‚Ø§Ù… Ø§Ù„ÙØ¹Ù„ÙŠØ© Ù…Ù† Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø£Ø¹Ù„Ø§Ù‡ Ø¹Ù†Ø¯ Ø§Ù„Ø¥Ø¬Ø§Ø¨Ø©
- Ø¥Ø°Ø§ Ø·ÙÙ„Ø¨ ØªÙ‚Ø±ÙŠØ± Ø£Ùˆ ØªØ­Ù„ÙŠÙ„ØŒ Ù‚Ø¯Ù‘Ù…Ù‡ Ø¨Ø´ÙƒÙ„ Ù…Ù†Ø¸Ù‘Ù… Ù…Ø¹ Ø§Ù„Ù†Ù‚Ø§Ø· Ø§Ù„Ø±Ø¦ÙŠØ³ÙŠØ©
- Ù„Ø§ ØªØ®ØªØ±Ø¹ Ø£Ø±Ù‚Ø§Ù…Ø§Ù‹ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø© ÙÙŠ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª
- Ø¥Ø°Ø§ Ø³ÙØ¦Ù„Øª Ø¹Ù† Ø´ÙŠØ¡ Ø®Ø§Ø±Ø¬ ØµÙ„Ø§Ø­ÙŠØ§ØªÙƒØŒ Ø£Ø®Ø¨Ø± Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… Ø¨Ø°Ù„Ùƒ Ø¨Ø£Ø¯Ø¨"""


async def call_groq(system_prompt: str, messages: list) -> str:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY Ù…ÙÙ‚ÙˆØ¯ Ù…Ù† .env")

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
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Groq error {response.status_code}: {response.text[:300]}",
            )

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except httpx.ConnectError:
        raise HTTPException(status_code=500, detail="ØªØ¹Ø°Ù‘Ø± Ø§Ù„Ø§ØªØµØ§Ù„ Ø¨Ù€ Groq API")


# POST /api/ai/chat
@router.post("/chat")
async def ai_chat(data: ChatRequest, user=Depends(get_current_user)):
    if not data.message:
        raise HTTPException(status_code=400, detail="Ø§Ù„Ø±Ø³Ø§Ù„Ø© Ù…Ø·Ù„ÙˆØ¨Ø©")

    pool = await get_pool()

    try:
        context = await get_system_context(user, pool)
        system_prompt = build_system_prompt(user, context)

        messages = [
            *[
                {"role": msg.role, "content": msg.content}
                for msg in (data.history or [])[-10:]
            ],
            {"role": "user", "content": data.message},
        ]

        reply = await call_groq(system_prompt, messages)

        return {"reply": reply}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ø®Ø·Ø£ ÙÙŠ Ø§Ù„Ù…Ø³Ø§Ø¹Ø¯ Ø§Ù„Ø°ÙƒÙŠ: {str(e)}")


# POST /api/ai/analyze
@router.post("/analyze")
async def ai_analyze(user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="ØºÙŠØ± Ù…ØµØ±Ø­")

    pool = await get_pool()

    try:
        context = await get_system_context(user, pool)
        system_prompt = build_system_prompt(user, context)

        messages = [
            {
                "role": "user",
                "content": "Ø£Ø¹Ø·Ù†ÙŠ Ù…Ù„Ø®ØµØ§Ù‹ Ø³Ø±ÙŠØ¹Ø§Ù‹ ÙÙŠ 3-4 Ù†Ù‚Ø§Ø· Ø¹Ù† Ø§Ù„ÙˆØ¶Ø¹ Ø§Ù„Ù…Ø§Ù„ÙŠ Ø§Ù„Ø­Ø§Ù„ÙŠ Ù…Ø¹ Ø£Ù‡Ù… Ø§Ù„ØªÙ†Ø¨ÙŠÙ‡Ø§Øª Ø§Ù„ØªÙŠ ØªØ³ØªÙˆØ¬Ø¨ Ø§Ù„Ø§Ù†ØªØ¨Ø§Ù‡ Ø§Ù„ÙÙˆØ±ÙŠ.",
            }
        ]

        analysis = await call_groq(system_prompt, messages)

        return {"analysis": analysis}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ø®Ø·Ø£ ÙÙŠ Ø§Ù„ØªØ­Ù„ÙŠÙ„: {str(e)}")


# GET /api/ai/analytics
@router.get("/analytics")
async def ai_analytics(
    period: str = Query(default="weekly"), user=Depends(get_current_user)
):
    if user.get("role") not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="ØºÙŠØ± Ù…ØµØ±Ø­")

    intervals = {"daily": "30 days", "weekly": "12 weeks", "monthly": "12 months"}
    trunc_map = {"daily": "day", "weekly": "week", "monthly": "month"}

    interval = intervals.get(period, intervals["weekly"])
    trunc_unit = trunc_map.get(period, "week")

    pool = await get_pool()

    try:
        # Use string interpolation safely â€” trunc_unit is from a whitelist
        sales_rows = await pool.fetch(f"""
            SELECT
                DATE_TRUNC('{trunc_unit}', date) AS period,
                COALESCE(SUM(total_amount), 0) AS total_sales,
                COUNT(*) AS invoice_count
            FROM invoices
            WHERE date >= NOW() - INTERVAL '{interval}'
              AND COALESCE(status, 'approved') = 'approved'
            GROUP BY 1
            ORDER BY 1 ASC
            """)

        payments_rows = await pool.fetch(f"""
            SELECT
                DATE_TRUNC('{trunc_unit}', payment_date) AS period,
                COALESCE(SUM(amount), 0) AS total_collected
            FROM payments
            WHERE status = 'approved'
              AND payment_date >= NOW() - INTERVAL '{interval}'
            GROUP BY 1
            ORDER BY 1 ASC
            """)

        checks_rows = await pool.fetch(f"""
            SELECT
                DATE_TRUNC('{trunc_unit}', due_date) AS period,
                COUNT(*) FILTER (WHERE status='cashed') AS cashed,
                COUNT(*) FILTER (WHERE status='returned') AS returned,
                COUNT(*) FILTER (WHERE status='pending') AS pending
            FROM checks
            WHERE due_date >= NOW() - INTERVAL '{interval}'
            GROUP BY 1
            ORDER BY 1 ASC
            """)

        return {
            "period": period,
            "sales": [row_to_dict(r) for r in sales_rows],
            "payments": [row_to_dict(r) for r in payments_rows],
            "checks": [row_to_dict(r) for r in checks_rows],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ø®Ø·Ø£ ÙÙŠ Ø§Ù„Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª: {str(e)}")

