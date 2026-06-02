-- ============================================================
-- نظام أبو عمران — قاعدة البيانات الكاملة v3
-- انسخ هذا كاملاً في Supabase → SQL Editor → اضغط Run
-- ============================================================

-- 1. جدول المستخدمين
CREATE TABLE IF NOT EXISTS users (
  id               SERIAL PRIMARY KEY,
  username         VARCHAR(100) UNIQUE NOT NULL,
  password_hash    TEXT NOT NULL,              -- ← مهم: اسمه password_hash وليس password
  full_name        VARCHAR(200) NOT NULL,
  role             VARCHAR(20) NOT NULL CHECK (role IN ('admin','accountant','employee','client')),
  client_id        INTEGER,
  telegram_chat_id BIGINT,
  telegram_link_code VARCHAR(50),
  is_active        BOOLEAN DEFAULT true,
  last_login       TIMESTAMPTZ,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 2. جدول العملاء
CREATE TABLE IF NOT EXISTS clients (
  id            SERIAL PRIMARY KEY,
  name          VARCHAR(200) NOT NULL,
  department    VARCHAR(30) DEFAULT 'porcelain' CHECK (department IN ('porcelain','shoes','egyptian')),
  credit_limit  NUMERIC(12,2) DEFAULT 5000,
  risk_level    VARCHAR(10) DEFAULT 'medium' CHECK (risk_level IN ('low','medium','high')),
  phone         VARCHAR(30),
  email         VARCHAR(100),
  notes         TEXT,
  is_blocked    BOOLEAN DEFAULT false,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ربط users بـ clients
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS fk_users_client
  FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL;

-- 3. جدول الفواتير
CREATE TABLE IF NOT EXISTS invoices (
  id              SERIAL PRIMARY KEY,
  client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  invoice_number  VARCHAR(50),
  department      VARCHAR(30) DEFAULT 'porcelain',
  type            VARCHAR(10) DEFAULT 'debt' CHECK (type IN ('debt','cash')),
  amount          NUMERIC(12,2) DEFAULT 0,
  discount        NUMERIC(12,2) DEFAULT 0,
  net_amount      NUMERIC(12,2) NOT NULL,
  tax_amount      NUMERIC(12,2) DEFAULT 0,
  total_amount    NUMERIC(12,2) NOT NULL,
  date            DATE NOT NULL DEFAULT CURRENT_DATE,
  payment_method  VARCHAR(20) DEFAULT 'credit',
  notes           TEXT,
  attachment_url  TEXT,
  created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 4. جدول المدفوعات
CREATE TABLE IF NOT EXISTS payments (
  id               SERIAL PRIMARY KEY,
  client_id        INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  amount           NUMERIC(12,2) NOT NULL,
  payment_method   VARCHAR(20) DEFAULT 'cash',
  payment_date     DATE NOT NULL DEFAULT CURRENT_DATE,
  notes            TEXT,
  receipt_url      TEXT,
  status           VARCHAR(10) DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  rejection_reason TEXT,
  submitted_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
  approved_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
  approved_at      TIMESTAMPTZ,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 5. جدول الشيكات
CREATE TABLE IF NOT EXISTS checks (
  id                SERIAL PRIMARY KEY,
  client_id         INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  check_number      VARCHAR(100) NOT NULL,
  bank_name         VARCHAR(200),
  owner_name        VARCHAR(200),
  amount            NUMERIC(12,2) NOT NULL,
  due_date          DATE NOT NULL,
  status            VARCHAR(15) DEFAULT 'pending' CHECK (status IN ('pending','cashed','returned','cancelled')),
  notes             TEXT,
  status_notes      TEXT,
  image_url         TEXT,
  created_by        INTEGER REFERENCES users(id) ON DELETE SET NULL,
  status_updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  status_updated_at TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- 6. جدول الإشعارات
CREATE TABLE IF NOT EXISTS notifications (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
  role       VARCHAR(20),
  message    TEXT NOT NULL,
  type       VARCHAR(30) DEFAULT 'info',
  is_read    BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. جدول سجل التدقيق
CREATE TABLE IF NOT EXISTS audit_log (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
  user_name   VARCHAR(200),
  action      VARCHAR(100) NOT NULL,
  entity_type VARCHAR(50),
  entity_id   INTEGER,
  detail      TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- فهارس لتسريع الاستعلامات
CREATE INDEX IF NOT EXISTS idx_invoices_client  ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date    ON invoices(date);
CREATE INDEX IF NOT EXISTS idx_payments_client  ON payments(client_id);
CREATE INDEX IF NOT EXISTS idx_payments_status  ON payments(status);
CREATE INDEX IF NOT EXISTS idx_checks_client    ON checks(client_id);
CREATE INDEX IF NOT EXISTS idx_checks_due       ON checks(due_date);
CREATE INDEX IF NOT EXISTS idx_checks_status    ON checks(status);
CREATE INDEX IF NOT EXISTS idx_notif_user       ON notifications(user_id);

-- ============================================================
-- بيانات تجريبية — كلمة المرور = Abu@1234
-- ============================================================
INSERT INTO clients (name, department, credit_limit, risk_level, phone) VALUES
  ('الجالودي',           'porcelain', 10000, 'low',    '0791000001'),
  ('معن ابو عمران',      'porcelain',  8000, 'low',    '0791000002'),
  ('ابو احمد',           'porcelain',  5000, 'medium', '0791000003'),
  ('النمروطي',           'porcelain', 12000, 'low',    '0791000004'),
  ('القريوتي',           'porcelain',  6000, 'medium', '0791000005'),
  ('ابو لين',            'porcelain',  9000, 'low',    '0791000006'),
  ('فارس',               'porcelain',  4000, 'medium', '0791000007'),
  ('حمزة عوض',           'porcelain',  3000, 'high',   '0791000008'),
  ('ابو الزينات',        'porcelain',  7000, 'low',    '0791000009'),
  ('لطفي دبور',          'porcelain',  5000, 'medium', '0791000010'),
  ('وليد ابو دية',       'egyptian',  15000, 'low',    '0791000011'),
  ('سيف ابو عمران',      'porcelain',  2000, 'high',   '0791000012'),
  ('محمود حسن الفالوجي', 'porcelain',  8000, 'low',    '0791000013')
ON CONFLICT DO NOTHING;

-- كلمة المرور = Abu@1234
INSERT INTO users (username, password_hash, full_name, role, client_id) VALUES
  ('admin',      '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'المدير العام',  'admin',      NULL),
  ('accountant', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'أحمد محاسب',   'accountant', NULL),
  ('employee1',  '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'خالد موظف',    'employee',   NULL),
  ('jaloudi',    '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'الجالودي',     'client',     1),
  ('namrooti',   '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'النمروطي',     'client',     4)
ON CONFLICT (username) DO NOTHING;

SELECT 'تم الإعداد بنجاح! كلمة المرور الافتراضية: Abu@1234' AS status;