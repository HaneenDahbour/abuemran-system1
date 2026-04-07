// routes/invoices.js
// ─────────────────────────────────────────────────────────
// GET  /api/invoices        → كل الفواتير (مع فلترة)
// POST /api/invoices        → إضافة فاتورة جديدة
// ─────────────────────────────────────────────────────────

const express = require('express');
const router = express.Router();
const pool = require('../config/db');
const verifyToken = require('../middleware/auth');
const requireRole = require('../middleware/roles');

// ── GET /api/invoices ─────────────────────────────────────
router.get('/', verifyToken, async (req, res) => {
  try {
    let query;
    let params = [];

    if (req.user.role === 'client') {
      // العميل يرى فواتيره فقط
      query = `
        SELECT i.*, c.name AS client_name, u.full_name AS employee_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        LEFT JOIN users u ON i.employee_id = u.id
        WHERE c.user_id = $1
        ORDER BY i.invoice_date DESC
      `;
      params = [req.user.id];

    } else if (req.user.role === 'employee') {
      // الموظف يرى فواتيره التي أضافها
      query = `
        SELECT i.*, c.name AS client_name, u.full_name AS employee_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        LEFT JOIN users u ON i.employee_id = u.id
        WHERE i.employee_id = $1
        ORDER BY i.invoice_date DESC
      `;
      params = [req.user.id];

    } else {
      // المدير يرى كل الفواتير
      query = `
        SELECT i.*, c.name AS client_name, u.full_name AS employee_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        LEFT JOIN users u ON i.employee_id = u.id
        ORDER BY i.invoice_date DESC
      `;
    }

    const result = await pool.query(query, params);
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── POST /api/invoices ────────────────────────────────────
// المدير والموظف يضيفون فواتير
router.post('/', verifyToken, requireRole('admin', 'employee'), async (req, res) => {
  try {
    const {
      invoice_number, client_id, department,
      type, amount, discount, has_attachment, attachment_url, notes, invoice_date
    } = req.body;

    // التحقق من البيانات المطلوبة
    if (!invoice_number || !client_id || !amount || !type) {
      return res.status(400).json({ error: 'رقم الفاتورة، العميل، النوع، والقيمة مطلوبة' });
    }

    const disc = parseFloat(discount) || 0;
    const net = parseFloat(amount) - disc;

    const result = await pool.query(
      `INSERT INTO invoices
         (invoice_number, client_id, employee_id, department, type,
          amount, discount, net_amount, has_attachment, attachment_url, notes, invoice_date)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
       RETURNING *`,
      [
        invoice_number, client_id, req.user.id, department || 'بورسلان',
        type, parseFloat(amount), disc, net,
        has_attachment || false, attachment_url || null,
        notes || null, invoice_date || new Date().toISOString().split('T')[0]
      ]
    );

    const newInvoice = result.rows[0];

    // سجّل في audit log
    await pool.query(
      `INSERT INTO audit_logs (user_id, user_name, action, entity_type, entity_id, entity_desc, details)
       VALUES ($1, $2, 'أضاف فاتورة', 'invoice', $3, $4, $5)`,
      [
        req.user.id, req.user.fullName, newInvoice.id,
        `فاتورة ${invoice_number}`,
        `${net} د.أ — client_id: ${client_id}`
      ]
    );

    // أرسل إشعاراً للمدير
    await pool.query(
      `INSERT INTO notifications (role, message, type)
       VALUES ('admin', $1, 'invoice')`,
      [`📄 ${req.user.fullName} أضاف فاتورة ${invoice_number} بقيمة ${net} د.أ`]
    );

    res.status(201).json(newInvoice);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

module.exports = router;
