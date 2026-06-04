// js/dashboard.js — fixed full version

/* ═══════════════════════════════════════════════════
   Safe fallbacks + helpers
═══════════════════════════════════════════════════ */

function safeJsonParse(value, fallback = null) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

if (typeof getUser !== 'function') {
  function getUser() {
    return safeJsonParse(localStorage.getItem('user'), null);
  }
}

if (typeof roleLabel !== 'function') {
  function roleLabel(role) {
    const map = {
      admin: 'مدير عام',
      accountant: 'محاسب',
      employee: 'موظف',
      client: 'عميل',
      recipient: 'زبون',
    };
    return map[role] || role || '—';

  }
}

if (typeof isAdmin !== 'function') {
  function isAdmin() {
    return getUser()?.role === 'admin';
  }
}

if (typeof isAccountant !== 'function') {
  function isAccountant() {
    const role = getUser()?.role;
    return role === 'admin' || role === 'accountant';
  }
}

if (typeof isClient !== 'function') {
  function isClient() {
    return getUser()?.role === 'client';
  }
}

if (typeof fmt !== 'function') {
  function fmt(value) {
    const num = Number(value || 0);
    return num.toLocaleString('en-US', {
      minimumFractionDigits: 3,
      maximumFractionDigits: 3
    });
  }
}

if (typeof fmtDate !== 'function') {
  function fmtDate(value) {
    if (!value) return '—';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleDateString('ar-JO', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }
}

if (typeof toast !== 'function') {
  function toast(message, type = 'info') {
    const wrap = document.getElementById('toast-wrap');
    if (!wrap) {
      alert(message);
      return;
    }

    const colors = {
      success: '#0a7650',
      error: '#b42318',
      info: '#1a4fd6',
      warning: '#b54708'
    };

    const el = document.createElement('div');
    el.style.cssText = `
      background:#fff;
      color:#1a1815;
      border-right:4px solid ${colors[type] || colors.info};
      box-shadow:0 10px 28px rgba(0,0,0,.14);
      border-radius:12px;
      padding:12px 14px;
      margin-top:10px;
      min-width:220px;
      max-width:360px;
      font-size:13px;
      line-height:1.5;
      transition:.2s;
    `;
    el.textContent = message;
    wrap.appendChild(el);

    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(-4px)';
      setTimeout(() => el.remove(), 200);
    }, 2800);
  }
}

if (typeof openModal !== 'function') {
  function openModal(html, width = '560px') {
    closeModal();

    const overlay = document.createElement('div');
    overlay.id = 'global-modal-overlay';
    overlay.style.cssText = `
      position:fixed;
      inset:0;
      background:rgba(0,0,0,.45);
      z-index:99999;
      display:flex;
      align-items:center;
      justify-content:center;
      padding:20px;
    `;

    const modal = document.createElement('div');
    modal.id = 'global-modal';
    modal.style.cssText = `
      width:min(${width}, 96vw);
      max-height:92vh;
      overflow:auto;
      background:#fff;
      border-radius:18px;
      box-shadow:0 20px 60px rgba(0,0,0,.25);
      padding:18px;
      direction:rtl;
    `;
    modal.innerHTML = html;

    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal();
    });

    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';
  }
}
function isRecipient() {
  return getUser()?.role === 'recipient';
}
if (typeof closeModal !== 'function') {
  function closeModal() {
    const overlay = document.getElementById('global-modal-overlay');
    if (overlay) overlay.remove();
    document.body.style.overflow = '';
  }
}

if (typeof doLogout !== 'function') {
  function doLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    location.reload();
  }
}

function escHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function jsString(value) {
  return `'${String(value ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/\r/g, '\\r')
    .replace(/\n/g, '\\n')
    .replace(/</g, '\\x3C')
    .replace(/>/g, '\\x3E')
    .replace(/&/g, '\\x26')}'`;
}

function encodePayload(data) {
  return encodeURIComponent(JSON.stringify(data ?? null));
}

function decodePayload(encoded) {
  try {
    return JSON.parse(decodeURIComponent(encoded));
  } catch {
    return null;
  }
}

function formatAiTextSafe(text) {
  return escHtml(String(text || ''))
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

function emptyRow(msg, cols) {
  return `<tr><td colspan="${cols}" style="text-align:center; padding:40px; color:var(--tx3)">${escHtml(msg)}</td></tr>`;
}

function filterTable(tbodyId, val) {
  document.querySelectorAll(`#${tbodyId} tr`).forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes(String(val || '').toLowerCase()) ? '' : 'none';
  });
}

function filterClients(val) {
  const rows = document.querySelectorAll('#clients-tbody tr');
  rows.forEach(r => {
    r.style.display = r.textContent.includes(val) ? '' : 'none';
  });
}

function payMethodBadge(m) {
  const map = {
    cash: '<span class="badge badge-green">نقداً</span>',
    credit: '<span class="badge badge-red">ذمم</span>',
    partial: '<span class="badge badge-amber">جزئي</span>',
    check: '<span class="badge badge-blue">شيك</span>',
    transfer: '<span class="badge badge-amber">حوالة</span>'
  };
  return map[m] || `<span class="badge badge-gray">${escHtml(m || '—')}</span>`;
}

function invoiceStatusBadge(status) {
  const map = {
    // workflow statuses
    pending: '<span class="badge badge-amber">⏳ بانتظار الاعتماد</span>',
    rejected: '<span class="badge badge-red">✗ مرفوضة</span>',
    approved: '<span class="badge badge-green">✅ معتمدة</span>',
    // payment statuses (shown inside approved invoices)
    paid: '<span class="badge badge-green">✅ مدفوعة</span>',
    partial: '<span class="badge badge-amber">🔶 دفع جزئي</span>',
    debt: '<span class="badge badge-red">📋 ذمم</span>',
  };
  return map[status] || `<span class="badge badge-gray">${escHtml(status || '—')}</span>`;
}

function purchaseStatusBadge(s) {
  const map = {
    pending: '<span class="badge badge-amber">⏳ معلّقة</span>',
    received: '<span class="badge badge-green">✅ مستلمة</span>',
    cancelled: '<span class="badge badge-gray">❌ ملغاة</span>',
  };
  return map[s] || `<span class="badge badge-gray">${escHtml(s || '—')}</span>`;
}

function checkStatusBadge(s) {
  const map = {
    pending: '<span class="badge badge-amber">⏳ معلّق</span>',
    cashed: '<span class="badge badge-green">✅ محصَّل</span>',
    returned: '<span class="badge badge-red">↩️ مرتجع</span>',
    cancelled: '<span class="badge badge-gray">❌ ملغى</span>',
  };
  return map[s] || `<span class="badge badge-gray">${escHtml(s || '—')}</span>`;
}

function riskLabel(level) {
  const map = {
    low: '<span class="badge badge-green">منخفض</span>',
    medium: '<span class="badge badge-amber">متوسط</span>',
    high: '<span class="badge badge-red">عالٍ</span>'
  };
  return map[level] || `<span class="badge badge-gray">${escHtml(level || '—')}</span>`;
}

function roleBadge(r) {
  const map = {
    admin: '<span class="badge badge-red">مدير عام</span>',
    accountant: '<span class="badge badge-blue">محاسب</span>',
    employee: '<span class="badge badge-gray">موظف</span>',
    client: '<span class="badge badge-green">عميل</span>',
    recipient: '<span class="badge badge-amber">زبون</span>',
  };
  return map[r] || `<span class="badge badge-gray">${escHtml(r || '—')}</span>`;
}

function printStatementFromEncoded(name, encoded) {
  const data = decodePayload(encoded);
  if (!data) {
    toast('تعذر تجهيز بيانات الطباعة', 'error');
    return;
  }
  printStatement(name, data);
}

function printMyStatementFromEncoded(name, encoded) {
  const data = decodePayload(encoded);
  if (!data) {
    toast('تعذر تجهيز بيانات الطباعة', 'error');
    return;
  }
  printMyStatement(name, data);
}

function printInvoiceFromEncoded(encoded) {
  const data = decodePayload(encoded);
  if (!data) {
    toast('تعذر تجهيز بيانات الفاتورة', 'error');
    return;
  }
  printInvoice(data);
}
function openInvoiceModalFromEncoded(encoded) {
  const data = decodePayload(encoded);
  if (!data) {
    toast('تعذر تحميل بيانات الفاتورة للتعديل', 'error');
    return;
  }
  openInvoiceModal(data);
}
function printInvoicesListFromEncoded(encoded) {
  const data = decodePayload(encoded);
  if (!data) {
    toast('تعذر تجهيز بيانات الطباعة', 'error');
    return;
  }
  printInvoicesList(data);
}

function printPaymentsFromEncoded(encoded) {
  const data = decodePayload(encoded);
  if (!data) {
    toast('تعذر تجهيز بيانات الطباعة', 'error');
    return;
  }
  printPayments(data);
}

function printChecksFromEncoded(encoded) {
  const data = decodePayload(encoded);
  if (!data) {
    toast('تعذر تجهيز بيانات الطباعة', 'error');
    return;
  }
  printChecks(data);
}

function printUsersFromEncoded(encoded) {
  const data = decodePayload(encoded);
  if (!data) {
    toast('تعذر تجهيز بيانات الطباعة', 'error');
    return;
  }
  printUsers(data);
}

/* ───── Init ───── */
document.addEventListener('DOMContentLoaded', function init() {
  const token = localStorage.getItem('token');
  const loginPage = document.getElementById('loginPage');
  const appLayout = document.getElementById('appLayout');

  if (!loginPage || !appLayout) return;

  if (!token || !localStorage.getItem('user')) {
    loginPage.classList.remove('hidden');
    appLayout.classList.add('hidden');
    setupLoginPage();
  } else {
    loginPage.classList.add('hidden');
    appLayout.classList.remove('hidden');
    setupApp();
  }
});

function setupLoginPage() {
  const loginBtn = document.getElementById('login-btn');
  const userInput = document.getElementById('lu');
  const passInput = document.getElementById('lp');

  const submitLogin = () => {
    const u = userInput?.value?.trim() || '';
    const p = passInput?.value?.trim() || '';
    if (!u || !p) {
      toast('الرجاء إدخال بيانات الدخول', 'error');
      return;
    }
    doLogin(u, p);
  };

  if (loginBtn && !loginBtn.dataset.bound) {
    loginBtn.dataset.bound = '1';
    loginBtn.addEventListener('click', submitLogin);
  }

  [userInput, passInput].forEach(el => {
    if (el && !el.dataset.boundEnter) {
      el.dataset.boundEnter = '1';
      el.addEventListener('keydown', e => {
        if (e.key === 'Enter') submitLogin();
      });
    }
  });
}

/* ───── App Setup ───── */
let currentSection = null;
function navItem(section, icon, label) {
  const active = currentSection === section ? 'active' : '';

  return `
    <button
      type="button"
      class="nav-item nav-link ${active}"
      data-section="${escHtml(section)}"
      onclick="navigateTo('${section}')"
    >
      <span class="nav-icon">${icon}</span>
      <span>${escHtml(label)}</span>
    </button>
  `;
}

function setActiveNav(section) {
  document.querySelectorAll('[data-section]').forEach(el => {
    el.classList.toggle('active', el.dataset.section === section);
  });
}

