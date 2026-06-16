-- الراتب الشهري الأساسي للموظف — شغّليه مرة واحدة في Supabase SQL Editor
ALTER TABLE users ADD COLUMN IF NOT EXISTS base_salary NUMERIC(12,3) DEFAULT 0;
