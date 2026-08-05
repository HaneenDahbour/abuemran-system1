import os
import sys
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-unit-tests")


class FakeRecord(dict):
    def keys(self):
        return super().keys()


class FakeConnection:
    def __init__(self, pool):
        self._pool = pool

    async def fetch(self, query, *args):
        return self._pool._fetch_results

    async def fetchrow(self, query, *args):
        rows = self._pool._fetchrow_results
        if callable(rows):
            return rows(query, *args)
        return rows

    async def fetchval(self, query, *args):
        val = self._pool._fetchval_results
        if callable(val):
            return val(query, *args)
        return val

    async def execute(self, query, *args):
        return "OK"

    def transaction(self):
        return FakeTransaction()


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class FakePool:
    def __init__(self):
        self._fetch_results = []
        self._fetchrow_results = None
        self._fetchval_results = True

    async def fetch(self, query, *args):
        return self._fetch_results

    async def fetchrow(self, query, *args):
        rows = self._fetchrow_results
        if callable(rows):
            return rows(query, *args)
        return rows

    async def fetchval(self, query, *args):
        val = self._fetchval_results
        if callable(val):
            return val(query, *args)
        return val

    async def execute(self, query, *args):
        return "OK"

    def acquire(self):
        return FakeAcquire(self)


class FakeAcquire:
    def __init__(self, pool):
        self._pool = pool

    async def __aenter__(self):
        return FakeConnection(self._pool)

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def fake_pool():
    return FakePool()


def _make_admin_user():
    return {"id": 1, "role": "admin", "full_name": "Admin", "username": "admin"}

def _make_accountant_user():
    return {"id": 2, "role": "accountant", "full_name": "Accountant", "username": "accountant"}

def _make_employee_user():
    return {"id": 3, "role": "employee", "full_name": "Employee", "username": "employee"}


@pytest.fixture
def app(fake_pool):
    import config.db as db_mod
    db_mod.pool = fake_pool

    from main import app as _app
    return _app


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
