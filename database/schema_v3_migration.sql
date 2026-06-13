-- ============================================================
-- نظام أبو عمران — Migration v3
-- شغّل هذا في Supabase → SQL Editor → Run
-- يضيف: قسم الصين (مستقل تماماً) + فهارس مساعدة
-- لا يحذف ولا يعدّل أي بيانات موجودة
-- ============================================================


-- ════════════════════════════════════════
-- 1. قسم الصين — مستقل تماماً عن باقي النظام
-- ════════════════════════════════════════

-- المستثمرون / الشركاء في تجارة الصين
CREATE TABLE IF NOT EXISTS china_investors (
  id         SERIAL        PRIMARY KEY,
  name       VARCHAR(200)  NOT NULL,
  phone      VARCHAR(30),
  notes      TEXT,
  created_by INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ   DEFAULT NOW()
);

-- حركات كل مستثمر: مبلغ أعطاه (contribution) / استرجعه (return) / حصته من الربح (profit_share)
CREATE TABLE IF NOT EXISTS china_investor_transactions (
  id           SERIAL        PRIMARY KEY,
  investor_id  INTEGER       NOT NULL REFERENCES china_investors(id) ON DELETE CASCADE,
  type         VARCHAR(20)   NOT NULL CHECK (type IN ('contribution','return','profit_share')),
  amount       NUMERIC(12,3) NOT NULL,
  trans_date   DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes        TEXT,
  created_by   INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at   TIMESTAMPTZ   DEFAULT NOW()
);

-- الدفعات المرسلة للموردين في الصين
CREATE TABLE IF NOT EXISTS china_payments (
  id             SERIAL        PRIMARY KEY,
  supplier_name  VARCHAR(200)  NOT NULL,
  amount         NUMERIC(12,3) NOT NULL,
  payment_date   DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes          TEXT,
  created_by     INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

-- المشتريات (ما تم شراؤه من الصين) — تكلفة فقط، بدون مخزون
CREATE TABLE IF NOT EXISTS china_purchases (
  id          SERIAL        PRIMARY KEY,
  item_name   VARCHAR(300)  NOT NULL,
  quantity    NUMERIC(12,3) DEFAULT 1,
  amount      NUMERIC(12,3) NOT NULL,
  purchase_date DATE        NOT NULL DEFAULT CURRENT_DATE,
  supplier_name VARCHAR(200),
  notes       TEXT,
  created_by  INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ   DEFAULT NOW()
);

-- المبيعات (ما تم بيعه من بضاعة الصين) — إيراد فقط
CREATE TABLE IF NOT EXISTS china_sales (
  id          SERIAL        PRIMARY KEY,
  item_name   VARCHAR(300)  NOT NULL,
  quantity    NUMERIC(12,3) DEFAULT 1,
  amount      NUMERIC(12,3) NOT NULL,
  sale_date   DATE          NOT NULL DEFAULT CURRENT_DATE,
  buyer_name  VARCHAR(200),
  notes       TEXT,
  created_by  INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ   DEFAULT NOW()
);


-- ════════════════════════════════════════
-- 2. فهارس
-- ════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_china_inv_trans_investor ON china_investor_transactions(investor_id);
CREATE INDEX IF NOT EXISTS idx_china_payments_date       ON china_payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_china_purchases_date      ON china_purchases(purchase_date);
CREATE INDEX IF NOT EXISTS idx_china_sales_date          ON china_sales(sale_date);

SELECT 'Migration v3 تم بنجاح ✅ — قسم الصين جاهز' AS status;
