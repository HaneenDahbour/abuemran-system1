-- ============================================================
-- نظام أبو عمران — Migration v5
-- شغّل هذا في Supabase → SQL Editor → Run
-- يضيف: قسم "المحلات" (مستقل تماماً) بتسجيل دخول خاص
--       - فئات المحلات (محلات الأحذية / الملابس ... قابلة للإضافة)
--       - كل محل: موظف مسؤول، موردين، مشتريات، شيكات، مصاريف/رواتب،
--         وصندوق نقدي يومي (إيداعات + مقبوضات اليوم - مصاريف = الباقي)
-- لا يحذف ولا يعدّل أي بيانات موجودة
-- ============================================================


-- ════════════════════════════════════════
-- 0. أدوار جديدة للمستخدمين: مدير محلات / موظف محل
-- ════════════════════════════════════════

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
  CHECK (role IN ('admin','accountant','employee','client','recipient','shop_manager','shop_employee'));


-- ════════════════════════════════════════
-- 1. فئات المحلات (مثل: محلات الأحذية، محلات الملابس)
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS shop_categories (
  id         SERIAL        PRIMARY KEY,
  name       VARCHAR(200)  NOT NULL,
  icon       VARCHAR(20)   DEFAULT '🏬',
  notes      TEXT,
  created_by INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ   DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_shop_categories_name_unique
  ON shop_categories (LOWER(name));


-- ════════════════════════════════════════
-- 2. المحلات نفسها
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS shops (
  id                     SERIAL        PRIMARY KEY,
  category_id            INTEGER       NOT NULL REFERENCES shop_categories(id) ON DELETE CASCADE,
  name                   VARCHAR(200)  NOT NULL,
  responsible_employee_id INTEGER      REFERENCES users(id) ON DELETE SET NULL,
  responsible_name       VARCHAR(200), -- اسم المسؤول إن لم يكن له حساب مستخدم
  location               VARCHAR(300),
  phone                  VARCHAR(30),
  notes                  TEXT,
  is_active              BOOLEAN       DEFAULT TRUE,
  created_by             INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at             TIMESTAMPTZ   DEFAULT NOW(),
  updated_at             TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shops_category ON shops(category_id);
CREATE INDEX IF NOT EXISTS idx_shops_employee ON shops(responsible_employee_id);

-- ربط المستخدم (موظف المحل) بالمحل الذي يديره — يسهل تسجيل الدخول المباشر لمحله
ALTER TABLE users ADD COLUMN IF NOT EXISTS shop_id INTEGER REFERENCES shops(id) ON DELETE SET NULL;


-- ════════════════════════════════════════
-- 3. موردو المحل
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS shop_suppliers (
  id         SERIAL        PRIMARY KEY,
  shop_id    INTEGER       NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  name       VARCHAR(200)  NOT NULL,
  phone      VARCHAR(30),
  notes      TEXT,
  created_by INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shop_suppliers_shop ON shop_suppliers(shop_id);


-- ════════════════════════════════════════
-- 4. مشتريات المحل (ما اشتراه الموظف ومن أي مورد)
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS shop_purchases (
  id             SERIAL        PRIMARY KEY,
  shop_id        INTEGER       NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  supplier_id    INTEGER       REFERENCES shop_suppliers(id) ON DELETE SET NULL,
  supplier_name  VARCHAR(200), -- نسخة من الاسم وقت الإدخال (أو اسم حر بدون مورد مسجّل)
  invoice_number VARCHAR(100),
  description    TEXT,
  amount         NUMERIC(12,3) NOT NULL,
  purchase_date  DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes          TEXT,
  attachment_url TEXT,
  created_by     INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shop_purchases_shop ON shop_purchases(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_purchases_date ON shop_purchases(purchase_date);


-- ════════════════════════════════════════
-- 5. شيكات المحل (شيكات كتبها الموظف لصالح موردين أو غيرهم)
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS shop_checks (
  id                SERIAL        PRIMARY KEY,
  shop_id           INTEGER       NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  check_number      VARCHAR(100)  NOT NULL,
  bank_name         VARCHAR(200),
  owner_name        VARCHAR(200), -- لمن صدر الشيك (مورد/شخص)
  amount            NUMERIC(12,3) NOT NULL,
  due_date          DATE          NOT NULL,
  status            VARCHAR(15)   DEFAULT 'pending' CHECK (status IN ('pending','cashed','returned','cancelled')),
  notes             TEXT,
  status_notes      TEXT,
  image_url         TEXT,
  created_by        INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  status_updated_by INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  status_updated_at TIMESTAMPTZ,
  created_at        TIMESTAMPTZ   DEFAULT NOW(),
  updated_at        TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shop_checks_shop   ON shop_checks(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_checks_due    ON shop_checks(due_date);
CREATE INDEX IF NOT EXISTS idx_shop_checks_status ON shop_checks(status);


-- ════════════════════════════════════════
-- 6. مصاريف ورواتب المحل
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS shop_expenses (
  id            SERIAL        PRIMARY KEY,
  shop_id       INTEGER       NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  expense_type  VARCHAR(20)   NOT NULL DEFAULT 'other' CHECK (expense_type IN ('salary','rent','utility','other')),
  title         VARCHAR(200)  NOT NULL,
  employee_name VARCHAR(200), -- في حالة راتب موظف
  amount        NUMERIC(12,3) NOT NULL,
  expense_date  DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes         TEXT,
  created_by    INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shop_expenses_shop ON shop_expenses(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_expenses_date ON shop_expenses(expense_date);


-- ════════════════════════════════════════
-- 7. الصندوق اليومي للمحل
--    type = 'deposit'  : مبلغ تُسلِّمه الإدارة للمحل (يزيد الرصيد)
--    type = 'income'   : مقبوضات/مبيعات يومية يسجّلها الموظف (يزيد الرصيد)
--    type = 'expense'  : ما يُصرف من الصندوق (ينقص الرصيد)
--    الرصيد المتبقي = SUM(deposit) + SUM(income) - SUM(expense)
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS shop_cash_transactions (
  id         SERIAL        PRIMARY KEY,
  shop_id    INTEGER       NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  type       VARCHAR(10)   NOT NULL CHECK (type IN ('deposit','income','expense')),
  amount     NUMERIC(12,3) NOT NULL CHECK (amount > 0),
  trans_date DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes      TEXT,
  created_by INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shop_cash_shop ON shop_cash_transactions(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_cash_date ON shop_cash_transactions(trans_date);
CREATE INDEX IF NOT EXISTS idx_shop_cash_type ON shop_cash_transactions(type);


SELECT 'Migration v5 تم بنجاح ✅ — قسم المحلات جاهز' AS status;
