-- ═══════════════════════════════════════════════════════════
-- الأمانات الشخصية — إعطاء مبالغ لأشخاص وسحبها
-- آمن للتشغيل المتكرر (IF NOT EXISTS)
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS personal_people (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    phone      TEXT,
    notes      TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS personal_transactions (
    id               SERIAL PRIMARY KEY,
    person_id        INTEGER NOT NULL REFERENCES personal_people(id) ON DELETE CASCADE,
    amount           NUMERIC(12,3) NOT NULL CHECK (amount > 0),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('give', 'withdraw')),
    transaction_date DATE DEFAULT CURRENT_DATE,
    notes            TEXT,
    created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_personal_transactions_person ON personal_transactions(person_id);
CREATE INDEX IF NOT EXISTS idx_personal_transactions_date   ON personal_transactions(transaction_date);
