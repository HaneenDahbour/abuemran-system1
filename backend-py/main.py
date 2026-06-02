from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import recipients   # أضيفي هذا السطر

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from config.db import connect_db, close_db
from routers import (
    auth,
    clients,
    invoices,
    payments,
    checks,
    audit,
    notifications,
    suppliers,
    products,
    purchases,
    warehouse_categories,
    warehouse_invoices,
    search,
    ai,
)

app = FastAPI(title="Abu Emran System API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await connect_db()


@app.on_event("shutdown")
async def shutdown():
    await close_db()


@app.get("/")
async def root():
    return {
        "status": "✅ يعمل",
        "system": "نظام أبو عمران Python API v2",
        "version": "2.0.0",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Auth ──────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])

# ── Core Accounting ───────────────────────────────────────────
app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(checks.router, prefix="/api/checks", tags=["Checks"])

# ── System ────────────────────────────────────────────────────
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])

# ── Warehouse ─────────────────────────────────────────────────
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["Suppliers"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(purchases.router, prefix="/api/purchases", tags=["Purchases"])
app.include_router(warehouse_categories.router, prefix="/api/warehouse-categories", tags=["Warehouse Categories"])
app.include_router(warehouse_invoices.router, prefix="/api/warehouse-invoices", tags=["Warehouse Invoices"])

# ── Search ────────────────────────────────────────────────────
app.include_router(search.router, prefix="/api/search", tags=["Search"])

# ── AI ────────────────────────────────────────────────────────
app.include_router(ai.router, prefix="/api/ai", tags=["AI"])
app.include_router(recipients.router, prefix="/api/recipients", tags=["recipients"])



# في آخر الملف، بعد كل الـ routers
