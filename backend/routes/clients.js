// routes/clients.js
// ─────────────────────────────────────────────────────────
// GET    /api/clients          → كل العملاء
// GET    /api/clients/:id      → عميل واحد بالتفصيل
// POST   /api/clients          → إضافة عميل جديد (admin)
// PUT    /api/clients/:id      → تعديل عميل (admin)
// ─────────────────────────────────────────────────────────

const express = require('express');
const router = express.Router();
const pool = require('../config/db');
const verifyToken = require('../middleware/auth');
const requireRole = require('../middleware/roles');

// ── GET /api/clients ──────────────────────────────────────
// المدير والموظف يرون كل العملاء
// العميل يرى بياناته فقط (يُعالج في الـ frontend)
router.get('/', verifyToken, async (req, res) => {
  try {
    // إذا كان العميل، نعيد له بياناته فقط حسب user_id
    if (req.user.role === 'client') {
      const result = await pool.query(
        'SELECT * FROM clients WHERE user_id = $1',
        [req.user.id]
      );
      return res.json(result.rows);
    }

    // للمدير والموظف: كل العملاء
    const result = await pool.query(
      'SELECT * FROM clients ORDER BY name ASC'
    );
    res.json(result.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── GET /api/clients/:id ──────────────────────────────────
// تفاصيل عميل واحد مع إجمالياته المالية
router.get('/:id', verifyToken, async (req, res) => {
  try {
    const { id } = req.params;

    const clientResult = await pool.query(
      'SELECT * FROM clients WHERE id = $1',
      [id]
    );
    if (!clientResult.rows[0]) {
      return res.status(404).json({ error: 'العميل غير موجود' });
    }

    // احسب الإجمالي والمدفوع والمتبقي
    const totalsResult = await pool.query(
      `SELECT
         COALESCE(SUM(i.net_amount), 0) AS total_invoiced,
         COALESCE((
           SELECT SUM(p.amount) FROM payments p
           WHERE p.client_id = $1 AND p.status = 'approved'
         ), 0) AS total_paid
       FROM invoices i
       WHERE i.client_id = $1 AND i.type = 'ذمة'`,
      [id]
    );

    const totals = totalsResult.rows[0];
    const remaining = parseFloat(totals.total_invoiced) - parseFloat(totals.total_paid);

    res.json({
      client: clientResult.rows[0],
      totals: {
        total_invoiced: parseFloat(totals.total_invoiced),
        total_paid:     parseFloat(totals.total_paid),
        remaining:      Math.max(0, remaining)
      }
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── POST /api/clients ─────────────────────────────────────
// إضافة عميل جديد — للمدير فقط
router.post('/', verifyToken, requireRole('admin'), async (req, res) => {
  try {
    const { name, department, credit_limit, risk_level, phone, notes } = req.body;

    if (!name) {
      return res.status(400).json({ error: 'اسم العميل مطلوب' });
    }

    const result = await pool.query(
      `INSERT INTO clients (name, department, credit_limit, risk_level, phone, notes)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING *`,
      [name, department || 'بورسلان', credit_limit || 5000, risk_level || 'low', phone, notes]
    );

    // سجّل في audit log
    await pool.query(
      `INSERT INTO audit_logs (user_id, user_name, action, entity_type, entity_id, entity_desc)
       VALUES ($1, $2, 'أضاف عميل', 'client', $3, $4)`,
      [req.user.id, req.user.fullName, result.rows[0].id, name]
    );

    res.status(201).json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

// ── PUT /api/clients/:id ──────────────────────────────────
// تعديل بيانات عميل — للمدير فقط
router.put('/:id', verifyToken, requireRole('admin'), async (req, res) => {
  try {
    const { id } = req.params;
    const { name, department, credit_limit, risk_level, phone, notes } = req.body;

    const result = await pool.query(
      `UPDATE clients
       SET name=$1, department=$2, credit_limit=$3, risk_level=$4, phone=$5, notes=$6
       WHERE id=$7
       RETURNING *`,
      [name, department, credit_limit, risk_level, phone, notes, id]
    );

    if (!result.rows[0]) {
      return res.status(404).json({ error: 'العميل غير موجود' });
    }

    res.json(result.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'خطأ في السيرفر' });
  }
});

module.exports = router;
