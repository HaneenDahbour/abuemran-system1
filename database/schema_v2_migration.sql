-- ============================================================
-- نظام أبو عمران — Migration v2 للـ Python Backend
-- شغّل هذا في Supabase → SQL Editor → Run
-- يضيف الجداول والأعمدة الناقصة دون حذف أي بيانات موجودة
-- ============================================================


-- ════════════════════════════════════════
-- 1. إضافة أعمدة ناقصة لجداول موجودة
-- ════════════════════════════════════════

-- users: إضافة اسم الزبون (للموظفين من نوع recipient)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS recipient_name VARCHAR(200);

-- invoices: أعمدة النظام الجديد
ALTER TABLE invoices
  ADD COLUMN IF NOT EXISTS recipient_name         VARCHAR(200),
  ADD COLUMN IF NOT EXISTS attributed_employee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS status                 VARCHAR(20) DEFAULT 'approved'
                                                  CHECK (status IN ('pending','approved','rejected')),
  ADD COLUMN IF NOT EXISTS approved_by            INTEGER REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS approved_at            TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS initial_paid_amount    NUMERIC(12,3) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS invoice_writer_name    VARCHAR(200);

-- payments: ربط المقبوضة بفاتورة (legacy cleanup)
ALTER TABLE payments
  ADD COLUMN IF NOT EXISTS invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL;


-- ════════════════════════════════════════
-- 2. جداول المستودع الجديدة
-- ════════════════════════════════════════

