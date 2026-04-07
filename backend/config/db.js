// config/db.js
// ─────────────────────────────────────────────────────────
// هذا الملف ينشئ الاتصال بقاعدة بيانات PostgreSQL (Supabase)
// نستخدمه في كل ملفات الـ routes بدلاً من كتابة الاتصال في كل مكان
// ─────────────────────────────────────────────────────────

const { Pool } = require('pg');
require('dotenv').config();

// Pool = مجموعة اتصالات — أكفأ من فتح اتصال جديد لكل طلب
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false // مطلوب لـ Supabase
  }
});

// اختبار الاتصال عند بدء تشغيل السيرفر
pool.connect((err, client, release) => {
  if (err) {
    console.error('❌ فشل الاتصال بقاعدة البيانات:', err.message);
  } else {
    console.log('✅ تم الاتصال بـ Supabase بنجاح');
    release();
  }
});

module.exports = pool;