async function navigateTo(section) {
  currentSection = section;
  setActiveNav(section);

  const container = document.getElementById('mainContent');
  if (!container) {
    console.error('mainContent not found');
    return;
  }

  container.innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      <p>جاري التحميل...</p>
    </div>
  `;

  const renderers = {
    dashboard: renderDashboard,
    cashbox: renderCashbox,
    employees: renderEmployees,
    expenses: renderExpenses,
    clients: renderClients,
    invoices: renderInvoices,
    recipients: renderRecipients,
    payments: renderPayments,
    checks: renderChecks,
    purchases: renderPurchases,
    warehouse: renderWarehouse,
    users: renderUsers,
    audit: renderAudit,
    analytics: renderAnalytics,
    my_account: renderMyAccount,
    recipient_account: renderRecipientAccount,
  };

  const renderer = renderers[section];

  if (!renderer) {
    container.innerHTML = `
      <div class="card">
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <p>القسم غير موجود: ${escHtml(section)}</p>
        </div>
      </div>
    `;
    return;
  }

  try {
    await renderer(container);
    setActiveNav(section);
  } catch (e) {
    console.error(e);
    container.innerHTML = `
      <div class="alert alert-danger">
        حدث خطأ أثناء تحميل الصفحة: ${escHtml(e.message || e)}
      </div>
    `;
  }
}

function setupApp() {
  const user = getUser();
  if (!user) {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    location.reload();
    return;
  }

  const fullName = user.full_name || user.name || user.username || 'مستخدم';

  const topName = document.getElementById('topName');
  const topRole = document.getElementById('topRole');
  const topAv = document.getElementById('topAv');

  if (topName) topName.textContent = fullName;
  if (topRole) topRole.textContent = roleLabel(user.role);
  if (topAv) topAv.textContent = fullName.charAt(0);

  const aiWidget = document.getElementById('ai-widget');
  if (aiWidget) {
    aiWidget.style.display = 'flex';
    if (typeof initAIChips === 'function') initAIChips();
  }

  renderSidebar();
  navigateTo('dashboard');

  const aiIn = document.getElementById('ai-input');
  if (aiIn && !aiIn.dataset.bound) {
    aiIn.dataset.bound = '1';
    aiIn.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey && typeof sendAIMessage === 'function') {
        e.preventDefault();
        sendAIMessage();
      }
    });
  }

  if (typeof showGlobalSearch === 'function') {
    showGlobalSearch();
  }
}

/* ───── Sidebar ───── */
function renderSidebar() {
  const sb = document.getElementById('sidebarNav');
  if (!sb) return;

  let html = '';

  html += navItem('dashboard', '📊', 'لوحة التحكم');

  if (isAccountant()) {
    html += '<div class="nav-section-title">إدارة الأعمال</div>';
    html += navItem('cashbox', '💼', 'صندوق خالد');
    html += navItem('employees', '👷', 'الموظفون');
    html += navItem('expenses', '📋', 'المصاريف والرواتب');
    html += navItem('invoices', '🧾', 'الفواتير');
    html += navItem('recipients', '🧑‍🤝‍🧑', 'زبائن الفواتير');
    html += navItem('payments', '💰', 'المقبوضات');
    html += navItem('checks', '🏦', 'الشيكات');
    html += navItem('purchases', '🛒', 'المشتريات');
  }

  if (canManageWarehouse()) {
    html += '<div class="nav-section-title">المستودع</div>';
    html += navItem('warehouse', '🏭', 'المستودع');
  }

  if (isAdmin()) {
    html += '<div class="nav-section-title">الإدارة</div>';
    html += navItem('users', '🔐', 'إدارة المستخدمين');
    html += navItem('audit', '📋', 'سجل العمليات');
    html += navItem('analytics', '📊', 'لوحة التحليلات');
  }

  if (isClient()) {
    html += '<div class="nav-section-title">حسابي</div>';
    html += navItem('my_account', '📄', 'كشف حسابي');
  }
  if (isRecipient()) {
    html += '<div class="nav-section-title">حسابي</div>';
    html += navItem('recipient_account', '📄', 'كشف حسابي');
  }

  sb.innerHTML = html;
}
async function renderRecipientAccount(container) {
  const user = getUser() || {};
  const recipientName = user.recipient_name || user.full_name;

  if (!recipientName) {
    container.innerHTML = `
      <div class="page-header">
        <div class="page-title">كشف حسابي</div>
      </div>
      <div class="card">
        <div class="empty-state">
          <div class="empty-icon">🔗</div>
          <p>لم يتم ربط حسابك باسم زبون بعد.</p>
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      <p>جاري تحميل كشف حسابك...</p>
    </div>
  `;

  try {
    const data = await API.getRecipientStatement(recipientName);
    const txs = data.transactions || [];
    const balance = Number(data.balance || 0);

    container.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">كشف حسابي</div>
          <div class="page-sub">${escHtml(recipientName)}</div>
        </div>
      </div>

      <div class="metrics-grid">
        <div class="metric-card blue">
          <div class="metric-label">إجمالي الفواتير</div>
          <div class="metric-value">${fmt(data.total_invoiced || 0)}</div>
          <div class="metric-sub">دينار أردني</div>
        </div>

        <div class="metric-card green">
          <div class="metric-label">إجمالي المدفوع</div>
          <div class="metric-value">${fmt(data.total_paid || 0)}</div>
          <div class="metric-sub">دينار أردني</div>
        </div>

        <div class="metric-card ${balance > 0 ? 'red' : 'green'}">
          <div class="metric-label">الرصيد المتبقي</div>
          <div class="metric-value">${fmt(Math.abs(balance))}</div>
          <div class="metric-sub">دينار أردني</div>
        </div>
      </div>

      <div class="card" style="padding:0; overflow:hidden">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>التاريخ</th>
                <th>البيان</th>
                <th>مدين</th>
                <th>دائن</th>
                <th>الرصيد</th>
              </tr>
            </thead>
            <tbody>
              ${txs.length ? txs.map(t => `
                <tr>
                  <td>${fmtDate(t.date)}</td>
                  <td>${t.type === 'invoice' ? `فاتورة #${escHtml(t.invoice_number || t.id)}` : escHtml(t.notes || 'دفعة')}</td>
                  <td style="color:var(--rd);font-weight:700">${t.type === 'invoice' ? fmt(t.amount) : '—'}</td>
                  <td style="color:var(--gr);font-weight:700">${t.type === 'payment' ? fmt(t.amount) : '—'}</td>
                  <td style="font-weight:800">${fmt(t.running_balance || 0)} د.أ</td>
                </tr>
              `).join('') : emptyRow('لا توجد حركات', 5)}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">${escHtml(e.message)}</div>`;
  }
}
/* ═══════════════════════════════════════════════════
   DASHBOARD
═══════════════════════════════════════════════════ */
async function renderDashboard(container) {
  let stats = {};

  try {
    stats = await Promise.race([
      API.getStats(),
      new Promise(resolve => setTimeout(() => resolve({}), 3000))
    ]);
  } catch (e) {
    console.warn('Stats failed:', e);
    stats = {};
  }

  const user = getUser() || {};

  if (isClient()) {
    return renderMyAccount(container);
  }

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">لوحة التحكم</div>
        <div class="page-sub">مرحباً ${escHtml(user.full_name || user.name || user.username || 'مستخدم')} — ${new Date().toLocaleDateString('ar-JO', { weekday: 'long', day: 'numeric', month: 'long' })}</div>
      </div>
    </div>

    <div class="metrics-grid">
      <div class="metric-card blue">
        <div class="metric-icon">📈</div>
        <div class="metric-label">إجمالي المبيعات</div>
        <div class="metric-value">${fmt(stats.total_sales)}</div>
        <div class="metric-sub">دينار أردني</div>
      </div>
      <div class="metric-card red">
        <div class="metric-icon">💳</div>
        <div class="metric-label">الديون القائمة</div>
        <div class="metric-value">${fmt(stats.total_debts)}</div>
        <div class="metric-sub">دينار أردني</div>
      </div>
      <div class="metric-card green">
        <div class="metric-icon">💰</div>
        <div class="metric-label">المقبوضات</div>
        <div class="metric-value">${fmt(stats.total_payments)}</div>
        <div class="metric-sub">دينار أردني</div>
      </div>
      <div class="metric-card amber">
        <div class="metric-icon">🏦</div>
        <div class="metric-label">شيكات اليوم</div>
        <div class="metric-value">${stats.today_checks || 0}</div>
        <div class="metric-sub">شيك مستحق</div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px">
      <div class="card" id="dash-alerts">
        <div class="card-title">🔔 تنبيهات النظام</div>
        <div id="alerts-content"><div class="loading"><div class="spinner"></div></div></div>
      </div>
      <div class="card">
        <div class="card-title">⚡ إجراءات سريعة</div>
        <div style="display:flex; flex-direction:column; gap:10px; margin-top:4px">
          ${isAccountant() ? `
          <button class="btn btn-primary btn-full" onclick="navigateTo('invoices'); setTimeout(openInvoiceModal,200)">➕ فاتورة جديدة</button>
          <button class="btn btn-success btn-full" onclick="navigateTo('payments'); setTimeout(openPaymentModal,200)">💰 تسجيل مقبوضة</button>
          <button class="btn btn-ghost btn-full" onclick="navigateTo('checks'); setTimeout(openCheckModal,200)">🏦 إضافة شيك</button>
          ` : ''}
        </div>
      </div>
    </div>
  `;

  loadAlertsAsync();
}
function canManageWarehouse() {
  const role = getUser()?.role;
  return role === 'admin' || role === 'accountant' || role === 'employee';
}

function canEditWarehouseStructure() {
  const role = getUser()?.role;
  return role === 'admin' || role === 'accountant';
}
async function loadAlertsAsync() {
  const el = document.getElementById('alerts-content');
  if (!el) return;

  try {
    const [checks, clients] = await Promise.all([
      API.getChecks(),
      API.getClients(),
    ]);
    // Pending invoices — admin only
    let pendingInvoices = 0;
    if (isAdmin()) {
      try {
        const invs = await API.getInvoices();
        pendingInvoices = (invs || []).filter(i => (i.status || 'approved') === 'pending').length;
      } catch { }
    }

    const today = new Date().toISOString().split('T')[0];
    const todayChecks = (checks || []).filter(c => c.due_date?.split('T')[0] === today && c.status === 'pending');
    const upcoming = (checks || []).filter(c => {
      const d = c.due_date?.split('T')[0];
      return d > today && d <= new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0] && c.status === 'pending';
    });
    const overLimit = (clients || []).filter(c =>
      parseFloat(c.credit_limit || 0) > 0 && parseFloat(c.balance || 0) > parseFloat(c.credit_limit || 0)
    );

    let html = '';
    if (todayChecks.length) {
      todayChecks.forEach(c => {
        html += `<div class="alert alert-danger">🏦 شيك مستحق اليوم — ${escHtml(c.client_name || 'عميل')} — ${fmt(c.amount)} د.أ</div>`;
      });
    }
    if (pendingInvoices > 0) {
      html = `<div class="alert alert-warning" style="cursor:pointer" onclick="navigateTo('invoices')">
        📋 <strong>${pendingInvoices} فاتورة</strong> بانتظار موافقتك — انقر للمراجعة
      </div>` + html;
    }
    if (upcoming.length) {
      html += `<div class="alert alert-warning">⚠️ ${upcoming.length} شيك مستحق خلال الأسبوع القادم</div>`;
    }
    if (overLimit.length) {
      html += `<div class="alert alert-danger">💳 ${overLimit.length} عميل تجاوز حد الائتمان — <a href="#" onclick="navigateTo('clients')" style="color:inherit;text-decoration:underline">عرض العملاء</a></div>`;
    }
    if (!html) html = `<div class="alert alert-success">✅ لا توجد تنبيهات عاجلة اليوم</div>`;
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = `<p style="color:var(--tx3); font-size:12px">تعذّر تحميل التنبيهات</p>`;
  }
}
/* ═══════════════════════════════════════════════════
   CLIENTS
═══════════════════════════════════════════════════ */
async function renderClients(container) {
  let clients = [];
  try { clients = await API.getClients() || []; } catch (e) { clients = []; }

  window._clientsCache = clients;

  container.innerHTML = `
  <div class="page-header">
    <div>
      <div class="page-title">العملاء</div>
      <div class="page-sub">${clients.length} عميل مسجّل</div>
    </div>
    <div style="display:flex; gap:10px">
      <div class="search-bar">
        <span>🔍</span>
        <input type="text" placeholder="بحث عن عميل..." id="client-search" oninput="filterClients(this.value)">
      </div>
      ${isAccountant() ? `<button class="btn btn-primary" onclick="openClientModal()">+ عميل جديد</button>` : ''}
      ${isAdmin() ? `<button class="btn btn-ghost btn-sm" onclick="printClients(window._clientsCache||[])">🖨️ طباعة</button>` : ''}
    </div>
  </div>

  <div class="card" style="padding:0; overflow:hidden">
    <div class="table-wrap">
      <table id="clients-table">
        <thead>
          <tr>
            <th>اسم العميل</th>
            <th>القسم</th>
            <th>الرصيد الحالي</th>

            <th>مستوى الخطر</th>
            <th>الإجراءات</th>
          </tr>
        </thead>
        <tbody id="clients-tbody">
          ${clients.length ? clients.map(renderClientRow).join('') : emptyRow('لا يوجد عملاء مسجّلون', 6)}
        </tbody>
      </table>
    </div>
  </div>
`;
}

function renderClientRow(cl) {
  const balance = parseFloat(cl.balance || 0);
  const limit = parseFloat(cl.credit_limit || 0);
  const balColor = balance > 0 ? 'var(--rd)' : balance < 0 ? 'var(--gr)' : 'var(--tx)';
  const overLimit = limit > 0 && balance > limit;
  const overLimitBadge = overLimit
    ? `<span class="badge badge-red" style="margin-right:4px;font-size:10px">⚠️ تجاوز الحد</span>` : '';
  const deptLabel = { porcelain: 'بورسلان', egyptian: 'مصري', shoes: 'أخرى' }[cl.department] || cl.department || '—';

  return `<tr data-client-id="${cl.id}" ${overLimit ? 'style="background:#fff5f5"' : ''}>
    <td>
      <strong>${escHtml(cl.name)}</strong>
      ${cl.telegram_chat_id ? '<span class="badge badge-green" style="margin-right:6px;font-size:10px">📱</span>' : ''}
    </td>
    <td><span class="badge badge-blue">${deptLabel}</span></td>
    <td style="color:${balColor}; font-weight:700">
      ${fmt(balance)} د.أ ${overLimitBadge}
    </td>
    <td>${riskLabel(cl.risk_level)}</td>
    <td>
      <div style="display:flex; gap:6px; flex-wrap:wrap">
        <button class="btn btn-ghost btn-sm" onclick="viewClientStatement(${cl.id}, ${jsString(cl.name)})">📄 كشف تفصيلي</button>
        ${isAccountant() ? `
          <button class="btn btn-primary btn-sm" onclick="openQuickPayment(${cl.id}, ${jsString(cl.name)})">💰 قبض</button>
          <button class="btn btn-ghost btn-sm" onclick="openEditClient(${cl.id})">✏️</button>
        ` : ''}
        ${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deleteClient(${cl.id}, ${jsString(cl.name)})">🗑️</button>` : ''}
      </div>
    </td>
  </tr>`;
}

function openClientModal(data = null) {
  const isEdit = !!data;
  openModal(`
    <div class="modal-header">
      <div class="modal-title">${isEdit ? 'تعديل بيانات العميل' : 'إضافة عميل جديد'}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">اسم العميل *</label>
        <input class="form-input" id="cl_name" value="${escHtml(data?.name || '')}" placeholder="الاسم الكامل">
      </div>
      <div class="form-group">
        <label class="form-label">القسم</label>
        <select class="form-select" id="cl_dept">
          <option value="porcelain" ${data?.department === 'porcelain' ? 'selected' : ''}>بورسلان</option>
          <option value="egyptian"  ${data?.department === 'egyptian' ? 'selected' : ''}>مصري</option>
          <option value="shoes"     ${data?.department === 'shoes' ? 'selected' : ''}>أخرى</option>
        </select>
      </div>
    </div>
    <div class="form-row">

      <div class="form-group">
        <label class="form-label">مستوى الخطر</label>
        <select class="form-select" id="cl_risk">
          <option value="low"    ${data?.risk_level === 'low' ? 'selected' : ''}>منخفض</option>
          <option value="medium" ${data?.risk_level === 'medium' ? 'selected' : ''}>متوسط</option>
          <option value="high"   ${data?.risk_level === 'high' ? 'selected' : ''}>عالٍ</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">رقم هاتف</label>
      <input class="form-input" id="cl_phone" value="${escHtml(data?.phone || '')}" placeholder="07X XXXX XXXX">
    </div>
    <div style="display:flex; gap:10px; margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="${isEdit ? `saveEditClient(${data.id})` : 'saveNewClient()'}">
        ${isEdit ? 'حفظ التعديلات' : 'إضافة العميل'}
      </button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveNewClient() {
  const name = document.getElementById('cl_name')?.value?.trim();
  if (!name) { toast('الاسم مطلوب', 'error'); return; }
  const btn = document.querySelector('#global-modal .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = 'جاري الحفظ...'; }
  try {
    const newClient = await API.createClient({
      name,
      department: document.getElementById('cl_dept')?.value || 'porcelain',
      credit_limit: 0,
      risk_level: document.getElementById('cl_risk')?.value || 'low',
      phone: document.getElementById('cl_phone')?.value || null,
    });
    newClient.balance = 0;
    toast('تمت إضافة العميل بنجاح ✅', 'success');
    closeModal();
    if (window._clientsCache) window._clientsCache.unshift(newClient);
    const tbody = document.getElementById('clients-tbody');
    if (tbody) {
      const empty = tbody.querySelector('td[colspan]');
      if (empty) tbody.innerHTML = '';
      tbody.insertAdjacentHTML('afterbegin', renderClientRow(newClient));
      const sub = document.querySelector('.page-sub');
      if (sub) sub.textContent = `${tbody.children.length} عميل مسجّل`;
    }
  } catch (e) {
    toast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'إضافة العميل'; }
  }
}

async function openEditClient(id) {
  try {
    const cl = await API.getClient(id);
    openClientModal(cl);
  } catch (e) { toast('تعذّر تحميل بيانات العميل', 'error'); }
}

async function saveEditClient(id) {
  const name = document.getElementById('cl_name')?.value?.trim();
  if (!name) { toast('الاسم مطلوب', 'error'); return; }
  const btn = document.querySelector('#global-modal .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = 'جاري الحفظ...'; }
  try {
    const updated = await API.updateClient(id, {
      name,
      department: document.getElementById('cl_dept')?.value || 'porcelain',
      credit_limit: 0,
      risk_level: document.getElementById('cl_risk')?.value || 'low',
      phone: document.getElementById('cl_phone')?.value || null,
    });
    // preserve balance from cache
    if (window._clientsCache) {
      const cached = window._clientsCache.find(c => c.id === id);
      if (cached) updated.balance = cached.balance;
      const idx = window._clientsCache.findIndex(c => c.id === id);
      if (idx !== -1) window._clientsCache[idx] = { ...window._clientsCache[idx], ...updated };
    }
    toast('تم تحديث بيانات العميل ✅', 'success');
    closeModal();
    const row = document.querySelector(`#clients-tbody tr[data-client-id="${id}"]`);
    if (row) row.outerHTML = renderClientRow(updated);
  } catch (e) {
    toast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'حفظ التعديلات'; }
  }
}

async function deleteClient(id, name) {
  if (!confirm(`هل أنت متأكد من حذف العميل "${name}"؟`)) return;
  const row = document.querySelector(`#clients-tbody tr[data-client-id="${id}"]`);
  if (row) { row.style.opacity = '0.4'; row.style.pointerEvents = 'none'; }
  try {
    await API.deleteClient(id);
    toast('تم حذف العميل ✅', 'success');
    if (window._clientsCache) {
      window._clientsCache = window._clientsCache.filter(c => c.id !== id);
    }
    if (row) {
      row.style.transition = 'opacity 0.25s';
      row.style.opacity = '0';
      setTimeout(() => {
        row.remove();
        const tbody = document.getElementById('clients-tbody');
        if (!tbody) return;
        const sub = document.querySelector('.page-sub');
        if (sub) sub.textContent = `${tbody.children.length} عميل مسجّل`;
        if (!tbody.children.length) {
          tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--tx3)">لا يوجد عملاء مسجّلون</td></tr>`;
        }
      }, 280);
    }
  } catch (e) {
    if (row) { row.style.opacity = '1'; row.style.pointerEvents = ''; }
    toast(e.message, 'error');
  }
}
async function viewClientStatement(id, name) {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">📄 كشف حساب — ${escHtml(name)}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="stmt-content">
      <div class="loading"><div class="spinner"></div><p>جاري التحميل...</p></div>
    </div>
  `, '780px');

  try {
    const data = await API.getClientStatement(id);
    const el = document.getElementById('stmt-content');
    if (!el) return;

    const txs = data.transactions || [];
    const s = data.summary || {};
    const balance = parseFloat(data.balance || 0);
    const limit = parseFloat(data.credit_limit || 0);
    const overLimit = limit > 0 && balance > limit;
    const encoded = encodePayload(data);

    const pmBadge = (method) => {
      const map = {
        cash: '<span style="background:#edfaf4;color:#057a55;padding:2px 7px;border-radius:20px;font-size:10px;font-weight:700">نقد</span>',
        credit: '<span style="background:#fff0f0;color:#c21515;padding:2px 7px;border-radius:20px;font-size:10px;font-weight:700">ذمم</span>',
        partial: '<span style="background:#fff8ee;color:#9a4500;padding:2px 7px;border-radius:20px;font-size:10px;font-weight:700">جزئي</span>',
        check: '<span style="background:#eef3ff;color:#1a4fd6;padding:2px 7px;border-radius:20px;font-size:10px;font-weight:700">شيك</span>',
        transfer: '<span style="background:#eef3ff;color:#1a4fd6;padding:2px 7px;border-radius:20px;font-size:10px;font-weight:700">حوالة</span>',
      };
      return map[method] || '';
    };

    el.innerHTML = `
      <!-- ملخص الحساب -->
      <div style="background:#1a1815;color:white;padding:18px 20px;border-radius:12px;margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
          <div>
            <div style="font-size:11px;opacity:.5;margin-bottom:4px">المتبقي على زبائن العميل</div>
            <div style="font-size:32px;font-weight:800;letter-spacing:-1px;color:${balance > 0 ? '#ff6b6b' : '#51cf66'}">
              ${fmt(Math.abs(balance))} د.أ
            </div>
            <div style="font-size:11px;opacity:.5;margin-top:4px">
              ${balance > 0 ? '← المتبقي على زبائن هذا العميل' : '← لا يوجد متبقي على زبائنه'}
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px">
            <div style="background:rgba(255,255,255,.08);border-radius:8px;padding:8px 12px">
              <div style="opacity:.5;font-size:10px;margin-bottom:2px">إجمالي الفواتير</div>
              <div style="font-weight:700">${fmt(s.total_invoiced)} د.أ</div>
            </div>
            <div style="background:rgba(255,255,255,.08);border-radius:8px;padding:8px 12px">
              <div style="opacity:.5;font-size:10px;margin-bottom:2px">إجمالي المدفوع</div>
              <div style="font-weight:700;color:#51cf66">${fmt(s.total_paid)} د.أ</div>
            </div>
            <div style="background:rgba(255,255,255,.08);border-radius:8px;padding:8px 12px">
              <div style="opacity:.5;font-size:10px;margin-bottom:2px">نقد فوري</div>
              <div style="font-weight:700;color:#51cf66">${fmt(s.total_cash_on_invoices)} د.أ</div>
            </div>
            <div style="background:rgba(255,255,255,.08);border-radius:8px;padding:8px 12px">
              <div style="opacity:.5;font-size:10px;margin-bottom:2px">ذمم متبقية</div>
              <div style="font-weight:700;color:#ff6b6b">${fmt(s.total_credit_invoices)} د.أ</div>
            </div>
          </div>
        </div>

        ${overLimit ? `
          <div style="margin-top:12px;padding:8px 12px;background:rgba(255,0,0,.2);border-radius:8px;font-size:12px;font-weight:700">
            ⚠️ تجاوز حد الائتمان ${fmt(limit)} د.أ — الرصيد الحالي ${fmt(balance)} د.أ
          </div>` : ''}
      </div>

      <!-- شريط الإحصائيات -->
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px">
        <div style="background:#edfaf4;border-radius:10px;padding:10px 14px;border:1px solid rgba(10,118,80,.1)">
          <div style="font-size:10px;color:#057a55;font-weight:700;margin-bottom:2px">💰 نقد مدفوع</div>
          <div style="font-size:16px;font-weight:800;color:#057a55">${fmt(s.total_cash_on_invoices)} د.أ</div>
        </div>
        <div style="background:#fff0f0;border-radius:10px;padding:10px 14px;border:1px solid rgba(194,21,21,.1)">
          <div style="font-size:10px;color:#c21515;font-weight:700;margin-bottom:2px">📋 ذمم قائمة</div>
          <div style="font-size:16px;font-weight:800;color:#c21515">${fmt(s.total_credit_invoices)} د.أ</div>
        </div>
        <div style="background:#eef3ff;border-radius:10px;padding:10px 14px;border:1px solid rgba(26,79,214,.1)">
          <div style="font-size:10px;color:#1a4fd6;font-weight:700;margin-bottom:2px">💳 مقبوضات إضافية</div>
          <div style="font-size:16px;font-weight:800;color:#1a4fd6">${fmt(s.total_standalone_payments)} د.أ</div>
        </div>
      </div>

      <!-- جدول الحركات -->
      <div style="border:1px solid #e8e5e0;border-radius:10px;overflow:hidden">
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead>
            <tr style="background:#f5f3f0">
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94;white-space:nowrap">التاريخ</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">البيان</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94;white-space:nowrap">نوع الدفع</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94;white-space:nowrap">مدين (فاتورة)</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94;white-space:nowrap">نقد مدفوع</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94;white-space:nowrap">دائن (قبض)</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94;white-space:nowrap">ذمم متبقية</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94;white-space:nowrap">الرصيد</th>
            </tr>
          </thead>
          <tbody>
            ${txs.length ? txs.map((t, idx) => {
      const isInv = t.type === 'invoice';
      const isStandalone = t.type === 'payment' && !t.is_invoice_payment;
      const isInvPay = t.type === 'payment' && t.is_invoice_payment;
      const bg = isInvPay
        ? 'background:#f9fff9'
        : isInv && parseFloat(t.remaining_amount) > 0
          ? 'background:#fff9f9'
          : idx % 2 === 0 ? '' : 'background:#faf9f7';

      return `<tr style="border-top:1px solid #f0ede8;${bg}">
                <td style="padding:10px 12px;color:#9e9a94;white-space:nowrap">${fmtDate(t.date)}</td>
                <td style="padding:10px 12px">
                  ${isInv
          ? `<div style="font-weight:700">فاتورة #${escHtml(t.description || t.id)}</div>
                       ${t.notes ? `<div style="font-size:10px;color:#9e9a94;margin-top:2px">${escHtml(t.notes.replace(/invoice_id:\d+\|?/g, '').replace(/method:\w+/g, '').trim())}</div>` : ''}`
          : isInvPay
            ? `<div style="color:#057a55;font-weight:600">↳ واصل ${escHtml(t.payment_method === 'cash' ? 'نقد' : t.payment_method === 'check' ? 'شيك' : 'حوالة')}</div>`
            : `<div style="font-weight:600">مقبوضة مستقلة</div>
                         ${t.notes ? `<div style="font-size:10px;color:#9e9a94">${escHtml(t.notes.replace(/method:\w+/g, '').trim())}</div>` : ''}`
        }
                </td>
                <td style="padding:10px 12px">${isInv ? pmBadge(t.payment_method) : ''}</td>
                <td style="padding:10px 12px;color:#c21515;font-weight:700;text-align:left">
                  ${isInv ? fmt(t.amount) : '—'}
                </td>
                <td style="padding:10px 12px;color:#057a55;font-weight:700;text-align:left">
                  ${isInv && parseFloat(t.paid_amount) > 0 ? fmt(t.paid_amount) : '—'}
                </td>
                <td style="padding:10px 12px;color:#057a55;font-weight:700;text-align:left">
                  ${!isInv ? fmt(t.amount) : '—'}
                </td>
                <td style="padding:10px 12px;text-align:left">
                  ${isInv && parseFloat(t.remaining_amount) > 0
          ? `<span style="color:#c21515;font-weight:700">${fmt(t.remaining_amount)}</span>`
          : isInv
            ? '<span style="color:#057a55;font-size:11px">✓ مسدد</span>'
            : '—'}
                </td>
                <td style="padding:10px 12px;font-weight:800;text-align:left;${parseFloat(t.running_balance) > 0 ? 'color:#c21515' : 'color:#057a55'}">
                  ${fmt(Math.abs(t.running_balance))}
                  <div style="font-size:9px;font-weight:400;color:#9e9a94">${parseFloat(t.running_balance) > 0 ? 'عليه' : 'له'}</div>
                </td>
              </tr>`;
    }).join('') : `<tr><td colspan="8" style="text-align:center;padding:30px;color:#9e9a94">لا توجد حركات</td></tr>`}
          </tbody>
          <!-- إجمالي الجدول -->
          <tfoot>
            <tr style="background:#1a1815;color:white">
              <td colspan="3" style="padding:10px 12px;font-weight:700;font-size:12px">الإجماليات</td>
              <td style="padding:10px 12px;font-weight:800;text-align:left">${fmt(s.total_invoiced)}</td>
              <td style="padding:10px 12px;font-weight:800;color:#51cf66;text-align:left">${fmt(s.total_cash_on_invoices)}</td>
              <td style="padding:10px 12px;font-weight:800;color:#51cf66;text-align:left">${fmt(s.total_standalone_payments)}</td>
              <td style="padding:10px 12px;font-weight:800;color:#ff6b6b;text-align:left">${fmt(s.total_credit_invoices)}</td>
              <td style="padding:10px 12px;font-weight:800;text-align:left">${fmt(Math.abs(balance))}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <!-- أزرار -->
      <div style="display:flex;gap:8px;margin-top:14px">
        <button class="btn btn-ghost btn-sm" onclick="printStatementFromEncoded(${jsString(name)}, ${jsString(encoded)})">🖨️ طباعة</button>
        <button class="btn btn-ghost btn-sm" onclick="closeModal()">إغلاق</button>
      </div>
    `;
  } catch (e) {
    const el = document.getElementById('stmt-content');
    if (el) el.innerHTML = `<div class="alert alert-danger">${escHtml(e.message)}</div>`;
  }
}

/* ═══════════════════════════════════════════════════
   INVOICES
═══════════════════════════════════════════════════ */

function getInvoiceRecipientName(inv) {
  const fromNotes =
    String(inv.notes || '')
      .match(/المطلوب من السادة:\s*([^|]+)/)?.[1]
      ?.trim() || '';

  return String(inv.recipient_name || fromNotes || '').trim();
}

function renderInvoiceRow(inv) {
  const total = parseFloat(inv.total_amount || inv.net_amount || inv.amount || 0);
  const paid = parseFloat(inv.paid_amount || 0);
  const remaining = inv.remaining_amount !== undefined
    ? parseFloat(inv.remaining_amount || 0)
    : Math.max(total - paid, 0);

  const wfStatus = inv.status || 'approved'; // workflow: pending / approved / rejected
  const payStatus = inv.payment_status ||
    (remaining <= 0 && total > 0 ? 'paid' : paid > 0 ? 'partial' : 'debt');

  // What to show in the status cell
  let statusCell;
  if (wfStatus === 'pending') statusCell = invoiceStatusBadge('pending');
  else if (wfStatus === 'rejected') statusCell = invoiceStatusBadge('rejected');
  else statusCell = invoiceStatusBadge(payStatus); // approved → show payment status

  const recip = getInvoiceRecipientName(inv);

  // Row background hint
  const rowStyle = wfStatus === 'pending'
    ? 'background:#fffbeb'
    : wfStatus === 'rejected'
      ? 'background:#fff5f5;opacity:0.7'
      : '';

  return `<tr data-invoice-id="${inv.id}" data-status="${wfStatus}" style="${rowStyle}">
    <td>
      <strong>#${escHtml(inv.invoice_number || inv.id)}</strong>
      ${wfStatus === 'pending' ? '<span style="font-size:10px;color:var(--am);margin-right:4px">⏳</span>' : ''}
    </td>
    <td>${escHtml(inv.client_name || '—')}</td>
    <td>
      ${recip
      ? `<button class="btn btn-ghost btn-sm" style="font-size:11px" onclick="viewRecipientStatement(${jsString(recip)})">${escHtml(recip)}</button>`
      : `<span style="color:var(--tx3)">—</span>`}
    </td>
    <td style="font-weight:700">${fmt(total)} د.أ</td>
    <td style="color:var(--gr);font-weight:700">
      ${wfStatus === 'approved' ? fmt(paid) + ' د.أ' : '—'}
    </td>
    <td style="color:${remaining > 0 ? 'var(--rd)' : 'var(--gr)'};font-weight:700">
      ${wfStatus === 'approved' ? fmt(remaining) + ' د.أ' : '—'}
    </td>
    <td>${statusCell}</td>
    <td style="font-size:12px;color:var(--tx3)">${fmtDate(inv.date || inv.invoice_date)}</td>
    <td>${_invoiceActionButtons(inv)}</td>
  </tr>`;
}
async function renderInvoices(container) {
  let invoices = [], clients = [];
  try {
    [invoices, clients] = await Promise.all([API.getInvoices(), API.getClients()]);
  } catch (e) { invoices = []; clients = []; }

  window._clientsCache = clients || [];
  window._invoicesCache = invoices || [];

  const pending = (invoices || []).filter(i => (i.status || 'approved') === 'pending').length;
  const rejected = (invoices || []).filter(i => (i.status || 'approved') === 'rejected').length;

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">الفواتير</div>
        <div class="page-sub">
          ${(invoices || []).length} فاتورة
          ${pending ? `— <span style="color:var(--am);font-weight:700">${pending} بانتظار الاعتماد</span>` : ''}
        </div>
      </div>
      <div style="display:flex;gap:10px">
        <div class="search-bar">
          <span>🔍</span>
          <input type="text" placeholder="بحث..." oninput="filterInvoicesByText(this.value)">
        </div>
        ${isAccountant() ? `<button class="btn btn-primary" onclick="openInvoiceModal()">+ فاتورة جديدة</button>` : ''}
        <button class="btn btn-ghost btn-sm" onclick="printInvoicesListFromEncoded(${jsString(encodePayload((invoices || []).filter(i => (i.status || 'approved') === 'approved')))})">🖨️</button>
      </div>
    </div>

    ${isAdmin() && pending ? `
      <div class="alert alert-warning" style="cursor:pointer;margin-bottom:12px" onclick="setInvoiceTab('pending')">
        ⚠️ يوجد <strong>${pending} فاتورة</strong> بانتظار موافقتك — انقر للعرض
      </div>` : ''}

    <div style="display:flex;gap:4px;margin-bottom:16px;background:var(--bg);border:1px solid var(--brd);border-radius:var(--r);padding:4px;width:fit-content">
      <button class="tab-btn active" id="inv-tab-all"      onclick="setInvoiceTab('all')">الكل</button>
      ${pending ? `<button class="tab-btn" id="inv-tab-pending"   onclick="setInvoiceTab('pending')"  style="color:var(--am)">⏳ انتظار (${pending})</button>` : ''}
      <button class="tab-btn" id="inv-tab-approved" onclick="setInvoiceTab('approved')">✅ معتمدة</button>
      ${rejected ? `<button class="tab-btn" id="inv-tab-rejected"  onclick="setInvoiceTab('rejected')" style="color:var(--rd)">✗ مرفوضة (${rejected})</button>` : ''}
    </div>

    <div class="card" style="padding:0;overflow:hidden">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>رقم الفاتورة</th><th>كتبها الموظف</th><th>الزبون / مطلوب من السادة</th>              <th>الإجمالي</th><th>المدفوع</th><th>الباقي</th>
              <th>الحالة</th><th>التاريخ</th><th>الإجراءات</th>
            </tr>
          </thead>
          <tbody id="inv-tbody">
            ${(invoices || []).length ? (invoices || []).map(renderInvoiceRow).join('') : emptyRow('لا توجد فواتير', 9)}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function setInvoiceTab(status) {
  ['all', 'pending', 'approved', 'rejected'].forEach(s => {
    const el = document.getElementById(`inv-tab-${s}`);
    if (el) el.classList.toggle('active', s === status);
  });
  const invoices = window._invoicesCache || [];
  const tbody = document.getElementById('inv-tbody');
  if (!tbody) return;
  const filtered = status === 'all'
    ? invoices
    : invoices.filter(i => (i.status || 'approved') === status);
  tbody.innerHTML = filtered.length
    ? filtered.map(renderInvoiceRow).join('')
    : emptyRow('لا توجد فواتير في هذا التصنيف', 9);
}

function filterInvoicesByText(val) {
  document.querySelectorAll('#inv-tbody tr').forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes((val || '').toLowerCase()) ? '' : 'none';
  });
}

function _invoiceActionButtons(inv) {
  const wfStatus = inv.status || 'approved';
  const encoded = encodePayload(inv);
  let html = '';

  if (wfStatus === 'pending') {
    if (isAdmin()) {
      html += `
        <button class="btn btn-success btn-sm" onclick="approveInvoice(${inv.id})">✅ اعتماد</button>
        <button class="btn btn-danger btn-sm"  onclick="rejectInvoiceModal(${inv.id})">✗ رفض</button>
      `;
    }
    // Creator or admin can delete pending
    html += `<button class="btn btn-ghost btn-sm" onclick="deleteInvoice(${inv.id})">🗑️</button>`;

  } else if (wfStatus === 'rejected') {
    html += `
      <span style="font-size:11px;color:var(--rd);font-style:italic">
        ${escHtml(inv.rejection_reason || 'مرفوضة')}
      </span>
    `;
    if (isAdmin()) {
      html += `<button class="btn btn-danger btn-sm" onclick="deleteInvoice(${inv.id})">🗑️</button>`;
    }

  } else {
    // approved — normal actions
    html += `<button class="btn btn-ghost btn-sm" onclick="printInvoiceFromEncoded(${jsString(encoded)})">🖨️ طباعة</button>`;
    if (isAccountant()) {
      html += `
<button class="btn btn-success btn-sm" onclick="openRecipientPayment(${jsString(getInvoiceRecipientName(inv) || inv.recipient_name || '')}, null)">💰 قبض</button>        <button class="btn btn-primary btn-sm" onclick="openInvoiceModalFromEncoded(${jsString(encoded)})">✏️ تعديل</button>
      `;
    }
    if (isAdmin()) {
      html += `<button class="btn btn-danger btn-sm" onclick="deleteInvoice(${inv.id})">🗑️</button>`;
    }
  }

  return `<div style="display:flex;gap:6px;flex-wrap:wrap">${html}</div>`;
}

function downloadInvoicePDF(invoiceId) {
  const token = localStorage.getItem('token');
  const url = `${window.API_BASE || window.ENV_API_BASE || (location.hostname === 'localhost' ? 'http://localhost:8000/api' : '/api')}/invoices/${invoiceId}/pdf`;

  fetch(url, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
    .then(res => {
      if (!res.ok) throw new Error('فشل تحميل PDF');
      return res.blob();
    })
    .then(blob => {
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `invoice-${invoiceId}.pdf`;
      a.click();
      URL.revokeObjectURL(blobUrl);
    })
    .catch(e => toast(e.message, 'error'));
}

function openInvoiceModal(invoice = null) {
  const isEdit = !!invoice;
  const clientOpts = (window._clientsCache || []).map(c =>
    `<option value="${c.id}" ${String(invoice?.client_id || '') === String(c.id) ? 'selected' : ''}>${escHtml(c.name)}</option>`
  ).join('');

  const invDate = invoice?.date
    ? String(invoice.date).split('T')[0]
    : new Date().toISOString().split('T')[0];

  const paid = Number(invoice?.paid_amount || 0);
  const notes = invoice?.notes || '';
  const recipient = invoice?.recipient_name ||
    notes.match(/المطلوب من السادة:\s*([^|]+)/)?.[1]?.trim() || '';
  const cleanNotes = notes
    .replace(/المطلوب من السادة:\s*[^|]+/g, '')
    .replace(/\|/g, '')
    .trim();

  window._invoiceItemIndex = 0;
  window._editingInvoiceId = isEdit ? invoice.id : null;
  window._invoiceSaving = false;

  openModal(`
    <div class="modal-header">
      <div class="modal-title">${isEdit ? '✏️ تعديل فاتورة' : 'إنشاء فاتورة جديدة'}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>

    <div class="form-group">
      <label class="form-label">المطلوب من السادة</label>
    <input class="form-input" id="inv_recipient" value="${escHtml(recipient)}" placeholder="اسم الزبون الذي عليه الدفع" required>    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">العميل *</label>
        <select class="form-select" id="inv_client">
          <option value="">اختر عميلاً</option>
          ${clientOpts}
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">رقم الفاتورة</label>
        <input class="form-input" id="inv_num" value="${escHtml(invoice?.invoice_number || '')}" placeholder="تلقائي إن تُرك فارغاً">
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">تاريخ الفاتورة</label>
        <input class="form-input" id="inv_date" type="date" value="${invDate}">
      </div>

      <div class="form-group">
        <label class="form-label">نوع الدفع</label>
        <select class="form-select" id="inv_pay" onchange="handleInvoicePaymentChange()">
          <option value="credit" ${invoice?.payment_method === 'credit' ? 'selected' : ''}>ذمم / آجل</option>
          <option value="cash" ${invoice?.payment_method === 'cash' ? 'selected' : ''}>نقد كامل</option>
          <option value="partial" ${invoice?.payment_method === 'partial' ? 'selected' : ''}>جزئي</option>
          <option value="check" ${invoice?.payment_method === 'check' ? 'selected' : ''}>شيك</option>
          <option value="transfer" ${invoice?.payment_method === 'transfer' ? 'selected' : ''}>حوالة</option>
        </select>
      </div>
    </div>

    <div style="margin:12px 0; display:flex; align-items:center; gap:10px">
      <label style="font-size:13px; font-weight:600; color:var(--tx2)">ربط بأصناف المستودع؟</label>
      <input type="checkbox" id="inv_has_items" checked onchange="toggleInvoiceItems()"
             style="width:16px; height:16px; cursor:pointer">
    </div>

    <div id="inv-items-section">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <div style="font-weight:700; font-size:13px">📦 الأصناف — مثل الفاتورة الورقية</div>
        <button class="btn btn-ghost btn-sm" onclick="addInvoiceItemRow()">+ إضافة صنف</button>
      </div>

      <div style="
  display:grid;
  grid-template-columns:.85fr 1.4fr 1.3fr .65fr .8fr .8fr .8fr .9fr auto;
  gap:8px;
  padding:8px 10px;
  background:#f5f3f0;
  border-radius:10px;
  font-size:11px;
  font-weight:800;
  color:#777;
  margin-bottom:8px;
">
  <div>الفئة</div>
  <div>الصنف</div>
  <div>البيان</div>
  <div>الكمية</div>
  <div>عدد الحبات</div>
  <div>سعر 12 / الدزينة</div>
  <div>سعر الحبة</div>
  <div>المجموع</div>
  <div></div>
</div>
      <div id="inv-items-wrap" style="display:flex; flex-direction:column; gap:8px"></div>
    </div>

    <div id="inv-manual-section" style="display:none">
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">المبلغ الصافي *</label>
          <input class="form-input" id="inv_net" type="number" value="${Number(invoice?.net_amount || 0).toFixed(3)}" min="0" step="0.001" oninput="calcInvoiceTax()">
        </div>
        <div class="form-group">
          <label class="form-label">نسبة الضريبة %</label>
          <input class="form-input" id="inv_tax" type="number" value="0" min="0" step="0.001" oninput="calcInvoiceTax()">
        </div>
      </div>
    </div>

    <div style="background:#f5f3f0;border-radius:12px;padding:14px;margin-top:12px">
      <div style="font-size:12px;font-weight:700;color:#5a5650;margin-bottom:10px">💰 تفصيل الدفع</div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
        <div style="padding:10px 14px;background:white;border-radius:8px;border:1px solid #e8e5e0">
          <div style="font-size:10px;color:#9e9a94;margin-bottom:4px">إجمالي الفاتورة</div>
          <div id="inv_total_display" style="font-size:18px;font-weight:800;color:#1a4fd6">0.000 د.أ</div>
        </div>
        <div style="padding:10px 14px;background:white;border-radius:8px;border:1px solid #e8e5e0">
          <div style="font-size:10px;color:#9e9a94;margin-bottom:4px">نوع الدفع</div>
          <div id="inv_pay_label" style="font-size:13px;font-weight:700;color:#1a1815">—</div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
        <div style="padding:10px 14px;background:#edfaf4;border-radius:8px;border:1px solid rgba(10,118,80,.15)">
          <div style="font-size:10px;color:#057a55;font-weight:700;margin-bottom:4px">نقد مدفوع الآن</div>
          <input class="form-input" id="inv_paid" type="number" min="0" step="0.001" value="${paid.toFixed(3)}"
            oninput="calcInvoicePayment()"
            style="margin-top:4px;font-size:16px;font-weight:800;color:#057a55;border-color:rgba(10,118,80,.2);background:white">
        </div>
        <div style="padding:10px 14px;background:#fff0f0;border-radius:8px;border:1px solid rgba(194,21,21,.15)">
          <div style="font-size:10px;color:#c21515;font-weight:700;margin-bottom:4px">ذمم / باقي</div>
          <div id="inv_remaining_display" style="font-size:18px;font-weight:800;color:#c21515;margin-top:8px">0.000 د.أ</div>
        </div>
        <div style="padding:10px 14px;background:#eef3ff;border-radius:8px;border:1px solid rgba(26,79,214,.15)">
          <div style="font-size:10px;color:#1a4fd6;font-weight:700;margin-bottom:4px">حالة الفاتورة</div>
          <div id="inv_status_label" style="font-size:13px;font-weight:800;margin-top:8px;color:#1a4fd6">—</div>
        </div>
      </div>
    </div>

    <div class="form-group" style="margin-top:12px">
      <label class="form-label">ملاحظات</label>
      <input class="form-input" id="inv_notes" value="${escHtml(cleanNotes)}" placeholder="اختياري">
    </div>

    <div style="display:flex; gap:10px; margin-top:8px">
      <button class="btn btn-primary" style="flex:1" id="save-invoice-btn" onclick="saveInvoice()">
        ${isEdit ? 'حفظ التعديلات' : 'حفظ الفاتورة'}
      </button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `, '980px');

  Promise.all([
    API.getProducts(),
    API.getWarehouseCategories()
  ])
    .then(([prods, categories]) => {
      window._productsCache = Array.isArray(prods) ? prods : [];
      window._invoiceCategoriesCache = Array.isArray(categories) ? categories : [];

      const oldItems = Array.isArray(invoice?.items) ? invoice.items : [];

      if (oldItems.length) {
        oldItems.forEach(item => addInvoiceItemRow(item));
      } else {
        addInvoiceItemRow();
      }

      calcInvoiceItemsTotal();
      handleInvoicePaymentChange();
    })
    .catch(() => {
      window._productsCache = [];
      window._invoiceCategoriesCache = [];
      addInvoiceItemRow();
      calcInvoiceItemsTotal();
      handleInvoicePaymentChange();
    });
  if (!window._clientsCache?.length) {
    API.getClients().then(cls => {
      window._clientsCache = cls || [];
      const sel = document.getElementById('inv_client');
      if (sel) {
        sel.innerHTML = '<option value="">اختر عميلاً</option>' +
          cls.map(c => `<option value="${c.id}" ${String(invoice?.client_id || '') === String(c.id) ? 'selected' : ''}>${escHtml(c.name)}</option>`).join('');
      }
    });
  }
}
function toggleInvoiceItems() {
  const checked = document.getElementById('inv_has_items')?.checked;
  const itemsSection = document.getElementById('inv-items-section');
  const manualSection = document.getElementById('inv-manual-section');
  if (itemsSection) itemsSection.style.display = checked ? 'block' : 'none';
  if (manualSection) manualSection.style.display = checked ? 'none' : 'block';

  if (checked && document.getElementById('inv-items-wrap')?.children.length === 0) {
    addInvoiceItemRow();
  }

  checked ? calcInvoiceItemsTotal() : calcInvoiceTax();
}

function getInvoiceTotalNumber() {
  const txt = document.getElementById('inv_total_display')?.textContent || '0';
  return parseFloat(txt.replace(/,/g, '').replace(/[^0-9.\-]/g, '')) || 0;
}

function handleInvoicePaymentChange() {
  const method = document.getElementById('inv_pay')?.value || 'credit';
  const paidEl = document.getElementById('inv_paid');
  const total = getInvoiceTotalNumber();

  if (!paidEl) return;

  if (method === 'cash') {
    paidEl.value = total ? total.toFixed(3) : '0';
    paidEl.readOnly = true;
    paidEl.style.opacity = '.7';
  } else if (method === 'credit') {
    paidEl.value = '0';
    paidEl.readOnly = true;
    paidEl.style.opacity = '.7';
  } else {
    paidEl.readOnly = false;
    paidEl.style.opacity = '1';
  }

  calcInvoicePayment();
}

function calcInvoicePayment() {
  const total = getInvoiceTotalNumber();
  const paidEl = document.getElementById('inv_paid');
  const remainingEl = document.getElementById('inv_remaining_display');
  const statusEl = document.getElementById('inv_status_label');
  const payLabelEl = document.getElementById('inv_pay_label');
  const method = document.getElementById('inv_pay')?.value || 'credit';

  if (!paidEl || !remainingEl) return;

  let paid = parseFloat(paidEl.value) || 0;
  if (paid < 0) paid = 0;
  if (paid > total) paid = total;

  const remaining = Math.max(total - paid, 0);

  remainingEl.textContent = `${fmt(remaining)} د.أ`;
  remainingEl.style.color = remaining > 0 ? '#c21515' : '#057a55';

  if (statusEl) {
    if (remaining <= 0 && total > 0) {
      statusEl.textContent = '✅ مدفوعة بالكامل';
      statusEl.style.color = '#057a55';
    } else if (paid > 0) {
      statusEl.textContent = '🔶 دفع جزئي';
      statusEl.style.color = '#9a4500';
    } else {
      statusEl.textContent = '🔴 ذمم كاملة';
      statusEl.style.color = '#c21515';
    }
  }

  if (payLabelEl) {
    const labels = {
      cash: '💵 نقد كامل',
      credit: '📋 ذمم / آجل',
      partial: '🔶 جزئي',
      check: '🏦 شيك',
      transfer: '💳 حوالة'
    };
    payLabelEl.textContent = labels[method] || method;
  }
}
function printInvoice(inv) {
  const items = Array.isArray(inv.items) ? inv.items : [];
  const total = Number(inv.total_amount || inv.net_amount || 0);
  const paid = Number(inv.paid_amount || 0);
  const remaining = Math.max(total - paid, 0);

  const w = window.open('', '_blank');

  w.document.write(`<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>فاتورة #${escHtml(inv.invoice_number || inv.id)}</title>
<style>
  body {
    font-family: Arial, sans-serif;
    padding: 24px;
    direction: rtl;
    color: #111;
  }

  .invoice-box {
    border: 2px solid #222;
    padding: 14px;
    max-width: 900px;
    margin: auto;
  }

  .top {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    align-items: center;
    border-bottom: 2px solid #222;
    padding-bottom: 8px;
    margin-bottom: 10px;
  }

  .title {
    text-align: center;
    font-size: 22px;
    font-weight: 800;
  }

  .small {
    font-size: 12px;
    color: #333;
  }

  .meta {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin: 10px 0;
    font-size: 14px;
  }

  .field {
    border: 1px solid #777;
    padding: 7px 9px;
    min-height: 32px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
  }

  th, td {
    border: 1px solid #333;
    padding: 8px;
    font-size: 13px;
    text-align: center;
  }

  th {
    background: #eee;
    font-weight: 800;
  }

  td.desc {
    text-align: right;
  }

  .totals {
    margin-top: 12px;
    display: grid;
    grid-template-columns: 1fr 260px;
    gap: 12px;
  }

  .total-table td {
    font-weight: 800;
  }

  .sign {
    margin-top: 35px;
    display: flex;
    justify-content: space-between;
    font-size: 13px;
  }

  @media print {
    body { padding: 0; }
    .invoice-box { border: 2px solid #000; }
  }
</style>
</head>
<body>
  <div class="invoice-box">
    <div class="top">
      <div>
        <div><strong>رقم الفاتورة:</strong> ${escHtml(inv.invoice_number || inv.id)}</div>
        <div class="small"><strong>التاريخ:</strong> ${fmtDate(inv.date || inv.invoice_date)}</div>
      </div>

      <div class="title">عرض سعر / فاتورة</div>

      <div style="text-align:left">
        <div><strong>مجموعة أبو عمران التجارية</strong></div>
        <div class="small">Price Offer</div>
      </div>
    </div>

    <div class="meta">
      <div class="field"><strong>المطلوب من السادة:</strong> ${escHtml((inv.notes || '').match(/المطلوب من السادة:\\s*([^|]+)/)?.[1]?.trim() || inv.client_name || '—')}</div>
      <div class="field"><strong>طريقة الدفع:</strong> ${escHtml(inv.payment_method || '—')}</div>
    </div>

    <table>
      <thead>
        <tr>
          <th style="width:45px">رقم</th>
          <th>البيان</th>
          <th style="width:90px">الكمية</th>
          <th style="width:120px">سعر الوحدة</th>
          <th style="width:120px">المجموع</th>
        </tr>
      </thead>
      <tbody>
        ${items.length
      ? items.map((item, i) => {
        const qty = Number(item.quantity || 0);
        const unit = Number(item.unit_price || 0);
        const lineTotal = Number(item.line_total || qty * unit || 0);
        return `
                  <tr>
                    <td>${i + 1}</td>
                    <td class="desc">${escHtml(item.description || item.product_name || '—')}</td>
                    <td>${qty.toFixed(3)}</td>
                    <td>${unit.toFixed(3)}</td>
                    <td>${lineTotal.toFixed(3)}</td>
                  </tr>
                `;
      }).join('')
      : `
              <tr>
                <td>1</td>
                <td class="desc">مبيعات بضاعة</td>
                <td>1.000</td>
                <td>${total.toFixed(3)}</td>
                <td>${total.toFixed(3)}</td>
              </tr>
            `
    }

        ${Array.from({ length: Math.max(0, 8 - items.length) }).map(() => `
          <tr>
            <td>&nbsp;</td>
            <td class="desc">&nbsp;</td>
            <td>&nbsp;</td>
            <td>&nbsp;</td>
            <td>&nbsp;</td>
          </tr>
        `).join('')}
      </tbody>
    </table>

    <div class="totals">
      <div class="field">
        <strong>ملاحظات:</strong>
        ${escHtml((inv.notes || '').replace(/المطلوب من السادة:\\s*[^|]+/g, '').replace(/\\|/g, '').trim() || '—')}
      </div>

      <table class="total-table">
        <tr>
          <td>الإجمالي</td>
          <td>${total.toFixed(3)}</td>
        </tr>
        <tr>
          <td>المدفوع</td>
          <td>${paid.toFixed(3)}</td>
        </tr>
        <tr>
          <td>الباقي</td>
          <td>${remaining.toFixed(3)}</td>
        </tr>
      </table>
    </div>

    <div class="sign">
      <div>توقيع المستلم: __________________</div>
      <div>التوقيع: __________________</div>
    </div>
  </div>
</body>
</html>`);

  w.document.close();
  setTimeout(() => w.print(), 500);
}

function getInvoiceProductById(productId) {
  return (window._productsCache || []).find(
    p => String(p.id) === String(productId)
  );
}

function getInvoiceProductCategoryId(productId) {
  const product = getInvoiceProductById(productId);
  return product?.category_id ? String(product.category_id) : '';
}

function invoiceCategoryOptionsHtml(selectedCategoryId = '') {
  const categories = window._invoiceCategoriesCache || window._whCategoriesCache || [];

  return categories.map(cat => `
    <option value="${cat.id}" ${String(cat.id) === String(selectedCategoryId) ? 'selected' : ''}>
      ${escHtml(cat.icon || '📦')} ${escHtml(cat.name || '')}
    </option>
  `).join('');
}

function invoiceProductOptionsHtml(categoryId = '', selectedProductId = '') {
  const products = window._productsCache || [];
  const selectedProduct = getInvoiceProductById(selectedProductId);

  let filtered = [];

  if (categoryId) {
    filtered = products.filter(
      p => String(p.category_id || '') === String(categoryId)
    );
  }

  // مهم للتعديل: إذا كانت الفاتورة القديمة فيها صنف، نخليه ظاهر حتى لو تغيرت الفئة
  if (
    selectedProduct &&
    !filtered.some(p => String(p.id) === String(selectedProduct.id))
  ) {
    filtered.unshift(selectedProduct);
  }

  const firstOption = categoryId
    ? '<option value="">اختر صنفاً</option>'
    : '<option value="">اختر الفئة أولاً</option>';

  return firstOption + filtered.map(p => `
    <option value="${p.id}" ${String(p.id) === String(selectedProductId) ? 'selected' : ''}>
      ${escHtml(p.name || '')} — المتوفر: ${p.current_stock ?? 0} ${escHtml(p.unit || '')}
    </option>
  `).join('');
}

function handleInvoiceItemCategoryChange(idx) {
  const categoryId = document.getElementById(`ii_cat_${idx}`)?.value || '';
  const productSelect = document.getElementById(`ii_prod_${idx}`);
  const descEl = document.getElementById(`ii_desc_${idx}`);

  if (!productSelect) return;

  productSelect.innerHTML = invoiceProductOptionsHtml(categoryId, '');
  productSelect.disabled = !categoryId;

  if (descEl && !descEl.dataset.manual) {
    descEl.value = '';
  }

  calcInvoiceItemsTotal();
}

function handleInvoiceProductChange(idx) {
  fillInvoiceDescriptionFromProduct(idx);
  calcInvoiceItemsTotal();
}
function addInvoiceItemRow(item = null) {
  const wrap = document.getElementById('inv-items-wrap');
  if (!wrap) return;

  if (typeof window._invoiceItemIndex !== 'number') {
    window._invoiceItemIndex = 0;
  }

  const idx = window._invoiceItemIndex++;

  const selectedProductId = item?.product_id || '';
  const selectedCategoryId =
    item?.category_id ||
    getInvoiceProductCategoryId(selectedProductId) ||
    '';

  const description = item?.description || item?.product_name || '';

  let qty = Number(item?.quantity || 0);
  const unit = Number(item?.unit_price || 0);
  const lineTotal = Number(item?.line_total || item?.total || (qty * unit) || 0);

  if ((!qty || qty <= 0) && unit > 0 && lineTotal > 0) {
    qty = lineTotal / unit;
  }

  const packQty = Number(item?.package_qty || 12);
  const packPrice = Number(item?.package_price || (unit > 0 ? unit * packQty : 0));

  const row = document.createElement('div');
  row.className = 'invoice-item-row';
  row.dataset.idx = idx;

  row.style.cssText = `
    display:grid;
    grid-template-columns:.85fr 1.4fr 1.3fr .65fr .8fr .8fr .8fr .9fr auto;
    gap:8px;
    align-items:center;
    background:#faf9f7;
    border:1px solid #eee;
    padding:8px 10px;
    border-radius:10px;
  `;

  row.innerHTML = `
    <select
      class="form-select"
      id="ii_cat_${idx}"
      onchange="handleInvoiceItemCategoryChange(${idx})"
    >
      <option value="">اختر الفئة</option>
      ${invoiceCategoryOptionsHtml(selectedCategoryId)}
    </select>

    <select
      class="form-select"
      id="ii_prod_${idx}"
      onchange="handleInvoiceProductChange(${idx})"
      ${selectedCategoryId ? '' : 'disabled'}
    >
      ${invoiceProductOptionsHtml(selectedCategoryId, selectedProductId)}
    </select>

    <input
      class="form-input"
      id="ii_desc_${idx}"
      value="${escHtml(description)}"
      placeholder="البيان / الوصف"
      style="font-weight:600"
      oninput="this.dataset.manual='1'"
    >

    <input
      class="form-input"
      id="ii_qty_${idx}"
      type="number"
      value="${qty ? qty.toFixed(3) : ''}"
      placeholder="الكمية"
      min="0"
      step="0.001"
      oninput="calcInvoiceLineAuto(${idx})"
    >

    <input
      class="form-input"
      id="ii_pack_qty_${idx}"
      type="number"
      value="${packQty ? packQty.toFixed(0) : '12'}"
      placeholder="12"
      min="1"
      step="1"
      title="عدد الحبات في الدزينة أو الكرتونة"
      oninput="calcInvoiceLineAuto(${idx})"
    >

    <input
      class="form-input"
      id="ii_pack_price_${idx}"
      type="number"
      value="${packPrice ? packPrice.toFixed(3) : ''}"
      placeholder="سعر 12"
      min="0"
      step="0.001"
      title="مثلاً: 12 حبة = 13 دينار"
      oninput="calcInvoiceLineFromPack(${idx})"
      style="font-weight:800;color:#9a4500"
    >

    <input
      class="form-input"
      id="ii_price_${idx}"
      type="number"
      value="${unit ? unit.toFixed(3) : ''}"
      placeholder="سعر الحبة"
      min="0"
      step="0.001"
      oninput="calcInvoiceLineFromUnit(${idx})"
    >

    <input
      class="form-input"
      id="ii_total_${idx}"
      type="number"
      value="${lineTotal ? lineTotal.toFixed(3) : ''}"
      placeholder="المجموع"
      min="0"
      step="0.001"
      oninput="calcInvoiceLineFromTotal(${idx})"
      style="font-weight:800;color:#1a4fd6"
    >

    <button
      class="btn btn-danger btn-sm"
      onclick="this.closest('.invoice-item-row').remove(); calcInvoiceItemsTotal()"
    >
      ✕
    </button>

    <div
      id="ii_hint_${idx}"
      style="grid-column:1 / -1; font-size:11px; color:#777; padding:2px 4px"
    >
      اختاري الفئة أولاً، ثم سيظهر فقط أصناف هذه الفئة.
    </div>
  `;

  wrap.appendChild(row);

  if (item) {
    calcInvoiceItemsTotal();
  }
}

function fillInvoiceDescriptionFromProduct(idx) {
  const prodId = document.getElementById(`ii_prod_${idx}`)?.value;
  const descEl = document.getElementById(`ii_desc_${idx}`);

  if (!prodId || !descEl || descEl.value.trim()) return;

  const product = (window._productsCache || []).find(p => String(p.id) === String(prodId));
  if (product) descEl.value = product.name || '';
}

function calcInvoiceLineAuto(idx) {
  const packPrice = parseFloat(document.getElementById(`ii_pack_price_${idx}`)?.value) || 0;

  if (packPrice > 0) {
    calcInvoiceLineFromPack(idx);
  } else {
    calcInvoiceLineFromUnit(idx);
  }
}

function calcInvoiceLineFromPack(idx) {
  const qty = parseFloat(document.getElementById(`ii_qty_${idx}`)?.value) || 0;
  const packQty = parseFloat(document.getElementById(`ii_pack_qty_${idx}`)?.value) || 12;
  const packPrice = parseFloat(document.getElementById(`ii_pack_price_${idx}`)?.value) || 0;

  const priceEl = document.getElementById(`ii_price_${idx}`);
  const totalEl = document.getElementById(`ii_total_${idx}`);
  const hintEl = document.getElementById(`ii_hint_${idx}`);

  if (qty <= 0 || packQty <= 0 || packPrice <= 0) {
    if (priceEl) priceEl.value = '';
    if (totalEl) totalEl.value = '';
    calcInvoiceItemsTotal();
    return;
  }

  const unitPrice = packPrice / packQty;
  const lineTotal = qty * unitPrice;

  if (priceEl) priceEl.value = unitPrice.toFixed(3);
  if (totalEl) totalEl.value = lineTotal.toFixed(3);

  if (hintEl) {
    hintEl.textContent =
      `سعر ${packQty} حبة = ${packPrice.toFixed(3)} د.أ — سعر الحبة = ${unitPrice.toFixed(3)} — الكمية ${qty.toFixed(3)} = ${lineTotal.toFixed(3)} د.أ`;
  }

  calcInvoiceItemsTotal();
}

function calcInvoiceLineFromUnit(idx) {
  const qty = parseFloat(document.getElementById(`ii_qty_${idx}`)?.value) || 0;
  const unitPrice = parseFloat(document.getElementById(`ii_price_${idx}`)?.value) || 0;

  const packPriceEl = document.getElementById(`ii_pack_price_${idx}`);
  const totalEl = document.getElementById(`ii_total_${idx}`);
  const hintEl = document.getElementById(`ii_hint_${idx}`);

  if (packPriceEl) packPriceEl.value = '';

  const lineTotal = qty * unitPrice;

  if (totalEl) {
    totalEl.value = lineTotal > 0 ? lineTotal.toFixed(3) : '';
  }

  if (hintEl) {
    hintEl.textContent = 'السعر محسوب من سعر الحبة مباشرة.';
  }

  calcInvoiceItemsTotal();
}

function calcInvoiceLineFromTotal(idx) {
  const qty = parseFloat(document.getElementById(`ii_qty_${idx}`)?.value) || 0;
  const lineTotal = parseFloat(document.getElementById(`ii_total_${idx}`)?.value) || 0;

  const priceEl = document.getElementById(`ii_price_${idx}`);
  const packPriceEl = document.getElementById(`ii_pack_price_${idx}`);
  const hintEl = document.getElementById(`ii_hint_${idx}`);

  if (packPriceEl) packPriceEl.value = '';

  if (priceEl) {
    if (qty > 0 && lineTotal > 0) {
      priceEl.value = (lineTotal / qty).toFixed(3);
    } else {
      priceEl.value = '';
    }
  }

  if (hintEl) {
    hintEl.textContent = 'السعر محسوب من المجموع ÷ الكمية.';
  }

  calcInvoiceItemsTotal();
}

function calcInvoiceItemsTotal() {
  let total = 0;

  document.querySelectorAll('.invoice-item-row').forEach(row => {
    const idx = row.dataset.idx;

    const qty = parseFloat(document.getElementById(`ii_qty_${idx}`)?.value) || 0;
    const unitPrice = parseFloat(document.getElementById(`ii_price_${idx}`)?.value) || 0;
    const lineTotalInput = parseFloat(document.getElementById(`ii_total_${idx}`)?.value) || 0;

    const lineTotal = lineTotalInput > 0 ? lineTotalInput : qty * unitPrice;
    total += lineTotal;
  });

  const el = document.getElementById('inv_total_display');
  if (el) el.textContent = `${fmt(total)} د.أ`;

  handleInvoicePaymentChange();
}



function calcInvoiceLineFromTotal(idx) {
  const qty = parseFloat(document.getElementById(`ii_qty_${idx}`)?.value) || 0;
  const lineTotal = parseFloat(document.getElementById(`ii_total_${idx}`)?.value) || 0;
  const priceEl = document.getElementById(`ii_price_${idx}`);

  if (priceEl) {
    if (qty > 0 && lineTotal > 0) {
      priceEl.value = (lineTotal / qty).toFixed(3);
    } else {
      priceEl.value = '';
    }
  }

  calcInvoiceItemsTotal();
}




function calcInvoiceLineFromTotal(idx) {
  const qty = parseFloat(document.getElementById(`ii_qty_${idx}`)?.value) || 0;
  const lineTotal = parseFloat(document.getElementById(`ii_total_${idx}`)?.value) || 0;
  const priceEl = document.getElementById(`ii_price_${idx}`);

  if (priceEl) {
    if (qty > 0 && lineTotal > 0) {
      priceEl.value = (lineTotal / qty).toFixed(3);
    } else {
      priceEl.value = '';
    }
  }

  calcInvoiceItemsTotal();
}

function calcInvoiceItemsTotal() {
  let total = 0;

  document.querySelectorAll('.invoice-item-row').forEach(row => {
    const idx = row.dataset.idx;
    const qty = parseFloat(document.getElementById(`ii_qty_${idx}`)?.value) || 0;
    const unitPrice = parseFloat(document.getElementById(`ii_price_${idx}`)?.value) || 0;
    const lineTotalInput = parseFloat(document.getElementById(`ii_total_${idx}`)?.value) || 0;

    const lineTotal = lineTotalInput > 0 ? lineTotalInput : qty * unitPrice;
    total += lineTotal;
  });

  const el = document.getElementById('inv_total_display');
  if (el) el.textContent = `${fmt(total)} د.أ`;

  handleInvoicePaymentChange();
}

function calcInvoiceTax() {
  const net = parseFloat(document.getElementById('inv_net')?.value) || 0;
  const tax = parseFloat(document.getElementById('inv_tax')?.value) || 0;
  const total = net + (net * tax / 100);
  const el = document.getElementById('inv_total_display');
  if (el) el.textContent = `${fmt(total)} د.أ`;
  handleInvoicePaymentChange();
}

async function saveInvoice() {
  if (window._invoiceSaving) {
    toast('جاري حفظ الفاتورة... انتظري', 'warning');
    return;
  }

  const btn = document.getElementById('save-invoice-btn');
  const invoiceId = window._editingInvoiceId || null;

  const client_id = null;

  const hasItems = document.getElementById('inv_has_items')?.checked;
  const invNum = document.getElementById('inv_num')?.value.trim() || `INV-${Date.now()}`;
  const taxRate = parseFloat(document.getElementById('inv_tax')?.value) || 0;
  const paymentMethod = document.getElementById('inv_pay')?.value || 'credit';

  let net = 0;
  let tax = 0;
  let total = 0;
  const items = [];

  if (hasItems) {
    document.querySelectorAll('.invoice-item-row').forEach(row => {
      const idx = row.dataset.idx;

      const product_id = document.getElementById(`ii_prod_${idx}`)?.value;
      const description = document.getElementById(`ii_desc_${idx}`)?.value?.trim() || '';
      let quantity = parseFloat(document.getElementById(`ii_qty_${idx}`)?.value);
      let unit_price = parseFloat(document.getElementById(`ii_price_${idx}`)?.value);
      let line_total = parseFloat(document.getElementById(`ii_total_${idx}`)?.value);

      const package_qty = parseFloat(document.getElementById(`ii_pack_qty_${idx}`)?.value) || 12;
      const package_price = parseFloat(document.getElementById(`ii_pack_price_${idx}`)?.value) || 0;

      if ((!quantity || quantity <= 0) && unit_price > 0 && line_total > 0) {
        quantity = line_total / unit_price;
      }

      if ((!line_total || line_total <= 0) && quantity > 0 && unit_price >= 0) {
        line_total = quantity * unit_price;
      }

      if (product_id && quantity > 0) {
        if ((!unit_price || unit_price <= 0) && line_total > 0) {
          unit_price = line_total / quantity;
        }

        if (unit_price >= 0 && line_total >= 0) {
          items.push({
            product_id: product_id || null,
            description,
            quantity: Number(quantity.toFixed(3)),
            unit_price: Number(unit_price.toFixed(3)),
            line_total: Number(line_total.toFixed(3)),
            package_qty: Number(package_qty.toFixed(3)),
            package_price: package_price > 0 ? Number(package_price.toFixed(3)) : null
          });
        }
      }
    });

    if (!items.length) {
      toast('أضف صنفاً واحداً على الأقل', 'error');
      return;
    }

    net = Number(items.reduce((sum, item) => sum + Number(item.line_total || item.quantity * item.unit_price || 0), 0).toFixed(3));
    tax = net * taxRate / 100;
    total = net + tax;
  } else {
    net = parseFloat(document.getElementById('inv_net')?.value);
    if (!net || net <= 0) {
      toast('المبلغ غير صحيح', 'error');
      return;
    }
    tax = net * taxRate / 100;
    total = net + tax;
  }

  net = Number(net.toFixed(3));
  tax = Number(tax.toFixed(3));
  total = Number(total.toFixed(3));

  let paidAmount = parseFloat(document.getElementById('inv_paid')?.value) || 0;
  if (paymentMethod === 'cash') paidAmount = total;
  if (paymentMethod === 'credit') paidAmount = 0;

  paidAmount = Number(paidAmount.toFixed(3));

  if (paidAmount < 0 || paidAmount > total) {
    toast('المبلغ المدفوع غير صحيح', 'error');
    return;
  }

  const recipientName = document.getElementById('inv_recipient')?.value?.trim() || '';
  if (!recipientName) {
    toast('اسم الزبون / مطلوب من السادة مطلوب', 'error');
    return;
  }
  const normalNotes = document.getElementById('inv_notes')?.value?.trim() || '';

  const payload = {
    client_id,
    invoice_number: invNum,
    net_amount: net,
    tax_amount: tax,
    total_amount: total,
    paid_amount: paidAmount,
    invoice_date: document.getElementById('inv_date')?.value,
    payment_method: paymentMethod,

    // مهم: صار اسم الزبون محفوظ بعمود مستقل، وليس فقط notes
    recipient_name: recipientName || undefined,

    notes: [
      recipientName ? `المطلوب من السادة: ${recipientName}` : '',
      normalNotes
    ].filter(Boolean).join(' | ') || undefined,

    items: items.length ? items : undefined,
  };

  window._invoiceSaving = true;
  if (btn) { btn.disabled = true; btn.dataset.oldText = btn.textContent; btn.textContent = 'جاري الحفظ...'; btn.style.opacity = '0.65'; }

  try {
    let result;
    if (invoiceId) {
      result = await API.updateInvoice(invoiceId, payload);
      toast('تم تعديل الفاتورة ✅', 'success');
    } else {
      result = await API.createInvoice(payload);
      toast('تمت إضافة الفاتورة ✅', 'success');
    }
    closeModal();

    const tbody = document.getElementById('inv-tbody');
    if (tbody && result) {
      result.client_name = result.client_name ||
        (window._clientsCache || []).find(c => c.id === result.client_id)?.name || '—';
      if (invoiceId) {
        const existing = document.querySelector(`#inv-tbody tr[data-invoice-id="${invoiceId}"]`);
        if (existing) existing.outerHTML = renderInvoiceRow(result);
      } else {
        const empty = tbody.querySelector('td[colspan]');
        if (empty) tbody.innerHTML = '';
        tbody.insertAdjacentHTML('afterbegin', renderInvoiceRow(result));
        const sub = document.querySelector('.page-sub');
        if (sub) sub.textContent = `${tbody.children.length} فاتورة مسجّلة`;
      }
    }
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    window._invoiceSaving = false;
    if (btn) { btn.disabled = false; btn.textContent = btn.dataset.oldText || 'حفظ الفاتورة'; btn.style.opacity = '1'; }
  }
}

