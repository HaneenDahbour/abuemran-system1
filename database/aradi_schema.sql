-- ============================================================
-- نظام الأراضي (Aradi) — SQL Migration
-- Run this once in Supabase SQL editor (or psql).
-- All statements use IF NOT EXISTS — safe to re-run.
-- ============================================================

-- 1. aradi_plots — قطع الأراضي
CREATE TABLE IF NOT EXISTS aradi_plots (
    id              BIGSERIAL PRIMARY KEY,
    plot_number     TEXT NOT NULL,
    project_name    TEXT,
    location        TEXT,
    area            NUMERIC(14,3),
    purchase_price  NUMERIC(14,3) NOT NULL DEFAULT 0,
    expected_sale_price NUMERIC(14,3) NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'available'
                    CHECK (status IN ('available','reserved','sold','invested','blocked')),
    notes           TEXT,
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Unique on plot_number — one plot_number per entry
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'aradi_plots_plot_number_key'
    ) THEN
        ALTER TABLE aradi_plots ADD CONSTRAINT aradi_plots_plot_number_key UNIQUE (plot_number);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_aradi_plots_status ON aradi_plots(status);


-- 2. aradi_buyers — المشترون
CREATE TABLE IF NOT EXISTS aradi_buyers (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    address     TEXT,
    notes       TEXT,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);


