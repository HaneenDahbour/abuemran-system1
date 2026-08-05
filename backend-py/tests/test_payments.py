"""Regression tests for the payments endpoints."""

import pytest
import httpx
from datetime import date, datetime
from decimal import Decimal

from middleware.auth import get_current_user
from tests.conftest import (
    FakeRecord,
    _make_admin_user, _make_accountant_user, _make_employee_user,
)


def payment_record(**overrides):
    base = FakeRecord({
        "id": 1,
        "client_id": 10,
        "invoice_id": None,
        "submitted_by": 3,
        "approved_by": 1,
        "amount": Decimal("100.000"),
        "status": "approved",
        "notes": "test | method:cash",
        "payment_date": date(2024, 6, 1),
        "approved_at": datetime(2024, 6, 1, 12, 0, 0),
        "created_at": datetime(2024, 6, 1, 12, 0, 0),
        "rejection_reason": None,
    })
    base.update(overrides)
    return base


def override_auth(user_fn):
    async def _dep():
        return user_fn()
    return _dep


@pytest.mark.asyncio
async def test_create_payment_as_admin(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)
    created = payment_record(status="approved")

    def mock_fetchval(q, *a):
        return True

    def mock_fetchrow(q, *a):
        if "INSERT INTO payments" in q:
            return created
        return None

    fake_pool._fetchval_results = mock_fetchval
    fake_pool._fetchrow_results = mock_fetchrow

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/payments",
            json={"client_id": 10, "amount": 100.0, "payment_method": "cash"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["amount"] == 100.0
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_payment_as_employee_is_pending(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_employee_user)
    created = payment_record(status="pending", approved_by=None, approved_at=None)

    def mock_fetchval(q, *a):
        return True

    def mock_fetchrow(q, *a):
        if "INSERT INTO payments" in q:
            return created
        return None

    fake_pool._fetchval_results = mock_fetchval
    fake_pool._fetchrow_results = mock_fetchrow

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/payments",
            json={"client_id": 10, "amount": 50.0, "payment_method": "cash"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_payment_invalid_amount(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/payments",
            json={"client_id": 10, "amount": -5.0},
        )

    assert resp.status_code == 400
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_payment_invalid_method(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/payments",
            json={"client_id": 10, "amount": 100.0, "payment_method": "bitcoin"},
        )

    assert resp.status_code == 400
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_approve_payment(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)
    approved = payment_record(status="approved")
    fake_pool._fetchrow_results = approved

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/payments/1/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_approve_requires_admin(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_accountant_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/payments/1/approve")

    assert resp.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reject_payment(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)
    rejected = payment_record(status="rejected", rejection_reason="خطأ")
    fake_pool._fetchrow_results = rejected

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/payments/1/reject",
            json={"reason": "خطأ في المبلغ"},
        )

    assert resp.status_code == 200
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reject_empty_reason(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/payments/1/reject",
            json={"reason": "   "},
        )

    assert resp.status_code == 400
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_payment(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)
    existing = payment_record()
    updated = payment_record(amount=Decimal("200.000"), notes="updated | method:transfer")

    def mock_fetchrow(q, *a):
        if "SELECT" in q:
            return existing
        if "UPDATE" in q:
            return updated
        return None

    fake_pool._fetchrow_results = mock_fetchrow

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/payments/1",
            json={"amount": 200.0, "payment_method": "transfer"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["amount"] == 200.0
    assert data["payment_method"] == "transfer"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_payment_not_found(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)
    fake_pool._fetchrow_results = None

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/payments/999",
            json={"amount": 200.0},
        )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_payment_requires_accountant_or_admin(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_employee_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/payments/1",
            json={"amount": 200.0},
        )

    assert resp.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_payment(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)
    deleted = payment_record()
    fake_pool._fetchrow_results = deleted

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/payments/1")

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_payment_not_found(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)
    fake_pool._fetchrow_results = None

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/payments/999")

    assert resp.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_requires_admin(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_accountant_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/payments/1")

    assert resp.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_payments(app, fake_pool):
    app.dependency_overrides[get_current_user] = override_auth(_make_admin_user)
    rows = [
        payment_record(id=1, amount=Decimal("100.000")),
        payment_record(id=2, amount=Decimal("200.000")),
    ]
    fake_pool._fetch_results = rows

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/payments")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_no_auth_returns_401_or_403(app, fake_pool):
    app.dependency_overrides.clear()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/payments")

    assert resp.status_code in (401, 403)