async function deleteInvoice(id) {
  if (!confirm('حذف الفاتورة؟')) return;
  const row = document.querySelector(`#inv-tbody tr[data-invoice-id="${id}"]`);
  if (row) { row.style.opacity = '0.4'; row.style.pointerEvents = 'none'; }
  try {
    await API.deleteInvoice(id);
    toast('تم الحذف ✅', 'success');
    if (row) {
      row.style.transition = 'opacity 0.25s';
      row.style.opacity = '0';
      setTimeout(() => {
        row.remove();
        const tbody = document.getElementById('inv-tbody');
        const sub = document.querySelector('.page-sub');
        if (sub && tbody) sub.textContent = `${tbody.children.length} فاتورة مسجّلة`;
      }, 280);
    }
  } catch (e) {
    if (row) { row.style.opacity = '1'; row.style.pointerEvents = ''; }
    toast(e.message, 'error');
  }
}

async function approveInvoice(id) {
  if (!confirm('اعتماد هذه الفاتورة؟ سيتم خصم الكميات من المستودع فوراً.')) return;

  const row = document.querySelector(`#inv-tbody tr[data-invoice-id="${id}"]`);
  if (row) { row.style.opacity = '0.5'; row.style.pointerEvents = 'none'; }

  try {
    const result = await API.approveInvoice(id);
    toast('✅ تمت الموافقة على الفاتورة — تم خصم المخزون', 'success');

    // Update cache
    if (window._invoicesCache) {
      const idx = window._invoicesCache.findIndex(i => i.id === id);
      if (idx !== -1) window._invoicesCache[idx] = { ...window._invoicesCache[idx], ...result };
    }

    if (row && result) {
      // preserve client_name if not in result
      if (!result.client_name) {
        result.client_name = row.querySelector('td:nth-child(2)')?.textContent?.trim() || '—';
      }
      row.outerHTML = renderInvoiceRow(result);
    }

    // Refresh pending count badge in tab
    const pending = (window._invoicesCache || []).filter(i => (i.status || 'approved') === 'pending').length;
    const tabEl = document.getElementById('inv-tab-pending');
    if (tabEl) {
      if (pending === 0) tabEl.remove();
      else tabEl.textContent = `⏳ انتظار (${pending})`;
    }
    // Remove warning banner if no more pending
    if (pending === 0) {
      document.querySelectorAll('.alert-warning').forEach(el => {
        if (el.textContent.includes('بانتظار موافقتك')) el.remove();
      });
    }

  } catch (e) {
    if (row) { row.style.opacity = '1'; row.style.pointerEvents = ''; }
    toast(e.message, 'error');
  }
}

