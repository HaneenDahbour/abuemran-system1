// frontend/js/dashboard.js
// ─────────────────────────────────────────────────────────
// لوحة التحكم الرئيسية — يُحمَّل بعد تسجيل الدخول
// يجلب البيانات من السيرفر عبر api.js
// ─────────────────────────────────────────────────────────

// ── 1. تحقق من تسجيل الدخول ───────────────────────────────
// إذا لم يكن المستخدم مسجّلاً، يُعاد توجيهه لصفحة الدخول
const cUser = requireLogin();
if (!cUser) throw new Error('Redirecting to login');

// ── 2. عرض معلومات المستخدم في الـ topbar ──────────────────
function setupTop() {
  const roleNames = { admin: 'مدير', employee: 'موظف', client: 'عميل' };
  const roleColors = {
    admin:    { bg: '#eff6ff', color: '#1e40af' },
    employee: { bg: '#f0fdf4', color: '#065f46' },
    client:   { bg: '#fffbeb', color: '#78350f' }
  };

  document.getElementById('topName').textContent = cUser.fullName || cUser.full_name;
  document.getElementById('topRole').textContent = roleNames[cUser.role] || cUser.role;

  const av = document.getElementById('topAv');
  const c = roleColors[cUser.role] || {};
  av.style.background = c.bg;
  av.style.color = c.color;
  av.textContent = (cUser.fullName || cUser.full_name || '?').charAt(0);
}

// ── 3. جلب وعرض لوحة التحكم ───────────────────────────────
async function renderDashboard() {
  const content = document.getElementById('mainContent');
  content.innerHTML = '<div style="text-align:center;padding:3rem;color:#9e9b96">⏳ جاري تحميل البيانات...</div>';

  try {
    // جلب البيانات بالتوازي (أسرع من الطلبات المتسلسلة)
    const [clients, invoices, payments, checks, notifications] = await Promise.all([
      api.get('/clients'),
      api.get('/invoices'),
      api.get('/payments'),
      api.get('/checks'),
      api.get('/notifications')
    ]);

    // حدّث رمز الإشعارات
    const unread = notifications.filter(n => !n.is_read).length;
    const nc = document.getElementById('nc');
    if (unread > 0) {
      nc.textContent = unread;
      nc.classList.remove('hidden');
    }

    // اعرض حسب الدور
    if (cUser.role === 'admin') {
      renderAdminDash({ clients, invoices, payments, checks });
    } else if (cUser.role === 'employee') {
      renderEmployeeDash({ invoices, payments });
    } else {
      renderClientDash({ invoices, payments, checks });
    }

  } catch (err) {
    content.innerHTML = `
      <div style="background:#fef2f2;border:1px solid rgba(200,30,30,.2);border-radius:10px;padding:1rem;color:#c81e1e">
        ❌ خطأ في تحميل البيانات: ${err.message}
      </div>`;
  }
}

