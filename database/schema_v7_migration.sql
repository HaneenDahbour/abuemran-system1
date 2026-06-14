-- Schema v7: per-user permissions
ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions JSONB DEFAULT NULL;

SELECT 'تمت إضافة عمود الصلاحيات permissions بنجاح' AS status;
