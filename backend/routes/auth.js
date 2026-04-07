// routes/auth.js
// ─────────────────────────────────────────────────────────
// POST /api/auth/login  → تسجيل الدخول
// GET  /api/auth/me     → بيانات المستخدم الحالي
// ─────────────────────────────────────────────────────────

const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const pool = require('../config/db');
const verifyToken = require('../middleware/auth');

// ── POST /api/auth/login ──────────────────────────────────
// يتحقق من بيانات الدخول ويعطي JWT token
router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    // 1. تحقق أن البيانات موجودة
    if (!username || !password) {
      return res.status(400).json({ error: 'يرجى إدخال اسم المستخدم وكلمة المرور' });
    }

    // 2. ابحث عن المستخدم في قاعدة البيانات
    const result = await pool.query(
      'SELECT * FROM users WHERE username = $1 AND is_active = TRUE',
      [username.trim()]
    );

    const user = result.rows[0];
    if (!user) {
      return res.status(401).json({ error: 'اسم المستخدم أو كلمة المرور غير صحيحة' });
    }

    // 3. قارن كلمة المرور مع النسخة المشفّرة في قاعدة البيانات
    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
      return res.status(401).json({ error: 'اسم المستخدم أو كلمة المرور غير صحيحة' });
    }

    // 4. أنشئ JWT token يحتوي بيانات المستخدم (تنتهي صلاحيته بعد 7 أيام)
    const token = jwt.sign(
      {
        id:       user.id,
        username: user.username,
        fullName: user.full_name,
        role:     user.role
      },
      process.env.JWT_SECRET,
      { expiresIn: '7d' }
    );

    // 5. أرجع الـ token وبيانات المستخدم للـ frontend
    res.json({
      token,
      user: {
        id:       user.id,
        username: user.username,
        fullName: user.full_name,
        role:     user.role
      }
    });

  } catch (err) {
    console.error('خطأ في تسجيل الدخول:', err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── GET /api/auth/me ──────────────────────────────────────
// يعيد بيانات المستخدم المسجّل حالياً (من الـ token)
router.get('/me', verifyToken, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, username, full_name, role FROM users WHERE id = $1',
      [req.user.id]
    );
    if (!result.rows[0]) {
      return res.status(404).json({ error: 'المستخدم غير موجود' });
    }
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

module.exports = router;
