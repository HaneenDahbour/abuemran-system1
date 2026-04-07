// middleware/roles.js
// ─────────────────────────────────────────────────────────
// يتحقق من صلاحيات المستخدم — يستخدم بعد verifyToken
// الاستخدام: router.get('/...', verifyToken, requireRole('admin'), handler)
// ─────────────────────────────────────────────────────────

function requireRole(...roles) {
  return (req, res, next) => {
    // req.user أتى من middleware/auth.js
    if (!req.user || !roles.includes(req.user.role)) {
      return res.status(403).json({
        error: `هذه الصفحة للـ ${roles.join(' / ')} فقط — ليس لديك صلاحية`
      });
    }
    next();
  };
}

module.exports = requireRole;
