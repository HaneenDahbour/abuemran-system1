# نظام أبو عمران — CLAUDE.md
> دليل المطور الكامل لـ Claude Code

---

## نظرة عامة على المشروع

نظام إدارة أعمال تجاري متكامل لمجموعة أبو عمران التجارية.
يشمل: إدارة العملاء، الفواتير، المقبوضات، الشيكات، مساعد ذكي، وبوت تيليغرام.

---

## هيكل المشروع

```
abuemran-system/
├── backend/                    # Node.js + Express
│   ├── server.js               # نقطة البداية — يشغّل السيرفر والبوت
│   ├── bot.js                  # بوت تيليغرام (Telegraf)
│   ├── seed.js                 # بيانات تجريبية — يُشغَّل مرة واحدة
│   ├── .env                    # المتغيرات السرية — لا تُرفع على GitHub
│   ├── config/
│   │   └── db.js               # اتصال PostgreSQL عبر pg Pool
│   ├── middleware/
│   │   ├── auth.js             # التحقق من JWT Token
│   │   └── roles.js            # التحقق من الصلاحيات
│   └── routes/
│       ├── auth.js             # تسجيل دخول + إدارة المستخدمين
│       ├── clients.js          # العملاء + كشف الحساب
│       ├── invoices.js         # الفواتير
│       ├── payments.js         # المقبوضات + موافقة/رفض
│       ├── checks.js           # الشيكات
│       ├── notifications.js    # الإشعارات
│       ├── audit.js            # الإحصائيات + سجل العمليات
│       └── ai.js               # المساعد الذكي (Anthropic Claude)
├── frontend/
│   ├── index.html              # الصفحة الرئيسية (login + app)
│   ├── css/
│   │   └── style.css           # كل التنسيقات
│   └── js/
│       ├── api.js              # طبقة التواصل مع الـ backend
│       ├── auth.js             # toast + modal + formatting helpers
│       └── dashboard.js        # كل منطق الواجهة
└── database/
    └── schema.sql              # هيكل قاعدة البيانات الكامل
```

---

## قاعدة البيانات (Supabase PostgreSQL)

### الجداول

| الجدول | الوصف | أهم الأعمدة |
|--------|-------|-------------|
| `users` | المستخدمون | id, username, password_hash, role, client_id, telegram_chat_id |
| `clients` | العملاء | id, name, department, credit_limit, risk_level, phone |
| `invoices` | الفواتير | id, client_id, invoice_number, net_amount, tax_amount, total_amount, date |
| `payments` | المقبوضات | id, client_id, amount, status, submitted_by, approved_by, payment_date |
| `checks` | الشيكات | id, client_id, check_number, amount, due_date, status, created_by |
| `notifications` | الإشعارات | id, user_id, role, message, type, is_read |
| `audit_log` | سجل العمليات | id, user_id, user_name, action, entity_type, entity_id, detail |

### تنبيهات مهمة على الأعمدة
- `payments` → يستخدم `submitted_by` وليس `employee_id`
- `checks` → يستخدم `created_by` وليس `employee_id`
- `audit_log` → العمود `detail` وليس `details` أو `entity_desc`
- `invoices` → يحتوي على `net_amount` و `tax_amount` و `total_amount`
- `users` → كلمة المرور في `password_hash` وليس `password`

---

## الصلاحيات (Roles)

| الدور | الصلاحيات |
|-------|-----------|
| `admin` | كل شيء — يرى جميع البيانات، يعتمد/يرفض المدفوعات، يدير المستخدمين |
| `accountant` | إدارة العملاء، الفواتير، المقبوضات، الشيكات — لا يدير المستخدمين |
| `employee` | يسجّل مقبوضات وشيكات فقط — تنتظر موافقة المدير |
| `client` | يرى بياناته الخاصة فقط — رصيده، فواتيره، شيكاته |

---

## متغيرات البيئة (.env)

```env
DATABASE_URL=postgresql://...          # Supabase connection string
JWT_SECRET=...                         # سر تشفير JWT
PORT=3001                              # منفذ السيرفر
FRONTEND_URL=*                         # رابط الفرونت
NODE_ENV=development
TELEGRAM_TOKEN=...                     # توكن بوت تيليغرام
MANAGER_CHAT_ID=...                    # chat_id للمدير على تيليغرام
ANTHROPIC_API_KEY=sk-ant-...           # مفتاح Anthropic API
```

