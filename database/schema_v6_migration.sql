-- ============================================================
-- نظام أبو عمران — Migration v6
-- شغّل هذا في Supabase → SQL Editor → Run
-- يضيف: قسم "المستثمرين" لمستودع الأصناف
--       - جدول المستثمرين (اسم، هاتف، ملاحظات)
--       - مساهمة كل مستثمر في كل فئة مستودع (المبلغ الذي ساهم به)
--       - الأرباح تُحسب لاحقاً في الباك إند:
--           50% للمالك + 50% توزَّع على المستثمرين بنسبة مساهمتهم في الفئة
-- لا يحذف ولا يعدّل أي بيانات موجودة
-- ============================================================


-- ════════════════════════════════════════
-- 1. المستثمرون
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS warehouse_investors (
  id         SERIAL        PRIMARY KEY,
  name       VARCHAR(200)  NOT NULL,
  phone      VARCHAR(30),
  notes      TEXT,
  created_by INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ   DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouse_investors_name_unique
  ON warehouse_investors (LOWER(name));


-- ════════════════════════════════════════
-- 2. مساهمة كل مستثمر في كل فئة مستودع
--    amount = المبلغ الذي ساهم به هذا المستثمر في هذه الفئة
--    نسبة المستثمر في الفئة = amount / إجمالي مساهمات الفئة
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS warehouse_category_investments (
  id          SERIAL        PRIMARY KEY,
  category_id INTEGER       NOT NULL REFERENCES warehouse_categories(id) ON DELETE CASCADE,
  investor_id INTEGER       NOT NULL REFERENCES warehouse_investors(id) ON DELETE CASCADE,
  amount      NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (amount >= 0),
  notes       TEXT,
  created_by  INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ   DEFAULT NOW(),
  updated_at  TIMESTAMPTZ   DEFAULT NOW(),
  UNIQUE (category_id, investor_id)
);

CREATE INDEX IF NOT EXISTS idx_wci_category ON warehouse_category_investments(category_id);
CREATE INDEX IF NOT EXISTS idx_wci_investor ON warehouse_category_investments(investor_id);


-- ════════════════════════════════════════
-- 3. سجل توزيعات الأرباح المؤرشفة (اختياري — لتوثيق كل تقسيم ربح تم تنفيذه)
--    يُستخدم عند "تأكيد" توزيع ربح فئة في تاريخ معيّن، بدلاً من حساب حي فقط
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS warehouse_profit_distributions (
  id              SERIAL        PRIMARY KEY,
  category_id     INTEGER       NOT NULL REFERENCES warehouse_categories(id) ON DELETE CASCADE,
  total_profit    NUMERIC(12,3) NOT NULL,
  owner_share     NUMERIC(12,3) NOT NULL,
  investors_share NUMERIC(12,3) NOT NULL,
  distribution_date DATE        NOT NULL DEFAULT CURRENT_DATE,
  notes           TEXT,
  created_by      INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouse_profit_distribution_items (
  id               SERIAL        PRIMARY KEY,
  distribution_id  INTEGER       NOT NULL REFERENCES warehouse_profit_distributions(id) ON DELETE CASCADE,
  investor_id      INTEGER       NOT NULL REFERENCES warehouse_investors(id) ON DELETE CASCADE,
  contribution_amount NUMERIC(12,3) NOT NULL,
  contribution_pct    NUMERIC(6,3)  NOT NULL,
  profit_share        NUMERIC(12,3) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wpd_category ON warehouse_profit_distributions(category_id);
CREATE INDEX IF NOT EXISTS idx_wpdi_distribution ON warehouse_profit_distribution_items(distribution_id);
CREATE INDEX IF NOT EXISTS idx_wpdi_investor ON warehouse_profit_distribution_items(investor_id);


SELECT 'Migration v6 تم بنجاح ✅ — قسم مستثمري المستودع جاهز' AS status;
