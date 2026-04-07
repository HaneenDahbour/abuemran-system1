// middleware/auth.js
// ─────────────────────────────────────────────────────────
// هذا الـ middleware يحمي أي route يحتاج تسجيل دخول
// يتحقق من الـ JWT Token في كل طلب
// ─────────────────────────────────────────────────────────

const jwt = require('jsonwebtoken');

function verifyToken(req, res, next) {
  // الـ token يُرسل في الـ header هكذا: Authorization: Bearer <token>
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1]; // نأخذ الجزء بعد "Bearer "

  if (!token) {
    return res.status(401).json({ error: 'غير مصرح — يجب تسجيل الدخول أولاً' });
  }

  jwt.verify(token, process.env.JWT_SECRET, (err, userData) => {
    if (err) {
      return res.status(403).json({ error: 'الجلسة انتهت — يرجى تسجيل الدخول مجدداً' });
    }

    // نضيف بيانات المستخدم على الـ request لكي تستخدمها الـ routes
    req.user = userData;
    next(); // تابع للـ route التالي
  });
}

module.exports = verifyToken;
