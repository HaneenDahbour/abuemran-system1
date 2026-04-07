-- ============================================================
-- نظام ابو عمران — PostgreSQL Database Schema
-- ============================================================
-- كيفية الاستخدام:
--   1. افتح Supabase → SQL Editor
--   2. انسخ هذا الملف كله والصقه
--   3. اضغط "Run"
-- ============================================================


-- ─────────────────────────────────────────────
-- 1. جدول المستخدمين (users)
-- ─────────────────────────────────────────────
-- يخزن كل من يستخدم النظام: مدير، موظف، عميل
-- كلمة المرور مشفّرة (bcrypt) — لا تُخزن أبداً كنص عادي
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(100) UNIQUE NOT NULL,        -- اسم تسجيل الدخول
    password    TEXT NOT NULL,                       -- مشفّرة بـ bcrypt
    full_name   VARCHAR(200) NOT NULL,               -- الاسم الكامل للعرض
    role        VARCHAR(20) NOT NULL                 -- 'admin' | 'employee' | 'client'
                CHECK (role IN ('admin', 'employee', 'client')),
    is_active   BOOLEAN DEFAULT TRUE,                -- هل الحساب مفعّل؟
    created_at  TIMESTAMP DEFAULT NOW()
);


-- ─────────────────────────────────────────────
-- 2. جدول العملاء (clients)
-- ─────────────────────────────────────────────
-- كل عميل له سجل هنا، مرتبط باختياري بحساب مستخدم
CREATE TABLE IF NOT EXISTS clients (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL, -- حساب تسجيل الدخول (اختياري)
    name            VARCHAR(200) NOT NULL,           -- اسم العميل
    department      VARCHAR(50) DEFAULT 'بورسلان',   -- القسم: بورسلان | أحذية | مصري
    credit_limit    DECIMAL(12,2) DEFAULT 5000,      -- الحد الائتماني
    risk_level      VARCHAR(20) DEFAULT 'low'        -- مستوى المخاطرة
                    CHECK (risk_level IN ('low', 'medium', 'high')),
    phone           VARCHAR(50),
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);


-- ─────────────────────────────────────────────
-- 3. جدول الفواتير (invoices)
-- ─────────────────────────────────────────────
-- كل عملية بيع تُسجَّل هنا
CREATE TABLE IF NOT EXISTS invoices (
    id              SERIAL PRIMARY KEY,
    invoice_number  VARCHAR(50) NOT NULL,            -- رقم الفاتورة (مثال: 3402)
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    employee_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    department      VARCHAR(50) DEFAULT 'بورسلان',   -- القسم
    type            VARCHAR(20) NOT NULL             -- ذمة (آجل) | نقدي
                    CHECK (type IN ('ذمة', 'نقدي')),
    amount          DECIMAL(12,2) NOT NULL,          -- القيمة قبل الخصم
    discount        DECIMAL(12,2) DEFAULT 0,         -- الخصم
    net_amount      DECIMAL(12,2) NOT NULL,          -- الصافي
    has_attachment  BOOLEAN DEFAULT FALSE,           -- هل يوجد صورة مرفقة؟
    attachment_url  TEXT,                            -- رابط الصورة في Supabase Storage
    notes           TEXT,
    invoice_date    DATE DEFAULT CURRENT_DATE,
    created_at      TIMESTAMP DEFAULT NOW()
);


-- ─────────────────────────────────────────────
-- 4. جدول المدفوعات (payments)
-- ─────────────────────────────────────────────
-- يخزن الدفعات المحصّلة مع workflow الموافقة
--   pending  → الموظف أرسله، ينتظر المدير
--   approved → المدير وافق، يُخصم من رصيد العميل
--   rejected → المدير رفض مع سبب
CREATE TABLE IF NOT EXISTS payments (
    id               SERIAL PRIMARY KEY,
    client_id        INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    employee_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- من سجّل الدفعة
    approved_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- من وافق / رفض
    amount           DECIMAL(12,2) NOT NULL,
    status           VARCHAR(20) DEFAULT 'pending'
                     CHECK (status IN ('pending', 'approved', 'rejected')),
    rejection_reason TEXT,                           -- سبب الرفض عند الرفض فقط
    has_attachment   BOOLEAN DEFAULT FALSE,
    attachment_url   TEXT,
    notes            TEXT,
    payment_date     DATE DEFAULT CURRENT_DATE,
    approved_at      TIMESTAMP,                      -- وقت الموافقة أو الرفض
    created_at       TIMESTAMP DEFAULT NOW()
);


