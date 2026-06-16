-- ═══════════════════════════════════════════════════════════
-- إصلاح شامل: أعمدة المستخدمين من نوع UUID → integer
-- المشكلة: بعض الجداول أُنشئت بأعمدة مستخدم من نوع UUID بينما
-- النظام يستخدم users.id كأرقام صحيحة — أي عملية كتابة تفشل بخطأ:
-- "invalid input for query argument ... 'int' object has no attribute 'bytes'"
-- هذا السكربت يبحث في كل الجداول ويصلّح كل عمود متأثر تلقائياً.
-- آمن للتشغيل المتكرر. شغّليه كاملاً في Supabase → SQL Editor
-- ═══════════════════════════════════════════════════════════

DO $$
DECLARE
  r  RECORD;
  fk RECORD;
BEGIN
  FOR r IN
    SELECT c.table_name, c.column_name
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_name = c.table_name AND t.table_schema = 'public'
    WHERE c.table_schema = 'public'
      AND t.table_type = 'BASE TABLE'
      AND c.data_type = 'uuid'
      AND c.column_name IN
        ('created_by','user_id','employee_user_id',
         'submitted_by','approved_by','attributed_employee_id')
      AND c.table_name <> 'users'
  LOOP
    -- إسقاط قيود المفاتيح الأجنبية على هذا العمود أولاً
    FOR fk IN
      SELECT con.conname
      FROM pg_constraint con
      JOIN pg_class rel ON rel.oid = con.conrelid
      JOIN pg_attribute att
        ON att.attrelid = rel.oid AND att.attnum = ANY (con.conkey)
      WHERE rel.relname = r.table_name
        AND att.attname = r.column_name
        AND con.contype = 'f'
    LOOP
      EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I',
                     r.table_name, fk.conname);
    END LOOP;

    -- تحويل النوع إلى integer (القيم القديمة UUID لا تشير لمستخدمين فعليين — تُمسح)
    EXECUTE format(
      'ALTER TABLE %I ALTER COLUMN %I TYPE integer USING NULL',
      r.table_name, r.column_name);

    -- إعادة ربط العمود بجدول المستخدمين
    EXECUTE format(
      'ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I)
       REFERENCES users(id) ON DELETE SET NULL',
      r.table_name,
      r.table_name || '_' || r.column_name || '_fk_int',
      r.column_name);

    RAISE NOTICE 'تم إصلاح: %.% (uuid → integer)', r.table_name, r.column_name;
  END LOOP;
END $$;

-- ── تحقق نهائي: يجب ألا يُرجِع أي صف ──
SELECT c.table_name, c.column_name, c.data_type
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND c.data_type = 'uuid'
  AND c.column_name IN
    ('created_by','user_id','employee_user_id',
     'submitted_by','approved_by','attributed_employee_id')
  AND c.table_name <> 'users';
