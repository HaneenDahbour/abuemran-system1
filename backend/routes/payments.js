// routes/payments.js
// ─────────────────────────────────────────────────────────
// GET  /api/payments               → كل المدفوعات
// POST /api/payments               → تسجيل دفعة جديدة (employee → pending)
// POST /api/payments/:id/approve   → موافقة المدير
// POST /api/payments/:id/reject    → رفض المدير مع سبب
// ─────────────────────────────────────────────────────────

const express = require('express');
const router = express.Router();
const pool = require('../config/db');
const verifyToken = require('../middleware/auth');
const requireRole = require('../middleware/roles');

// ── GET /api/payments ─────────────────────────────────────
router.get('/', verifyToken, async (req, res) => {
  try {
    let query, params = [];

    if (req.user.role === 'client') {
      query = `
        SELECT p.*, c.name AS client_name, e.full_name AS employee_name
        FROM payments p
        JOIN clients c ON p.client_id = c.id
        LEFT JOIN users e ON p.employee_id = e.id
        WHERE c.user_id = $1
        ORDER BY p.created_at DESC
      `;
      params = [req.user.id];

    } else if (req.user.role === 'employee') {
      query = `
        SELECT p.*, c.name AS client_name
        FROM payments p
        JOIN clients c ON p.client_id = c.id
        WHERE p.employee_id = $1
        ORDER BY p.created_at DESC
      `;
      params = [req.user.id];

    } else {
      // المدير يرى كل شيء
      query = `
        SELECT p.*, c.name AS client_name, e.full_name AS employee_name,
               a.full_name AS approver_name
        FROM payments p
        JOIN clients c ON p.client_id = c.id
        LEFT JOIN users e ON p.employee_id = e.id
        LEFT JOIN users a ON p.approved_by = a.id
        ORDER BY p.created_at DESC
      `;
    }

    const result = await pool.query(query, params);
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── POST /api/payments ────────────────────────────────────
// الموظف يُسجّل دفعة → تصير pending حتى يوافق المدير
router.post('/', verifyToken, requireRole('admin', 'employee'), async (req, res) => {
  try {
    const { client_id, amount, payment_date, notes, has_attachment, attachment_url } = req.body;

    if (!client_id || !amount) {
      return res.status(400).json({ error: 'العميل والمبلغ مطلوبان' });
    }

    // المدير يعتمد الدفعة مباشرة — الموظف ينتظر الموافقة
    const status = req.user.role === 'admin' ? 'approved' : 'pending';
    const approvedBy = req.user.role === 'admin' ? req.user.id : null;
    const approvedAt = req.user.role === 'admin' ? new Date() : null;

    const result = await pool.query(
      `INSERT INTO payments
         (client_id, employee_id, approved_by, amount, status,
          has_attachment, attachment_url, notes, payment_date, approved_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
       RETURNING *`,
      [
        client_id, req.user.id, approvedBy, parseFloat(amount), status,
        has_attachment || false, attachment_url || null,
        notes || null,
        payment_date || new Date().toISOString().split('T')[0],
        approvedAt
      ]
    );

    const newPayment = result.rows[0];

    // إشعار للمدير إذا كانت الدفعة من موظف
    if (req.user.role === 'employee') {
      await pool.query(
        `INSERT INTO notifications (role, message, type)
         VALUES ('admin', $1, 'pending')`,
        [`⏳ ${req.user.fullName} أرسل دفعة ${amount} د.أ تنتظر موافقتك`]
      );
    }

    // audit log
    await pool.query(
      `INSERT INTO audit_logs (user_id, user_name, action, entity_type, entity_id, entity_desc)
       VALUES ($1, $2, $3, 'payment', $4, $5)`,
      [
        req.user.id, req.user.fullName,
        req.user.role === 'admin' ? 'سجّل دفعة مباشرة' : 'أرسل دفعة للموافقة',
        newPayment.id, `${amount} د.أ — client_id: ${client_id}`
      ]
    );

    res.status(201).json(newPayment);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── POST /api/payments/:id/approve ───────────────────────
// المدير يوافق على الدفعة
router.post('/:id/approve', verifyToken, requireRole('admin'), async (req, res) => {
  try {
    const { id } = req.params;

    const result = await pool.query(
      `UPDATE payments
       SET status='approved', approved_by=$1, approved_at=NOW()
       WHERE id=$2 AND status='pending'
       RETURNING *`,
      [req.user.id, id]
    );

    if (!result.rows[0]) {
      return res.status(404).json({ error: 'الدفعة غير موجودة أو تمت معالجتها مسبقاً' });
    }

    const payment = result.rows[0];

    // إشعار للموظف والعميل
    await pool.query(
      `INSERT INTO notifications (user_id, message, type)
       VALUES ($1, $2, 'approved')`,
      [payment.employee_id, `✓ اعتمد المدير دفعتك بقيمة ${payment.amount} د.أ`]
    );

    // audit log
    await pool.query(
      `INSERT INTO audit_logs (user_id, user_name, action, entity_type, entity_id, entity_desc)
       VALUES ($1, $2, 'اعتمد دفعة', 'payment', $3, $4)`,
      [req.user.id, req.user.fullName, id, `${payment.amount} د.أ`]
    );

    res.json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── POST /api/payments/:id/reject ────────────────────────
// المدير يرفض الدفعة مع سبب
router.post('/:id/reject', verifyToken, requireRole('admin'), async (req, res) => {
  try {
    const { id } = req.params;
    const { reason } = req.body;

    if (!reason || !reason.trim()) {
      return res.status(400).json({ error: 'سبب الرفض مطلوب' });
    }

    const result = await pool.query(
      `UPDATE payments
       SET status='rejected', rejection_reason=$1, approved_by=$2, approved_at=NOW()
       WHERE id=$3 AND status='pending'
       RETURNING *`,
      [reason.trim(), req.user.id, id]
    );

    if (!result.rows[0]) {
      return res.status(404).json({ error: 'الدفعة غير موجودة أو تمت معالجتها مسبقاً' });
    }

    const payment = result.rows[0];

    // إشعار للموظف بسبب الرفض
    await pool.query(
      `INSERT INTO notifications (user_id, message, type)
       VALUES ($1, $2, 'rejected')`,
      [payment.employee_id, `✗ رُفضت دفعتك ${payment.amount} د.أ — السبب: ${reason}`]
    );

    // audit log
    await pool.query(
      `INSERT INTO audit_logs (user_id, user_name, action, entity_type, entity_id, details)
       VALUES ($1, $2, 'رفض دفعة', 'payment', $3, $4)`,
      [req.user.id, req.user.fullName, id, `السبب: ${reason}`]
    );

    res.json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

module.exports = router;