function rejectInvoiceModal(id) {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">✗ رفض الفاتورة</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="alert alert-info" style="margin-bottom:16px">
      لن يتأثر المخزون. الفاتورة ستُحفظ كمرفوضة وسيُبلَّغ الموظف.
    </div>
    <div class="form-group">
      <label class="form-label">سبب الرفض *</label>
      <input class="form-input" id="rej_reason" placeholder="مثال: بيانات الصنف غير صحيحة، الكمية تجاوزت المخزون..." autofocus>
    </div>
    <div style="display:flex;gap:10px;margin-top:8px">
      <button class="btn btn-danger" style="flex:1" id="rej-confirm-btn" onclick="doRejectInvoice(${id})">
        تأكيد الرفض
      </button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
  document.getElementById('rej_reason')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') doRejectInvoice(id);
  });
}

async function doRejectInvoice(id) {
  const reason = document.getElementById('rej_reason')?.value?.trim();
  if (!reason) { toast('سبب الرفض مطلوب', 'error'); return; }

  const btn = document.getElementById('rej-confirm-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'جاري الرفض...'; }

  try {
    const result = await API.rejectInvoice(id, reason);
    toast('تم رفض الفاتورة', 'success');
    closeModal();

    // Update cache
    if (window._invoicesCache) {
      const idx = window._invoicesCache.findIndex(i => i.id === id);
      if (idx !== -1) window._invoicesCache[idx] = { ...window._invoicesCache[idx], ...result };
    }

    const row = document.querySelector(`#inv-tbody tr[data-invoice-id="${id}"]`);
    if (row && result) {
      if (!result.client_name) {
        result.client_name = row.querySelector('td:nth-child(2)')?.textContent?.trim() || '—';
      }
      row.outerHTML = renderInvoiceRow(result);
    }

    // Update pending tab count
    const pending = (window._invoicesCache || []).filter(i => (i.status || 'approved') === 'pending').length;
    const tabEl = document.getElementById('inv-tab-pending');
    if (tabEl) {
      if (pending === 0) tabEl.remove();
      else tabEl.textContent = `⏳ انتظار (${pending})`;
    }

  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = 'تأكيد الرفض'; }
    toast(e.message, 'error');
  }
}

function renderPaymentRow(p) {
  return `<tr data-payment-id="${p.id}">
    <td><strong>${escHtml(p.client_name || '—')}</strong></td>
    <td style="color:var(--gr);font-weight:700">+${fmt(p.amount)} د.أ</td>
    <td>${payMethodBadge(p.payment_method || 'cash')}</td>
    <td style="font-size:12px;color:var(--tx3)">${fmtDate(p.payment_date)}</td>
    <td style="color:var(--tx2);font-size:12px">${escHtml(
    (p.notes || '').replace(/invoice_id:\d+\s*\|?\s*/g, '').replace(/method:\w+/g, '').trim() || '—'
  )}</td>
    <td>${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deletePayment(${p.id})">🗑️</button>` : ''}</td>
  </tr>`;
}
async function renderPayments(container) {
  let payments = [];
  try { payments = await API.getPayments() || []; } catch (e) { payments = []; }

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">المقبوضات</div>
        <div class="page-sub">${payments.length} عملية مسجّلة</div>
      </div>
      <div style="display:flex; gap:10px">
        ${isAccountant() ? `<button class="btn btn-success" onclick="openPaymentModal()">+ تسجيل مقبوضة</button>` : ''}
        <button class="btn btn-ghost btn-sm" onclick="printPaymentsFromEncoded(${jsString(encodePayload(payments))})">🖨️</button>
      </div>
    </div>

    <div class="card" style="padding:0; overflow:hidden">
      <div class="table-wrap">
        <table>
          <thead><tr><th>العميل</th><th>المبلغ</th><th>طريقة الدفع</th><th>التاريخ</th><th>ملاحظات</th><th>الإجراءات</th></tr></thead>
          ${payments.length
      ? payments.map(renderPaymentRow).join('')
      : emptyRow('لا توجد مقبوضات', 6)}
        </table>
      </div>
    </div>
  `;
}

function openPaymentModal(clientId = null, invoiceId = null) {
  window._paymentInvoiceId = invoiceId || null;

  const clientOpts = (window._clientsCache || [])
    .map(c => `<option value="${c.id}" ${c.id == clientId ? 'selected' : ''}>${escHtml(c.name)}</option>`)
    .join('');

  openModal(`
    <div class="modal-header">
      <div class="modal-title">${invoiceId ? '💰 قبض على فاتورة' : '💰 تسجيل مقبوضة'}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>

    ${invoiceId ? `
      <div class="alert alert-info">
        هذه الدفعة ستُربط مباشرة بالفاتورة رقم: <strong>#${invoiceId}</strong>
      </div>
    ` : `
      <div class="alert alert-warning">
        هذه دفعة عامة للعميل. إذا أردتِ أن تنعكس على فاتورة محددة، افتحي الدفعة من زر "قبض للفاتورة" داخل صفحة الفواتير.
      </div>
    `}

    <div class="form-group">
  <label class="form-label">كتبها الموظف</label>
  <input class="form-input" value="${escHtml((getUser() || {}).full_name || '—')}" disabled>
</div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">المبلغ (د.أ) *</label>
        <input class="form-input" id="pay_amount" type="number" step="0.001" placeholder="0.000">
      </div>

      <div class="form-group">
        <label class="form-label">طريقة الدفع</label>
        <select class="form-select" id="pay_method">
          <option value="cash">نقداً</option>
          <option value="check">شيك</option>
          <option value="transfer">حوالة</option>
        </select>
      </div>
    </div>

    <div class="form-group">
      <label class="form-label">تاريخ القبض</label>
      <input class="form-input" id="pay_date" type="date" value="${new Date().toISOString().split('T')[0]}">
    </div>

    <div class="form-group">
      <label class="form-label">ملاحظات</label>
      <input class="form-input" id="pay_notes" placeholder="اختياري">
    </div>

    <div style="display:flex; gap:10px; margin-top:8px">
      <button class="btn btn-success" style="flex:1" onclick="savePayment()">تسجيل المقبوضة</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);

  if (!window._clientsCache || !window._clientsCache.length) {
    API.getClients().then(cls => {
      window._clientsCache = cls || [];
      const sel = document.getElementById('pay_client');
      if (sel) {
        sel.innerHTML =
          '<option value="">اختر عميلاً</option>' +
          cls.map(c => `<option value="${c.id}" ${c.id == clientId ? 'selected' : ''}>${escHtml(c.name)}</option>`).join('');
      }
    }).catch(() => { });
  }
}

function openQuickPayment(id) {
  openPaymentModal(id, null);
}

async function savePayment() {
  const client_id = document.getElementById('pay_client')?.value;
  const amount = parseFloat(document.getElementById('pay_amount')?.value);
  if (!client_id) { toast('الرجاء اختيار عميل', 'error'); return; }
  if (!amount || amount <= 0) { toast('المبلغ غير صحيح', 'error'); return; }

  const btn = document.querySelector('#global-modal .btn-success');
  if (btn) { btn.disabled = true; btn.textContent = 'جاري الحفظ...'; }

  try {
    const result = await API.createPayment({
      client_id: Number(client_id),
      invoice_id: window._paymentInvoiceId || null,
      amount: Number(amount.toFixed(3)),
      payment_method: document.getElementById('pay_method')?.value || 'cash',
      payment_date: document.getElementById('pay_date')?.value,
      notes: document.getElementById('pay_notes')?.value || null,
    });
    toast('تم تسجيل المقبوضة بنجاح ✅', 'success');
    closeModal();

    // Attach client name from cache
    result.client_name = (window._clientsCache || []).find(c => c.id === result.client_id)?.name || '—';
    result.payment_method = document.getElementById('pay_method')?.value || 'cash';

    if (window._paymentInvoiceId) {
      window._paymentInvoiceId = null;
      // Refresh the invoice row's paid/remaining amounts
      navigateTo('invoices');
    } else {
      const tbody = document.getElementById('pay-tbody');
      if (tbody) {
        const empty = tbody.querySelector('td[colspan]');
        if (empty) tbody.innerHTML = '';
        tbody.insertAdjacentHTML('afterbegin', renderPaymentRow(result));
        const sub = document.querySelector('.page-sub');
        if (sub) sub.textContent = `${tbody.children.length} عملية مسجّلة`;
      }
    }
  } catch (e) {
    toast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'تسجيل المقبوضة'; }
  }
}
async function deletePayment(id) {
  if (!confirm('حذف هذه المقبوضة؟')) return;
  const row = document.querySelector(`#pay-tbody tr[data-payment-id="${id}"]`);
  if (row) { row.style.opacity = '0.4'; row.style.pointerEvents = 'none'; }
  try {
    await API.deletePayment(id);
    toast('تم الحذف ✅', 'success');
    if (row) {
      row.style.transition = 'opacity 0.25s';
      row.style.opacity = '0';
      setTimeout(() => row.remove(), 280);
    }
  } catch (e) {
    if (row) { row.style.opacity = '1'; row.style.pointerEvents = ''; }
    toast(e.message, 'error');
  }
}

/* ═══════════════════════════════════════════════════
   CHECKS
═══════════════════════════════════════════════════ */

function renderCheckRow(ch) {
  const today = new Date().toISOString().split('T')[0];
  const isOverdue = ch.status === 'pending' && (ch.due_date || '').split('T')[0] < today;
  return `<tr data-check-id="${ch.id}" style="${isOverdue ? 'background:#fff5f5' : ''}">
    <td><strong>${escHtml(ch.client_name || '—')}</strong></td>
    <td style="font-family:monospace;font-size:13px">${escHtml(ch.check_number || '—')}</td>
    <td style="font-weight:700">${fmt(ch.amount)} د.أ</td>
    <td style="${isOverdue ? 'color:var(--rd);font-weight:700' : 'color:var(--tx2);font-size:12px'}">${fmtDate(ch.due_date)}${isOverdue ? ' ⚠️' : ''}</td>
    <td>${checkStatusBadge(ch.status)}</td>
    <td>
      <div style="display:flex;gap:6px">
        ${ch.status === 'pending' && isAccountant() ? `
          <button class="btn btn-success btn-sm" onclick="updateCheck(${ch.id},'cashed')">✅ تحصيل</button>
          <button class="btn btn-ghost btn-sm" onclick="updateCheck(${ch.id},'returned')">↩️ راجع</button>` : ''}
        ${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deleteCheck(${ch.id})">🗑️</button>` : ''}
      </div>
    </td>
  </tr>`;
}
async function renderChecks(container) {
  let checks = [];
  try { checks = await API.getChecks() || []; } catch (e) { checks = []; }

  const today = new Date().toISOString().split('T')[0];
  const pending = checks.filter(c => c.status === 'pending');
  const overdue = pending.filter(c => c.due_date?.split('T')[0] < today);

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">الشيكات</div>
        <div class="page-sub">${pending.length} شيك معلّق ${overdue.length ? `— <span style="color:var(--rd)">${overdue.length} متأخر</span>` : ''}</div>
      </div>
      <div style="display:flex; gap:10px">
        ${isAccountant() ? `<button class="btn btn-primary" onclick="openCheckModal()">+ إضافة شيك</button>` : ''}
        <button class="btn btn-ghost btn-sm" onclick="printChecksFromEncoded(${jsString(encodePayload(checks))})">🖨️</button>
      </div>
    </div>

    ${overdue.length ? `<div class="alert alert-danger">⚠️ يوجد ${overdue.length} شيك متأخر — يرجى المتابعة الفورية</div>` : ''}

    <div class="card" style="padding:0; overflow:hidden">
      <div class="table-wrap">
        <table>
          <thead><tr><th>العميل</th><th>رقم الشيك</th><th>المبلغ</th><th>تاريخ الاستحقاق</th><th>الحالة</th><th>الإجراءات</th></tr></thead>
          ${checks.length
      ? checks.map(renderCheckRow).join('')
      : emptyRow('لا توجد شيكات', 6)}
        </table>
      </div>
    </div>
  `;
}

