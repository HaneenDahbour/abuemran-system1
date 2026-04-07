// frontend/js/api.js
// ─────────────────────────────────────────────────────────
// هذا الملف هو الوسيط بين الـ frontend والـ backend
// كل اتصال بالسيرفر يمر من هنا — لا شيء في localStorage
//
// كيفية الاستخدام في أي ملف JS آخر:
//   const data = await api.get('/clients');
//   const result = await api.post('/auth/login', { username, password });
// ─────────────────────────────────────────────────────────

// ⚙️ رابط الـ Backend
// — في التطوير المحلي: localhost:3001
// — عند النشر على Vercel: غيّر هذا لرابط Railway الحقيقي
const RAILWAY_URL = ''; // ← ضع هنا رابط Railway بعد النشر (مثال: https://backend-production-xxxx.up.railway.app)
const BASE_URL = (RAILWAY_URL || 'http://localhost:3001') + '/api';


// ─── دوال المساعدة الداخلية ───────────────────────────────

// تجلب الـ token المحفوظ في sessionStorage (ذاكرة الجلسة)
// sessionStorage تُمسح عند إغلاق المتصفح — أكثر أماناً من localStorage
function getToken() {
  return sessionStorage.getItem('token');
}

// تبني الـ headers لكل طلب
function buildHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// دالة إرسال الطلبات الأساسية
async function request(method, path, body = null) {
  const options = {
    method,
    headers: buildHeaders()
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(`${BASE_URL}${path}`, options);
    const data = await response.json();

    // إذا انتهت الجلسة، أرسل المستخدم لصفحة الدخول
    if (response.status === 401 || response.status === 403) {
      sessionStorage.clear();
      window.location.href = 'index.html';
      return;
    }

    if (!response.ok) {
      // أعد رسالة الخطأ من السيرفر
      throw new Error(data.error || 'حدث خطأ غير معروف');
    }

    return data;
  } catch (err) {
    // إذا السيرفر غير متاح
    if (err.message === 'Failed to fetch') {
      throw new Error('لا يمكن الاتصال بالسيرفر — تأكد أن السيرفر يعمل');
    }
    throw err;
  }
}

// ─── الـ API العلني ────────────────────────────────────────
const api = {
  get:    (path)        => request('GET',    path),
  post:   (path, body)  => request('POST',   path, body),
  put:    (path, body)  => request('PUT',    path, body),
  delete: (path)        => request('DELETE', path)
};

// ─── دوال المستخدم (Auth) ─────────────────────────────────

// تحفظ بيانات المستخدم بعد تسجيل الدخول
function saveSession(token, user) {
  sessionStorage.setItem('token', token);
  sessionStorage.setItem('user', JSON.stringify(user));
}

// تجلب بيانات المستخدم المسجّل
function getCurrentUser() {
  try {
    return JSON.parse(sessionStorage.getItem('user'));
  } catch {
    return null;
  }
}

// تتحقق هل المستخدم مسجّل دخول
function isLoggedIn() {
  return !!getToken() && !!getCurrentUser();
}

// تمسح الجلسة عند الخروج
function clearSession() {
  sessionStorage.clear();
}
