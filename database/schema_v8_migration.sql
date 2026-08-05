-- ============================================================
-- نظام أبو عمران — Migration v8
-- شغّل هذا في Supabase → SQL Editor → Run
-- يضيف: تسجيل الدفعات للمستثمرين (المبالغ المدفوعة لهم من أرباحهم)
--       - كل دفعة سطر مستقل (تاريخ + مبلغ + ملاحظة)
--       - "المتبقي" لكل مستثمر = إجمالي أرباحه المستحقة − مجموع دفعاته
--       - يُحسب في الباك إند ويُعرض في قائمة المستثمرين والتفاصيل وشاشة الفئة
-- لا يحذف ولا يعدّل أي بيانات موجودة
-- ============================================================


-- ════════════════════════════════════════
-- سجل الدفعات المدفوعة للمستثمر
-- ════════════════════════════════════════

CREATE TABLE IF NOT EXISTS warehouse_investor_payouts (
  id          SERIAL        PRIMARY KEY,
  investor_id INTEGER       NOT NULL REFERENCES warehouse_investors(id) ON DELETE CASCADE,
  amount      NUMERIC(14,3) NOT NULL CHECK (amount > 0),
  payout_date DATE          NOT NULL DEFAULT CURRENT_DATE,
  notes       TEXT,
  created_by  INTEGER       REFERENCES users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wip_investor ON warehouse_investor_payouts(investor_id);


SELECT 'Migration v8 تم بنجاح ✅ — تسجيل دفعات المستثمرين جاهز' AS status;
