-- ═══════════════════════════════════════════════════════════
-- ربط الفواتير والمقبوضات القديمة بالعملاء عبر تطابق الاسم
-- المشكلة: فواتير ومقبوضات سُجِّلت باسم الزبون فقط (client_id فارغ)
-- فكان كشف العميل لا يراها بينما كشف زبائن الفواتير يراها.
-- آمن للتشغيل المتكرر. شغّليه كاملاً في Supabase → SQL Editor
-- ═══════════════════════════════════════════════════════════

-- ربط الفواتير غير المربوطة بعميل يطابق اسمه "المطلوب من السادة"
UPDATE invoices i
SET client_id = c.id
FROM clients c
WHERE i.client_id IS NULL
  AND i.recipient_name IS NOT NULL
  AND LOWER(TRIM(i.recipient_name)) = LOWER(TRIM(c.name));

-- ربط المقبوضات غير المربوطة بعميل يطابق اسم الزبون
UPDATE recipient_payments rp
SET client_id = c.id
FROM clients c
WHERE rp.client_id IS NULL
  AND rp.recipient_name IS NOT NULL
  AND LOWER(TRIM(rp.recipient_name)) = LOWER(TRIM(c.name));

-- ═══ تقرير نهائي ═══
-- 1) ما تبقّى غير مربوط (أسماء زبائن لا يوجد لها عميل بنفس الاسم بالضبط)
SELECT 'فواتير غير مربوطة' AS النوع, recipient_name AS الاسم, COUNT(*) AS العدد,
       SUM(total_amount) AS الإجمالي
FROM invoices
WHERE client_id IS NULL AND recipient_name IS NOT NULL AND TRIM(recipient_name) <> ''
GROUP BY recipient_name
UNION ALL
SELECT 'مقبوضات غير مربوطة', recipient_name, COUNT(*), SUM(amount)
FROM recipient_payments
WHERE client_id IS NULL AND recipient_name IS NOT NULL AND TRIM(recipient_name) <> ''
GROUP BY recipient_name
ORDER BY النوع, الإجمالي DESC;
