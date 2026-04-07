// routes/checks.js
// ─────────────────────────────────────────────────────────
// GET  /api/checks             → كل الشيكات
// POST /api/checks             → إضافة شيك
// PUT  /api/checks/:id/status  → تحديث حالة الشيك (cashed / returned)
// ─────────────────────────────────────────────────────────

const express = require('express');
const router = express.Router();
const pool = require('../config/db');
const verifyToken = require('../middleware/auth');
const requireRole = require('../middleware/roles');

// ── GET /api/checks ───────────────────────────────────────
router.get('/', verifyToken, async (req, res) => {
  try {
    let query, params = [];

    if (req.user.role === 'client') {
      query = `
        SELECT ch.*, c.name AS client_name
        FROM checks ch
        JOIN clients c ON ch.client_id = c.id
        WHERE c.user_id = $1
        ORDER BY ch.due_date ASC
      `;
      params = [req.user.id];
    } else {
      query = `
        SELECT ch.*, c.name AS client_name, u.full_name AS employee_name
        FROM checks ch
        JOIN clients c ON ch.client_id = c.id
        LEFT JOIN users u ON ch.employee_id = u.id
        ORDER BY ch.due_date ASC
      `;
    }

    const result = await pool.query(query, params);
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── POST /api/checks ──────────────────────────────────────
router.post('/', verifyToken, requireRole('admin', 'employee'), async (req, res) => {
  try {
    const { client_id, check_number, bank_name, owner_name, amount, due_date, notes } = req.body;

    if (!client_id || !check_number || !amount || !due_date) {
      return res.status(400).json({ error: 'العميل، رقم الشيك، القيمة، وتاريخ الاستحقاق مطلوبة' });
    }

    const result = await pool.query(
      `INSERT INTO checks
         (client_id, employee_id, check_number, bank_name, owner_name, amount, due_date, notes)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
       RETURNING *`,
      [client_id, req.user.id, check_number, bank_name, owner_name, parseFloat(amount), due_date, notes]
    );

    const newCheck = result.rows[0];

    // إشعار للمدير
    await pool.query(
      `INSERT INTO notifications (role, message, type)
       VALUES ('admin', $1, 'check')`,
      [`🏦 ${req.user.fullName} أضاف شيك #${check_number} قيمته ${amount} د.أ يستحق ${due_date}`]
    );

    // audit log
    await pool.query(
      `INSERT INTO audit_logs (user_id, user_name, action, entity_type, entity_id, entity_desc)
       VALUES ($1,$2,'أضاف شيك','check',$3,$4)`,
      [req.user.id, req.user.fullName, newCheck.id, `شيك #${check_number} — ${amount} د.أ`]
    );

    res.status(201).json(newCheck);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── PUT /api/checks/:id/status ────────────────────────────
// المدير يحدّث حالة الشيك: cashed أو returned
router.put('/:id/status', verifyToken, requireRole('admin'), async (req, res) => {
  try {
    const { id } = req.params;
    const { status } = req.body;

    if (!['cashed', 'returned', 'cancelled'].includes(status)) {
      return res.status(400).json({ error: 'الحالة يجب أن تكون: cashed أو returned أو cancelled' });
    }

    const result = await pool.query(
      `UPDATE checks SET status=$1, updated_at=NOW()
       WHERE id=$2 RETURNING *`,
      [status, id]
    );

    if (!result.rows[0]) {
      return res.status(404).json({ error: 'الشيك غير موجود' });
    }

    const check = result.rows[0];

    // إشعار إذا كان مرتجعاً
    if (status === 'returned') {
      await pool.query(
        `INSERT INTO notifications (role, message, type)
         VALUES ('admin', $1, 'rejected')`,
        [`↩ شيك #${check.check_number} مرتجع — ${check.amount} د.أ`]
      );
    }

    // audit log
    await pool.query(
      `INSERT INTO audit_logs (user_id, user_name, action, entity_type, entity_id, entity_desc)
       VALUES ($1,$2,$3,'check',$4,$5)`,
      [
        req.user.id, req.user.fullName,
        status === 'cashed' ? 'صرف شيك' : 'سجّل شيك مرتجع',
        id, `شيك #${check.check_number}`
      ]
    );

    res.json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

module.exports = router;
