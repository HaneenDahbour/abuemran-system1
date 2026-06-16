-- Schema v8: ربط سجلات الرواتب والسلف والمصاريف بالمستخدمين عبر مطابقة الاسم

-- ربط الرواتب (employee_salaries)
UPDATE employee_salaries s
SET employee_user_id = u.id
FROM users u
WHERE s.employee_user_id IS NULL
  AND LOWER(TRIM(s.employee_name)) = LOWER(TRIM(u.full_name));

-- ربط السلف (employee_advances)
UPDATE employee_advances ea
SET user_id = u.id
FROM users u
WHERE ea.user_id IS NULL
  AND LOWER(TRIM(ea.employee_name)) = LOWER(TRIM(u.full_name));

-- ربط المصاريف (cashbox_expenses) — إن وجد عمود employee_user_id
UPDATE cashbox_expenses ce
SET employee_user_id = u.id
FROM users u
WHERE ce.employee_user_id IS NULL
  AND ce.employee_name IS NOT NULL
  AND LOWER(TRIM(ce.employee_name)) = LOWER(TRIM(u.full_name));

-- عرض النتائج
SELECT 'رواتب مرتبطة'        AS نوع, COUNT(*) AS عدد FROM employee_salaries  WHERE employee_user_id IS NOT NULL
UNION ALL
SELECT 'رواتب غير مرتبطة',   COUNT(*) FROM employee_salaries  WHERE employee_user_id IS NULL
UNION ALL
SELECT 'سلف مرتبطة',          COUNT(*) FROM employee_advances  WHERE user_id IS NOT NULL
UNION ALL
SELECT 'سلف غير مرتبطة',      COUNT(*) FROM employee_advances  WHERE user_id IS NULL;
