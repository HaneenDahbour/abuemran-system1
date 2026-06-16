-- ═══════════════════════════════════════════════════════════
-- جداول المصاريف والرواتب والسلف
-- شغّلي هذا الملف في Supabase → SQL Editor إذا لم تكن الجداول موجودة
-- آمن للتشغيل المتكرر (IF NOT EXISTS)
-- ═══════════════════════════════════════════════════════════

-- المصاريف (صفحة المصاريف + الصندوق)
CREATE TABLE IF NOT EXISTS cashbox_expenses (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    amount       NUMERIC(12,3) NOT NULL CHECK (amount > 0),
    expense_type TEXT DEFAULT 'daily',          -- daily / monthly / fixed / other
    category     TEXT,
    is_fixed     BOOLEAN DEFAULT FALSE,
    expense_date DATE DEFAULT CURRENT_DATE,
    notes        TEXT,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- رواتب الموظفين
CREATE TABLE IF NOT EXISTS employee_salaries (
    id               SERIAL PRIMARY KEY,
    employee_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    employee_name    TEXT NOT NULL,
    salary_amount    NUMERIC(12,3) NOT NULL CHECK (salary_amount > 0),
    salary_month     DATE NOT NULL,
    paid_date        DATE,
    status           TEXT DEFAULT 'paid',       -- paid / pending
    notes            TEXT,
    created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMP DEFAULT NOW()
);

-- سلف الموظفين
CREATE TABLE IF NOT EXISTS employee_advances (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    employee_name TEXT NOT NULL,
    amount       NUMERIC(12,3) NOT NULL CHECK (amount > 0),
    advance_date DATE DEFAULT CURRENT_DATE,
    advance_type TEXT DEFAULT 'advance',        -- advance / deduction
    notes        TEXT,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- فهارس للأداء
CREATE INDEX IF NOT EXISTS idx_cashbox_expenses_date  ON cashbox_expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_employee_salaries_user ON employee_salaries(employee_user_id);
CREATE INDEX IF NOT EXISTS idx_employee_advances_user ON employee_advances(user_id);
