# Aradi Module — Test Checklist

## Before Running

1. Run the SQL migration in Supabase SQL editor:
   ```
   database/aradi_schema.sql
   ```
2. Restart the backend server.
3. Log in as `admin` to get a JWT token.

---

## A — Startup Checks

| # | Test | Expected |
|---|------|----------|
| A1 | `GET /health` | `{"status":"ok"}` |
| A2 | `GET /api/aradi/dashboard` (empty DB) | Returns all zeros, no 500 error |
| A3 | `GET /api/clients` | Still works (existing module unaffected) |
| A4 | `GET /api/warehouse-categories` | Still works (warehouse unaffected) |
| A5 | `GET /api/shops` | Still works (shop unaffected) |

---

## B — Plots

```bash
# Create a plot
POST /api/aradi/plots
{
  "plot_number": "710",
  "project_name": "مشروع الشمال",
  "location": "شارع الملك",
  "area": 500.5,
  "purchase_price": 20000,
  "expected_sale_price": 30000,
  "status": "available"
}
```

| # | Test | Expected |
|---|------|----------|
| B1 | POST above | Returns created plot with id |
| B2 | POST same plot_number again | 400 — رقم القطعة مستخدم مسبقاً |
| B3 | `GET /api/aradi/plots` | Returns list including new plot |
| B4 | `GET /api/aradi/plots/{id}` | Returns single plot |
| B5 | `PUT /api/aradi/plots/{id}` with `"status":"reserved"` | Status updated |
| B6 | POST with invalid status `"status":"unknown"` | 400 error |

---

## C — Buyers

```bash
POST /api/aradi/buyers
{"name": "عبدالله هشام الديس", "phone": "0599123456"}
```

| # | Test | Expected |
|---|------|----------|
| C1 | POST above | Returns buyer with id |
| C2 | POST with empty name | 400 error |
| C3 | `GET /api/aradi/buyers` | Returns list |
| C4 | `GET /api/aradi/buyers/{id}` | Returns single buyer |

---

## D — Sale Contracts (Core transaction test)

```bash
POST /api/aradi/contracts
{
  "plot_id": 1,
  "buyer_id": 1,
  "contract_number": "C-001",
  "sale_price": 30000,
  "down_payment": 15000,
  "installment_amount": 1500,
  "installment_count": 10,
  "first_installment_date": "2025-07-01"
}
```

| # | Test | Expected |
|---|------|----------|
| D1 | POST above | Contract created |
| D2 | Check `aradi_buyer_payments` | One row with type=down_payment, amount=15000, status=confirmed |
| D3 | `GET /api/aradi/contracts/{id}/installments` | 10 installment rows, monthly dates |
| D4 | First installment due = 2025-07-01, second = 2025-08-01 | ✓ |
| D5 | `GET /api/aradi/plots/1` | status = "sold" |
| D6 | POST contract with installment_count>0 but no first_installment_date | 400 error |
| D7 | POST with sale_price = -1 | 400 error (negative not allowed) |
| D8 | `GET /api/aradi/contracts/{id}/statement` | Returns contract + installments + payments + summary |
| D9 | summary.remaining = sale_price - total_paid | 30000 - 15000 = 15000 ✓ |

---

## E — Buyer Payments

```bash
POST /api/aradi/payments
{
  "contract_id": 1,
  "installment_id": 2,
  "payment_type": "installment",
  "amount": 1500,
  "payment_date": "2025-08-01",
  "method": "cash",
  "status": "confirmed"
}
```

| # | Test | Expected |
|---|------|----------|
| E1 | POST above | Payment created |
| E2 | Check installment #2 via GET contracts/1/installments | computed_status = "paid" |
| E3 | `PUT /api/aradi/payments/{id}` with `"status":"void"` | Status changed |
| E4 | After void, installment #2 computed_status = "overdue" or "pending" | ✓ (not counted) |
| E5 | POST with amount=0, type=installment | 400 error |
| E6 | POST with type=correction, amount=-100 | Allowed (correction type) |

---

## F — Investors & Investments

```bash
POST /api/aradi/investors
{"name": "يوسف أبو هاني", "phone": "0598765432"}

POST /api/aradi/investments
{
  "plot_id": 1,
  "investor_id": 1,
  "investment_number": "INV-001",
  "capital_amount": 50000,
  "profit_amount": 5926
}
```

| # | Test | Expected |
|---|------|----------|
| F1 | POST investor | Returns with id |
| F2 | POST investment | total_due = 55926 (auto-calculated) |
| F3 | `GET /api/aradi/investments/{id}/statement` | remaining_to_pay = 55926 |
| F4 | POST investor payment: `{"investment_id":1,"amount":10000,"payment_date":"2025-08-01"}` | OK |
| F5 | GET investment statement | remaining_to_pay = 45926 ✓ |

---

## G — Dashboard Totals

| # | Test | Expected |
|---|------|----------|
| G1 | `GET /api/aradi/dashboard` after above tests | |
|    | total_buyer_payments = 15000 (down) + 0 paid installments | ✓ |
|    | total_investor_payments = 10000 | ✓ |
|    | net_cash = buyer_payments - investor_payments - expenses | ✓ |
| G2 | Dashboard with empty DB | All zeros, no errors | 

---

## H — Reports

| # | Test | Expected |
|---|------|----------|
| H1 | `GET /api/aradi/reports/overdue-installments` | Lists overdue installments (past due_date, unpaid) |
| H2 | `GET /api/aradi/reports/upcoming-installments?days=30` | Lists due in next 30 days |
| H3 | `GET /api/aradi/reports/buyer-balances` | All active contracts with remaining |
| H4 | `GET /api/aradi/reports/investor-balances` | All active investments with remaining |
| H5 | `GET /api/aradi/reports/plot-profitability` | Net profit per plot |
| H6 | `GET /api/aradi/reports/upcoming-checks?days=14` | Checks due in 14 days |

---

## I — Access Control

| # | Test | Expected |
|---|------|----------|
| I1 | Any aradi endpoint without JWT token | 403 |
| I2 | Login as `client` role, try `GET /api/aradi/plots` | 403 — ليس لديك صلاحية |
| I3 | Login as `accountant`, access aradi | Allowed |
| I4 | Login as `admin`, full access | Allowed |

---

## J — Quick smoke test (bash/curl)

```bash
BASE="http://localhost:3001"
TOKEN="<your-jwt-here>"

# Dashboard (must return 200 even on empty DB)
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/aradi/dashboard" | python3 -m json.tool

# Existing routes still work
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/clients" | python3 -c "import sys,json; d=json.load(sys.stdin); print('clients OK, count:', len(d))"
```