---

## تشغيل المشروع

```bash
# تثبيت المكتبات
cd backend
npm install

# تشغيل السيرفر (يشغّل البوت تلقائياً)
node server.js

# تشغيل مع إعادة تشغيل تلقائي عند التعديل
npm run dev
```

### ما يجب أن تراه في الكونسول:
```
🤖 بوت تيليغرام يعمل
🚀 السيرفر يعمل على http://localhost:3001
✅ تم الاتصال بـ Supabase بنجاح
```

---

## API Endpoints

### Auth
```
POST /api/auth/login              → تسجيل دخول
GET  /api/auth/users              → قائمة المستخدمين (admin)
POST /api/auth/users              → إنشاء مستخدم (admin)
DELETE /api/auth/users/:id        → حذف مستخدم (admin)
GET  /api/auth/telegram-code      → توليد كود ربط تيليغرام
```

### Clients
```
GET    /api/clients               → كل العملاء
GET    /api/clients/:id           → عميل واحد
GET    /api/clients/:id/statement → كشف حساب
POST   /api/clients               → إضافة عميل
PUT    /api/clients/:id           → تعديل عميل
DELETE /api/clients/:id           → حذف عميل (admin)
```

### Invoices
```
GET    /api/invoices              → كل الفواتير
POST   /api/invoices              → إضافة فاتورة
DELETE /api/invoices/:id          → حذف فاتورة (admin)
```

### Payments
```
GET  /api/payments                → كل المقبوضات
POST /api/payments                → تسجيل مقبوضة
POST /api/payments/:id/approve    → اعتماد (admin)
POST /api/payments/:id/reject     → رفض (admin)
```

### Checks
```
GET /api/checks                   → كل الشيكات
POST /api/checks                  → إضافة شيك
PUT /api/checks/:id/status        → تحديث الحالة (cashed/returned/cancelled)
```

### AI
```
POST /api/ai/chat                 → محادثة مع المساعد الذكي
POST /api/ai/analyze              → تحليل تلقائي للوضع المالي
GET  /api/ai/analytics            → إحصائيات ?period=daily|weekly|monthly
```

### Audit
```
GET /api/audit/stats              → إحصائيات لوحة التحكم
GET /api/audit/log                → سجل العمليات
```

---

## Frontend — كيف يعمل

### تدفق الصفحة
1. `index.html` يُحمَّل
2. `dashboard.js` يتحقق من `localStorage` للـ token
3. إذا موجود → يعرض `appLayout` ويستدعي `setupApp()`
4. إذا غير موجود → يعرض `loginPage`

### الدوال الرئيسية في dashboard.js

```javascript
setupApp()          // تهيئة التطبيق بعد تسجيل الدخول
renderSidebar()     // بناء القائمة الجانبية حسب الصلاحية
navigateTo(sec)     // التنقل بين الأقسام

// أقسام رئيسية
renderDashboard()   // لوحة التحكم والإحصائيات
renderClients()     // قائمة العملاء
renderInvoices()    // قائمة الفواتير
renderPayments()    // قائمة المقبوضات
renderChecks()      // قائمة الشيكات
renderUsers()       // إدارة المستخدمين (admin فقط)
renderAudit()       // سجل العمليات (admin فقط)
renderMyAccount()   // كشف حساب العميل

// طباعة
printInvoice(inv)         // طباعة فاتورة واحدة
printStatement(name,data) // طباعة كشف حساب
printPayments(payments)   // طباعة تقرير المقبوضات
printChecks(checks)       // طباعة تقرير الشيكات
printClients(clients)     // طباعة تقرير العملاء
printUsers(users)         // طباعة تقرير المستخدمين
printInvoicesList(invs)   // طباعة قائمة الفواتير

// AI
toggleAI()          // فتح/إغلاق لوحة المساعد
sendAIMessage()     // إرسال رسالة للمساعد
loadAIAnalysis()    // تحليل تلقائي عند فتح اللوحة
```

### Helper Functions في auth.js
```javascript
toast(msg, type)     // إشعار سريع (success/error/info)
openModal(html)      // فتح نافذة منبثقة
closeModal()         // إغلاق النافذة
fmt(n)               // تنسيق الأرقام بالفاصلة
fmtDate(d)           // تنسيق التاريخ بالعربي
isAdmin()            // هل المستخدم مدير؟
isAccountant()       // هل المستخدم محاسب أو مدير؟
isClient()           // هل المستخدم عميل؟
getUser()            // بيانات المستخدم الحالي
doLogout()           // تسجيل خروج
```

