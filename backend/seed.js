// backend/seed.js
// ─────────────────────────────────────────────────────────
// يُشغَّل مرة واحدة فقط لإضافة المستخدمين التجريبيين بكلمات مرور مشفّرة
// الأمر: node seed.js
// ─────────────────────────────────────────────────────────

const bcrypt = require('bcryptjs');
const pool   = require('./config/db');

async function seed() {
  console.log('🌱 جاري إضافة البيانات التجريبية...');

  // كلمات المرور تُشفَّر هنا
  const hash1234 = await bcrypt.hash('1234', 10);

  // ── المستخدمون ──────────────────────────────────────────
  const users = [
    { username: 'admin',   password: hash1234, full_name: 'المدير العام',    role: 'admin'    },
    { username: 'emp',     password: hash1234, full_name: 'أحمد محاسب',      role: 'employee' },
    { username: 'khaled',  password: hash1234, full_name: 'خالد موظف',       role: 'employee' },
    { username: 'jaloudi', password: hash1234, full_name: 'الجالودي',        role: 'client'   },
    { username: 'nemroti', password: hash1234, full_name: 'النمروطي',        role: 'client'   },
  ];

  for (const u of users) {
    await pool.query(
      `INSERT INTO users (username, password, full_name, role)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (username) DO UPDATE SET password=$2, full_name=$3`,
      [u.username, u.password, u.full_name, u.role]
    );
    console.log(`  ✅ مستخدم: ${u.username} (${u.role})`);
  }

  // ── العملاء ─────────────────────────────────────────────
  const clients = [
    { name:'الجالودي',            dept:'بورسلان', limit:10000, risk:'low'    },
    { name:'معن ابو عمران',       dept:'بورسلان', limit:8000,  risk:'low'    },
    { name:'ابو احمد',            dept:'بورسلان', limit:5000,  risk:'medium' },
    { name:'النمروطي',            dept:'بورسلان', limit:12000, risk:'low'    },
    { name:'القريوتي',            dept:'بورسلان', limit:6000,  risk:'medium' },
    { name:'ابو لين',             dept:'بورسلان', limit:9000,  risk:'low'    },
    { name:'فارس',                dept:'بورسلان', limit:4000,  risk:'medium' },
    { name:'حمزة عوض',            dept:'بورسلان', limit:3000,  risk:'high'   },
    { name:'ابو الزينات',         dept:'بورسلان', limit:7000,  risk:'low'    },
    { name:'لطفي دبور',           dept:'بورسلان', limit:5000,  risk:'medium' },
    { name:'وليد ابو دية',        dept:'مصري',    limit:15000, risk:'low'    },
    { name:'سيف ابو عمران',       dept:'بورسلان', limit:2000,  risk:'high'   },
    { name:'محمود حسن الفالوجي',  dept:'بورسلان', limit:8000,  risk:'low'    },
  ];

  // ربط عملاء Jaloudi و Nemroti بحساباتهم
  const jalId  = (await pool.query(`SELECT id FROM users WHERE username='jaloudi'`)).rows[0]?.id;
  const nemId  = (await pool.query(`SELECT id FROM users WHERE username='nemroti'`)).rows[0]?.id;

  for (const c of clients) {
    let userId = null;
    if (c.name === 'الجالودي')  userId = jalId;
    if (c.name === 'النمروطي') userId = nemId;

    await pool.query(
      `INSERT INTO clients (name, department, credit_limit, risk_level, user_id)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT DO NOTHING`,
      [c.name, c.dept, c.limit, c.risk, userId]
    );
    console.log(`  ✅ عميل: ${c.name}`);
  }

  console.log('\n🎉 اكتملت البيانات التجريبية بنجاح!');
  console.log('   يمكنك الآن الدخول بـ: admin / 1234');
  process.exit(0);
}

seed().catch(err => {
  console.error('❌ خطأ:', err.message);
  process.exit(1);
});