-- ─────────────────────────────────────────────
-- 5. جدول الشيكات (checks)
-- ─────────────────────────────────────────────
-- يتتبع الشيكات من استلامها حتى صرفها أو إرجاعها
CREATE TABLE IF NOT EXISTS checks (
    id              SERIAL PRIMARY KEY,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    employee_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    check_number    VARCHAR(100) NOT NULL,           -- رقم الشيك
    bank_name       VARCHAR(200),                    -- اسم البنك
    owner_name      VARCHAR(200),                    -- اسم صاحب الشيك
    amount          DECIMAL(12,2) NOT NULL,
    due_date        DATE NOT NULL,                   -- تاريخ الاستحقاق
    status          VARCHAR(20) DEFAULT 'pending'    -- pending | cashed | returned | cancelled
                    CHECK (status IN ('pending', 'cashed', 'returned', 'cancelled')),
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);


-- ─────────────────────────────────────────────
-- 6. جدول الإشعارات (notifications)
-- ─────────────────────────────────────────────
-- إشعارات داخلية موجّهة للمستخدمين حسب الدور
CREATE TABLE IF NOT EXISTS notifications (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE, -- لمستخدم معيّن
    role        VARCHAR(20),                         -- أو لكل مستخدمي هذا الدور
    message     TEXT NOT NULL,
    type        VARCHAR(30) DEFAULT 'info'
                CHECK (type IN ('info', 'pending', 'approved', 'rejected', 'check', 'invoice')),
    is_read     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);


-- ─────────────────────────────────────────────
-- 7. جدول سجل التدقيق (audit_logs)
-- ─────────────────────────────────────────────
-- يسجّل كل عملية مهمة — لا يُحذف أبداً (read-only trail)
CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    user_name   VARCHAR(200),                        -- نسخة من الاسم وقت العملية
    action      VARCHAR(100) NOT NULL,               -- مثال: 'أضاف فاتورة'
    entity_type VARCHAR(50),                         -- invoice | payment | check | client
    entity_id   INTEGER,
    entity_desc TEXT,                                -- وصف قصير للسجل المتأثر
    details     TEXT,
    ip_address  VARCHAR(50),
    created_at  TIMESTAMP DEFAULT NOW()
);


-- ─────────────────────────────────────────────
-- فهارس لتسريع الاستعلامات (Indexes)
-- ─────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_invoices_client    ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date      ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_payments_client    ON payments(client_id);
CREATE INDEX IF NOT EXISTS idx_payments_status    ON payments(status);
CREATE INDEX IF NOT EXISTS idx_checks_client      ON checks(client_id);
CREATE INDEX IF NOT EXISTS idx_checks_due_date    ON checks(due_date);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created      ON audit_logs(created_at);


-- ─────────────────────────────────────────────
-- بيانات تجريبية أوّلية (Seed Data)
-- ─────────────────────────────────────────────
-- كلمة المرور المشفّرة أدناه = bcrypt('1234', 10)
-- يمكنك تغييرها لاحقاً من لوحة التحكم

INSERT INTO users (username, password, full_name, role) VALUES
    ('admin',   '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'المدير العام',    'admin'),
    ('emp',     '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'أحمد محاسب',      'employee'),
    ('khaled',  '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'خالد موظف',       'employee'),
    ('jaloudi', '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'الجالودي',        'client'),
    ('nemroti', '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'النمروطي',        'client')
ON CONFLICT (username) DO NOTHING;

INSERT INTO clients (name, department, credit_limit, risk_level, user_id) VALUES
    ('الجالودي',           'بورسلان', 10000, 'low',    (SELECT id FROM users WHERE username='jaloudi')),
    ('معن ابو عمران',      'بورسلان', 8000,  'low',    NULL),
    ('ابو احمد',           'بورسلان', 5000,  'medium', NULL),
    ('النمروطي',           'بورسلان', 12000, 'low',    (SELECT id FROM users WHERE username='nemroti')),
    ('القريوتي',           'بورسلان', 6000,  'medium', NULL),
    ('ابو لين',            'بورسلان', 9000,  'low',    NULL),
    ('فارس',               'بورسلان', 4000,  'medium', NULL),
    ('حمزة عوض',           'بورسلان', 3000,  'high',   NULL),
    ('ابو الزينات',        'بورسلان', 7000,  'low',    NULL),
    ('لطفي دبور',          'بورسلان', 5000,  'medium', NULL),
    ('وليد ابو دية',       'مصري',    15000, 'low',    NULL),
    ('سيف ابو عمران',      'بورسلان', 2000,  'high',   NULL),
    ('محمود حسن الفالوجي', 'بورسلان', 8000,  'low',    NULL)
ON CONFLICT DO NOTHING;