function openCheckModal() {
  const clientOpts = (window._clientsCache || []).map(c => `<option value="${c.id}">${escHtml(c.name)}</option>`).join('');

  openModal(`
    <div class="modal-header">
      <div class="modal-title">🏦 إضافة شيك جديد</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-group">
      <label class="form-label">العميل *</label>
      <select class="form-select" id="chk_client">
        <option value="">اختر عميلاً</option>
        ${clientOpts}
      </select>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">رقم الشيك *</label>
        <input class="form-input" id="chk_num" placeholder="XXXXXXXX">
      </div>
      <div class="form-group">
        <label class="form-label">المبلغ (د.أ) *</label>
        <input class="form-input" id="chk_amount" type="number" placeholder="0.00">
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">تاريخ الاستحقاق *</label>
        <input class="form-input" id="chk_due" type="date">
      </div>
      <div class="form-group">
        <label class="form-label">اسم البنك</label>
        <input class="form-input" id="chk_bank" placeholder="مثال: البنك العربي">
      </div>
    </div>
    <div style="display:flex; gap:10px; margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="saveCheck()">حفظ الشيك</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);

  if (!window._clientsCache || !window._clientsCache.length) {
    API.getClients().then(cls => {
      window._clientsCache = cls || [];
      const sel = document.getElementById('chk_client');
      if (sel) {
        sel.innerHTML = '<option value="">اختر عميلاً</option>' +
          cls.map(c => `<option value="${c.id}">${escHtml(c.name)}</option>`).join('');
      }
    }).catch(() => { });
  }
}

async function saveCheck() {
  const client_id = document.getElementById('chk_client')?.value;
  const amount = parseFloat(document.getElementById('chk_amount')?.value);
  const due_date = document.getElementById('chk_due')?.value;
  const check_number = document.getElementById('chk_num')?.value?.trim();

  if (!client_id || !amount || !due_date || !check_number) {
    toast('يرجى ملء الحقول المطلوبة', 'error');
    return;
  }
  const btn = document.querySelector('#global-modal .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = 'جاري الحفظ...'; }

  try {
    const result = await API.createCheck({
      client_id,
      amount,
      due_date,
      check_number,
      bank_name: document.getElementById('chk_bank')?.value || null,
    });
    toast('تمت إضافة الشيك ✅', 'success');
    closeModal();

    result.client_name = (window._clientsCache || []).find(c => String(c.id) === String(client_id))?.name || '—';
    result.status = result.status || 'pending';

    const tbody = document.querySelector('#checks-table tbody, tbody');
    // use data attribute lookup to find the checks tbody reliably
    const allTbodies = document.querySelectorAll('tbody');
    let checksTbody = null;
    allTbodies.forEach(tb => {
      if (tb.querySelector('tr[data-check-id]') || (tb.id && tb.id.includes('check'))) {
        checksTbody = tb;
      }
    });
    if (!checksTbody && allTbodies.length) checksTbody = allTbodies[0];

    if (checksTbody) {
      const empty = checksTbody.querySelector('td[colspan]');
      if (empty) checksTbody.innerHTML = '';
      checksTbody.insertAdjacentHTML('afterbegin', renderCheckRow(result));
    }
  } catch (e) {
    toast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'حفظ الشيك'; }
  }
}

async function updateCheck(id, status) {
  try {
    const updated = await API.updateCheckStatus(id, status);
    toast(status === 'cashed' ? 'تم تحصيل الشيك ✅' : 'تم تسجيل الشيك مرتجعاً', 'success');
    // preserve client_name
    const existingRow = document.querySelector(`tr[data-check-id="${id}"]`);
    if (existingRow) {
      const clientCell = existingRow.querySelector('td:first-child strong');
      if (clientCell) updated.client_name = clientCell.textContent;
    }
    if (existingRow) existingRow.outerHTML = renderCheckRow(updated);
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteCheck(id) {
  if (!confirm('حذف هذا الشيك؟')) return;
  const row = document.querySelector(`tr[data-check-id="${id}"]`);
  if (row) { row.style.opacity = '0.4'; row.style.pointerEvents = 'none'; }
  try {
    await API.deleteCheck(id);
    toast('تم الحذف ✅', 'success');
    if (row) {
      row.style.transition = 'opacity 0.25s';
      row.style.opacity = '0';
      setTimeout(() => row.remove(), 280);
    }
  } catch (e) {
    if (row) { row.style.opacity = '1'; row.style.pointerEvents = ''; }
    toast(e.message, 'error');
  }
}

/* ═══════════════════════════════════════════════════
   PURCHASES — المشتريات
═══════════════════════════════════════════════════ */
async function renderPurchases(container) {
  let purchases = [], suppliers = [];
  try {
    [purchases, suppliers] = await Promise.all([API.getPurchases(), API.getSuppliers()]);
  } catch (e) { purchases = []; suppliers = []; }

  window._suppliersCache = suppliers;

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">🛒 المشتريات والموردين</div>
        <div class="page-sub">${purchases.length} فاتورة شراء — ${suppliers.length} مورد</div>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap">
        <div class="search-bar">
          <span>🔍</span>
          <input type="text" placeholder="بحث..." oninput="filterTable('pur-tbody', this.value)">
        </div>
        ${isAccountant() ? `<button class="btn btn-primary" onclick="openPurchaseModal()">+ فاتورة شراء</button>` : ''}
        ${isAccountant() ? `<button class="btn btn-ghost" onclick="openAddSupplierModal()">+ مورد جديد</button>` : ''}
      </div>
    </div>

    <!-- الموردين وأرصدتهم -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">🏪 الموردين — الذمم</div>
      <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(220px,1fr)); gap:10px; margin-top:8px">
        ${suppliers.length ? suppliers.map(s => {
    const balance = parseFloat(s.balance || 0);
    return `
            <div style="border:1px solid var(--brd); border-radius:10px; padding:12px 14px; background:${balance > 0 ? '#fff8ee' : '#fff'}">
              <div style="font-weight:700; font-size:14px">${escHtml(s.name)}</div>
              ${s.phone ? `<div style="font-size:11px; color:var(--tx3)">${escHtml(s.phone)}</div>` : ''}
              <div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center">
                <div>
                  <div style="font-size:10px; color:var(--tx3)">متبقي له</div>
                  <div style="font-size:16px; font-weight:800; color:${balance > 0 ? 'var(--rd)' : 'var(--gr)'}">${fmt(balance)} د.أ</div>
                </div>
                <div style="display:flex; gap:4px">
                  <button class="btn btn-ghost btn-sm" onclick="viewSupplierStatement(${s.id}, ${jsString(s.name)})">📄</button>
                  ${isAccountant() && balance > 0 ? `<button class="btn btn-primary btn-sm" onclick="openSupplierPaymentModal(${s.id}, ${jsString(s.name)})">💰 دفع</button>` : ''}
                </div>
              </div>
            </div>
          `;
  }).join('') : '<div style="color:var(--tx3); font-size:13px">لا يوجد موردون مسجّلون</div>'}
      </div>
    </div>

    <!-- فواتير الشراء -->
    <div class="card" style="padding:0; overflow:hidden">
      <div style="padding:14px 18px; border-bottom:1px solid var(--brd); font-weight:700">فواتير الشراء</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>رقم الفاتورة</th><th>المورد</th><th>الإجمالي</th>
              <th>التاريخ</th><th>الحالة</th><th>الإجراءات</th>
            </tr>
          </thead>
          <tbody id="pur-tbody">
            ${purchases.length ? purchases.map(p => `
              <tr>
                <td><strong>#${escHtml(p.invoice_number || p.id)}</strong></td>
                <td>${escHtml(p.supplier_name || '—')}</td>
                <td style="font-weight:700">${fmt(p.total)} د.أ</td>
                <td style="font-size:12px; color:var(--tx3)">${fmtDate(p.date)}</td>
                <td>${purchaseStatusBadge(p.status)}</td>
                <td>
                  <div style="display:flex; gap:6px">
                    <button class="btn btn-ghost btn-sm" onclick="viewPurchaseItems(${p.id})">📋 الأصناف</button>
                    ${p.status === 'pending' && isAccountant() ? `<button class="btn btn-success btn-sm" onclick="confirmReceive(${p.id})">✅ استلام</button>` : ''}
                    ${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deletePurchase(${p.id})">🗑️</button>` : ''}
                  </div>
                </td>
              </tr>
            `).join('') : `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--tx3)">لا توجد فواتير شراء</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function openPurchaseModal() {
  const supplierOpts = (window._suppliersCache || [])
    .map(s => `<option value="${s.id}">${escHtml(s.name)}</option>`)
    .join('');

  openModal(`
    <div class="modal-header">
      <div class="modal-title">🛒 فاتورة شراء جديدة</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">المورد</label>
        <select class="form-select" id="pur_supplier">
          <option value="">اختر مورداً</option>
          ${supplierOpts}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">رقم الفاتورة</label>
        <input class="form-input" id="pur_num" placeholder="تلقائي إن تُرك فارغاً">
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">التاريخ</label>
        <input class="form-input" id="pur_date" type="date" value="${new Date().toISOString().split('T')[0]}">
      </div>
      <div class="form-group">
        <label class="form-label">ملاحظات</label>
        <input class="form-input" id="pur_notes" placeholder="اختياري">
      </div>
    </div>

    <div style="margin:16px 0 8px; font-weight:700; font-size:13px">📦 الأصناف</div>
    <div id="pur-items-wrap" style="display:flex; flex-direction:column; gap:8px"></div>
    <button class="btn btn-ghost btn-sm" style="margin-top:8px" onclick="addPurchaseItemRow()">+ إضافة صنف</button>

    <div style="margin-top:16px; padding:12px; background:var(--bll); border-radius:var(--r); display:flex; justify-content:space-between; align-items:center">
      <span style="font-weight:700; color:var(--tx2)">الإجمالي</span>
      <span style="font-size:18px; font-weight:800; color:var(--bld)" id="pur_total">0.00 د.أ</span>
    </div>

    <div style="display:flex; gap:10px; margin-top:16px">
      <button class="btn btn-primary" style="flex:1" onclick="savePurchase()">حفظ الفاتورة</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `, '620px');

  API.getProducts().then(prods => {
    window._productsCache = prods || [];
    addPurchaseItemRow();
  }).catch(() => {
    window._productsCache = [];
    addPurchaseItemRow();
  });
}

function addPurchaseItemRow() {
  const wrap = document.getElementById('pur-items-wrap');
  if (!wrap) return;

  const idx = wrap.children.length;
  const prodOpts = (window._productsCache || [])
    .map(p => `<option value="${p.id}" data-unit="${escHtml(p.unit)}">${escHtml(p.name)}</option>`)
    .join('');

  const row = document.createElement('div');
  row.style.cssText = 'display:grid; grid-template-columns:2fr 1fr 1fr 1fr auto; gap:8px; align-items:center';
  row.innerHTML = `
    <select class="form-select" id="pi_prod_${idx}" onchange="calcPurchaseTotal()">
      <option value="">اختر صنفاً</option>
      ${prodOpts}
    </select>
    <input class="form-input" id="pi_qty_${idx}" type="number" placeholder="الكمية" min="0.001" step="0.001" oninput="calcPurchaseTotal()">
    <input class="form-input" id="pi_price_${idx}" type="number" placeholder="السعر" min="0" step="0.01" oninput="calcPurchaseTotal()">
    <div id="pi_subtotal_${idx}" style="padding:10px; background:var(--bg); border-radius:var(--r); font-size:12px; font-weight:700; color:var(--tx2); text-align:center">0.00</div>
    <button class="btn btn-danger btn-sm" onclick="this.parentElement.remove(); calcPurchaseTotal()">✕</button>
  `;
  wrap.appendChild(row);
}

function calcPurchaseTotal() {
  const wrap = document.getElementById('pur-items-wrap');
  if (!wrap) return;

  let total = 0;
  for (let i = 0; i < 50; i++) {
    const qty = parseFloat(document.getElementById(`pi_qty_${i}`)?.value) || 0;
    const price = parseFloat(document.getElementById(`pi_price_${i}`)?.value) || 0;
    const sub = qty * price;
    const subEl = document.getElementById(`pi_subtotal_${i}`);
    if (subEl) subEl.textContent = fmt(sub);
    total += sub;
  }

  const el = document.getElementById('pur_total');
  if (el) el.textContent = `${fmt(total)} د.أ`;
}

async function savePurchase() {
  const wrap = document.getElementById('pur-items-wrap');
  if (!wrap) return;

  const items = [];
  for (let i = 0; i < 50; i++) {
    const prodEl = document.getElementById(`pi_prod_${i}`);
    const qtyEl = document.getElementById(`pi_qty_${i}`);
    const priceEl = document.getElementById(`pi_price_${i}`);
    if (!prodEl) continue;

    const product_id = prodEl.value;
    const quantity = parseFloat(qtyEl?.value);
    const unit_price = parseFloat(priceEl?.value);

    if (product_id && quantity > 0 && unit_price >= 0) {
      items.push({ product_id, quantity, unit_price });
    }
  }

  if (!items.length) {
    toast('أضف صنفاً واحداً على الأقل', 'error');
    return;
  }

  try {
    await API.createPurchase({
      supplier_id: document.getElementById('pur_supplier').value || null,
      invoice_number: document.getElementById('pur_num').value.trim() || null,
      date: document.getElementById('pur_date').value,
      notes: document.getElementById('pur_notes').value,
      items,
    });
    toast('تمت إضافة فاتورة الشراء', 'success');
    closeModal();
    navigateTo('purchases');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function confirmReceive(id) {
  if (!confirm('تأكيد استلام الفاتورة؟ سيتم رفع المخزون تلقائياً.')) return;
  try {
    await API.receivePurchase(id);
    toast('تم استلام الفاتورة ✅ — تم تحديث المخزون', 'success');
    navigateTo('purchases');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function viewPurchaseItems(id) {
  try {
    const purchases = await API.getPurchases();
    const p = (purchases || []).find(x => x.id === id);
    const items = p?.items || [];

    openModal(`
      <div class="modal-header">
        <div class="modal-title">📋 أصناف الفاتورة #${escHtml(p?.invoice_number || id)}</div>
        <button class="modal-close" onclick="closeModal()">✕</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>الصنف</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr></thead>
          <tbody>
            ${items.length ? items.map(i => `<tr>
              <td>${escHtml(i.product_name || '—')}</td>
              <td>${i.quantity}</td>
              <td>${fmt(i.unit_price)} د.أ</td>
              <td style="font-weight:700">${fmt(i.total)} د.أ</td>
            </tr>`).join('') : emptyRow('لا توجد أصناف', 4)}
          </tbody>
        </table>
      </div>
      <div style="margin-top:16px; text-align:left">
        <strong>الإجمالي: ${fmt(p?.total)} د.أ</strong>
      </div>
    `, '550px');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deletePurchase(id) {
  if (!confirm('حذف فاتورة الشراء؟')) return;
  try {
    await API.deletePurchase(id);
    toast('تم الحذف', 'success');
    navigateTo('purchases');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function doLogin(username, password) {
  try {
    const res = await API.login(username, password);
    localStorage.setItem('token', res.token);
    localStorage.setItem('user', JSON.stringify(res.user));
    location.reload();
  } catch (e) {
    toast(e.message || 'فشل تسجيل الدخول', 'error');
  }
}

/* ═══════════════════════════════════════════════════
   WAREHOUSE — المستودع
═══════════════════════════════════════════════════ */
async function renderWarehouse(container) {
  let categories = [];

  if (window._whCategoriesCache && window._whCategoriesCache.length) {
    categories = window._whCategoriesCache;
  } else {
    try {
      categories = await API.getWarehouseCategories();
      categories = Array.isArray(categories) ? categories : [];
      window._whCategoriesCache = categories;
    } catch (e) {
      categories = [];
    }
  }

  const totalProducts = categories.reduce((s, c) => s + parseInt(c.product_count || 0), 0);

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">🏭 المستودع</div>
        <div class="page-sub">${categories.length} فئة — ${totalProducts} صنف</div>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap">
  ${canManageWarehouse() ? `
  <button class="btn btn-primary" onclick="openImportProductsExcel()">
    📥 استيراد Excel
  </button>

  <button class="btn btn-ghost" onclick="exportWarehouseExcel()">
    📤 تصدير Excel
  </button>
` : ''}

  ${isAccountant() ? `
    <button class="btn btn-ghost" onclick="openWarehouseInvoiceModal()">📄 فاتورة جديدة</button>
    <button class="btn btn-primary" onclick="openCategoryModal()">+ فئة جديدة</button>
  ` : ''}

  <button class="btn btn-ghost btn-sm" onclick="viewWarehouseInvoices()">🧾 الفواتير</button>
</div>
    </div>

    <div style="display:flex; flex-direction:column; gap:14px">
      ${categories.length ? categories.map(cat => `
        <div class="card" style="padding:18px 20px; border:1px solid var(--brd); border-radius:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap">

            <div style="display:flex; align-items:center; gap:14px; min-width:220px;">
              <div style="
                width:52px; height:52px; border-radius:14px;
                background:var(--bg); display:flex; align-items:center; justify-content:center;
                font-size:26px;
              ">
                ${escHtml(cat.icon || '📦')}
              </div>

              <div>
                <div style="font-size:17px; font-weight:800; color:var(--tx)">
                  ${escHtml(cat.name)}
                </div>
                <div style="font-size:12px; color:var(--tx3); margin-top:3px">
                  ${cat.product_count || 0} صنف
                </div>
              </div>
            </div>

            <div style="display:flex; gap:24px; flex-wrap:wrap; align-items:center;">
              <div>
                <div style="font-size:11px; color:var(--tx3)">إجمالي الكمية</div>
                <div style="font-size:16px; font-weight:800">${fmt(cat.total_stock || 0)}</div>
              </div>

              <div>
                <div style="font-size:11px; color:var(--tx3)">إجمالي المبيعات</div>
                <div style="font-size:16px; font-weight:800; color:var(--gr)">${fmt(cat.total_sold || 0)} د.أ</div>
              </div>
            </div>

            <div style="display:flex; gap:6px; flex-wrap:wrap;">
              ${canEditWarehouseStructure() ? `
                  <button class="btn btn-ghost btn-sm" onclick="openEditCategoryModal(${cat.id})">✏️</button>
                    ` : ''}
              ${canManageWarehouse() ? `
                  <button class="btn btn-primary btn-sm" onclick="openAddProductModal(${cat.id})">+ صنف</button>
                ` : ''}
              ${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deleteCategoryConfirm(${cat.id})">🗑️</button>` : ''}
              <button class="btn btn-ghost btn-sm" onclick="openCategoryFolder(${cat.id})">📂 فتح</button>
            </div>

          </div>
        </div>
      `).join('') : `
        <div class="empty-state">
          <div class="empty-icon">🏭</div>
          <p>لا توجد فئات — أضف فئة للبدء</p>
        </div>
      `}
    </div>
  `;
}
function openImportProductsExcel() {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">📥 استيراد أصناف من Excel</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>

    <div class="modal-body">
      <p style="line-height:1.8">
        ارفعي ملف Excel الجاهز للاستيراد.
        يجب أن يحتوي الملف على صفحة اسمها:
        <b>import_ready_products</b>
      </p>

      <input
        id="productsExcelFile"
        type="file"
        accept=".xlsx"
        class="form-control"
      />

      <label style="display:flex; gap:8px; align-items:center; margin-top:12px;">
        <input id="updateExistingProducts" type="checkbox" />
        تحديث الأصناف الموجودة مسبقاً
      </label>

      <p style="font-size:13px; color:#666; margin-top:10px;">
        إذا كان هذا أول استيراد، اتركي خيار التحديث غير مفعّل.
      </p>

      <div
        id="excelImportStatus"
        style="display:none; margin-top:14px; padding:10px 12px; border-radius:10px; background:#eef3ff; color:#1a4fd6; font-size:13px; font-weight:700;"
      >
        ⏳ جاري رفع الملف واستيراد الأصناف... لا تغلقي الصفحة.
      </div>
    </div>

    <div class="modal-footer">
      <button class="btn" id="cancelExcelImportBtn" onclick="closeModal()">إلغاء</button>
      <button class="btn btn-primary" id="submitExcelImportBtn" onclick="submitProductsExcelImport()">
        استيراد
      </button>
    </div>
  `);
}


async function submitProductsExcelImport() {
  const fileInput = document.getElementById('productsExcelFile');
  const updateExisting = document.getElementById('updateExistingProducts')?.checked || false;
  const statusEl = document.getElementById('excelImportStatus');
  const submitBtn = document.getElementById('submitExcelImportBtn');
  const cancelBtn = document.getElementById('cancelExcelImportBtn');

  if (!fileInput || !fileInput.files || !fileInput.files[0]) {
    toast('اختاري ملف Excel أولاً', 'error');
    return;
  }

  try {
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.background = '#eef3ff';
      statusEl.style.color = '#1a4fd6';
      statusEl.textContent = '⏳ جاري رفع الملف واستيراد الأصناف... لا تغلقي الصفحة.';
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.dataset.oldText = submitBtn.textContent;
      submitBtn.textContent = 'جاري الاستيراد...';
      submitBtn.style.opacity = '0.65';
    }

    if (cancelBtn) {
      cancelBtn.disabled = true;
      cancelBtn.style.opacity = '0.65';
    }

    const result = await API.importProductsExcel(fileInput.files[0], updateExisting);

    toast(
      `${result.message || 'تم الاستيراد'} — جديد: ${result.inserted || 0}، تحديث: ${result.updated || 0}، متخطى: ${result.skipped || 0}`,
      'success'
    );

    if (result.failed && result.failed.length) {
      console.warn('Excel import failed rows:', result.failed);
      toast(`تم الاستيراد مع وجود ${result.failed.length} صف فيه مشكلة. راجعي Console.`, 'warning');
    }

    window._whCategoriesCache = null;
    window._productsCache = null;

    closeModal();
    await navigateTo('warehouse');

  } catch (err) {
    console.error(err);

    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.background = '#fff0f0';
      statusEl.style.color = '#c21515';
      statusEl.textContent = '❌ فشل الاستيراد. راجعي رسالة الخطأ أو terminal.';
    }

    toast(err.message || 'فشل استيراد ملف الإكسل', 'error');

    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = submitBtn.dataset.oldText || 'استيراد';
      submitBtn.style.opacity = '1';
    }

    if (cancelBtn) {
      cancelBtn.disabled = false;
      cancelBtn.style.opacity = '1';
    }
  }
}
function parseProductProperties(p) {
  if (!p || !p.properties) return {};

  if (typeof p.properties === 'object') {
    return p.properties || {};
  }

  try {
    return JSON.parse(p.properties);
  } catch (e) {
    return {};
  }
}

function ensureProductDetailsStyles() {
  if (document.getElementById('product-details-inline-style')) return;

  const style = document.createElement('style');
  style.id = 'product-details-inline-style';
  style.innerHTML = `
    .product-name-cell {
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 260px;
      max-width: 430px;
    }

    .product-main-name {
      font-weight: 800;
      color: var(--tx);
      line-height: 1.5;
    }

    .product-mini-details {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      margin-top: 2px;
    }

    .product-mini-details span {
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 11px;
      color: #374151;
      white-space: nowrap;
      font-weight: 600;
    }

    .details-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }

    .details-table th,
    .details-table td {
      border-bottom: 1px solid #eee;
      padding: 10px 8px;
      text-align: right;
    }

    .details-table th {
      color: var(--tx3);
      width: 190px;
      font-weight: 700;
    }

    .details-table td {
      color: var(--tx);
      font-weight: 700;
    }
  `;

  document.head.appendChild(style);
}

function productDetailValue(value) {
  if (value === null || value === undefined || value === '') return null;
  return value;
}





function productDetailRow(label, value) {
  const v = productDetailValue(value);
  if (v === null) return '';

  return `
    <tr>
      <th>${escHtml(label)}</th>
      <td>${escHtml(String(v))}</td>
    </tr>
  `;
}

async function openProductDetails(productId) {
  try {
    const products = await API.getProducts();
    const p = (products || []).find(x => String(x.id) === String(productId));

    if (!p) {
      toast('الصنف غير موجود', 'error');
      return;
    }

    const props = parseProductProperties(p);

    openModal(`
      <div class="modal-header">
        <div class="modal-title">🔎 تفاصيل الصنف</div>
        <button class="modal-close" onclick="closeModal()">✕</button>
      </div>

      <div class="modal-body">
        <table class="details-table">
          ${productDetailRow('اسم الصنف', p.name)}
          ${productDetailRow('الفئة', p.category_name || p.category || props.category_from_excel)}
          ${productDetailRow('الكود', p.sku)}
          ${productDetailRow('الوحدة', p.unit)}
          ${productDetailRow('الكمية الحالية', p.current_stock)}
          ${productDetailRow('الحد الأدنى', p.min_stock)}

          ${productDetailRow('النوع', props.brand_or_type)}
          ${productDetailRow('الصنف الأساسي', props.base_product_name)}
          ${productDetailRow('الموديل', props.model)}
          ${productDetailRow('اللون', props.color)}
          ${productDetailRow('المقاس', props.size)}

          ${productDetailRow('التعبئة', props.pack_size)}
          ${productDetailRow('عدد الشوالات / الكراتين', props.containers_count)}
          ${productDetailRow('العدد الإفرادي', props.loose_count)}
          ${productDetailRow('المجموع الكامل', props.original_total_qty)}

          ${productDetailRow('المباع قبل النظام', props.sold_qty_before_system)}
          ${productDetailRow('الكمية الحالية المستوردة', props.current_stock_qty_imported)}

          ${productDetailRow('السعر الإفرادي', props.unit_price_from_excel)}
          ${productDetailRow('السعر الإجمالي', props.total_price_from_excel)}
          ${productDetailRow('ملاحظة', props.import_note)}
        </table>
      </div>
    `, '650px');
  } catch (err) {
    console.error(err);
    toast('فشل فتح تفاصيل الصنف', 'error');
  }
}
async function openCategoryFolder(catId) {
  ensureProductDetailsStyles();

  window._openWarehouseCategoryId = catId;

  const cat = (window._whCategoriesCache || []).find(c => String(c.id) === String(catId));
  const catName = cat?.name || '';
  const catIcon = cat?.icon || '📦';

  let products = [];

  try {
    const allProducts = await API.getProducts() || [];

    products = allProducts.filter(p =>
      String(p.category_id || '') === String(catId) ||
      String(p.category || '') === String(catName) ||
      String(p.category_name || '') === String(catName)
    );
  } catch (e) {
    try {
      products = await API.getCategoryProducts(catId) || [];
    } catch (err) {
      products = [];
    }
  }

  openModal(`
    <div class="modal-header">
      <div class="modal-title">${escHtml(catIcon)} ${escHtml(catName)}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>

    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
      <div style="font-size:13px; color:var(--tx3)">${products.length} صنف في هذه الفئة</div>
      ${canManageWarehouse() ? `<button class="btn btn-primary btn-sm" onclick="closeModal(); openAddProductModal(${catId})">+ إضافة صنف</button>` : ''}
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>اسم الصنف والتفاصيل</th>
            <th>الكود</th>
            <th>الوحدة</th>
            <th>الكمية الحالية</th>
            <th>الحد الأدنى</th>
            <th style="text-align:center">الحالة</th>
            <th>الإجراءات</th>
          </tr>
        </thead>

        <tbody>
          ${products.length ? products.map(p => {
    const stock = parseFloat(p.current_stock || 0);
    const minStock = parseFloat(p.min_stock || 0);

    const isOut = stock === 0;
    const isLow = !isOut && minStock > 0 && stock <= minStock;

    const pct = minStock > 0
      ? Math.min((stock / (minStock * 2)) * 100, 100)
      : 50;

    const barColor = isOut
      ? 'var(--rd)'
      : isLow
        ? 'var(--am)'
        : 'var(--gr)';

    const statusBadge = isOut
      ? '<span class="badge badge-red">🚫 نفد</span>'
      : isLow
        ? '<span class="badge badge-amber">⚠️ منخفض</span>'
        : '<span class="badge badge-green">✅ سليم</span>';

    return `
<tr data-product-id="${p.id}" style="${isOut ? 'background:#fff5f5' : isLow ? 'background:#fffbeb' : ''}">                <td>${productNameWithDetails(p)}</td>

                <td style="font-family:monospace;font-size:11px;color:var(--tx3)">
                  ${escHtml(p.sku || '—')}
                </td>

                <td>
                  <span class="badge badge-gray">${escHtml(p.unit || 'قطعة')}</span>
                </td>

                <td>
                  <div style="display:flex;align-items:center;gap:8px">
                    <span style="font-weight:800;font-size:15px;color:${isOut ? 'var(--rd)' : isLow ? 'var(--am)' : 'var(--tx)'}">
                      ${stock}
                    </span>

                    <div style="width:60px;height:5px;background:#e8e5e0;border-radius:3px;overflow:hidden">
                      <div style="height:100%;width:${pct}%;background:${barColor};border-radius:3px"></div>
                    </div>
                  </div>
                </td>

                <td style="color:var(--tx3);font-size:12px">
                  ${minStock || '—'}
                </td>

                <td>${statusBadge}</td>

                <td>
                  <div style="display:flex;gap:4px;flex-wrap:wrap">
                    <button class="btn btn-ghost btn-sm" onclick="openProductDetails('${p.id}')">🔎</button>
                    <button class="btn btn-ghost btn-sm" onclick="viewMovements('${p.id}', ${jsString(p.name)})">📊</button>
                    ${canManageWarehouse() ? `<button class="btn btn-ghost btn-sm" onclick="openEditProduct('${p.id}', ${catId})">✏️</button>` : ''}
                    ${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deleteProduct('${p.id}', ${catId}, this)">🗑️</button>` : ''}
                  </div>
                </td>
              </tr>
            `;
  }).join('') : `<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--tx3)">لا توجد أصناف</td></tr>`}
        </tbody>
      </table>
    </div>

    ${products.length ? `
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:16px">
        <div style="background:var(--grl);border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:20px;font-weight:800;color:var(--gr)">
            ${products.filter(p => parseFloat(p.current_stock || 0) > 0 && (parseFloat(p.min_stock || 0) === 0 || parseFloat(p.current_stock || 0) > parseFloat(p.min_stock || 0))).length}
          </div>
          <div style="font-size:11px;color:var(--gr)">سليم</div>
        </div>

        <div style="background:var(--aml);border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:20px;font-weight:800;color:var(--am)">
            ${products.filter(p => {
    const s = parseFloat(p.current_stock || 0);
    const m = parseFloat(p.min_stock || 0);
    return s > 0 && m > 0 && s <= m;
  }).length}
          </div>
          <div style="font-size:11px;color:var(--am)">منخفض</div>
        </div>

        <div style="background:var(--rdl);border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:20px;font-weight:800;color:var(--rd)">
            ${products.filter(p => parseFloat(p.current_stock || 0) === 0).length}
          </div>
          <div style="font-size:11px;color:var(--rd)">نفد</div>
        </div>
      </div>
    ` : ''}
  `, '980px');
}

function openCategoryModal() {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">📁 إضافة فئة جديدة</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">اسم الفئة *</label>
        <input class="form-input" id="cat_name" placeholder="مثال: إلكترونيات">
      </div>
      <div class="form-group">
        <label class="form-label">أيقونة (emoji)</label>
        <input class="form-input" id="cat_icon" placeholder="📦" maxlength="4">
      </div>
    </div>
    <div style="display:flex; gap:10px; margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="saveCategory()">إضافة الفئة</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveCategory() {
  const name = document.getElementById('cat_name').value.trim();
  if (!name) { toast('الاسم مطلوب', 'error'); return; }

  try {
    await API.createWarehouseCategory({
      name,
      icon: document.getElementById('cat_icon').value.trim() || '📦'
    });
    toast('تمت إضافة الفئة', 'success');
    closeModal();
    navigateTo('warehouse');
  } catch (e) {
    toast(e.message, 'error');
  }
}


function productDetailRow(label, value) {
  if (value === null || value === undefined || value === '') return '';

  return `
    <tr>
      <th style="width: 180px;">${escHtml(label)}</th>
      <td>${escHtml(String(value))}</td>
    </tr>
  `;
}

async function openProductDetails(productId) {
  try {
    const products = await API.getProducts();
    const p = (products || []).find(x => String(x.id) === String(productId));

    if (!p) {
      toast('الصنف غير موجود', 'error');
      return;
    }

    const props = parseProductProperties(p);

    openModal(`
      <div class="modal-header">
        <div class="modal-title">📦 تفاصيل الصنف</div>
        <button class="modal-close" onclick="closeModal()">✕</button>
      </div>

      <div class="modal-body">
        <table class="details-table">
          ${productDetailRow('اسم الصنف', p.name)}
          ${productDetailRow('الفئة', p.category_name || p.category)}
          ${productDetailRow('الكود', p.sku)}
          ${productDetailRow('الوحدة', p.unit)}
          ${productDetailRow('الكمية الحالية', p.current_stock)}
          ${productDetailRow('الحد الأدنى', p.min_stock)}

          ${productDetailRow('النوع', props.brand_or_type)}
          ${productDetailRow('الصنف الأساسي', props.base_product_name)}
          ${productDetailRow('الموديل', props.model)}
          ${productDetailRow('اللون', props.color)}
          ${productDetailRow('المقاس', props.size)}

          ${productDetailRow('التعبئة / عدد الحبات بالكرتونة أو الشوال', props.pack_size)}
          ${productDetailRow('عدد الشوالات / الكراتين', props.containers_count)}
          ${productDetailRow('العدد الإفرادي', props.loose_count)}
          ${productDetailRow('المجموع الكامل الأصلي', props.original_total_qty)}

          ${productDetailRow('المباع قبل النظام', props.sold_qty_before_system)}
          ${productDetailRow('الكمية المستوردة من Excel', props.current_stock_qty_imported)}

          ${productDetailRow('السعر الإفرادي من Excel', props.unit_price_from_excel)}
          ${productDetailRow('السعر الإجمالي من Excel', props.total_price_from_excel)}
          ${productDetailRow('ملاحظة الاستيراد', props.import_note)}
        </table>
      </div>
    `);
  } catch (err) {
    console.error(err);
    toast('فشل فتح تفاصيل الصنف', 'error');
  }
}


function productMiniDetails(p) {
  const props = parseProductProperties(p);
  const category = String(p.category_name || p.category || '').trim();

  const parts = [];

  if (props.brand_or_type) parts.push(`النوع: ${props.brand_or_type}`);
  if (props.model) parts.push(`الموديل: ${props.model}`);
  if (props.color) parts.push(`اللون: ${props.color}`);
  if (props.size) parts.push(`المقاس: ${props.size}`);

  if (props.containers_count) {
    if (category.includes('الادوات') || category.includes('منزل')) {
      parts.push(`عدد الكراتين: ${props.containers_count}`);
    } else {
      parts.push(`عدد الشوالات: ${props.containers_count}`);
    }
  }

  if (props.pack_size) parts.push(`التعبئة: ${props.pack_size}`);
  if (props.loose_count) parts.push(`إفرادي: ${props.loose_count}`);
  if (props.original_total_qty) parts.push(`الكلي: ${props.original_total_qty}`);

  if (!parts.length) return '';

  return `
    <div class="product-mini-details">
      ${parts.map(x => `<span>${escHtml(x)}</span>`).join('')}
    </div>
  `;
}

function productNameWithDetails(p) {
  return `
    <div class="product-name-cell">
      <div class="product-main-name">${escHtml(p.name || '')}</div>
      ${productMiniDetails(p)}
    </div>
  `;
}
async function exportWarehouseExcel() {
  try {
    await API.exportProductsExcel();
    toast('تم تصدير ملف Excel بنجاح', 'success');
  } catch (err) {
    console.error(err);
    toast('فشل تصدير ملف Excel', 'error');
  }
}
async function deleteCategoryConfirm(id) {
  if (!confirm('حذف هذه الفئة؟ سيتم إلغاء ربط أصنافها بالفئة، ولن يتم حذف الأصناف نفسها.')) return;

  try {
    await API.deleteWarehouseCategory(id);

    toast('تم حذف الفئة وتحديث قاعدة البيانات', 'success');

    window._whCategoriesCache = null;
    window._productsCache = null;

    await navigateTo('warehouse');
  } catch (e) {
    toast(e.message || 'تعذر حذف الفئة', 'error');
  }
}

function openEditCategoryModal(id) {
  const cat = (window._whCategoriesCache || []).find(c => c.id === id);
  if (!cat) {
    toast('لم يتم تحميل بيانات الفئة', 'error');
    return;
  }

  openModal(`
    <div class="modal-header">
      <div class="modal-title">✏️ تعديل الفئة</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">اسم الفئة *</label>
        <input class="form-input" id="ecat_name" value="${escHtml(cat.name)}">
      </div>
      <div class="form-group">
        <label class="form-label">أيقونة (emoji)</label>
        <input class="form-input" id="ecat_icon" value="${escHtml(cat.icon || '📦')}" maxlength="4">
      </div>
    </div>
    <div style="display:flex; gap:10px; margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="saveEditCategory(${id})">حفظ التعديلات</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveEditCategory(id) {
  const name = document.getElementById('ecat_name').value.trim();
  if (!name) { toast('الاسم مطلوب', 'error'); return; }

  try {
    await API.updateWarehouseCategory(id, {
      name,
      icon: document.getElementById('ecat_icon').value.trim() || '📦'
    });
    toast('تم تحديث الفئة', 'success');
    closeModal();
    navigateTo('warehouse');
  } catch (e) {
    toast(e.message, 'error');
  }
}
/* ── Add/Edit Product Modal ───────────────────────────────── */
/* ── Add/Edit Product Modal — Easy Safe Mode ───────────────── */

/* ── Add/Edit Product Modal — Safe Fast Mode ───────────────── */

window._productBusy = false;

function setProductButtonLoading(btn, loading, text = 'جاري الحفظ...') {
  if (!btn) return;

  if (loading) {
    btn.dataset.oldText = btn.textContent;
    btn.disabled = true;
    btn.style.opacity = '0.65';
    btn.style.pointerEvents = 'none';
    btn.textContent = text;
  } else {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.pointerEvents = '';
    btn.textContent = btn.dataset.oldText || 'حفظ';
  }
}

async function refreshWarehouseAfterAction() {
  const catId = window._openWarehouseCategoryId;
  // refresh categories cache in background silently
  API.getWarehouseCategories().then(cats => {
    window._whCategoriesCache = cats || [];
  }).catch(() => { });

  closeModal();

  if (catId) {
    // Go back to the folder we were in — products cache already updated
    await openCategoryFolder(catId);
  } else {
    // No category context — just refresh the warehouse page
    window._whCategoriesCache = null;
    await navigateTo('warehouse');
  }
}

async function openAddProductModal(catId) {
  const currentCat = (window._whCategoriesCache || []).find(c => String(c.id) === String(catId));
  const catName = currentCat?.name || '';

  let categories = [];
  try {
    categories = await API.getWarehouseCategories() || [];
  } catch (e) {
    categories = [];
  }

  window._whCategoriesCache = categories;

  const unitOptions = [
    'قطعة',
    'كرتون',
    'متر',
    'كيلو',
    'نصف كيلو',
    'طن',
    'طن ونص',
    '2 طن',
    '2.5 طن',
    '3 طن',
    'لتر',
    'نصف لتر',
    'زوج',
    'علبة'
  ];

  openModal(`
    <div class="modal-header">
      <div class="modal-title">➕ إضافة صنف — ${escHtml(catName)}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>


    <div class="alert alert-info" style="font-size:12px">
      اضغطي حفظ مرة واحدة فقط. الزر سيُغلق تلقائياً أثناء الحفظ.
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">اسم الصنف *</label>
        <input class="form-input" id="pr_name" placeholder="مثال: صحن بورسلان">
      </div>

      <div class="form-group">
        <label class="form-label">الكود / الباركود</label>
        <input class="form-input" id="pr_sku" placeholder="اختياري">
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">الفئة *</label>
        <select class="form-select" id="pr_cat_id">
          <option value="">اختر الفئة</option>
          ${categories.map(c => `
            <option value="${c.id}" ${String(c.id) === String(catId) ? 'selected' : ''}>
              ${escHtml(c.icon || '📦')} ${escHtml(c.name)}
            </option>
          `).join('')}
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">وحدة القياس</label>
        <select class="form-select" id="pr_unit">
          ${unitOptions.map(u => `<option value="${u}">${u}</option>`).join('')}
        </select>
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">الكمية</label>
        <input class="form-input" id="pr_opening_qty" type="number" min="0" step="1" value="0" oninput="calcProductTotals()">
      </div>
      <div class="form-group">
        <label class="form-label">عدد الشوالات</label>
        <input class="form-input" id="pr_bags" type="number" min="0" step="1" value="0" oninput="calcProductTotals()">
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">العدد الافرادي</label>
        <input class="form-input" id="pr_individual" type="number" min="0" step="1" value="0" oninput="calcProductTotals()">
      </div>
      <div class="form-group">
        <label class="form-label">المجموع كامل</label>
        <input class="form-input" id="pr_total_count" type="number" min="0" step="1" value="0" readonly style="background:#f5f3f0; color:var(--tx2)">
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">المباع</label>
        <input class="form-input" id="pr_sold" type="number" min="0" step="1" value="0" oninput="calcProductTotals()">
      </div>
      <div class="form-group">
        <label class="form-label">الباق</label>
        <input class="form-input" id="pr_remaining" type="number" min="0" step="1" value="0" readonly style="background:#f5f3f0; color:var(--tx2)">
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">السعر الافرادي</label>
        <input class="form-input" id="pr_unit_price" type="number" min="0" step="0.001" value="0" oninput="calcProductTotals()">
      </div>
      <div class="form-group">
        <label class="form-label">السعر الاجمالي</label>
        <input class="form-input" id="pr_total_price" type="number" min="0" step="0.001" value="0" readonly style="background:#f5f3f0; color:var(--tx2)">
      </div>
    </div>

    <div class="form-group">
      <label class="form-label">الحد الأدنى للتنبيه</label>
      <input class="form-input" id="pr_min" type="number" min="0" step="0.001" value="0">
    </div>

    <div style="display:flex; gap:10px; margin-top:8px">
      <button class="btn btn-primary" style="flex:1" id="save-product-btn">حفظ الصنف</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);

  const btn = document.getElementById('save-product-btn');
  if (btn) {
    btn.addEventListener('click', saveNewProductInCategory);
  }
}
function buildProductPropertiesFromForm(name, existingProps = {}) {
  const categoryText =
    document.getElementById('pr_cat_id')?.selectedOptions?.[0]?.textContent?.trim() || '';

  const packSize = parseFloat(document.getElementById('pr_opening_qty')?.value) || 0;
  const containers = parseFloat(document.getElementById('pr_bags')?.value) || 0;
  const loose = parseFloat(document.getElementById('pr_individual')?.value) || 0;
  const totalCount = parseFloat(document.getElementById('pr_total_count')?.value) || 0;
  const sold = parseFloat(document.getElementById('pr_sold')?.value) || 0;
  const remaining = parseFloat(document.getElementById('pr_remaining')?.value) || 0;
  const unitPrice = parseFloat(document.getElementById('pr_unit_price')?.value) || 0;
  const totalPrice = parseFloat(document.getElementById('pr_total_price')?.value) || 0;

  return {
    ...existingProps,

    import_source: existingProps.import_source || 'manual_ui',
    category_from_excel: existingProps.category_from_excel || categoryText,
    base_product_name: existingProps.base_product_name || name,

    pack_size: packSize || existingProps.pack_size || null,
    containers_count: containers || existingProps.containers_count || null,
    loose_count: loose || existingProps.loose_count || null,
    original_total_qty: totalCount || existingProps.original_total_qty || null,
    sold_qty_before_system: sold || existingProps.sold_qty_before_system || null,
    current_stock_qty_imported: remaining || existingProps.current_stock_qty_imported || null,

    unit_price_from_excel: unitPrice || existingProps.unit_price_from_excel || null,
    total_price_from_excel: totalPrice || existingProps.total_price_from_excel || null,
  };
}
async function saveNewProductInCategory() {
  if (window._productBusy) {
    toast('جاري الحفظ... لا تضغطي مرة ثانية', 'warning');
    return;
  }

  const btn = document.getElementById('save-product-btn');

  const name = document.getElementById('pr_name')?.value.trim();
  const sku = document.getElementById('pr_sku')?.value.trim() || null;
  const categoryValue = document.getElementById('pr_cat_id')?.value;
  const unit = document.getElementById('pr_unit')?.value || 'قطعة';
  const openingQty = parseFloat(document.getElementById('pr_remaining')?.value || '0');
  const unitPrice = parseFloat(document.getElementById('pr_unit_price')?.value || '0');
  const minStock = parseFloat(document.getElementById('pr_min')?.value || '0');

  if (!name) {
    toast('اسم الصنف مطلوب', 'error');
    return;
  }

  if (!categoryValue) {
    toast('اختر الفئة أولاً', 'error');
    return;
  }

  const categoryId = Number(categoryValue);

  if (!Number.isInteger(categoryId)) {
    toast('الفئة غير صحيحة', 'error');
    return;
  }

  if (Number.isNaN(openingQty) || openingQty < 0) {
    toast('الكمية الحالية يجب أن تكون رقماً لا يقل عن صفر', 'error');
    return;
  }

  if (Number.isNaN(minStock) || minStock < 0) {
    toast('الحد الأدنى يجب أن يكون رقماً لا يقل عن صفر', 'error');
    return;
  }

  window._productBusy = true;
  setProductButtonLoading(btn, true, 'جاري الحفظ...');

  try {
    const newProduct = await API.createProduct({
      name,
      sku,
      category_id: categoryId,
      unit,
      min_stock: minStock,
      opening_quantity: openingQty,
      properties: buildProductPropertiesFromForm(name),
    });

    toast('تم حفظ الصنف والكمية ✅', 'success');

    // Update cache
    if (window._productsCache) window._productsCache.unshift(newProduct);

    // Refresh category counts in background
    API.getWarehouseCategories().then(cats => {
      window._whCategoriesCache = cats || [];
    }).catch(() => { });

    closeModal();
    // Go back to the folder — uses updated cache, no extra API call
    await openCategoryFolder(categoryId);
  } catch (e) {
    toast(e.message || 'تعذر حفظ الصنف', 'error');
    setProductButtonLoading(btn, false, 'حفظ الصنف');
  } finally {
    window._productBusy = false;
  }
}
function calcProductTotals() {
  const packSize = parseFloat(document.getElementById('pr_opening_qty')?.value) || 0;
  const containers = parseFloat(document.getElementById('pr_bags')?.value) || 0;
  const loose = parseFloat(document.getElementById('pr_individual')?.value) || 0;
  const sold = parseFloat(document.getElementById('pr_sold')?.value) || 0;
  const unitPrice = parseFloat(document.getElementById('pr_unit_price')?.value) || 0;

  const totalCount = containers > 0
    ? (containers * packSize) + loose
    : packSize + loose;

  const remaining = Math.max(totalCount - sold, 0);
  const totalPrice = remaining * unitPrice;

  const totalCountEl = document.getElementById('pr_total_count');
  const remainingEl = document.getElementById('pr_remaining');
  const totalPriceEl = document.getElementById('pr_total_price');

  if (totalCountEl) totalCountEl.value = totalCount.toFixed(0);
  if (remainingEl) remainingEl.value = remaining.toFixed(0);
  if (totalPriceEl) totalPriceEl.value = totalPrice.toFixed(3);
}
async function openEditProduct(productId, catId = null) {
  if (window._productBusy) {
    toast('انتظري حتى تنتهي العملية الحالية', 'warning');
    return;
  }

  try {
    const products = await API.getProducts();
    const p = (products || []).find(x => String(x.id) === String(productId));

    if (!p) {
      toast('الصنف غير موجود', 'error');
      return;
    }

    let categories = window._whCategoriesCache || [];
    if (!categories.length) {
      try {
        categories = await API.getWarehouseCategories() || [];
      } catch (e) {
        categories = [];
      }
    }

    const unitOptions = [
      'قطعة',
      'كرتون',
      'متر',
      'كيلو',
      'نصف كيلو',
      'طن',
      'طن ونص',
      '2 طن',
      '2.5 طن',
      '3 طن',
      'لتر',
      'نصف لتر',
      'زوج',
      'علبة'
    ];

    const currentStock = parseFloat(p.current_stock || 0);
    window._editingProductProperties = parseProductProperties(p);

    openModal(`
      <div class="modal-header">
        <div class="modal-title">✏️ تعديل صنف — ${escHtml(p.name)}</div>
        <button class="modal-close" onclick="closeModal()">✕</button>
      </div>

      <div class="alert alert-info" style="font-size:12px">
        اكتبي الكمية النهائية الموجودة فعلياً في المخزن. النظام سيحسب الفرق تلقائياً.
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">اسم الصنف *</label>
          <input class="form-input" id="pr_name" value="${escHtml(p.name)}">
        </div>

        <div class="form-group">
          <label class="form-label">الكود / الباركود</label>
          <input class="form-input" id="pr_sku" value="${escHtml(p.sku || '')}">
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">الفئة *</label>
          <select class="form-select" id="pr_cat_id">
            <option value="">بدون فئة</option>
            ${categories.map(c => `
              <option value="${c.id}" ${String(c.id) === String(p.category_id || catId) ? 'selected' : ''}>
                ${escHtml(c.icon || '📦')} ${escHtml(c.name)}
              </option>
            `).join('')}
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">وحدة القياس</label>
          <select class="form-select" id="pr_unit">
            ${unitOptions.map(u => `
              <option value="${u}" ${p.unit === u ? 'selected' : ''}>${u}</option>
            `).join('')}
          </select>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">الكمية الحالية في المخزن</label>
          <input class="form-input" id="pr_stock_final" type="number" min="0" step="0.001" value="${currentStock}">
        </div>

        <div class="form-group">
          <label class="form-label">الحد الأدنى للتنبيه</label>
          <input class="form-input" id="pr_min" type="number" min="0" step="0.001" value="${parseFloat(p.min_stock || 0)}">
        </div>
      </div>

      <div style="padding:8px 12px; background:var(--bg); border-radius:var(--r); font-size:12px; color:var(--tx3); margin-bottom:8px">
        الكمية المسجلة حالياً:
        <strong style="color:var(--tx)">${currentStock}</strong>
        ${escHtml(p.unit || '')}
      </div>

      <div style="display:flex; gap:10px; margin-top:8px">
        <button class="btn btn-primary" style="flex:1" id="save-edit-product-btn">حفظ التعديل</button>
        <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
      </div>
    `);

    const btn = document.getElementById('save-edit-product-btn');
    if (btn) {
      btn.addEventListener('click', () => saveEditProductNew(p.id));
    }
  } catch (e) {
    toast('تعذّر تحميل الصنف: ' + (e.message || 'خطأ غير معروف'), 'error');
  }
}

async function saveEditProductNew(id) {
  if (window._productBusy) {
    toast('جاري الحفظ... لا تضغطي مرة ثانية', 'warning');
    return;
  }

  const btn = document.getElementById('save-edit-product-btn');
  const productId = String(id || '').trim();

  if (!productId || productId === 'undefined' || productId === 'null' || productId === 'NaN') {
    toast('معرّف الصنف غير صحيح. أغلقي النافذة وافتحي الصنف مرة ثانية.', 'error');
    return;
  }

  const name = document.getElementById('pr_name')?.value.trim();
  const sku = document.getElementById('pr_sku')?.value.trim() || null;
  const categoryValue = document.getElementById('pr_cat_id')?.value;
  const unit = document.getElementById('pr_unit')?.value || 'قطعة';
  const minStock = parseFloat(document.getElementById('pr_min')?.value || '0');
  const finalStock = parseFloat(document.getElementById('pr_stock_final')?.value || '0');

  if (!name) {
    toast('اسم الصنف مطلوب', 'error');
    return;
  }

  if (Number.isNaN(finalStock) || finalStock < 0) {
    toast('الكمية الحالية يجب أن تكون رقماً لا يقل عن صفر', 'error');
    return;
  }

  if (Number.isNaN(minStock) || minStock < 0) {
    toast('الحد الأدنى يجب أن يكون رقماً لا يقل عن صفر', 'error');
    return;
  }

  window._productBusy = true;
  setProductButtonLoading(btn, true, 'جاري حفظ التعديل...');

  try {
    await API.updateProduct(productId, {
      name, sku,
      category_id: (categoryValue && Number(categoryValue) > 0) ? Number(categoryValue) : null,
      unit,
      min_stock: minStock,
      final_stock: finalStock,
      properties: window._editingProductProperties || {},
    });

    toast('تم حفظ التعديل ✅', 'success');

    // Update cache
    if (window._productsCache) {
      const idx = window._productsCache.findIndex(p => String(p.id) === String(productId));
      if (idx !== -1) {
        window._productsCache[idx] = {
          ...window._productsCache[idx],
          name, sku,
          category_id: Number(categoryValue) || null,
          unit,
          min_stock: minStock,
          current_stock: finalStock,
        };
      }
    }

    // Refresh category counts in background
    API.getWarehouseCategories().then(cats => {
      window._whCategoriesCache = cats || [];
    }).catch(() => { });

    closeModal();
    const targetCatId = window._openWarehouseCategoryId;
    if (targetCatId) await openCategoryFolder(targetCatId);
  } catch (e) {
    toast(e.message || 'تعذر حفظ الصنف', 'error');
    setProductButtonLoading(btn, false, 'حفظ التعديل');
  } finally {
    window._productBusy = false;
  }
}

async function deleteProduct(id, catId = null, btn = null) {
  const productId = String(id || '').trim();
  const activeCatId = catId || window._openWarehouseCategoryId;

  if (!productId || productId === 'undefined' || productId === 'null') {
    toast('معرّف الصنف غير صحيح', 'error');
    return;
  }
  if (window._productBusy) { toast('جاري تنفيذ عملية أخرى...', 'warning'); return; }
  if (!confirm('حذف الصنف؟')) return;

  window._productBusy = true;
  const row = document.querySelector(`tr[data-product-id="${productId}"]`);
  if (row) { row.style.opacity = '0.4'; row.style.pointerEvents = 'none'; }
  if (btn) { btn.disabled = true; btn.textContent = '...'; }

  try {
    await API.deleteProduct(productId);
    toast('تم حذف الصنف ✅', 'success');

    // Update cache
    if (window._productsCache) {
      window._productsCache = window._productsCache.filter(p => String(p.id) !== productId);
    }

    // Remove row from open modal — no page reload needed
    if (row) {
      row.style.transition = 'opacity 0.25s';
      row.style.opacity = '0';
      setTimeout(() => row.remove(), 280);
    }

    // Refresh category counts in background
    API.getWarehouseCategories().then(cats => {
      window._whCategoriesCache = cats || [];
    }).catch(() => { });

  } catch (e) {
    toast(e.message, 'error');
    if (row) { row.style.opacity = '1'; row.style.pointerEvents = ''; }
    if (btn) { btn.disabled = false; btn.textContent = '🗑️'; }
  } finally {
    window._productBusy = false;
  }
}
/* ── Warehouse Invoices ───────────────────────────────────── */
async function viewWarehouseInvoices() {
  let invoices = [];
  try { invoices = await API.getWarehouseInvoices() || []; } catch (e) { invoices = []; }

  openModal(`
    <div class="modal-header">
      <div class="modal-title">🧾 فواتير المستودع</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
      <div style="font-size:13px; color:var(--tx3)">${invoices.length} فاتورة</div>
      ${isAccountant() ? `<button class="btn btn-primary btn-sm" onclick="closeModal(); openWarehouseInvoiceModal()">+ فاتورة جديدة</button>` : ''}
    </div>
    <div class="table-wrap" style="max-height:460px; overflow-y:auto">
      <table>
        <thead>
          <tr>
            <th>رقم الفاتورة</th>
            <th>الفئة</th>
            <th>المشتري</th>
            <th>المورد</th>
            <th>طرف الفاتورة</th>
            <th>الإجمالي</th>
            <th>التاريخ</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${invoices.length ? invoices.map(inv => `<tr>
            <td><strong>#${escHtml(inv.invoice_number || inv.id)}</strong></td>
            <td>${escHtml(inv.category_name || '—')}</td>
            <td style="font-size:12px">${escHtml(inv.buyer_name || '—')}</td>
            <td style="font-size:12px">${escHtml(inv.supplier_name || '—')}</td>
            <td style="font-size:12px; color:var(--tx3)">${escHtml(inv.issued_by_name || '—')}</td>
            <td style="font-weight:700">${fmt(inv.total)} د.أ</td>
            <td style="font-size:12px; color:var(--tx3)">${fmtDate(inv.date)}</td>
            <td>
              <div style="display:flex; gap:4px">
                <button class="btn btn-ghost btn-sm" onclick="viewWarehouseInvoiceItems(${inv.id})">📋</button>
                ${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deleteWarehouseInvoice(${inv.id})">🗑️</button>` : ''}
              </div>
            </td>
          </tr>`).join('') : `<tr><td colspan="8" style="text-align:center; padding:30px; color:var(--tx3)">لا توجد فواتير</td></tr>`}
        </tbody>
      </table>
    </div>
  `, '900px');
}

async function openWarehouseInvoiceModal() {
  let categories = [], products = [];
  try {
    [categories, products] = await Promise.all([
      API.getWarehouseCategories(),
      API.getProducts()
    ]);
  } catch (e) {
    categories = [];
    products = [];
  }

  window._whCategoriesCache = categories || [];
  window._productsCache = products || [];

  const catOpts = (categories || []).map(c =>
    `<option value="${c.id}">${escHtml(c.icon || '📦')} ${escHtml(c.name)}</option>`).join('');

  openModal(`
    <div class="modal-header">
      <div class="modal-title">📄 فاتورة مستودع جديدة</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">رقم الفاتورة</label>
        <input class="form-input" id="winv_num" placeholder="تلقائي">
      </div>
      <div class="form-group">
        <label class="form-label">الفئة</label>
        <select class="form-select" id="winv_cat" onchange="filterProductsByCategory()">
          <option value="">كل الفئات</option>
          ${catOpts}
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">اسم المشتري</label>
        <input class="form-input" id="winv_buyer" placeholder="اسم المشتري">
      </div>
      <div class="form-group">
        <label class="form-label">اسم المورد</label>
        <input class="form-input" id="winv_supplier" placeholder="اسم المورد">
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">التاريخ</label>
        <input class="form-input" id="winv_date" type="date" value="${new Date().toISOString().split('T')[0]}">
      </div>
      <div class="form-group">
        <label class="form-label">ملاحظات</label>
        <input class="form-input" id="winv_notes" placeholder="اختياري">
      </div>
    </div>

    <div style="margin:16px 0 8px; font-weight:700; font-size:13px">📦 الأصناف</div>
    <div id="winv-items-wrap" style="display:flex; flex-direction:column; gap:8px"></div>
    <button class="btn btn-ghost btn-sm" style="margin-top:8px" onclick="addWarehouseInvoiceRow()">+ إضافة صنف</button>

    <div style="margin-top:16px; padding:12px; background:var(--bll); border-radius:var(--r); display:flex; justify-content:space-between; align-items:center">
      <span style="font-weight:700; color:var(--tx2)">الإجمالي</span>
      <span style="font-size:18px; font-weight:800; color:var(--bld)" id="winv_total">0.00 د.أ</span>
    </div>

    <div style="display:flex; gap:10px; margin-top:16px">
      <button class="btn btn-primary" style="flex:1" onclick="saveWarehouseInvoice()">حفظ الفاتورة</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `, '640px');

  addWarehouseInvoiceRow();
}

function filterProductsByCategory() {
  const catId = document.getElementById('winv_cat')?.value;
  const allProds = window._productsCache || [];

  window._filteredProducts = catId
    ? allProds.filter(p => String(p.category_id) === String(catId))
    : allProds;

  const wrap = document.getElementById('winv-items-wrap');
  if (!wrap) return;

  Array.from(wrap.children).forEach((row, i) => {
    const sel = document.getElementById(`wp_prod_${i}`);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = `<option value="">اختر صنفاً</option>` +
      (window._filteredProducts || []).map(p =>
        `<option value="${p.id}" ${p.id == current ? 'selected' : ''}>${escHtml(p.name)} (${p.current_stock} ${escHtml(p.unit)})</option>`
      ).join('');
  });
}

function addWarehouseInvoiceRow() {
  const wrap = document.getElementById('winv-items-wrap');
  if (!wrap) return;

  const idx = wrap.children.length;
  const catId = document.getElementById('winv_cat')?.value;
  const allProds = window._productsCache || [];
  const prods = catId ? allProds.filter(p => String(p.category_id) === String(catId)) : allProds;
  window._filteredProducts = prods;

  const prodOpts = prods.map(p =>
    `<option value="${p.id}">${escHtml(p.name)} (${p.current_stock} ${escHtml(p.unit)})</option>`
  ).join('');

  const row = document.createElement('div');
  row.style.cssText = 'display:grid; grid-template-columns:2fr 1fr 1fr 1fr auto; gap:8px; align-items:center';
  row.innerHTML = `
    <select class="form-select" id="wp_prod_${idx}" onchange="calcWarehouseTotal()">
      <option value="">اختر صنفاً</option>
      ${prodOpts}
    </select>
    <input class="form-input" id="wp_qty_${idx}" type="number" placeholder="الكمية" min="0.001" step="0.001" oninput="calcWarehouseTotal()">
    <input class="form-input" id="wp_price_${idx}" type="number" placeholder="السعر" min="0" step="0.01" oninput="calcWarehouseTotal()">
    <div id="wp_sub_${idx}" style="padding:10px; background:var(--bg); border-radius:var(--r); font-size:12px; font-weight:700; color:var(--tx2); text-align:center">0.00</div>
    <button class="btn btn-danger btn-sm" onclick="this.parentElement.remove(); calcWarehouseTotal()">✕</button>
  `;
  wrap.appendChild(row);
}

function calcWarehouseTotal() {
  let total = 0;
  for (let i = 0; i < 50; i++) {
    const qty = parseFloat(document.getElementById(`wp_qty_${i}`)?.value) || 0;
    const price = parseFloat(document.getElementById(`wp_price_${i}`)?.value) || 0;
    const sub = qty * price;
    const subEl = document.getElementById(`wp_sub_${i}`);
    if (subEl) subEl.textContent = fmt(sub);
    total += sub;
  }
  const el = document.getElementById('winv_total');
  if (el) el.textContent = `${fmt(total)} د.أ`;
}

async function saveWarehouseInvoice() {
  const items = [];
  for (let i = 0; i < 50; i++) {
    const prodEl = document.getElementById(`wp_prod_${i}`);
    const qtyEl = document.getElementById(`wp_qty_${i}`);
    const priceEl = document.getElementById(`wp_price_${i}`);
    if (!prodEl) continue;

    const product_id = prodEl.value;
    const quantity = parseFloat(qtyEl?.value);
    const unit_price = parseFloat(priceEl?.value);

    if (product_id && quantity > 0 && unit_price >= 0) {
      items.push({ product_id, quantity, unit_price });
    }
  }

  if (!items.length) { toast('أضف صنفاً واحداً على الأقل', 'error'); return; }

  try {
    await API.createWarehouseInvoice({
      invoice_number: document.getElementById('winv_num').value.trim() || null,
      category_id: document.getElementById('winv_cat').value || null,
      buyer_name: document.getElementById('winv_buyer').value.trim() || null,
      supplier_name: document.getElementById('winv_supplier').value.trim() || null,
      date: document.getElementById('winv_date').value,
      notes: document.getElementById('winv_notes').value,
      items,
    });
    toast('تمت إضافة الفاتورة ✅ — تم خصم المخزون تلقائياً', 'success');
    closeModal();
    navigateTo('warehouse');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function viewWarehouseInvoiceItems(id) {
  try {
    const invoices = await API.getWarehouseInvoices();
    const inv = (invoices || []).find(x => x.id === id);
    const items = inv?.items || [];

    openModal(`
      <div class="modal-header">
        <div class="modal-title">📋 أصناف الفاتورة #${escHtml(inv?.invoice_number || id)}</div>
        <button class="modal-close" onclick="closeModal()">✕</button>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; padding:12px; background:var(--bg); border-radius:var(--r)">
        <div><span style="color:var(--tx3); font-size:11px">المشتري</span><br><strong>${escHtml(inv?.buyer_name || '—')}</strong></div>
        <div><span style="color:var(--tx3); font-size:11px">المورد</span><br><strong>${escHtml(inv?.supplier_name || '—')}</strong></div>
        <div><span style="color:var(--tx3); font-size:11px">طرف الفاتورة</span><br><strong>${escHtml(inv?.issued_by_name || '—')}</strong></div>
        <div><span style="color:var(--tx3); font-size:11px">الفئة</span><br><strong>${escHtml(inv?.category_name || '—')}</strong></div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>الصنف</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr></thead>
          <tbody>
            ${items.length ? items.map(i => `<tr>
              <td>${escHtml(i.product_name || '—')}</td>
              <td>${i.quantity}</td>
              <td>${fmt(i.unit_price)} د.أ</td>
              <td style="font-weight:700">${fmt(i.total)} د.أ</td>
            </tr>`).join('') : `<tr><td colspan="4" style="text-align:center; padding:20px; color:var(--tx3)">لا توجد أصناف</td></tr>`}
          </tbody>
        </table>
      </div>
      <div style="margin-top:12px; text-align:left; font-size:15px; font-weight:800">
        الإجمالي: ${fmt(inv?.total)} د.أ
      </div>
    `, '550px');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteWarehouseInvoice(id) {
  if (!confirm('حذف هذه الفاتورة؟')) return;
  try {
    await API.deleteWarehouseInvoice(id);
    toast('تم الحذف', 'success');
    closeModal();
    navigateTo('warehouse');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function viewMovements(productId, productName) {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">📊 حركات — ${escHtml(productName)}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="mv-content"><div class="loading"><div class="spinner"></div></div></div>
  `, '600px');

  try {
    const movements = await API.getStockMovements(productId);
    const el = document.getElementById('mv-content');
    if (!el) return;

    el.innerHTML = `
      <div class="table-wrap" style="max-height:360px; overflow-y:auto">
        <table>
          <thead><tr><th>النوع</th><th>الكمية</th><th>المصدر</th><th>ملاحظات</th><th>التاريخ</th></tr></thead>
          <tbody>
            ${movements.length ? movements.map(m => `<tr>
              <td>${m.type === 'in'
        ? '<span class="badge badge-green">↓ دخول</span>'
        : '<span class="badge badge-red">↑ خروج</span>'}</td>
              <td style="font-weight:700">${m.quantity}</td>
              <td style="font-size:12px; color:var(--tx2)">${escHtml(m.source_type || '—')}</td>
              <td style="font-size:12px; color:var(--tx3)">${escHtml(m.notes || '—')}</td>
              <td style="font-size:12px; color:var(--tx3)">${fmtDate(m.created_at)}</td>
            </tr>`).join('') : emptyRow('لا توجد حركات', 5)}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    const el = document.getElementById('mv-content');
    if (el) el.innerHTML = `<div class="alert alert-danger">${escHtml(e.message)}</div>`;
  }
}
/* ═══════════════════════════════════════════════════
   USERS (Admin Only)
═══════════════════════════════════════════════════ */
async function renderUsers(container) {
  if (!isAdmin()) {
    container.innerHTML = `<div class="alert alert-danger">غير مصرح لك بالوصول</div>`;
    return;
  }

  let users = [];
  try { users = await API.getUsers() || []; } catch (e) { users = []; }

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">إدارة المستخدمين</div>
        <div class="page-sub">${users.length} مستخدم مسجّل</div>
      </div>
      <div style="display:flex; gap:10px">
        <button class="btn btn-primary" onclick="openUserModal()">+ مستخدم جديد</button>
        <button class="btn btn-ghost btn-sm" onclick="printUsersFromEncoded(${jsString(encodePayload(users))})">🖨️</button>
      </div>
    </div>

    <div class="card" style="padding:0; overflow:hidden">
      <div class="table-wrap">
        <table>
          <thead><tr><th>الاسم الكامل</th><th>اسم المستخدم</th><th>الصلاحية</th><th>تاريخ الإنشاء</th><th>الإجراءات</th></tr></thead>
          <tbody>
            ${users.length
      ? users.map(u => `<tr>
                  <td>
                    <div style="display:flex; align-items:center; gap:10px">
                      <div class="user-avatar" style="background:${u.role === 'admin' ? 'var(--rd)' : 'var(--bl)'}">${escHtml(u.full_name?.charAt(0) || '?')}</div>
                      <strong>${escHtml(u.full_name || '—')}</strong>
                    </div>
                  </td>
                  <td style="font-family:monospace; color:var(--tx2)">${escHtml(u.username || '—')}</td>
                  <td>${roleBadge(u.role)}</td>
                  <td style="font-size:12px; color:var(--tx3)">${fmtDate(u.created_at)}</td>
                  <td>
                    ${u.id !== getUser()?.id
          ? `<button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id}, ${jsString(u.full_name)})">🗑️ حذف</button>`
          : '<span style="font-size:12px; color:var(--tx3)">أنت</span>'}
                  </td>
                </tr>`).join('')
      : emptyRow('لا يوجد مستخدمون', 5)}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function openUserModal() {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">إضافة مستخدم جديد</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-group">
      <label class="form-label">الاسم الكامل *</label>
      <input class="form-input" id="nu_name" placeholder="مثال: أحمد محمد">
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">اسم المستخدم *</label>
        <input class="form-input" id="nu_user" placeholder="بالإنجليزية">
      </div>
      <div class="form-group">
        <label class="form-label">كلمة المرور *</label>
        <input class="form-input" id="nu_pass" type="password" placeholder="••••••">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">الصلاحية *</label>
      <select class="form-select" id="nu_role">
        <option value="accountant">محاسب</option>
        <option value="employee">موظف</option>
        <option value="admin">مدير عام</option>
        <option value="client">عميل</option>
      </select>
    </div>
    <div style="display:flex; gap:10px; margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="saveUser()">إنشاء الحساب</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveUser() {
  const name = document.getElementById('nu_name').value.trim();
  const username = document.getElementById('nu_user').value.trim();
  const password = document.getElementById('nu_pass').value;
  const role = document.getElementById('nu_role').value;

  if (!name || !username || !password) {
    toast('يرجى ملء جميع الحقول', 'error');
    return;
  }

  try {
    await API.createUser({ full_name: name, username, password, role });
    toast('تم إنشاء الحساب بنجاح', 'success');
    closeModal();
    navigateTo('users');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteUser(id, name) {
  if (!confirm(`حذف المستخدم "${name}"؟`)) return;
  try {
    await API.deleteUser(id);
    toast('تم حذف المستخدم', 'success');
    navigateTo('users');
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ═══════════════════════════════════════════════════
   AUDIT LOG
═══════════════════════════════════════════════════ */
async function renderAudit(container) {
  if (!isAdmin()) {
    container.innerHTML = `<div class="alert alert-danger">غير مصرح لك بالوصول</div>`;
    return;
  }

  let log = [];
  try { log = await API.getAuditLog() || []; } catch (e) { log = []; }

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">سجل العمليات</div>
        <div class="page-sub">${log.length} عملية مسجّلة</div>
      </div>
    </div>

    <div class="card" style="padding:0; overflow:hidden">
      <div class="table-wrap" style="max-height:600px; overflow-y:auto">
        <table>
          <thead><tr><th>المستخدم</th><th>العملية</th><th>التفاصيل</th><th>التاريخ والوقت</th></tr></thead>
          <tbody>
            ${log.length
      ? log.map(l => `<tr>
                  <td><strong>${escHtml(l.user_name || l.username || '—')}</strong></td>
                  <td><span class="badge badge-blue">${escHtml(l.action || '—')}</span></td>
                  <td style="font-size:12px; color:var(--tx2); max-width:300px">${escHtml(l.detail || l.details || '—')}</td>
                  <td style="font-size:12px; color:var(--tx3); white-space:nowrap">${fmtDate(l.created_at)}</td>
                </tr>`).join('')
      : emptyRow('لا توجد سجلات', 4)}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/* ═══════════════════════════════════════════════════
   MY ACCOUNT (Client View)
═══════════════════════════════════════════════════ */
async function renderMyAccount(container) {
  const user = getUser();
  container.innerHTML = `<div class="loading"><div class="spinner"></div><p>جاري تحميل كشف حسابك...</p></div>`;

  try {
    const clients = await API.getClients();
    const myClient = clients?.find(c => c.user_id === user.id) || clients?.[0];

    if (!myClient) {
      container.innerHTML = `
        <div class="page-header"><div class="page-title">كشف حسابي</div></div>
        <div class="card">
          <div class="empty-state">
            <div class="empty-icon">🔗</div>
            <p>لم يتم ربط حسابك بعميل بعد. يرجى التواصل مع الإدارة.</p>
          </div>
        </div>`;
      return;
    }

    const data = await API.getClientStatement(myClient.id);
    const txs = data.transactions || [];
    const balance = parseFloat(data.balance || 0);
    const encoded = encodePayload(data);

    container.innerHTML = `
      <div class="page-header">
        <div class="page-title">كشف حسابي</div>
        <div class="page-sub">${escHtml(myClient.name || '—')}</div>
      </div>

      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap:16px; margin-bottom:20px">
        <div class="metric-card ${balance > 0 ? 'red' : 'green'}">
          <div class="metric-label">${balance > 0 ? 'مستحق عليك' : 'رصيدك الدائن'}</div>
          <div class="metric-value">${fmt(Math.abs(balance))}</div>
          <div class="metric-sub">دينار أردني</div>
        </div>
        <div class="metric-card blue">
          <div class="metric-label">عدد الفواتير</div>
          <div class="metric-value">${txs.filter(t => t.type === 'invoice').length}</div>
          <div class="metric-sub">فاتورة</div>
        </div>
        <div class="metric-card green">
          <div class="metric-label">إجمالي المدفوعات</div>
          <div class="metric-value">${fmt(txs.filter(t => t.type === 'payment').reduce((s, t) => s + parseFloat(t.amount), 0))}</div>
          <div class="metric-sub">دينار أردني</div>
        </div>
      </div>

      <div class="card" style="padding:0; overflow:hidden">
        <div style="padding:16px 20px; border-bottom:1px solid var(--brd); display:flex; justify-content:space-between; align-items:center">
          <div class="card-title" style="margin:0">حركات الحساب</div>
          <button class="btn btn-ghost btn-sm" onclick="printMyStatementFromEncoded(${jsString(myClient.name)}, ${jsString(encoded)})">🖨️ طباعة</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>التاريخ</th><th>البيان</th><th>مدين (عليك)</th><th>دائن (لك)</th><th>الرصيد</th></tr></thead>
            <tbody>
              ${txs.length
        ? txs.map(t => `<tr>
                    <td style="font-size:12px">${fmtDate(t.date)}</td>
                    <td>${escHtml(t.description || (t.type === 'invoice' ? 'فاتورة مبيعات' : 'مقبوضة'))}</td>
                    <td style="color:var(--rd)">${t.type === 'invoice' ? fmt(t.amount) : '—'}</td>
                    <td style="color:var(--gr)">${t.type === 'payment' ? fmt(t.amount) : '—'}</td>
                    <td style="font-weight:700">${fmt(t.running_balance || 0)} د.أ</td>
                  </tr>`).join('')
        : '<tr><td colspan="5" style="text-align:center; padding:24px; color:var(--tx3)">لا توجد حركات حتى الآن</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">${escHtml(e.message)}</div>`;
  }
}

/* ═══════════════════════════════════════════════════
═══════════════════════════════════════════════════ */

function printStatement(name, data) {
  const txs = data.transactions || [];
  const w = window.open('', '_blank');
  w.document.write(`<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
    <title>كشف حساب — ${escHtml(name)}</title>
    <style>
      body{font-family:Arial,sans-serif;padding:40px;direction:rtl}
      .header{text-align:center;margin-bottom:30px;border-bottom:2px solid #000;padding-bottom:20px}
      table{width:100%;border-collapse:collapse}
      th,td{border:1px solid #ccc;padding:10px;text-align:right;font-size:13px}
      th{background:#f0f0f0}
    </style>
  </head><body>
    <div class="header">
      <h1>مجموعة أبو عمران التجارية</h1>
      <h2>كشف حساب — ${escHtml(name)}</h2>
      <p>تاريخ الطباعة: ${new Date().toLocaleDateString('ar-JO')}</p>
    </div>
    <p><strong>الرصيد الحالي:</strong> ${fmt(data.balance)} دينار أردني</p><br>
    <table>
      <thead><tr><th>التاريخ</th><th>البيان</th><th>مدين</th><th>دائن</th><th>الرصيد</th></tr></thead>
      <tbody>
        ${txs.map(t => `<tr>
          <td>${fmtDate(t.date)}</td>
          <td>${escHtml(t.description || (t.type === 'invoice' ? 'فاتورة' : 'مقبوضة'))}</td>
          <td>${t.type === 'invoice' ? fmt(t.amount) : '—'}</td>
          <td>${t.type === 'payment' ? fmt(t.amount) : '—'}</td>
          <td>${fmt(t.running_balance || 0)}</td>
        </tr>`).join('')}
      </tbody>
    </table>
  </body></html>`);
  w.document.close();
  setTimeout(() => w.print(), 500);
}

function printMyStatement(name, data) { printStatement(name, data); }

function printPayments(payments) {
  const w = window.open('', '_blank');
  const total = payments.reduce((s, p) => s + parseFloat(p.amount || 0), 0);
  w.document.write(`<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
    <title>تقرير المقبوضات</title>
    <style>
      body{font-family:Arial,sans-serif;padding:40px;direction:rtl;font-size:13px}
      h1{font-size:22px}
      table{width:100%;border-collapse:collapse;margin-top:16px}
      th{background:#1a1815;color:white;padding:10px;text-align:right;font-size:12px}
      td{padding:10px;border-bottom:1px solid #eee}
      .total{margin-top:20px;font-size:16px;font-weight:bold}
    </style>
  </head><body>
    <h1>📦 مجموعة أبو عمران — تقرير المقبوضات</h1>
    <p style="color:#888">${new Date().toLocaleDateString('ar-JO', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
    <table>
      <thead><tr><th>#</th><th>العميل</th><th>المبلغ</th><th>التاريخ</th><th>ملاحظات</th></tr></thead>
      <tbody>
        ${payments.map((p, i) => `<tr>
          <td>${i + 1}</td>
          <td><strong>${escHtml(p.client_name || '—')}</strong></td>
          <td style="color:#057a55;font-weight:700">${fmt(p.amount)} د.أ</td>
          <td>${fmtDate(p.payment_date)}</td>
          <td style="color:#888">${escHtml(p.notes || '—')}</td>
        </tr>`).join('')}
      </tbody>
    </table>
    <div class="total">الإجمالي: ${fmt(total)} دينار أردني</div>
  </body></html>`);
  w.document.close();
  setTimeout(() => w.print(), 500);
}

function printChecks(checks) {
  const w = window.open('', '_blank');
  const total = checks.reduce((s, c) => s + parseFloat(c.amount || 0), 0);
  const today = new Date().toISOString().split('T')[0];
  w.document.write(`<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
    <title>تقرير الشيكات</title>
    <style>
      body{font-family:Arial,sans-serif;padding:40px;direction:rtl;font-size:13px}
      h1{font-size:22px}
      table{width:100%;border-collapse:collapse;margin-top:16px}
      th{background:#1a1815;color:white;padding:10px;text-align:right;font-size:12px}
      td{padding:10px;border-bottom:1px solid #eee}
      .total{margin-top:20px;font-size:16px;font-weight:bold}
      .overdue{color:#c21515;font-weight:bold}
    </style>
  </head><body>
    <h1>📦 مجموعة أبو عمران — تقرير الشيكات</h1>
    <p style="color:#888">${new Date().toLocaleDateString('ar-JO', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
    <table>
      <thead><tr><th>#</th><th>العميل</th><th>رقم الشيك</th><th>المبلغ</th><th>الاستحقاق</th><th>الحالة</th></tr></thead>
      <tbody>
        ${checks.map((c, i) => {
    const over = c.status === 'pending' && c.due_date?.split('T')[0] < today;
    return `<tr>
            <td>${i + 1}</td>
            <td><strong>${escHtml(c.client_name || '—')}</strong></td>
            <td style="font-family:monospace">${escHtml(c.check_number || '—')}</td>
            <td style="font-weight:700">${fmt(c.amount)} د.أ</td>
            <td class="${over ? 'overdue' : ''}">${fmtDate(c.due_date)}${over ? ' ⚠️' : ''}</td>
            <td>${({ pending: 'معلّق', cashed: 'محصَّل', returned: 'مرتجع', cancelled: 'ملغى' }[c.status] || c.status)}</td>
          </tr>`;
  }).join('')}
      </tbody>
    </table>
    <div class="total">إجمالي: ${fmt(total)} دينار أردني</div>
  </body></html>`);
  w.document.close();
  setTimeout(() => w.print(), 500);
}

function printClients(clients) {
  const w = window.open('', '_blank');
  const totalDebt = clients.reduce((s, c) => s + parseFloat(c.balance || 0), 0);
  const deptLabel = { porcelain: 'بورسلان', egyptian: 'مصري', shoes: 'أخرى' };
  w.document.write(`<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
    <title>تقرير العملاء</title>
    <style>
      body{font-family:Arial,sans-serif;padding:40px;direction:rtl;font-size:13px}
      h1{font-size:22px}
      table{width:100%;border-collapse:collapse;margin-top:16px}
      th{background:#1a1815;color:white;padding:10px;text-align:right;font-size:12px}
      td{padding:10px;border-bottom:1px solid #eee}
      .total{margin-top:20px;font-size:16px;font-weight:bold}
    </style>
  </head><body>
    <h1>📦 مجموعة أبو عمران — تقرير العملاء</h1>
    <p style="color:#888">${new Date().toLocaleDateString('ar-JO', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
    <table>
      <thead><tr><th>#</th><th>اسم العميل</th><th>القسم</th><th>الرصيد</th><th>حد الائتمان</th><th>الخطر</th><th>الهاتف</th></tr></thead>
      <tbody>
        ${clients.map((c, i) => `<tr>
          <td>${i + 1}</td>
          <td><strong>${escHtml(c.name)}</strong></td>
          <td>${deptLabel[c.department] || c.department || '—'}</td>
          <td style="color:${parseFloat(c.balance || 0) > 0 ? '#c21515' : '#057a55'};font-weight:700">${fmt(c.balance)} د.أ</td>
          <td>${fmt(c.credit_limit)} د.أ</td>
          <td>${({ low: 'منخفض', medium: 'متوسط', high: 'عالٍ' }[c.risk_level] || c.risk_level)}</td>
          <td>${escHtml(c.phone || '—')}</td>
        </tr>`).join('')}
      </tbody>
    </table>
    <div class="total">إجمالي الديون: ${fmt(totalDebt)} دينار أردني</div>
  </body></html>`);
  w.document.close();
  setTimeout(() => w.print(), 500);
}

function printUsers(users) {
  const w = window.open('', '_blank');
  const roleMap = { admin: 'مدير عام', accountant: 'محاسب', employee: 'موظف', client: 'عميل' };
  w.document.write(`<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
    <title>تقرير المستخدمين</title>
    <style>
      body{font-family:Arial,sans-serif;padding:40px;direction:rtl;font-size:13px}
      h1{font-size:22px}
      table{width:100%;border-collapse:collapse;margin-top:16px}
      th{background:#1a1815;color:white;padding:10px;text-align:right;font-size:12px}
      td{padding:10px;border-bottom:1px solid #eee}
    </style>
  </head><body>
    <h1>📦 مجموعة أبو عمران — تقرير المستخدمين</h1>
    <p style="color:#888">${new Date().toLocaleDateString('ar-JO', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
    <table>
      <thead><tr><th>#</th><th>الاسم الكامل</th><th>اسم المستخدم</th><th>الصلاحية</th><th>تاريخ الإنشاء</th></tr></thead>
      <tbody>
        ${users.map((u, i) => `<tr>
          <td>${i + 1}</td>
          <td><strong>${escHtml(u.full_name)}</strong></td>
          <td style="font-family:monospace">${escHtml(u.username)}</td>
          <td>${roleMap[u.role] || u.role}</td>
          <td>${fmtDate(u.created_at)}</td>
        </tr>`).join('')}
      </tbody>
    </table>
  </body></html>`);
  w.document.close();
  setTimeout(() => w.print(), 500);
}

function printInvoicesList(invoices) {
  const w = window.open('', '_blank');
  const total = invoices.reduce((s, i) => s + parseFloat(i.total_amount || i.net_amount || 0), 0);
  w.document.write(`<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">
    <title>تقرير الفواتير</title>
    <style>
      body{font-family:Arial,sans-serif;padding:40px;direction:rtl;font-size:13px}
      h1{font-size:22px}
      table{width:100%;border-collapse:collapse;margin-top:16px}
      th{background:#1a1815;color:white;padding:10px;text-align:right;font-size:12px}
      td{padding:10px;border-bottom:1px solid #eee}
      .total{margin-top:20px;font-size:16px;font-weight:bold}
    </style>
  </head><body>
    <h1>📦 مجموعة أبو عمران — تقرير الفواتير</h1>
    <p style="color:#888">${new Date().toLocaleDateString('ar-JO', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
    <table>
      <thead><tr><th>#</th><th>رقم الفاتورة</th><th>العميل</th><th>صافي</th><th>ضريبة</th><th>الإجمالي</th><th>التاريخ</th></tr></thead>
      <tbody>
        ${invoices.map((inv, i) => `<tr>
          <td>${i + 1}</td>
          <td><strong>#${escHtml(inv.invoice_number || inv.id)}</strong></td>
          <td>${escHtml(inv.client_name || '—')}</td>
          <td>${fmt(inv.net_amount)} د.أ</td>
          <td>${fmt(inv.tax_amount || 0)} د.أ</td>
          <td style="font-weight:700">${fmt(inv.total_amount || inv.net_amount)} د.أ</td>
          <td>${fmtDate(inv.date || inv.invoice_date)}</td>
        </tr>`).join('')}
      </tbody>
    </table>
    <div class="total">الإجمالي: ${fmt(total)} دينار أردني</div>
  </body></html>`);
  w.document.close();
  setTimeout(() => w.print(), 500);
}

/* ═══════════════════════════════════════════════════
   ANALYTICS DASHBOARD
═══════════════════════════════════════════════════ */
async function renderAnalytics(container) {
  if (!isAdmin() && !isAccountant()) {
    container.innerHTML = `<div class="alert alert-danger">غير مصرح</div>`;
    return;
  }

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">📊 لوحة التحليلات</div>
        <div class="page-sub">تحليل مالي ذكي شامل — ${new Date().toLocaleDateString('ar-JO', { weekday: 'long', day: 'numeric', month: 'long' })}</div>
      </div>
      <button class="btn btn-primary" onclick="refreshAnalytics()">🔄 تحديث</button>
    </div>

    <div style="display:grid; grid-template-columns:1fr 340px; gap:16px; align-items:start">

      <div style="display:flex; flex-direction:column; gap:16px">
        <div id="an-kpis" style="display:grid; grid-template-columns:repeat(4,1fr); gap:12px">
          ${[1, 2, 3, 4].map(() => `<div class="metric-card" style="height:90px; background:#f5f3f0; border:none; box-shadow:none; animation: pulse 1.5s infinite"></div>`).join('')}
        </div>

        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
            <div class="card-title" style="margin:0">📈 المبيعات والتحصيل</div>
            <div style="display:flex; gap:6px">
              <button class="btn btn-ghost btn-sm" onclick="loadSalesChart('daily')" id="an-d">يومي</button>
              <button class="btn btn-primary btn-sm" onclick="loadSalesChart('weekly')" id="an-w">أسبوعي</button>
              <button class="btn btn-ghost btn-sm" onclick="loadSalesChart('monthly')" id="an-m">شهري</button>
            </div>
          </div>
          <div id="an-sales-chart"><div class="loading"><div class="spinner"></div></div></div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px">
          <div class="card">
            <div class="card-title">🥧 توزيع مستوى الخطر</div>
            <div id="an-risk-chart"><div class="loading"><div class="spinner"></div></div></div>
          </div>
          <div class="card">
            <div class="card-title">🏦 حالة الشيكات</div>
            <div id="an-checks-chart"><div class="loading"><div class="spinner"></div></div></div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">🔴 أعلى العملاء مديونية</div>
          <div id="an-debtors-chart"><div class="loading"><div class="spinner"></div></div></div>
        </div>
      </div>

      <div style="position:sticky; top:80px">
        <div class="card" style="padding:0; overflow:hidden; height:calc(100vh - 140px); display:flex; flex-direction:column">
          <div style="background:#1a1815; color:white; padding:16px; display:flex; align-items:center; gap:10px; flex-shrink:0">
            <div style="width:36px; height:36px; background:rgba(255,255,255,.1); border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:18px">🤖</div>
            <div>
              <div style="font-weight:700; font-size:13px">محلل البيانات الذكي</div>
              <div style="font-size:10px; opacity:.5" id="agent-status">يحلل البيانات...</div>
            </div>
          </div>

          <div id="agent-analysis" style="background:linear-gradient(135deg,#eef3ff,#f0fdf4); border-bottom:1px solid rgba(0,0,0,.06); padding:12px 14px; font-size:12px; line-height:1.7; flex-shrink:0; max-height:180px; overflow-y:auto">
            <div style="display:flex; gap:6px; align-items:center; color:#9e9a94">
              <div class="spinner" style="width:14px;height:14px;border-width:2px;margin:0"></div>
              <span>جاري تحليل الوضع المالي الكامل...</span>
            </div>
          </div>

          <div id="agent-chips" style="display:flex; gap:6px; padding:10px 12px; overflow-x:auto; flex-shrink:0; border-bottom:1px solid rgba(0,0,0,.05); scrollbar-width:none"></div>

          <div id="agent-msgs" style="flex:1; overflow-y:auto; padding:12px; display:flex; flex-direction:column; gap:8px; scrollbar-width:thin">
            <div class="msg-bot" style="font-size:12px">اسألني عن أي رقم أو تحليل تراه أمامك 👆</div>
          </div>

          <div style="display:flex; gap:8px; padding:10px 12px; border-top:1px solid rgba(0,0,0,.07); flex-shrink:0">
            <input id="agent-input" style="flex:1; padding:9px 12px; border:1px solid rgba(0,0,0,.12); border-radius:10px; font-family:inherit; font-size:12px; outline:none; direction:rtl; text-align:right; background:#faf9f7" placeholder="اسأل عن البيانات..." />
            <button onclick="sendAgentMessage()" style="width:34px; height:34px; background:#1a1815; border:none; border-radius:9px; cursor:pointer; color:white; font-size:16px; display:flex; align-items:center; justify-content:center">➤</button>
          </div>
        </div>
      </div>
    </div>
  `;

  await Promise.all([
    loadAnalyticsKPIs(),
    loadSalesChart('weekly'),
    loadRiskChart(),
    loadChecksChart(),
    loadDebtorsChart(),
  ]);

  loadAgentAnalysis();

  document.getElementById('agent-chips').innerHTML = [
    'ما أكبر مشكلة مالية الآن؟',
    'من أكثر العملاء خطراً؟',
    'كيف المبيعات هذا الشهر؟',
    'الشيكات المتأخرة',
    'توصياتك للأسبوع القادم',
  ].map(c => `<button onclick="sendAgentChip(${jsString(c)})" style="flex-shrink:0; padding:5px 10px; background:#f4f3f0; border:1px solid rgba(0,0,0,.07); border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap; font-family:inherit; color:#5a5650">${c}</button>`).join('');

  document.getElementById('agent-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendAgentMessage();
  });
}

async function loadAnalyticsKPIs() {
  try {
    const [stats, clients, checks] = await Promise.all([
      API.getStats(), API.getClients(), API.getChecks()
    ]);

    const overdueChecks = (checks || []).filter(c => c.status === 'pending' && c.due_date?.split('T')[0] < new Date().toISOString().split('T')[0]);
    const collectRate = stats.total_sales > 0 ? ((stats.total_payments / stats.total_sales) * 100).toFixed(1) : 0;

    document.getElementById('an-kpis').innerHTML = `
      <div class="metric-card blue"><div class="metric-icon">📈</div><div class="metric-label">إجمالي المبيعات</div><div class="metric-value" style="font-size:20px">${fmt(stats.total_sales)}</div><div class="metric-sub">د.أ</div></div>
      <div class="metric-card red"><div class="metric-icon">💳</div><div class="metric-label">الديون القائمة</div><div class="metric-value" style="font-size:20px">${fmt(stats.total_debts)}</div><div class="metric-sub">د.أ</div></div>
      <div class="metric-card green"><div class="metric-icon">📊</div><div class="metric-label">نسبة التحصيل</div><div class="metric-value" style="font-size:20px">${collectRate}%</div><div class="metric-sub">من إجمالي المبيعات</div></div>
      <div class="metric-card amber"><div class="metric-icon">⚠️</div><div class="metric-label">شيكات متأخرة</div><div class="metric-value" style="font-size:20px">${overdueChecks.length}</div><div class="metric-sub">شيك متأخر</div></div>
    `;
  } catch (e) { }
}

let _currentSalesPeriod = 'weekly';

async function loadSalesChart(period = 'weekly') {
  _currentSalesPeriod = period;
  ['d', 'w', 'm'].forEach(x => {
    const el = document.getElementById(`an-${x}`);
    if (el) el.className = 'btn btn-ghost btn-sm';
  });

  const map = { daily: 'd', weekly: 'w', monthly: 'm' };
  const activeEl = document.getElementById(`an-${map[period]}`);
  if (activeEl) activeEl.className = 'btn btn-primary btn-sm';

  const el = document.getElementById('an-sales-chart');
  el.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;

  try {
    const data = await apiFetch(`/ai/analytics?period=${period}`);
    const sales = data.sales || [];
    const payments = data.payments || [];

    if (!sales.length) {
      el.innerHTML = `<div class="empty-state" style="padding:30px"><p>لا توجد بيانات</p></div>`;
      return;
    }

    const maxVal = Math.max(...sales.map(s => parseFloat(s.total_sales || 0)), ...payments.map(p => parseFloat(p.total_collected || 0)), 1);
    const W = 600, H = 160, PAD = 30, barW = Math.min(28, (W - PAD * 2) / (sales.length * 2.5));

    const salesBars = sales.slice(-12).map((s, i) => {
      const h = (parseFloat(s.total_sales || 0) / maxVal) * H;
      const x = PAD + i * ((W - PAD * 2) / Math.min(sales.length, 12));
      const pay = payments[i] ? parseFloat(payments[i].total_collected || 0) : 0;
      const ph = (pay / maxVal) * H;
      const label = new Date(s.period).toLocaleDateString('ar-JO', period === 'monthly' ? { month: 'short' } : { month: 'short', day: 'numeric' });
      return `
        <rect x="${x}" y="${H - h}" width="${barW}" height="${h}" fill="#1a4fd6" rx="3" opacity=".85"></rect>
        <rect x="${x + barW + 2}" y="${H - ph}" width="${barW}" height="${ph}" fill="#0a7650" rx="3" opacity=".85"></rect>
        <text x="${x + barW}" y="${H + 14}" text-anchor="middle" font-size="9" fill="#9e9a94">${label}</text>
      `;
    }).join('');

    el.innerHTML = `
      <div style="display:flex; gap:16px; margin-bottom:10px">
        <div style="display:flex; align-items:center; gap:6px; font-size:11px"><div style="width:12px;height:12px;background:#1a4fd6;border-radius:3px"></div> المبيعات</div>
        <div style="display:flex; align-items:center; gap:6px; font-size:11px"><div style="width:12px;height:12px;background:#0a7650;border-radius:3px"></div> المحصّل</div>
      </div>
      <svg viewBox="0 0 ${W} ${H + 20}" style="width:100%;height:auto;overflow:visible" dir="ltr">
        ${[0.25, 0.5, 0.75, 1].map(r => `
          <line x1="${PAD}" y1="${H - r * H}" x2="${W - PAD}" y2="${H - r * H}" stroke="#f0ede8" stroke-width="1"/>
          <text x="${PAD - 4}" y="${H - r * H + 4}" text-anchor="end" font-size="9" fill="#9e9a94">${fmt(maxVal * r / 1000)}k</text>
        `).join('')}
        <line x1="${PAD}" y1="${H}" x2="${W - PAD}" y2="${H}" stroke="#e0ddd8" stroke-width="1"/>
        ${salesBars}
      </svg>
    `;
  } catch (e) {
    el.innerHTML = `<div class="alert alert-danger" style="font-size:12px">${escHtml(e.message)}</div>`;
  }
}

async function loadRiskChart() {
  const el = document.getElementById('an-risk-chart');
  try {
    const clients = await API.getClients();
    const low = clients.filter(c => c.risk_level === 'low').length;
    const med = clients.filter(c => c.risk_level === 'medium').length;
    const high = clients.filter(c => c.risk_level === 'high').length;
    const total = clients.length || 1;

    const slices = [
      { val: low, color: '#0a7650', label: 'منخفض' },
      { val: med, color: '#9a4500', label: 'متوسط' },
      { val: high, color: '#c21515', label: 'عالٍ' },
    ];

    let startAngle = -Math.PI / 2;
    const cx = 80, cy = 80, r = 60, ir = 35;

    const paths = slices.map(s => {
      const angle = (s.val / total) * 2 * Math.PI;
      if (angle === 0) return '';
      const x1 = cx + r * Math.cos(startAngle);
      const y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(startAngle + angle);
      const y2 = cy + r * Math.sin(startAngle + angle);
      const xi1 = cx + ir * Math.cos(startAngle);
      const yi1 = cy + ir * Math.sin(startAngle);
      const xi2 = cx + ir * Math.cos(startAngle + angle);
      const yi2 = cy + ir * Math.sin(startAngle + angle);
      const large = angle > Math.PI ? 1 : 0;
      const path = `M ${xi1} ${yi1} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} L ${xi2} ${yi2} A ${ir} ${ir} 0 ${large} 0 ${xi1} ${yi1} Z`;
      startAngle += angle;
      return `<path d="${path}" fill="${s.color}" opacity=".85"></path>`;
    }).join('');

    const legend = slices.map(s => `
      <div style="display:flex; align-items:center; gap:6px; font-size:11px">
        <div style="width:10px;height:10px;background:${s.color};border-radius:50%;flex-shrink:0"></div>
        <span style="color:var(--tx2)">${s.label}</span>
        <span style="font-weight:700;margin-right:auto">${s.val}</span>
      </div>
    `).join('');

    el.innerHTML = `
      <div style="display:flex; align-items:center; gap:16px">
        <svg viewBox="0 0 160 160" style="width:120px;flex-shrink:0" dir="ltr">
          ${paths}
          <text x="${cx}" y="${cy - 6}" text-anchor="middle" font-size="18" font-weight="800" fill="#1a1815">${total}</text>
          <text x="${cx}" y="${cy + 12}" text-anchor="middle" font-size="9" fill="#9e9a94">عميل</text>
        </svg>
        <div style="display:flex;flex-direction:column;gap:8px;flex:1">${legend}</div>
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<div style="color:var(--tx3);font-size:12px">تعذّر التحميل</div>`;
  }
}

async function loadChecksChart() {
  const el = document.getElementById('an-checks-chart');
  try {
    const checks = await API.getChecks();
    const today = new Date().toISOString().split('T')[0];
    const pending = checks.filter(c => c.status === 'pending').length;
    const cashed = checks.filter(c => c.status === 'cashed').length;
    const returned = checks.filter(c => c.status === 'returned').length;
    const overdue = checks.filter(c => c.status === 'pending' && c.due_date?.split('T')[0] < today).length;

    const bars = [
      { label: 'معلّق', val: pending, color: '#9a4500' },
      { label: 'محصّل', val: cashed, color: '#0a7650' },
      { label: 'مرتجع', val: returned, color: '#c21515' },
      { label: 'متأخر', val: overdue, color: '#c21515', opacity: '.4' },
    ];
    const max = Math.max(...bars.map(b => b.val), 1);

    el.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:8px">
        ${bars.map(b => `
          <div>
            <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px">
              <span style="color:var(--tx2)">${b.label}</span>
              <span style="font-weight:700">${b.val}</span>
            </div>
            <div style="height:8px;background:#f0ede8;border-radius:4px;overflow:hidden">
              <div style="height:100%;width:${(b.val / max) * 100}%;background:${b.color};opacity:${b.opacity || '.85'};border-radius:4px;transition:width .4s"></div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<div style="color:var(--tx3);font-size:12px">تعذّر التحميل</div>`;
  }
}

async function loadDebtorsChart() {
  const el = document.getElementById('an-debtors-chart');
  try {
    const clients = await API.getClients();
    const sorted = [...clients]
      .filter(c => parseFloat(c.balance) > 0)
      .sort((a, b) => parseFloat(b.balance) - parseFloat(a.balance))
      .slice(0, 8);

    if (!sorted.length) {
      el.innerHTML = `<div class="empty-state" style="padding:20px"><p>لا توجد ديون مستحقة ✅</p></div>`;
      return;
    }

    const max = parseFloat(sorted[0].balance);
    const riskColor = { low: '#0a7650', medium: '#9a4500', high: '#c21515' };

    el.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:10px">
        ${sorted.map((c, i) => {
      const pct = (parseFloat(c.balance) / max) * 100;
      const color = riskColor[c.risk_level] || '#1a4fd6';
      return `
            <div style="display:flex;align-items:center;gap:10px">
              <div style="width:20px;text-align:center;font-size:11px;color:var(--tx3);font-weight:700">${i + 1}</div>
              <div style="flex:1">
                <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px">
                  <span style="font-weight:600">${escHtml(c.name)}</span>
                  <span style="color:var(--rd);font-weight:700">${fmt(c.balance)} د.أ</span>
                </div>
                <div style="height:10px;background:#f0ede8;border-radius:5px;overflow:hidden">
                  <div style="height:100%;width:${pct}%;background:${color};border-radius:5px;transition:width .5s"></div>
                </div>
              </div>
              ${riskLabel(c.risk_level)}
            </div>
          `;
    }).join('')}
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<div style="color:var(--tx3);font-size:12px">تعذّر التحميل</div>`;
  }
}

async function loadAgentAnalysis() {
  try {
    const data = await apiFetch('/ai/analyze', { method: 'POST', body: JSON.stringify({}) });
    const el = document.getElementById('agent-analysis');
    const status = document.getElementById('agent-status');
    if (el && data?.analysis) {
      el.innerHTML = `<div style="font-size:11.5px;line-height:1.7">${formatAiTextSafe(data.analysis)}</div>`;
    }
    if (status) status.textContent = 'جاهز للتحليل';
  } catch (e) {
    const el = document.getElementById('agent-analysis');
    if (el) el.style.display = 'none';
  }
}

async function sendAgentMessage() {
  const input = document.getElementById('agent-input');
  const msg = input.value.trim();
  if (!msg) return;

  const chat = document.getElementById('agent-msgs');
  const status = document.getElementById('agent-status');

  chat.innerHTML += `<div class="msg-user" style="font-size:12px">${escHtml(msg)}</div>`;
  input.value = '';
  input.disabled = true;
  if (status) status.textContent = 'يحلل...';
  chat.scrollTop = chat.scrollHeight;

  const typingEl = document.createElement('div');
  typingEl.style.cssText = 'display:flex;gap:4px;padding:8px 12px;background:#f4f3f0;border-radius:8px;align-self:flex-start;width:fit-content';
  typingEl.innerHTML = `<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>`;
  chat.appendChild(typingEl);
  chat.scrollTop = chat.scrollHeight;

  try {
    const res = await apiFetch('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ message: msg })
    });
    typingEl.remove();
    const reply = res?.reply || 'لم أتمكن من الإجابة';
    chat.innerHTML += `<div class="msg-bot" style="font-size:12px">${formatAiTextSafe(reply)}</div>`;
  } catch (e) {
    typingEl.remove();
    chat.innerHTML += `<div class="msg-bot" style="color:var(--rd);font-size:12px">❌ ${escHtml(e.message)}</div>`;
  }

  chat.scrollTop = chat.scrollHeight;
  input.disabled = false;
  input.focus();
  if (status) status.textContent = 'جاهز للتحليل';
}

function sendAgentChip(text) {
  document.getElementById('agent-input').value = text;
  sendAgentMessage();
}

function refreshAnalytics() {
  navigateTo('analytics');
}

/* ═══════════════════════════════════════════════════
   RECIPIENTS — زبائن الفواتير
═══════════════════════════════════════════════════ */
async function renderRecipients(container) {
  let list = [];
  try { list = await API.getRecipients() || []; } catch (e) { list = []; }

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">🧑‍🤝‍🧑 زبائن الفواتير</div>
        <div class="page-sub">${list.length} زبون مسجّل</div>
      </div>
      <div class="search-bar">
        <span>🔍</span>
        <input type="text" placeholder="بحث..." oninput="filterTable('recip-tbody', this.value)">
      </div>
    </div>

    <div class="card" style="padding:0; overflow:hidden">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>اسم الزبون</th>
              <th>العميل الرئيسي</th>
              <th>عدد الفواتير</th>
              <th>إجمالي الفواتير</th>
              <th>المدفوع</th>
              <th>الرصيد المتبقي</th>
              <th>الإجراءات</th>
            </tr>
          </thead>
          <tbody id="recip-tbody">
            ${list.length ? list.map(r => {
    const balance = parseFloat(r.balance || 0);
    const balColor = balance > 0 ? 'var(--rd)' : 'var(--gr)';
    return `<tr>
                <td><strong>${escHtml(r.name || '—')}</strong></td>
                <td><span class="badge badge-blue">${escHtml(r.client_name || '—')}</span></td>
                <td style="text-align:center">${r.invoice_count || 0}</td>
                <td style="font-weight:700">${fmt(r.total_invoiced)} د.أ</td>
                <td style="color:var(--gr); font-weight:700">${fmt(r.total_paid)} د.أ</td>
                <td style="color:${balColor}; font-weight:800">${fmt(balance)} د.أ</td>
                <td>
                  <div style="display:flex; gap:6px">
                    <button class="btn btn-ghost btn-sm"
                      onclick="viewRecipientStatement(${jsString(r.name)})">
                      📄 كشف
                    </button>
                    ${isAccountant() ? `
                    <button class="btn btn-primary btn-sm"
                      onclick="openRecipientPayment(${jsString(r.name)}, ${r.client_id || 'null'})">
                      💰 قبض
                    </button>` : ''}
                  </div>
                </td>
              </tr>`;
  }).join('') : '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--tx3)">لا يوجد زبائن بعد</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function viewRecipientStatement(name) {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">📄 كشف حساب — ${escHtml(name)}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="recip-stmt-content">
      <div class="loading"><div class="spinner"></div><p>جاري التحميل...</p></div>
    </div>
  `, '820px');

  try {
    const data = await API.getRecipientStatement(name);
    const el = document.getElementById('recip-stmt-content');
    if (!el) return;

    const txs = data.transactions || [];
    const balance = parseFloat(data.balance || 0);

    el.innerHTML = `
      <!-- ملخص -->
      <div style="background:#1a1815;color:white;padding:16px 20px;border-radius:12px;margin-bottom:16px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
        <div>
          <div style="font-size:10px;opacity:.5;margin-bottom:4px">إجمالي الفواتير</div>
          <div style="font-size:20px;font-weight:800;color:#ff6b6b">${fmt(data.total_invoiced)} د.أ</div>
        </div>
        <div>
          <div style="font-size:10px;opacity:.5;margin-bottom:4px">المدفوع</div>
          <div style="font-size:20px;font-weight:800;color:#51cf66">${fmt(data.total_paid)} د.أ</div>
        </div>
        <div>
          <div style="font-size:10px;opacity:.5;margin-bottom:4px">الرصيد المتبقي</div>
          <div style="font-size:20px;font-weight:800;color:${balance > 0 ? '#ff6b6b' : '#51cf66'}">${fmt(Math.abs(balance))} د.أ</div>
        </div>
      </div>

      <!-- الجدول -->
      <div style="border:1px solid #e8e5e0;border-radius:10px;overflow:hidden">
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead>
            <tr style="background:#f5f3f0">
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">التاريخ</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">البيان</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">مدين</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">دائن</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">الرصيد</th>
              <th style="padding:10px 12px"></th>
            </tr>
          </thead>
          <tbody>
            ${txs.length ? txs.map(t => {
      const isInv = t.type === 'invoice';
      return `<tr style="border-top:1px solid #f0ede8;${isInv ? '' : 'background:#f9fff9'}">
                <td style="padding:10px 12px;color:#9e9a94">${fmtDate(t.date)}</td>
                <td style="padding:10px 12px;font-weight:600">
                  ${isInv
          ? `فاتورة #${escHtml(t.invoice_number || t.id)} — ${escHtml(t.client_name || '')}`
          : `<span style="color:#057a55">دفعة مقبوضة</span>`}
                </td>
                <td style="padding:10px 12px;color:#c21515;font-weight:700">
                  ${isInv ? fmt(t.amount) + ' د.أ' : '—'}
                </td>
                <td style="padding:10px 12px;color:#057a55;font-weight:700">
                  ${!isInv ? fmt(t.amount) + ' د.أ' : '—'}
                </td>
                <td style="padding:10px 12px;font-weight:800;color:${parseFloat(t.running_balance) > 0 ? '#c21515' : '#057a55'}">
                  ${fmt(Math.abs(t.running_balance))} د.أ
                </td>
                <td style="padding:10px 12px">
                  ${!isInv && isAdmin()
          ? `<button class="btn btn-danger btn-sm" onclick="deleteRecipientPayment(${t.id}, ${jsString(name)})">🗑️</button>`
          : ''}
                </td>
              </tr>`;
    }).join('') : `<tr><td colspan="6" style="text-align:center;padding:30px;color:#9e9a94">لا توجد حركات</td></tr>`}
          </tbody>
        </table>
      </div>

      <div style="display:flex;gap:8px;margin-top:14px">
        ${isAccountant() ? `
        <button class="btn btn-primary btn-sm"
          onclick="closeModal(); openRecipientPayment(${jsString(name)}, ${txs.find(t => t.client_id)?.client_id || 'null'})">
          💰 تسجيل دفعة
        </button>` : ''}
        <button class="btn btn-ghost btn-sm" onclick="closeModal()">إغلاق</button>
      </div>
    `;
  } catch (e) {
    const el = document.getElementById('recip-stmt-content');
    if (el) el.innerHTML = `<div class="alert alert-danger">${escHtml(e.message)}</div>`;
  }
}

function openRecipientPayment(name, clientId) {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">💰 تسجيل دفعة — ${escHtml(name)}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-group">
      <label class="form-label">المبلغ (د.أ) *</label>
      <input class="form-input" id="rp_amount" type="number" min="0.001" step="0.001" placeholder="0.000">
    </div>
    <div class="form-group">
      <label class="form-label">تاريخ الدفع</label>
      <input class="form-input" id="rp_date" type="date" value="${new Date().toISOString().split('T')[0]}">
    </div>
    <div class="form-group">
      <label class="form-label">ملاحظات</label>
      <input class="form-input" id="rp_notes" placeholder="اختياري">
    </div>
    <div style="display:flex;gap:10px;margin-top:8px">
      <button class="btn btn-primary" style="flex:1"
        onclick="saveRecipientPayment(${jsString(name)}, ${clientId || 'null'})">
        تسجيل الدفعة
      </button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveRecipientPayment(name, clientId) {
  const amount = parseFloat(document.getElementById('rp_amount')?.value);
  if (!amount || amount <= 0) { toast('المبلغ غير صحيح', 'error'); return; }

  try {
    await API.createRecipientPayment({
      recipient_name: name,
      client_id: clientId || null,
      amount,
      payment_date: document.getElementById('rp_date')?.value,
      notes: document.getElementById('rp_notes')?.value || null,
    });
    toast('تم تسجيل الدفعة ✅', 'success');
    closeModal();
    viewRecipientStatement(name);
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteRecipientPayment(id, name) {
  if (!confirm('حذف هذه الدفعة؟')) return;
  try {
    await API.deleteRecipientPayment(id);
    toast('تم الحذف', 'success');
    viewRecipientStatement(name);
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function viewSupplierStatement(id, name) {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">📄 كشف حساب مورد — ${escHtml(name)}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="sup-stmt-content">
      <div class="loading"><div class="spinner"></div></div>
    </div>
  `, '780px');

  try {
    const data = await API.getSupplierStatement(id);
    const el = document.getElementById('sup-stmt-content');
    if (!el) return;

    const txs = data.transactions || [];
    const balance = parseFloat(data.balance || 0);

    el.innerHTML = `
      <div style="background:#1a1815;color:white;padding:16px 20px;border-radius:12px;margin-bottom:16px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
        <div>
          <div style="font-size:10px;opacity:.5;margin-bottom:4px">إجمالي المشتريات</div>
          <div style="font-size:20px;font-weight:800;color:#ff6b6b">${fmt(data.total_purchased)} د.أ</div>
        </div>
        <div>
          <div style="font-size:10px;opacity:.5;margin-bottom:4px">المدفوع</div>
          <div style="font-size:20px;font-weight:800;color:#51cf66">${fmt(data.total_paid)} د.أ</div>
        </div>
        <div>
          <div style="font-size:10px;opacity:.5;margin-bottom:4px">المتبقي له</div>
          <div style="font-size:20px;font-weight:800;color:${balance > 0 ? '#ff6b6b' : '#51cf66'}">${fmt(Math.abs(balance))} د.أ</div>
        </div>
      </div>

      <div style="border:1px solid #e8e5e0;border-radius:10px;overflow:hidden">
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead>
            <tr style="background:#f5f3f0">
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">التاريخ</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">البيان</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">مشتريات (عليك)</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">مدفوع (له)</th>
              <th style="padding:10px 12px;text-align:right;font-size:10px;font-weight:700;color:#9e9a94">الرصيد</th>
              <th style="padding:10px 12px"></th>
            </tr>
          </thead>
          <tbody>
            ${txs.length ? txs.map(t => `
              <tr style="border-top:1px solid #f0ede8;${t.type === 'payment' ? 'background:#f9fff9' : ''}">
                <td style="padding:10px 12px;color:#9e9a94">${fmtDate(t.date)}</td>
                <td style="padding:10px 12px;font-weight:600">
                  ${t.type === 'purchase'
        ? `فاتورة شراء #${escHtml(t.invoice_number || t.id)}`
        : `<span style="color:#057a55">دفعة لـ ${escHtml(name)}</span>`}
                </td>
                <td style="padding:10px 12px;color:#c21515;font-weight:700">
                  ${t.type === 'purchase' ? fmt(t.amount) + ' د.أ' : '—'}
                </td>
                <td style="padding:10px 12px;color:#057a55;font-weight:700">
                  ${t.type === 'payment' ? fmt(t.amount) + ' د.أ' : '—'}
                </td>
                <td style="padding:10px 12px;font-weight:800;color:${parseFloat(t.running_balance) > 0 ? '#c21515' : '#057a55'}">
                  ${fmt(Math.abs(t.running_balance))} د.أ
                </td>
                <td style="padding:10px 12px">
                  ${t.type === 'payment' && isAdmin()
        ? `<button class="btn btn-danger btn-sm" onclick="deleteSupPayment(${t.id}, ${id}, ${jsString(name)})">🗑️</button>`
        : ''}
                </td>
              </tr>
            `).join('') : `<tr><td colspan="6" style="text-align:center;padding:30px;color:#9e9a94">لا توجد حركات</td></tr>`}
          </tbody>
        </table>
      </div>

      <div style="display:flex;gap:8px;margin-top:14px">
        ${isAccountant() ? `<button class="btn btn-primary btn-sm" onclick="closeModal(); openSupplierPaymentModal(${id}, ${jsString(name)})">💰 تسجيل دفعة</button>` : ''}
        <button class="btn btn-ghost btn-sm" onclick="closeModal()">إغلاق</button>
      </div>
    `;
  } catch (e) {
    const el = document.getElementById('sup-stmt-content');
    if (el) el.innerHTML = `<div class="alert alert-danger">${escHtml(e.message)}</div>`;
  }
}

function openSupplierPaymentModal(supplierId, supplierName) {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">💰 دفعة لـ ${escHtml(supplierName)}</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-group">
      <label class="form-label">المبلغ (د.أ) *</label>
      <input class="form-input" id="sp_amount" type="number" min="0.001" step="0.001" placeholder="0.000">
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">التاريخ</label>
        <input class="form-input" id="sp_date" type="date" value="${new Date().toISOString().split('T')[0]}">
      </div>
      <div class="form-group">
        <label class="form-label">طريقة الدفع</label>
        <select class="form-select" id="sp_method">
          <option value="cash">نقداً</option>
          <option value="transfer">حوالة</option>
          <option value="check">شيك</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">ملاحظات</label>
      <input class="form-input" id="sp_notes" placeholder="اختياري">
    </div>
    <div style="display:flex;gap:10px;margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="saveSupplierPayment(${supplierId}, ${jsString(supplierName)})">تسجيل الدفعة</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveSupplierPayment(supplierId, supplierName) {
  const amount = parseFloat(document.getElementById('sp_amount')?.value);
  if (!amount || amount <= 0) { toast('المبلغ غير صحيح', 'error'); return; }
  try {
    await API.addSupplierPayment(supplierId, {
      amount,
      payment_date: document.getElementById('sp_date')?.value,
      notes: document.getElementById('sp_notes')?.value || null,
      payment_method: document.getElementById('sp_method')?.value,
    });
    toast('تم تسجيل الدفعة ✅', 'success');
    closeModal();
    viewSupplierStatement(supplierId, supplierName);
  } catch (e) { toast(e.message, 'error'); }
}

async function deleteSupPayment(paymentId, supplierId, supplierName) {
  if (!confirm('حذف هذه الدفعة؟')) return;
  try {
    await API.deleteSupplierPayment(paymentId);
    toast('تم الحذف', 'success');
    viewSupplierStatement(supplierId, supplierName);
  } catch (e) { toast(e.message, 'error'); }
}

async function renderCashbox(container) {
  container.innerHTML = `<div class="loading"><div class="spinner"></div><p>جاري التحميل...</p></div>`;

  try {
    const data = await API.getCashbox();
    const txs = data.transactions || [];
    const balance = parseFloat(data.balance || 0);

    container.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">💼 صندوق خالد</div>
          <div class="page-sub">الرصيد الحالي بإيد المحاسب</div>
        </div>
        ${isAccountant() ? `<button class="btn btn-ghost" onclick="openExpenseModal()">+ مصروف يدوي</button>` : ''}
      </div>

      <div class="metrics-grid" style="margin-bottom:20px">
        <div class="metric-card ${balance >= 0 ? 'green' : 'red'}">
          <div class="metric-icon">💼</div>
          <div class="metric-label">الرصيد الحالي</div>
          <div class="metric-value">${fmt(Math.abs(balance))}</div>
          <div class="metric-sub">${balance >= 0 ? 'موجود بالصندوق' : '⚠️ عجز'}</div>
        </div>
        <div class="metric-card blue">
          <div class="metric-icon">💰</div>
          <div class="metric-label">وارد من العملاء</div>
          <div class="metric-value">${fmt(data.total_in)}</div>
          <div class="metric-sub">نقد وشيكات</div>
        </div>
        <div class="metric-card amber">
          <div class="metric-icon">🏪</div>
          <div class="metric-label">مدفوع للموردين</div>
          <div class="metric-value">${fmt(data.total_out_suppliers)}</div>
          <div class="metric-sub">دينار أردني</div>
        </div>
        <div class="metric-card red">
          <div class="metric-icon">📋</div>
          <div class="metric-label">مصاريف أخرى</div>
          <div class="metric-value">${fmt(data.total_out_expenses)}</div>
          <div class="metric-sub">دينار أردني</div>
        </div>
      </div>

      <div class="card" style="padding:0; overflow:hidden">
        <div style="padding:14px 18px; border-bottom:1px solid var(--brd); font-weight:700">
          آخر الحركات
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>التاريخ</th><th>البيان</th><th>وارد ↓</th><th>صادر ↑</th>
              </tr>
            </thead>
            <tbody>
              ${txs.length ? txs.map(t => {
      const isIn = t.type === 'client_payment';
      return `<tr style="${isIn ? 'background:#f9fff9' : 'background:#fff9f9'}">
                  <td style="font-size:12px;color:var(--tx3)">${fmtDate(t.date)}</td>
                  <td>
                    <strong>${isIn ? '💰 من العميل: ' : t.type === 'supplier_payment' ? '🏪 دفع لـ: ' : '📋 '}${escHtml(t.description || '—')}</strong>
                    ${t.notes ? `<div style="font-size:11px;color:var(--tx3)">${escHtml(t.notes)}</div>` : ''}
                  </td>
                  <td style="color:var(--gr);font-weight:700">${isIn ? fmt(t.amount) + ' د.أ' : '—'}</td>
                  <td style="color:var(--rd);font-weight:700">${!isIn ? fmt(t.amount) + ' د.أ' : '—'}</td>
                </tr>`;
    }).join('') : `<tr><td colspan="4" style="text-align:center;padding:30px;color:var(--tx3)">لا توجد حركات</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">${escHtml(e.message)}</div>`;
  }
}

function openExpenseModal() {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">📋 مصروف يدوي من الصندوق</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-group">
      <label class="form-label">الوصف *</label>
      <input class="form-input" id="exp_desc" placeholder="مثال: رسوم توصيل، كهرباء...">
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">المبلغ (د.أ) *</label>
        <input class="form-input" id="exp_amount" type="number" min="0.001" step="0.001" placeholder="0.000">
      </div>
      <div class="form-group">
        <label class="form-label">التاريخ</label>
        <input class="form-input" id="exp_date" type="date" value="${new Date().toISOString().split('T')[0]}">
      </div>
    </div>
    <div style="display:flex;gap:10px;margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="saveExpense()">حفظ المصروف</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveExpense() {
  const amount = parseFloat(document.getElementById('exp_amount')?.value);
  const description = document.getElementById('exp_desc')?.value?.trim();
  if (!amount || amount <= 0) { toast('المبلغ غير صحيح', 'error'); return; }
  if (!description) { toast('الوصف مطلوب', 'error'); return; }
  try {
    await API.addCashboxExpense({
      amount,
      description,
      expense_date: document.getElementById('exp_date')?.value,
    });
    toast('تم تسجيل المصروف ✅', 'success');
    closeModal();
    navigateTo('cashbox');
  } catch (e) { toast(e.message, 'error'); }
}

function openAddSupplierModal() {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">🏪 إضافة مورد جديد</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-group">
      <label class="form-label">اسم المورد *</label>
      <input class="form-input" id="ns_name" placeholder="اسم المورد">
    </div>
    <div class="form-group">
      <label class="form-label">رقم الهاتف</label>
      <input class="form-input" id="ns_phone" placeholder="07X XXXX XXXX">
    </div>
    <div style="display:flex;gap:10px;margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="saveNewSupplier()">إضافة</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveNewSupplier() {
  const name = document.getElementById('ns_name')?.value?.trim();
  if (!name) { toast('الاسم مطلوب', 'error'); return; }
  try {
    await API.createSupplier({ name, phone: document.getElementById('ns_phone')?.value || null });
    toast('تم إضافة المورد ✅', 'success');
    closeModal();
    navigateTo('purchases');
  } catch (e) { toast(e.message, 'error'); }
}
async function renderExpenses(container) {
  let expenses = [];
  let salaries = [];

  try {
    [expenses, salaries] = await Promise.all([
      API.getExpenses(),
      API.getSalaries()
    ]);
  } catch (e) {
    expenses = [];
    salaries = [];
  }

  const totalExpenses = expenses.reduce((s, e) => s + Number(e.amount || 0), 0);
  const totalSalaries = salaries.reduce((s, e) => s + Number(e.salary_amount || 0), 0);

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">📋 المصاريف والرواتب</div>
        <div class="page-sub">مصاريف يومية / شهرية / ثابتة + رواتب الموظفين</div>
      </div>
      <div style="display:flex;gap:10px">
        <button class="btn btn-primary" onclick="openExpensePageModal()">+ مصروف</button>
        <button class="btn btn-ghost" onclick="openSalaryModal()">+ راتب موظف</button>
      </div>
    </div>

    <div class="metrics-grid" style="margin-bottom:18px">
      <div class="metric-card red">
        <div class="metric-icon">📋</div>
        <div class="metric-label">إجمالي المصاريف</div>
        <div class="metric-value">${fmt(totalExpenses)}</div>
        <div class="metric-sub">دينار أردني</div>
      </div>
      <div class="metric-card amber">
        <div class="metric-icon">👷</div>
        <div class="metric-label">إجمالي الرواتب</div>
        <div class="metric-value">${fmt(totalSalaries)}</div>
        <div class="metric-sub">دينار أردني</div>
      </div>
    </div>

    <div class="card" style="padding:0;overflow:hidden;margin-bottom:18px">
      <div style="padding:14px 18px;border-bottom:1px solid var(--brd);font-weight:800">
        المصاريف
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>التاريخ</th>
              <th>اسم المصروف</th>
              <th>النوع</th>
              <th>التصنيف</th>
              <th>المبلغ</th>
              <th>ملاحظات</th>
              <th>إجراءات</th>
            </tr>
          </thead>
          <tbody>
            ${expenses.length ? expenses.map(e => `
              <tr>
                <td>${fmtDate(e.expense_date)}</td>
                <td><strong>${escHtml(e.name || e.description || '—')}</strong></td>
                <td>${escHtml(e.expense_type || 'daily')}</td>
                <td>${escHtml(e.category || '—')}</td>
                <td style="font-weight:800;color:var(--rd)">${fmt(e.amount)} د.أ</td>
                <td>${escHtml(e.notes || '—')}</td>
                <td>
                  ${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deleteExpense(${e.id})">🗑️</button>` : '—'}
                </td>
              </tr>
            `).join('') : emptyRow('لا توجد مصاريف', 7)}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:14px 18px;border-bottom:1px solid var(--brd);font-weight:800">
        رواتب الموظفين
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>الشهر</th>
              <th>اسم الموظف</th>
              <th>الراتب</th>
              <th>تاريخ الدفع</th>
              <th>الحالة</th>
              <th>ملاحظات</th>
              <th>إجراءات</th>
            </tr>
          </thead>
          <tbody>
            ${salaries.length ? salaries.map(s => `
              <tr>
                <td>${fmtDate(s.salary_month)}</td>
                <td><strong>${escHtml(s.employee_name || '—')}</strong></td>
                <td style="font-weight:800;color:var(--rd)">${fmt(s.salary_amount)} د.أ</td>
                <td>${fmtDate(s.paid_date)}</td>
                <td>${escHtml(s.status || 'paid')}</td>
                <td>${escHtml(s.notes || '—')}</td>
                <td>
                  ${isAdmin() ? `<button class="btn btn-danger btn-sm" onclick="deleteSalary(${s.id})">🗑️</button>` : '—'}
                </td>
              </tr>
            `).join('') : emptyRow('لا توجد رواتب مسجلة', 7)}
          </tbody>
        </table>
      </div>
    </div>
  `;
}
function openExpensePageModal() {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">📋 إضافة مصروف</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>

    <div class="form-group">
      <label class="form-label">اسم المصروف *</label>
      <input class="form-input" id="pg_exp_name" placeholder="مثال: كهرباء، أجار، بنزين، توصيل">
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">المبلغ *</label>
        <input class="form-input" id="pg_exp_amount" type="number" step="0.001" min="0.001" placeholder="0.000">
      </div>
      <div class="form-group">
        <label class="form-label">التاريخ</label>
        <input class="form-input" id="pg_exp_date" type="date" value="${new Date().toISOString().split('T')[0]}">
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">نوع المصروف</label>
        <select class="form-select" id="pg_exp_type">
          <option value="daily">يومي</option>
          <option value="monthly">شهري</option>
          <option value="fixed">ثابت</option>
          <option value="other">آخر</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">التصنيف</label>
        <input class="form-input" id="pg_exp_category" placeholder="تشغيل، نقل، مكتب...">
      </div>
    </div>

    <div class="form-group">
      <label class="form-label">ملاحظات</label>
      <input class="form-input" id="pg_exp_notes" placeholder="اختياري">
    </div>

    <div style="display:flex;gap:10px;margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="savePageExpense()">حفظ</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function savePageExpense() {
  const name = document.getElementById('pg_exp_name')?.value?.trim();
  const amount = parseFloat(document.getElementById('pg_exp_amount')?.value);

  if (!name) { toast('اسم المصروف مطلوب', 'error'); return; }
  if (!amount || amount <= 0) { toast('المبلغ غير صحيح', 'error'); return; }

  try {
    await API.createExpense({
      name,
      amount,
      expense_type: document.getElementById('pg_exp_type')?.value || 'daily',
      category: document.getElementById('pg_exp_category')?.value || null,
      expense_date: document.getElementById('pg_exp_date')?.value,
      notes: document.getElementById('pg_exp_notes')?.value || null,
      is_fixed: document.getElementById('pg_exp_type')?.value === 'fixed',
    });

    toast('تم حفظ المصروف ✅', 'success');
    closeModal();
    navigateTo('expenses');
  } catch (e) {
    toast(e.message, 'error');
  }
}

function openSalaryModal() {
  openModal(`
    <div class="modal-header">
      <div class="modal-title">👷 إضافة راتب موظف</div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>

    <div class="form-group">
      <label class="form-label">اسم الموظف *</label>
      <input class="form-input" id="sal_employee_name" placeholder="اسم الموظف">
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">قيمة الراتب *</label>
        <input class="form-input" id="sal_amount" type="number" step="0.001" min="0.001" placeholder="0.000">
      </div>
      <div class="form-group">
        <label class="form-label">شهر الراتب</label>
        <input class="form-input" id="sal_month" type="date" value="${new Date().toISOString().slice(0, 8)}01">
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label class="form-label">تاريخ الدفع</label>
        <input class="form-input" id="sal_paid_date" type="date" value="${new Date().toISOString().split('T')[0]}">
      </div>
      <div class="form-group">
        <label class="form-label">الحالة</label>
        <select class="form-select" id="sal_status">
          <option value="paid">مدفوع</option>
          <option value="pending">غير مدفوع</option>
        </select>
      </div>
    </div>

    <div class="form-group">
      <label class="form-label">ملاحظات</label>
      <input class="form-input" id="sal_notes" placeholder="اختياري">
    </div>

    <div style="display:flex;gap:10px;margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="saveSalary()">حفظ الراتب</button>
      <button class="btn btn-ghost" onclick="closeModal()">إلغاء</button>
    </div>
  `);
}

async function saveSalary() {
  const employeeName = document.getElementById('sal_employee_name')?.value?.trim();
  const amount = parseFloat(document.getElementById('sal_amount')?.value);

  if (!employeeName) { toast('اسم الموظف مطلوب', 'error'); return; }
  if (!amount || amount <= 0) { toast('قيمة الراتب غير صحيحة', 'error'); return; }

  try {
    await API.createSalary({
      employee_name: employeeName,
      salary_amount: amount,
      salary_month: document.getElementById('sal_month')?.value,
      paid_date: document.getElementById('sal_paid_date')?.value,
      status: document.getElementById('sal_status')?.value || 'paid',
      notes: document.getElementById('sal_notes')?.value || null,
    });

    toast('تم حفظ الراتب ✅', 'success');
    closeModal();
    navigateTo('expenses');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteExpense(id) {
  if (!confirm('حذف هذا المصروف؟')) return;
  try {
    await API.deleteExpense(id);
    toast('تم حذف المصروف ✅', 'success');
    navigateTo('expenses');
  } catch (e) {
    toast(e.message, 'error');
  }
}
async function renderEmployees(container) {
  if (!isAdmin()) {
    container.innerHTML = `<div class="alert alert-danger">غير مصرح لك بالوصول</div>`;
    return;
  }

  let users = [];
  try {
    users = await API.getUsers() || [];
  } catch (e) {
    users = [];
  }

  const employees = users.filter(u =>
    ['admin', 'accountant', 'employee'].includes(u.role)
  );

  container.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">👷 الموظفون</div>
        <div class="page-sub">${employees.length} موظف مسجل</div>
      </div>
    </div>

    <div class="card" style="padding:0;overflow:hidden">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>اسم الموظف</th>
              <th>اسم المستخدم</th>
              <th>الصلاحية</th>
              <th>تاريخ الإنشاء</th>
            </tr>
          </thead>
          <tbody>
            ${employees.length ? employees.map(u => `
              <tr>
                <td><strong>${escHtml(u.full_name || '—')}</strong></td>
                <td>${escHtml(u.username || '—')}</td>
                <td>${roleBadge(u.role)}</td>
                <td>${fmtDate(u.created_at)}</td>
              </tr>
            `).join('') : emptyRow('لا يوجد موظفون', 4)}
          </tbody>
        </table>
      </div>
    </div>
  `;
}
async function deleteSalary(id) {
  if (!confirm('حذف هذا الراتب؟')) return;
  try {
    await API.deleteSalary(id);
    toast('تم حذف الراتب ✅', 'success');
    navigateTo('expenses');
  } catch (e) {
    toast(e.message, 'error');
  }
}
