// routes/audit.js
// ─────────────────────────────────────────────────────────
// GET /api/audit  → سجل التدقيق الكامل (للمدير فقط)
// ─────────────────────────────────────────────────────────

const express = require('express');
const router = express.Router();
const pool = require('../config/db');
const verifyToken = require('../middleware/auth');
const requireRole = require('../middleware/roles');

// ── GET /api/audit ────────────────────────────────────────
// يعرض آخر 100 عملية في النظام — للمدير فقط
router.get('/', verifyToken, requireRole('admin'), async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT * FROM audit_logs
       ORDER BY created_at DESC
       LIMIT 100`
    );
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

module.exports = router;
