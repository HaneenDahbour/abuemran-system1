-- ============================================================
-- نظام أبو عمران — Migration v4
-- شغّل هذا في Supabase → SQL Editor → Run
-- يضيف: موردين قسم الصين + دعم العملات (JOD/USD/CNY) + تعديل
--       السجلات + قسم إيجار المستودع (ضمن المصاريف والرواتب)
-- لا يحذف ولا يعدّل أي بيانات موجودة
-- ============================================================


-- ════════════════════════════════════════
-- 1. موردو الصين — سجل مستقل
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS china_suppliers (
  id         SERIAL        PRIMARY KEY,
  name       VARCHAR(200)  NOT NULL,
  phone      VARCHAR(30),
  notes      TEXT,
  created_by INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ   DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_china_suppliers_name_unique
  ON china_suppliers (LOWER(name));


-- ════════════════════════════════════════
-- 2. دعم العملات (JOD / USD / CNY) لسجلات الصين
--    amount        = المبلغ بالعملة المُدخلة
--    currency      = JOD / USD / CNY
--    exchange_rate = سعر الصرف لتحويل العملة إلى دينار أردني (1 وحدة = ? د.أ)
--    amount_jod    = المبلغ المحوّل إلى دينار أردني (amount * exchange_rate)
-- ════════════════════════════════════════

ALTER TABLE china_payments
  ADD COLUMN IF NOT EXISTS supplier_id    INTEGER REFERENCES china_suppliers(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS currency       VARCHAR(3)    NOT NULL DEFAULT 'JOD',
  ADD COLUMN IF NOT EXISTS exchange_rate  NUMERIC(12,6) NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS amount_jod     NUMERIC(12,3);

ALTER TABLE china_purchases
  ADD COLUMN IF NOT EXISTS supplier_id    INTEGER REFERENCES china_suppliers(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS currency       VARCHAR(3)    NOT NULL DEFAULT 'JOD',
  ADD COLUMN IF NOT EXISTS exchange_rate  NUMERIC(12,6) NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS amount_jod     NUMERIC(12,3);

ALTER TABLE china_sales
  ADD COLUMN IF NOT EXISTS supplier_id    INTEGER REFERENCES china_suppliers(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS currency       VARCHAR(3)    NOT NULL DEFAULT 'JOD',
  ADD COLUMN IF NOT EXISTS exchange_rate  NUMERIC(12,6) NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS amount_jod     NUMERIC(12,3);

-- تعبئة amount_jod للسجلات القديمة (كانت كلها دينار أردني)
UPDATE china_payments  SET amount_jod = amount WHERE amount_jod IS NULL;
UPDATE china_purchases SET amount_jod = amount WHERE amount_jod IS NULL;
UPDATE china_sales     SET amount_jod = amount WHERE amount_jod IS NULL;

CREATE INDEX IF NOT EXISTS idx_china_payments_supplier  ON china_payments(supplier_id);
CREATE INDEX IF NOT EXISTS idx_china_purchases_supplier ON china_purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_china_sales_supplier     ON china_sales(supplier_id);


-- ════════════════════════════════════════
-- 3. إيجار المستودع — تبويب جديد ضمن المصاريف والرواتب
--    warehouse_rents          : تعريف عقد/سجل إيجار (المبلغ الشهري + شهر البداية)
--    warehouse_rent_payments  : حالة كل شهر (مدفوع / غير مدفوع)
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS warehouse_rents (
  id             SERIAL        PRIMARY KEY,
  name           VARCHAR(200)  NOT NULL,           -- اسم المستودع / الجهة المؤجِّرة
  monthly_amount NUMERIC(12,3) NOT NULL CHECK (monthly_amount > 0),
  currency       VARCHAR(3)    NOT NULL DEFAULT 'JOD',
  start_month    DATE          NOT NULL,           -- أول شهر يبدأ منه الإيجار (يُحفظ كأول يوم بالشهر)
  notes          TEXT,
  is_active      BOOLEAN       DEFAULT TRUE,
  created_by     INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouse_rent_payments (
  id         SERIAL        PRIMARY KEY,
  rent_id    INTEGER       NOT NULL REFERENCES warehouse_rents(id) ON DELETE CASCADE,
  month      DATE          NOT NULL,               -- أول يوم من الشهر المعني
  status     VARCHAR(10)   NOT NULL DEFAULT 'pending',  -- paid / pending
  amount     NUMERIC(12,3),                         -- المبلغ الفعلي المدفوع (افتراضياً = monthly_amount)
  paid_date  DATE,
  notes      TEXT,
  created_by INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ   DEFAULT NOW(),
  UNIQUE (rent_id, month)
);

CREATE INDEX IF NOT EXISTS idx_warehouse_rent_payments_rent ON warehouse_rent_payments(rent_id);
CREATE INDEX IF NOT EXISTS idx_warehouse_rent_payments_month ON warehouse_rent_payments(month);

SELECT 'Migration v4 تم بنجاح ✅ — موردو الصين + العملات + إيجار المستودع جاهزة' AS status;
