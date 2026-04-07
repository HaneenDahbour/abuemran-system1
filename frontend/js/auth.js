// frontend/js/auth.js
// ─────────────────────────────────────────────────────────
// يتعامل مع تسجيل الدخول والخروج
// يستخدم api.js للتواصل مع السيرفر
// ─────────────────────────────────────────────────────────

// ── تسجيل الدخول ──────────────────────────────────────────
async function doLogin() {
  const username = document.getElementById('lu').value.trim();
  const password = document.getElementById('lp').value.trim();
  const errDiv   = document.getElementById('lerr');
  const btn      = document.getElementById('login-btn');

  // أخفِ أي خطأ سابق
  errDiv.classList.add('hidden');

  if (!username || !password) {
    errDiv.textContent = 'يرجى إدخال اسم المستخدم وكلمة المرور';
    errDiv.classList.remove('hidden');
    return;
  }

  // غيّر نص الزر حتى لا يضغط مرتين
  if (btn) { btn.textContent = '⏳ جاري الدخول...'; btn.disabled = true; }


  try {
    // أرسل بيانات الدخول للسيرفر
    const result = await api.post('/auth/login', { username, password });

    // احفظ الـ token وبيانات المستخدم في sessionStorage
    saveSession(result.token, result.user);

    // وجّه المستخدم لصفحة لوحة التحكم
    window.location.href = 'dashboard.html';

  } catch (err) {
    console.error('Login failed:', err);
    // اعرض رسالة الخطأ من السيرفر
    errDiv.textContent = err.message || 'بيانات غير صحيحة';
    errDiv.classList.remove('hidden');

    if (btn) { btn.textContent = 'دخول →'; btn.disabled = false; }
  }
}

// ── تسجيل الخروج ──────────────────────────────────────────
function doLogout() {
  clearSession();                      // امسح الـ token
  window.location.href = 'index.html'; // ارجع لصفحة الدخول
}

// ── حماية صفحة لوحة التحكم ────────────────────────────────
// ضع هذا الكود في أي صفحة تحتاج تسجيل دخول
function requireLogin() {
  if (!isLoggedIn()) {
    window.location.href = 'index.html';
    return null;
  }
  return getCurrentUser();
}

// ── ملء بيانات الدخول التجريبية ───────────────────────────
function setRole(role, btn) {
  document.querySelectorAll('.rt').forEach(b => b.classList.remove('sel'));
  btn.classList.add('sel');

  const credentials = {
    admin:    { username: 'admin',   password: '1234' },
    employee: { username: 'emp',     password: '1234' },
    client:   { username: 'jaloudi', password: '1234' }
  };

  const cred = credentials[role];
  if (cred) {
    document.getElementById('lu').value = cred.username;
    document.getElementById('lp').value = cred.password;
  }
}

// ── تشغيل الدخول بضغطة Enter ──────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const passInput = document.getElementById('lp');
  if (passInput) {
    passInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') doLogin();
    });
  }
});