-- 3. aradi_sale_contracts — عقود البيع
CREATE TABLE IF NOT EXISTS aradi_sale_contracts (
    id                      BIGSERIAL PRIMARY KEY,
    plot_id                 BIGINT REFERENCES aradi_plots(id) ON DELETE RESTRICT,
    buyer_id                BIGINT NOT NULL REFERENCES aradi_buyers(id) ON DELETE RESTRICT,
    contract_number         TEXT,
    sale_price              NUMERIC(14,3) NOT NULL CHECK (sale_price >= 0),
    down_payment            NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (down_payment >= 0),
    installment_amount      NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (installment_amount >= 0),
    installment_count       INTEGER NOT NULL DEFAULT 0 CHECK (installment_count >= 0),
    first_installment_date  DATE,
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','completed','cancelled','defaulted')),
    notes                   TEXT,
    created_by              INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aradi_sale_contracts_buyer  ON aradi_sale_contracts(buyer_id);
CREATE INDEX IF NOT EXISTS idx_aradi_sale_contracts_plot   ON aradi_sale_contracts(plot_id);
CREATE INDEX IF NOT EXISTS idx_aradi_sale_contracts_status ON aradi_sale_contracts(status);


-- 4. aradi_installments — الأقساط المتوقعة
CREATE TABLE IF NOT EXISTS aradi_installments (
    id                  BIGSERIAL PRIMARY KEY,
    contract_id         BIGINT NOT NULL REFERENCES aradi_sale_contracts(id) ON DELETE CASCADE,
    installment_number  INTEGER NOT NULL,
    due_date            DATE NOT NULL,
    amount              NUMERIC(14,3) NOT NULL CHECK (amount >= 0),
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (contract_id, installment_number)
);

CREATE INDEX IF NOT EXISTS idx_aradi_installments_contract ON aradi_installments(contract_id);
CREATE INDEX IF NOT EXISTS idx_aradi_installments_due_date ON aradi_installments(due_date);


-- 5. aradi_buyer_payments — المبالغ المحصلة فعلياً من المشترين
CREATE TABLE IF NOT EXISTS aradi_buyer_payments (
    id              BIGSERIAL PRIMARY KEY,
    contract_id     BIGINT NOT NULL REFERENCES aradi_sale_contracts(id) ON DELETE RESTRICT,
    installment_id  BIGINT REFERENCES aradi_installments(id) ON DELETE SET NULL,
    payment_type    TEXT NOT NULL DEFAULT 'installment'
                    CHECK (payment_type IN ('down_payment','installment','extra','correction')),
    amount          NUMERIC(14,3) NOT NULL,
    payment_date    DATE NOT NULL,
    method          TEXT NOT NULL DEFAULT 'cash'
                    CHECK (method IN ('cash','check','bank_transfer','other')),
    status          TEXT NOT NULL DEFAULT 'confirmed'
                    CHECK (status IN ('pending','confirmed','rejected','void')),
    notes           TEXT,
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Only confirmed payments count; allow negative for 'correction' type
ALTER TABLE aradi_buyer_payments
    DROP CONSTRAINT IF EXISTS aradi_buyer_payments_amount_check;
ALTER TABLE aradi_buyer_payments
    ADD CONSTRAINT aradi_buyer_payments_amount_check
    CHECK (amount > 0 OR payment_type = 'correction');

CREATE INDEX IF NOT EXISTS idx_aradi_buyer_payments_contract ON aradi_buyer_payments(contract_id);
CREATE INDEX IF NOT EXISTS idx_aradi_buyer_payments_status   ON aradi_buyer_payments(status);


-- 6. aradi_investors — المستثمرون / الشركاء
CREATE TABLE IF NOT EXISTS aradi_investors (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    address     TEXT,
    notes       TEXT,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);


-- 7. aradi_investments — استثمارات في الأراضي
CREATE TABLE IF NOT EXISTS aradi_investments (
    id                  BIGSERIAL PRIMARY KEY,
    plot_id             BIGINT REFERENCES aradi_plots(id) ON DELETE SET NULL,
    investor_id         BIGINT NOT NULL REFERENCES aradi_investors(id) ON DELETE RESTRICT,
    investment_number   TEXT,
    capital_amount      NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (capital_amount >= 0),
    profit_amount       NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (profit_amount >= 0),
    total_due           NUMERIC(14,3) GENERATED ALWAYS AS (capital_amount + profit_amount) STORED,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','closed','cancelled')),
    notes               TEXT,
    created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aradi_investments_investor ON aradi_investments(investor_id);
CREATE INDEX IF NOT EXISTS idx_aradi_investments_plot     ON aradi_investments(plot_id);
CREATE INDEX IF NOT EXISTS idx_aradi_investments_status   ON aradi_investments(status);


-- 8. aradi_investor_payouts — جداول الدفع المتوقعة للمستثمرين
CREATE TABLE IF NOT EXISTS aradi_investor_payouts (
    id              BIGSERIAL PRIMARY KEY,
    investment_id   BIGINT NOT NULL REFERENCES aradi_investments(id) ON DELETE CASCADE,
    payout_number   INTEGER,
    due_date        DATE,
    amount          NUMERIC(14,3) NOT NULL CHECK (amount >= 0),
    notes           TEXT,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aradi_investor_payouts_investment ON aradi_investor_payouts(investment_id);
CREATE INDEX IF NOT EXISTS idx_aradi_investor_payouts_due_date   ON aradi_investor_payouts(due_date);


-- 9. aradi_investor_payments — المبالغ المدفوعة فعلياً للمستثمرين
CREATE TABLE IF NOT EXISTS aradi_investor_payments (
    id              BIGSERIAL PRIMARY KEY,
    investment_id   BIGINT NOT NULL REFERENCES aradi_investments(id) ON DELETE RESTRICT,
    payout_id       BIGINT REFERENCES aradi_investor_payouts(id) ON DELETE SET NULL,
    amount          NUMERIC(14,3) NOT NULL CHECK (amount > 0),
    payment_date    DATE NOT NULL,
    method          TEXT NOT NULL DEFAULT 'cash'
                    CHECK (method IN ('cash','check','bank_transfer','other')),
    status          TEXT NOT NULL DEFAULT 'confirmed'
                    CHECK (status IN ('pending','confirmed','rejected','void')),
    notes           TEXT,
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aradi_investor_payments_investment ON aradi_investor_payments(investment_id);
CREATE INDEX IF NOT EXISTS idx_aradi_investor_payments_status     ON aradi_investor_payments(status);


-- 10. aradi_checks — الشيكات المرتبطة بالأراضي
CREATE TABLE IF NOT EXISTS aradi_checks (
    id              BIGSERIAL PRIMARY KEY,
    related_type    TEXT NOT NULL
                    CHECK (related_type IN ('buyer_payment','investor_payment','expense','manual')),
    related_id      BIGINT,
    person_name     TEXT,
    check_number    TEXT,
    amount          NUMERIC(14,3) NOT NULL CHECK (amount > 0),
    check_date      DATE,
    received_date   DATE,
    bank_name       TEXT,
    status          TEXT NOT NULL DEFAULT 'received'
                    CHECK (status IN ('received','deposited','cleared','returned','cancelled')),
    direction       TEXT NOT NULL DEFAULT 'in'
                    CHECK (direction IN ('in','out')),
    notes           TEXT,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aradi_checks_status    ON aradi_checks(status);
CREATE INDEX IF NOT EXISTS idx_aradi_checks_direction ON aradi_checks(direction);
CREATE INDEX IF NOT EXISTS idx_aradi_checks_check_date ON aradi_checks(check_date);


-- 11. aradi_expenses — مصاريف الأراضي
CREATE TABLE IF NOT EXISTS aradi_expenses (
    id              BIGSERIAL PRIMARY KEY,
    plot_id         BIGINT REFERENCES aradi_plots(id) ON DELETE SET NULL,
    expense_date    DATE NOT NULL,
    category        TEXT,
    amount          NUMERIC(14,3) NOT NULL CHECK (amount > 0),
    method          TEXT NOT NULL DEFAULT 'cash'
                    CHECK (method IN ('cash','check','bank_transfer','other')),
    status          TEXT NOT NULL DEFAULT 'confirmed'
                    CHECK (status IN ('pending','confirmed','rejected','void')),
    notes           TEXT,
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aradi_expenses_plot   ON aradi_expenses(plot_id);
CREATE INDEX IF NOT EXISTS idx_aradi_expenses_status ON aradi_expenses(status);
CREATE INDEX IF NOT EXISTS idx_aradi_expenses_date   ON aradi_expenses(expense_date);


-- ============================================================
-- Views
-- ============================================================

-- V1: Contract balance view
CREATE OR REPLACE VIEW aradi_v_contract_balance AS
SELECT
    sc.id                                               AS contract_id,
    sc.contract_number,
    sc.buyer_id,
    b.name                                              AS buyer_name,
    sc.plot_id,
    p.plot_number,
    sc.sale_price,
    sc.down_payment,
    sc.installment_amount,
    sc.installment_count,
    sc.first_installment_date,
    sc.status,

    COALESCE((
        SELECT SUM(bp.amount)
        FROM aradi_buyer_payments bp
        WHERE bp.contract_id = sc.id
          AND bp.status = 'confirmed'
    ), 0)                                               AS total_paid,

    sc.sale_price - COALESCE((
        SELECT SUM(bp.amount)
        FROM aradi_buyer_payments bp
        WHERE bp.contract_id = sc.id
          AND bp.status = 'confirmed'
    ), 0)                                               AS remaining,

    COALESCE((
        SELECT SUM(i.amount)
        FROM aradi_installments i
        WHERE i.contract_id = sc.id
    ), 0)                                               AS installment_total_expected,

    COALESCE((
        SELECT SUM(bp.amount)
        FROM aradi_buyer_payments bp
        WHERE bp.contract_id = sc.id
          AND bp.status = 'confirmed'
          AND bp.payment_type = 'installment'
    ), 0)                                               AS installment_total_paid,

    (
        SELECT COUNT(*)
        FROM aradi_installments i
        LEFT JOIN LATERAL (
            SELECT COALESCE(SUM(bp2.amount), 0) AS paid
            FROM aradi_buyer_payments bp2
            WHERE bp2.installment_id = i.id
              AND bp2.status = 'confirmed'
        ) pay ON TRUE
        WHERE i.contract_id = sc.id
          AND i.due_date < CURRENT_DATE
          AND pay.paid < i.amount
    )                                                   AS overdue_installments_count,

    (
        SELECT MIN(i.due_date)
        FROM aradi_installments i
        LEFT JOIN LATERAL (
            SELECT COALESCE(SUM(bp2.amount), 0) AS paid
            FROM aradi_buyer_payments bp2
            WHERE bp2.installment_id = i.id
              AND bp2.status = 'confirmed'
        ) pay ON TRUE
        WHERE i.contract_id = sc.id
          AND pay.paid < i.amount
          AND i.due_date >= CURRENT_DATE
    )                                                   AS next_installment_date

FROM aradi_sale_contracts sc
JOIN aradi_buyers b ON b.id = sc.buyer_id
LEFT JOIN aradi_plots p ON p.id = sc.plot_id;


-- V2: Installment balance view
CREATE OR REPLACE VIEW aradi_v_installment_balance AS
SELECT
    i.id                        AS installment_id,
    i.contract_id,
    i.installment_number,
    i.due_date,
    i.amount,
    COALESCE((
        SELECT SUM(bp.amount)
        FROM aradi_buyer_payments bp
        WHERE bp.installment_id = i.id
          AND bp.status = 'confirmed'
    ), 0)                       AS paid,

    i.amount - COALESCE((
        SELECT SUM(bp.amount)
        FROM aradi_buyer_payments bp
        WHERE bp.installment_id = i.id
          AND bp.status = 'confirmed'
    ), 0)                       AS remaining,

    CASE
        WHEN COALESCE((
            SELECT SUM(bp.amount)
            FROM aradi_buyer_payments bp
            WHERE bp.installment_id = i.id
              AND bp.status = 'confirmed'
        ), 0) >= i.amount                           THEN 'paid'
        WHEN COALESCE((
            SELECT SUM(bp.amount)
            FROM aradi_buyer_payments bp
            WHERE bp.installment_id = i.id
              AND bp.status = 'confirmed'
        ), 0) > 0                                   THEN 'partial'
        WHEN i.due_date < CURRENT_DATE              THEN 'overdue'
        ELSE 'pending'
    END                         AS computed_status

FROM aradi_installments i;


-- V3: Investment balance view
CREATE OR REPLACE VIEW aradi_v_investment_balance AS
SELECT
    inv.id                          AS investment_id,
    inv.investment_number,
    inv.investor_id,
    ir.name                         AS investor_name,
    inv.plot_id,
    p.plot_number,
    inv.capital_amount,
    inv.profit_amount,
    inv.total_due,
    inv.status,

    COALESCE((
        SELECT SUM(ip.amount)
        FROM aradi_investor_payments ip
        WHERE ip.investment_id = inv.id
          AND ip.status = 'confirmed'
    ), 0)                           AS total_paid_out,

    inv.total_due - COALESCE((
        SELECT SUM(ip.amount)
        FROM aradi_investor_payments ip
        WHERE ip.investment_id = inv.id
          AND ip.status = 'confirmed'
    ), 0)                           AS remaining_to_pay

FROM aradi_investments inv
JOIN aradi_investors ir ON ir.id = inv.investor_id
LEFT JOIN aradi_plots p ON p.id = inv.plot_id;
