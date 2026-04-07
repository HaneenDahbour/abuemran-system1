// server.js
// ─────────────────────────────────────────────────────────
// نقطة البداية للسيرفر
// يُشغَّل بالأمر: node server.js
// ─────────────────────────────────────────────────────────

const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();

// ── Middleware عام ────────────────────────────────────────

// CORS: يسمح للـ frontend بالتواصل مع السيرفر
// في production اجعل origin هو رابط Vercel الخاص بك
app.use(cors({
  origin: process.env.FRONTEND_URL || '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// يحوّل body الطلبات من JSON تلقائياً
app.use(express.json());

// ── Routes ────────────────────────────────────────────────
// كل route له مسار خاص
app.use('/api/auth',          require('./routes/auth'));
app.use('/api/clients',       require('./routes/clients'));
app.use('/api/invoices',      require('./routes/invoices'));
app.use('/api/payments',      require('./routes/payments'));
app.use('/api/checks',        require('./routes/checks'));
app.use('/api/notifications', require('./routes/notifications'));
app.use('/api/audit',         require('./routes/audit'));

// ── Route تجريبي للتحقق أن السيرفر يعمل ─────────────────
app.get('/', (req, res) => {
  res.json({
    message: '✅ نظام ابو عمران — السيرفر يعمل',
    version: '1.0.0',
    time: new Date().toISOString()
  });
});

// ── معالج الأخطاء العام ───────────────────────────────────
app.use((err, req, res, next) => {
  console.error('خطأ غير متوقع:', err);
  res.status(500).json({ error: 'خطأ داخلي في السيرفر' });
});

// ── تشغيل السيرفر ─────────────────────────────────────────
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`🚀 السيرفر يعمل على http://localhost:${PORT}`);
});