---

## بوت تيليغرام

### الأوامر المتاحة
```
/start    → ترحيب + طلب كود الربط
/balance  → رصيد العميل الحالي
/checks   → شيكات العميل المعلّقة
/help     → قائمة الأوامر
```

### تدفق ربط الحساب
1. العميل يرسل `/start`
2. البوت يطلب كود الربط
3. العميل يحصل على الكود من لوحة التحكم
4. يرسل الكود للبوت
5. البوت يربط `telegram_chat_id` بحساب العميل في `users`

### إشعارات المدير
- عند تسجيل مقبوضة → يصل إشعار فوري للمدير
- عند إرسال صورة وصل → أزرار تأكيد/رفض inline
- عند اعتماد الدفعة → إشعار للعميل

---

## المساعد الذكي (AI)

### كيف يعمل
1. يجلب بيانات النظام من DB حسب صلاحية المستخدم
2. يبني system prompt مخصص للدور
3. يرسل للـ Anthropic API مع تاريخ المحادثة
4. يعيد الرد للواجهة

### الصلاحيات في AI
- `admin` → يرى كل البيانات، تحليل كامل
- `accountant` → بيانات مالية كاملة بدون إدارة مستخدمين
- `employee` → مقبوضاته وشيكاته فقط
- `client` → رصيده وفواتيره فقط — معزول تماماً

---

## المشاكل الشائعة والحلول

### خطأ: column "X" does not exist
تحقق من أسماء الأعمدة الصحيحة:
- `employee_id` → `submitted_by` (payments) أو `created_by` (checks)
- `audit_logs` → `audit_log`
- `entity_desc` → `detail`
- `total_amount` في stats → `net_amount`

### البوت لا يعمل
```bash
# تحقق من وجود السطرين في server.js
if (process.env.TELEGRAM_TOKEN) {
  const bot = require('./bot');
  bot.launch();
}
```

### خطأ في JWT
تأكد أن `JWT_SECRET` في `.env` وأن `password_hash` وليس `password` في جدول users

### السيرفر يعمل على منفذ خاطئ
تأكد أن `PORT=3001` في `.env` وأن `API_BASE` في `frontend/js/api.js` يشير لنفس المنفذ

---

## المكتبات المستخدمة

### Backend
```json
{
  "express": "^4.19.2",
  "pg": "^8.11.5",
  "bcryptjs": "^2.4.3",
  "jsonwebtoken": "^9.0.2",
  "cors": "^2.8.5",
  "dotenv": "^16.4.5",
  "telegraf": "latest",
  "axios": "latest",
  "@anthropic-ai/sdk": "latest"
}
```

### Frontend
- IBM Plex Sans Arabic (Google Fonts)
- Vanilla JS — بدون أي framework
- CSS Variables للتنسيق

---

## النشر (Deployment)

### Backend → Railway
```toml
# railway.toml
[build]
buildCommand = "cd backend && npm install"
[deploy]
startCommand = "cd backend && node server.js"
```

### Frontend → Vercel
```json
// vercel.json
{
  "builds": [{ "src": "frontend/**", "use": "@vercel/static" }],
  "routes": [{ "src": "/(.*)", "dest": "/frontend/$1" }]
}
```

### متغيرات البيئة على Railway
أضف كل متغيرات `.env` في Railway → Variables

---

## بيانات الدخول التجريبية

| المستخدم | كلمة المرور | الصلاحية |
|----------|-------------|----------|
| admin | Abu@1234 | مدير عام |
| accountant | Abu@1234 | محاسب |
| employee1 | Abu@1234 | موظف |
| jaloudi | Abu@1234 | عميل |
| namrooti | Abu@1234 | عميل |

---

## ملاحظات للمطور

- كل الـ routes محمية بـ `verifyToken` ما عدا `/api/auth/login`
- المدير يعتمد المقبوضات مباشرة — الموظف ينتظر الموافقة
- `audit_log` يُسجَّل تلقائياً في كل عملية مهمة مع `.catch(() => {})` لعدم إيقاف العملية
- الإشعارات تُحفظ في DB وتُرسَّل عبر تيليغرام في نفس الوقت
- AI context يتغير حسب الدور — العميل معزول تماماً ولا يرى بيانات غيره