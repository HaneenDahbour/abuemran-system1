// routes/notifications.js
// ─────────────────────────────────────────────────────────
// GET  /api/notifications       → إشعارات المستخدم الحالي
// PUT  /api/notifications/read  → تعليم الكل كمقروء
// ─────────────────────────────────────────────────────────

const express = require('express');
const router = express.Router();
const pool = require('../config/db');
const verifyToken = require('../middleware/auth');

// ── GET /api/notifications ────────────────────────────────
// يجلب الإشعارات الموجّهة للمستخدم أو لدوره
router.get('/', verifyToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT * FROM notifications
       WHERE user_id = $1 OR role = $2
       ORDER BY created_at DESC
       LIMIT 50`,
      [req.user.id, req.user.role]
    );
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── PUT /api/notifications/read ───────────────────────────
// تعليم كل إشعارات المستخدم كمقروءة
router.put('/read', verifyToken, async (req, res) => {
  try {
    await pool.query(
      `UPDATE notifications SET is_read = TRUE
       WHERE user_id = $1 OR role = $2`,
      [req.user.id, req.user.role]
    );
    res.json({ message: 'تم تعليم الكل مقروءاً' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

module.exports = router;
