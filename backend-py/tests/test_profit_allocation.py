"""Loss handling for warehouse investors: losses reduce the total profit,
and only the net profit is split between the owner and the investors."""

import pytest

from routers.warehouse_investors import (
    allocate_profit,
    compute_investor_profit_due,
    compute_profit_allocation,
    get_category_total_profit,
    OWNER_SHARE_PCT,
)


def test_loss_is_deducted_proportionally_from_profitable_categories():
    # أ +1000، ب +500، ج −300  →  الصافي 1200 (أ 800، ب 400)
    a = allocate_profit({1: 1000.0, 2: 500.0, 3: -300.0})
    assert a["gross_profit"] == 1500
    assert a["total_loss"] == 300
    assert a["net_profit"] == 1200
    assert a["distributable_profit"] == 1200
    assert a["effective"][1] == pytest.approx(800)
    assert a["effective"][2] == pytest.approx(400)
    assert a["effective"][3] == 0
    assert sum(a["effective"].values()) == pytest.approx(1200)


def test_net_zero_or_negative_distributes_nothing():
    for raw in ({1: 300.0, 2: -300.0}, {1: 300.0, 2: -900.0}, {1: -50.0}):
        a = allocate_profit(raw)
        assert a["distributable_profit"] == 0
        assert all(v == 0 for v in a["effective"].values())


def test_no_losses_leaves_profits_untouched():
    a = allocate_profit({1: 1000.0, 2: 500.0})
    assert a["effective"] == {1: 1000.0, 2: 500.0}
    assert a["net_profit"] == 1500


def test_empty():
    a = allocate_profit({})
    assert a["distributable_profit"] == 0 and a["effective"] == {}


class FakePool:
    """Minimal asyncpg-like pool: categories + investments."""

    def __init__(self, investments):
        self.investments = investments  # {category_id: [(investor_id, amount)]}

    async def fetch(self, query, *args):
        if "FROM warehouse_categories" in query:
            return [{"id": cid} for cid in self.investments]
        if "FROM warehouse_category_investments" in query:
            return [{"investor_id": i, "amount": amt} for i, amt in self.investments[args[0]]]
        raise AssertionError(query)


@pytest.mark.asyncio
async def test_investor_profit_due_uses_net_profit(monkeypatch):
    profits = {1: 1000.0, 2: 500.0, 3: -300.0}

    async def fake_profit(pool, category_id):
        return {"total_profit": profits[category_id]}

    monkeypatch.setattr("routers.warehouse_investors.get_category_total_profit", fake_profit)
    pool = FakePool({
        1: [(10, 100.0), (11, 100.0)],   # مستثمران بالتساوي
        2: [(10, 100.0)],
        3: [(10, 100.0), (11, 100.0)],   # فئة خاسرة: لا توزيع منها
    })
    alloc = await compute_profit_allocation(pool)
    due = await compute_investor_profit_due(pool, alloc)

    investors_total = 1200 * (1 - OWNER_SHARE_PCT)
    assert sum(due.values()) == pytest.approx(investors_total)          # 600
    assert due[10] == pytest.approx(800 * 0.5 / 2 + 400 * 0.5)          # 200 + 200
    assert due[11] == pytest.approx(800 * 0.5 / 2)                      # 200


@pytest.mark.asyncio
async def test_profit_query_failure_is_not_hidden():
    from fastapi import HTTPException

    class BrokenPool:
        async def fetchrow(self, *a, **k):
            raise RuntimeError("column does not exist")

    with pytest.raises(HTTPException) as exc:
        await get_category_total_profit(BrokenPool(), 1)
    assert exc.value.status_code == 500
