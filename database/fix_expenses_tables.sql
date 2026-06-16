-- ═══════════════════════════════════════════════════════════
-- إصلاح جداول المصاريف والرواتب والسلف
-- المشكلة: الجداول القديمة أُنشئت بأعمدة UUID لكن النظام يستخدم
-- users.id كأرقام (integer) — لذلك كل عمليات الحفظ كانت تفشل بخطأ 500.
-- هذه الجداول فارغة (لم يقبل أي صف بسبب الخطأ) — آمن إعادة إنشاؤها.
-- شغّلي هذا الملف كاملاً في Supabase → SQL Editor
-- ═══════════════════════════════════════════════════════════

-- حذف الجداول القديمة فقط إذا كانت بالبنية الخاطئة (UUID)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='employee_salaries'
               AND column_name='employee_user_id' AND data_type='uuid') THEN
    DROP TABLE employee_salaries CASCADE;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='employee_advances'
               AND column_name='user_id' AND data_type='uuid') THEN
    DROP TABLE employee_advances CASCADE;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='cashbox_expenses'
               AND column_name='created_by' AND data_type='uuid') THEN
    DROP TABLE cashbox_expenses CASCADE;
  END IF;
END $$;

-- إعادة الإنشاء بالبنية الصحيحة (integer مثل users.id)

CREATE TABLE IF NOT EXISTS cashbox_expenses (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    amount       NUMERIC(12,3) NOT NULL CHECK (amount > 0),
    expense_type TEXT DEFAULT 'daily',
    category     TEXT,
    is_fixed     BOOLEAN DEFAULT FALSE,
    expense_date DATE DEFAULT CURRENT_DATE,
    notes        TEXT,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employee_salaries (
    id               SERIAL PRIMARY KEY,
    employee_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    employee_name    TEXT NOT NULL,
    salary_amount    NUMERIC(12,3) NOT NULL CHECK (salary_amount > 0),
    salary_month     DATE NOT NULL,
    paid_date        DATE,
    status           TEXT DEFAULT 'paid',
    notes            TEXT,
    created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employee_advances (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    employee_name TEXT NOT NULL,
    amount        NUMERIC(12,3) NOT NULL CHECK (amount > 0),
    advance_date  DATE DEFAULT CURRENT_DATE,
    advance_type  TEXT DEFAULT 'advance',
    notes         TEXT,
    created_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cashbox_expenses_date  ON cashbox_expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_employee_salaries_user ON employee_salaries(employee_user_id);
CREATE INDEX IF NOT EXISTS idx_employee_advances_user ON employee_advances(user_id);

-- تحقق نهائي — يجب أن تكون كل أعمدة المستخدمين integer
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('employee_salaries','employee_advances','cashbox_expenses')
  AND column_name IN ('employee_user_id','user_id','created_by')
ORDER BY table_name, column_name;