-- فئات المستودع
CREATE TABLE IF NOT EXISTS warehouse_categories (
  id         SERIAL PRIMARY KEY,
  name       VARCHAR(200) NOT NULL,
  icon       VARCHAR(20)  DEFAULT '📦',
  created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- الأصناف
CREATE TABLE IF NOT EXISTS products (
  id            UUID         DEFAULT gen_random_uuid() PRIMARY KEY,
  name          VARCHAR(300) NOT NULL,
  sku           VARCHAR(100),
  category_id   INTEGER      REFERENCES warehouse_categories(id) ON DELETE SET NULL,
  category      VARCHAR(200),
  unit          VARCHAR(50)  DEFAULT 'قطعة',
  min_stock     NUMERIC(12,3) DEFAULT 0,
  current_stock NUMERIC(12,3) DEFAULT 0,
  properties    JSONB         DEFAULT '{}',
  cost_price    NUMERIC(12,3) DEFAULT 0,
  base_price    NUMERIC(12,3) DEFAULT 0,   -- legacy alias
  created_at    TIMESTAMPTZ   DEFAULT NOW()
);

-- حركات المخزون
CREATE TABLE IF NOT EXISTS stock_movements (
  id          SERIAL       PRIMARY KEY,
  product_id  UUID         REFERENCES products(id) ON DELETE CASCADE,
  type        VARCHAR(5)   NOT NULL CHECK (type IN ('in','out')),
  quantity    NUMERIC(12,3) NOT NULL,
  source_type VARCHAR(30),
  source_id   INTEGER,
  notes       TEXT,
  created_by  INTEGER      REFERENCES users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- بنود الفواتير (مرتبطة بأصناف المستودع)
CREATE TABLE IF NOT EXISTS invoice_items (
  id            SERIAL        PRIMARY KEY,
  invoice_id    INTEGER       NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  product_id    UUID          REFERENCES products(id) ON DELETE SET NULL,
  description   TEXT,
  quantity      NUMERIC(12,3) NOT NULL,
  unit_price    NUMERIC(12,3) DEFAULT 0,
  line_total    NUMERIC(12,3) DEFAULT 0,
  package_qty   NUMERIC(12,3) DEFAULT 12,
  package_price NUMERIC(12,3) DEFAULT 0,
  pricing_note  TEXT,
  created_at    TIMESTAMPTZ   DEFAULT NOW()
);


-- ════════════════════════════════════════
-- 3. جداول فواتير المستودع الداخلية
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS warehouse_invoices (
  id             SERIAL        PRIMARY KEY,
  invoice_number VARCHAR(100),
  category_id    INTEGER       REFERENCES warehouse_categories(id) ON DELETE SET NULL,
  buyer_name     VARCHAR(200),
  supplier_name  VARCHAR(200),
  date           DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes          TEXT,
  total          NUMERIC(12,3) DEFAULT 0,
  issued_by      INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouse_invoice_items (
  id                   SERIAL        PRIMARY KEY,
  warehouse_invoice_id INTEGER       NOT NULL REFERENCES warehouse_invoices(id) ON DELETE CASCADE,
  product_id           UUID          REFERENCES products(id) ON DELETE SET NULL,
  quantity             NUMERIC(12,3) NOT NULL,
  unit_price           NUMERIC(12,3) DEFAULT 0,
  created_at           TIMESTAMPTZ   DEFAULT NOW()
);


-- ════════════════════════════════════════
-- 4. جداول الموردين والمشتريات
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS suppliers (
  id         SERIAL       PRIMARY KEY,
  name       VARCHAR(200) NOT NULL,
  phone      VARCHAR(30),
  created_at TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS supplier_payments (
  id             SERIAL        PRIMARY KEY,
  supplier_id    INTEGER       NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
  amount         NUMERIC(12,3) NOT NULL,
  payment_date   DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes          TEXT,
  payment_method VARCHAR(20)   DEFAULT 'cash',
  created_by     INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchases (
  id             SERIAL        PRIMARY KEY,
  supplier_id    INTEGER       REFERENCES suppliers(id) ON DELETE SET NULL,
  invoice_number VARCHAR(100),
  date           DATE          NOT NULL DEFAULT CURRENT_DATE,
  total          NUMERIC(12,3) DEFAULT 0,
  notes          TEXT,
  created_by     INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  status         VARCHAR(20)   DEFAULT 'pending' CHECK (status IN ('pending','received')),
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_items (
  id          SERIAL        PRIMARY KEY,
  purchase_id INTEGER       NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
  product_id  UUID          REFERENCES products(id) ON DELETE SET NULL,
  quantity    NUMERIC(12,3) NOT NULL,
  unit_price  NUMERIC(12,3) DEFAULT 0,
  created_at  TIMESTAMPTZ   DEFAULT NOW()
);


-- ════════════════════════════════════════
-- 5. جداول المصاريف والرواتب والسلف
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cashbox_expenses (
  id            SERIAL        PRIMARY KEY,
  name          VARCHAR(300)  NOT NULL,
  description   TEXT,
  amount        NUMERIC(12,3) NOT NULL,
  expense_type  VARCHAR(20)   DEFAULT 'daily'
                              CHECK (expense_type IN ('daily','monthly','fixed','other')),
  category      VARCHAR(100),
  is_fixed      BOOLEAN       DEFAULT false,
  expense_date  DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes         TEXT,
  created_by    INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employee_salaries (
  id                 SERIAL        PRIMARY KEY,
  employee_user_id   INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  employee_name      VARCHAR(200)  NOT NULL,
  salary_amount      NUMERIC(12,3) NOT NULL,
  salary_month       DATE          NOT NULL,
  paid_date          DATE          DEFAULT CURRENT_DATE,
  status             VARCHAR(20)   DEFAULT 'paid' CHECK (status IN ('paid','pending')),
  notes              TEXT,
  created_by         INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at         TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employee_advances (
  id            SERIAL        PRIMARY KEY,
  user_id       INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  employee_name VARCHAR(200)  NOT NULL,
  amount        NUMERIC(12,3) NOT NULL,
  advance_date  DATE          DEFAULT CURRENT_DATE,
  advance_type  VARCHAR(20)   DEFAULT 'advance',
  notes         TEXT,
  created_by    INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_expenses_date     ON cashbox_expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_salaries_employee ON employee_salaries(employee_user_id);
CREATE INDEX IF NOT EXISTS idx_advances_user     ON employee_advances(user_id);


-- ════════════════════════════════════════
-- 6. جدول المقبوضات الجديد (recipient_payments)
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS recipient_payments (
  id             SERIAL        PRIMARY KEY,
  recipient_name VARCHAR(200)  NOT NULL,
  client_id      INTEGER       REFERENCES clients(id) ON DELETE SET NULL,
  invoice_id     INTEGER       REFERENCES invoices(id) ON DELETE SET NULL,
  amount         NUMERIC(12,3) NOT NULL,
  payment_method VARCHAR(20)   DEFAULT 'cash',
  payment_date   DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes          TEXT,
  created_by     INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);


-- ════════════════════════════════════════
-- 7. فهارس لتسريع الاستعلامات
-- ════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_products_category    ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_sku         ON products(sku);
CREATE INDEX IF NOT EXISTS idx_stock_mov_product    ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_mov_created    ON stock_movements(created_at);
CREATE INDEX IF NOT EXISTS idx_inv_items_invoice    ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_inv_items_product    ON invoice_items(product_id);
CREATE INDEX IF NOT EXISTS idx_wh_inv_items_wh      ON warehouse_invoice_items(warehouse_invoice_id);
CREATE INDEX IF NOT EXISTS idx_wh_inv_items_prod    ON warehouse_invoice_items(product_id);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier   ON purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_pur   ON purchase_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_rcpt_pay_invoice     ON recipient_payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_rcpt_pay_client      ON recipient_payments(client_id);
CREATE INDEX IF NOT EXISTS idx_rcpt_pay_recipient   ON recipient_payments(recipient_name);
CREATE INDEX IF NOT EXISTS idx_invoices_attributed  ON invoices(attributed_employee_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status      ON invoices(status);

SELECT 'Migration v2 تم بنجاح ✅' AS status;
