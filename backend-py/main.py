from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config.db import connect_db, close_db
from routers import (
    ai,
    audit,
    auth,
    checks,
    clients,
    invoices,
    notifications,
    payments,
    products,
    purchases,
    recipients,
    search,
    suppliers,
    warehouse_categories,
    warehouse_invoices,
)

app = FastAPI(
    title="Abu Emran System API",
    version="2.0.0",
    redirect_slashes=True,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@app.on_event("startup")
async def startup():
    await connect_db()


@app.on_event("shutdown")
async def shutdown():
    await close_db()


@app.get("/")
async def root():
    index_file = FRONTEND_DIR / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    return {
        "status": "✅ يعمل",
        "system": "نظام أبو عمران Python API v2",
        "version": "2.0.0",
        "frontend": "frontend/index.html not found",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health")
async def api_health():
    return {
        "status": "ok",
        "system": "Abu Emran System API",
        "version": "2.0.0",
    }


# ── Auth ──────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])

# ── Core Accounting ───────────────────────────────────────────
app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(checks.router, prefix="/api/checks", tags=["Checks"])
app.include_router(recipients.router, prefix="/api/recipients", tags=["Recipients"])

# ── System ────────────────────────────────────────────────────
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])

# ── Warehouse ─────────────────────────────────────────────────
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["Suppliers"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(purchases.router, prefix="/api/purchases", tags=["Purchases"])

app.include_router(
    warehouse_categories.router,
    prefix="/api/warehouse-categories",
    tags=["Warehouse Categories"],
)

app.include_router(
    warehouse_invoices.router,
    prefix="/api/warehouse-invoices",
    tags=["Warehouse Invoices"],
)

# ── Search / AI ───────────────────────────────────────────────
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI"])


# ── Frontend static files ─────────────────────────────────────
@app.get("/{file_path:path}")
async def serve_frontend_file(file_path: str):
    if file_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    requested_file = FRONTEND_DIR / file_path

    if requested_file.exists() and requested_file.is_file():
        return FileResponse(requested_file)

    index_file = FRONTEND_DIR / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend not found")