// ── لوحة المدير ───────────────────────────────────────────
function renderAdminDash({ clients, invoices, payments, checks }) {
  const totalSales = invoices.reduce((s, i) => s + parseFloat(i.net_amount || 0), 0);
  const totalDebt  = invoices.filter(i => i.type === 'ذمة').reduce((s, i) => s + parseFloat(i.net_amount || 0), 0);
  const totalPaid  = payments.filter(p => p.status === 'approved').reduce((s, p) => s + parseFloat(p.amount || 0), 0);
  const pending    = payments.filter(p => p.status === 'pending');
  const today      = new Date().toISOString().split('T')[0];
  const dueToday   = checks.filter(c => c.status === 'pending' && c.due_date?.slice(0,10) === today);

  const fmt = n => parseFloat(n || 0).toLocaleString('ar-JO', { minimumFractionDigits: 2 });

  document.getElementById('mainContent').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:1rem">
      ${metric('إجمالي المبيعات', fmt(totalSales), 'د.أ', '')}
      ${metric('المتبقي من الذمم', fmt(totalDebt - totalPaid), '', '#c81e1e')}
      ${metric('موافقات معلقة', pending.length, '', pending.length ? '#92400e' : '#057a55')}
      ${metric('شيكات اليوم', dueToday.length, '', dueToday.length ? '#c81e1e' : '#057a55')}
    </div>

    ${pending.length ? `
    <div style="background:#fffbeb;border:1px solid rgba(146,64,14,.2);border-radius:10px;padding:12px;margin-bottom:1rem">
      ⏳ يوجد <strong>${pending.length}</strong> طلب دفعة بانتظار موافقتك
      <button onclick="showPendingApprovals()" style="margin-right:auto;background:var(--am,#92400e);color:#fff;border:none;padding:5px 12px;border-radius:8px;cursor:pointer;font-family:inherit;font-size:12px;margin-right:8px">عرض الطلبات</button>
    </div>` : ''}

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div style="background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:14px;padding:1.25rem">
        <div style="font-size:13px;font-weight:700;margin-bottom:12px">📄 آخر الفواتير</div>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead><tr>
            <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">رقم</th>
            <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">العميل</th>
            <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">الصافي</th>
          </tr></thead>
          <tbody>
            ${invoices.slice(0, 6).map(i => `
            <tr>
              <td style="padding:6px 8px">${i.invoice_number}</td>
              <td style="padding:6px 8px">${i.client_name || '—'}</td>
              <td style="padding:6px 8px;font-weight:700;color:#1a56db">${fmt(i.net_amount)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div style="background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:14px;padding:1.25rem">
        <div style="font-size:13px;font-weight:700;margin-bottom:12px">👥 العملاء (${clients.length})</div>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead><tr>
            <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">العميل</th>
            <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">القسم</th>
            <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">الحد</th>
          </tr></thead>
          <tbody>
            ${clients.slice(0, 6).map(c => `
            <tr>
              <td style="padding:6px 8px;font-weight:600">${c.name}</td>
              <td style="padding:6px 8px">${c.department}</td>
              <td style="padding:6px 8px">${fmt(c.credit_limit)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
}

// ── لوحة الموظف ───────────────────────────────────────────
function renderEmployeeDash({ invoices, payments }) {
  const fmt = n => parseFloat(n || 0).toLocaleString('ar-JO', { minimumFractionDigits: 2 });
  const today = new Date().toISOString().split('T')[0];
  const myPending = payments.filter(p => p.status === 'pending');
  const myRejected = payments.filter(p => p.status === 'rejected');
  const todayInvs = invoices.filter(i => i.invoice_date?.slice(0,10) === today);

  document.getElementById('mainContent').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:1rem">
      ${metric('فواتير اليوم', todayInvs.length, '', '')}
      ${metric('إجمالي فواتيري', invoices.length, '', '')}
      ${metric('معلقة / مرفوضة', `${myPending.length} / ${myRejected.length}`, '', myPending.length || myRejected.length ? '#92400e' : '#057a55')}
    </div>
    <div style="background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:14px;padding:1.25rem">
      <div style="font-size:13px;font-weight:700;margin-bottom:12px">آخر فواتيري</div>
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr>
          <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">رقم</th>
          <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">العميل</th>
          <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">الصافي</th>
          <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">التاريخ</th>
        </tr></thead>
        <tbody>
          ${invoices.slice(0,8).map(i => `
          <tr>
            <td style="padding:6px 8px">${i.invoice_number}</td>
            <td style="padding:6px 8px">${i.client_name || '—'}</td>
            <td style="padding:6px 8px;font-weight:700;color:#1a56db">${fmt(i.net_amount)}</td>
            <td style="padding:6px 8px;color:#6a6862">${i.invoice_date?.slice(0,10) || '—'}</td>
          </tr>`).join('') || '<tr><td colspan="4" style="text-align:center;padding:1rem;color:#9e9b96">لا توجد فواتير بعد</td></tr>'}
        </tbody>
      </table>
    </div>`;
}

// ── لوحة العميل ───────────────────────────────────────────
function renderClientDash({ invoices, payments, checks }) {
  const fmt = n => parseFloat(n || 0).toLocaleString('ar-JO', { minimumFractionDigits: 2 });
  const totalInv = invoices.filter(i => i.type === 'ذمة').reduce((s, i) => s + parseFloat(i.net_amount || 0), 0);
  const totalPaid = payments.filter(p => p.status === 'approved').reduce((s, p) => s + parseFloat(p.amount || 0), 0);
  const remaining = Math.max(0, totalInv - totalPaid);

  document.getElementById('mainContent').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:1rem">
      ${metric('إجمالي فواتيري', fmt(totalInv), 'د.أ', '')}
      ${metric('المدفوع', fmt(totalPaid), 'د.أ', '#057a55')}
      ${metric('المتبقي عليّ', fmt(remaining), 'د.أ', remaining > 0 ? '#c81e1e' : '#057a55')}
    </div>
    <div style="background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:14px;padding:1.25rem">
      <div style="font-size:13px;font-weight:700;margin-bottom:12px">فواتيري</div>
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr>
          <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">رقم</th>
          <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">القسم</th>
          <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">الصافي</th>
          <th style="text-align:right;padding:6px 8px;font-size:11px;color:#6a6862;border-bottom:1px solid rgba(0,0,0,.08)">التاريخ</th>
        </tr></thead>
        <tbody>
          ${invoices.slice(0,10).map(i => `
          <tr>
            <td style="padding:6px 8px">${i.invoice_number}</td>
            <td style="padding:6px 8px">${i.department}</td>
            <td style="padding:6px 8px;font-weight:700">${fmt(i.net_amount)}</td>
            <td style="padding:6px 8px;color:#6a6862">${i.invoice_date?.slice(0,10) || '—'}</td>
          </tr>`).join('') || '<tr><td colspan="4" style="text-align:center;padding:1rem;color:#9e9b96">لا توجد فواتير</td></tr>'}
        </tbody>
      </table>
    </div>`;
}

// ── موافقة الدفعات (للمدير) ───────────────────────────────
async function showPendingApprovals() {
  try {
    const payments = await api.get('/payments');
    const pending = payments.filter(p => p.status === 'pending');
    // سنطورها لاحقاً — في الوقت الحالي تعرض تنبيهاً
    alert(`يوجد ${pending.length} دفعة معلقة. سيتم إضافة واجهة موافقة كاملة في التحديث القادم.`);
  } catch (err) {
    alert('خطأ: ' + err.message);
  }
}

// ── دالة مساعدة لعرض الأرقام ──────────────────────────────
function metric(label, value, unit, color) {
  return `
    <div style="background:#faf9f7;border:1px solid rgba(0,0,0,.08);border-radius:10px;padding:.875rem">
      <div style="font-size:11px;font-weight:600;color:#6a6862;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">${label}</div>
      <div style="font-size:22px;font-weight:700;color:${color || '#181715'}">${value}</div>
      ${unit ? `<div style="font-size:11px;color:#9e9b96;margin-top:2px">${unit}</div>` : ''}
    </div>`;
}

// ── Bootstrap ──────────────────────────────────────────────
setupTop();
renderDashboard();
