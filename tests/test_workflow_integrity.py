import ast
import unittest
from datetime import date
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


def load_functions(path, names, extra=None):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    module = ast.Module(body=nodes, type_ignores=[])
    namespace = {"HTTPException": HTTPException, "date": date, "Optional": Optional}
    if extra:
        namespace.update(extra)
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


INVOICES_PATH = ROOT / "backend-py" / "routers" / "invoices.py"
CLIENTS_PATH = ROOT / "backend-py" / "routers" / "clients.py"
EXPENSES_PATH = ROOT / "backend-py" / "routers" / "expenses.py"


class FakeConn:
    def __init__(self):
        self.calls = []

    async def execute(self, sql, *args):
        self.calls.append((sql, args))


class FakePayrollPool:
    async def fetchval(self, sql, *args):
        if "FROM users" in sql:
            return 500
        if "FROM employee_advances" in sql:
            return 125
        raise AssertionError(sql)


class WorkflowIntegrityTests(unittest.TestCase):
    def test_payment_calculation(self):
        ns = load_functions(INVOICES_PATH, {"money3", "calculate_payment"})
        calculate = ns["calculate_payment"]
        self.assertEqual(calculate(100, "credit", 50), (0, 100, "debt"))
        self.assertEqual(calculate(100, "cash", 0), (100, 0, "paid"))
        self.assertEqual(calculate(100, "partial", 25), (25, 75, "partial"))

    def test_client_cannot_read_another_client(self):
        ns = load_functions(CLIENTS_PATH, {"require_client_access"}, {"require_permission": lambda *_: None})
        with self.assertRaises(HTTPException) as error:
            ns["require_client_access"]({"role": "client", "client_id": 7}, 8)
        self.assertEqual(error.exception.status_code, 403)

    def test_client_delete_restores_only_approved_invoice_stock(self):
        source = CLIENTS_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("COALESCE(i.status, 'approved') = 'approved'", source)

    def test_rejection_preserves_invoice(self):
        source = INVOICES_PATH.read_text(encoding="utf-8-sig")
        reject_source = source[source.index("async def reject_invoice"):source.index("async def delete_invoice")]
        self.assertIn("SET status='rejected'", reject_source)
        self.assertNotIn("DELETE FROM invoices", reject_source)

class AsyncWorkflowIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def test_invoice_edit_removes_only_automatic_recipient_payment(self):
        ns = load_functions(INVOICES_PATH, {"delete_auto_payment_for_invoice"})
        conn = FakeConn()
        await ns["delete_auto_payment_for_invoice"](conn, 42)
        self.assertEqual(len(conn.calls), 1)
        sql, args = conn.calls[0]
        self.assertIn("دفعة تلقائية", sql)
        self.assertNotIn("DELETE FROM payments", sql)
        self.assertEqual(args[0], 42)

    async def test_advance_preview_does_not_mutate_salary_rows(self):
        ns = load_functions(EXPENSES_PATH, {"next_month", "preview_advance_against_salary"})
        result = await ns["preview_advance_against_salary"](FakePayrollPool(), 3, date(2026, 6, 24))
        self.assertEqual(result["base_salary"], 500)
        self.assertEqual(result["month_advances"], 125)
        self.assertEqual(result["remaining_salary"], 375)
        self.assertFalse(result["auto_settled"])


if __name__ == "__main__":
    unittest.main()
