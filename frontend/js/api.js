// js/api.js

(function () {
  function isBrowser() {
    return typeof window !== 'undefined';
  }

  function getApiBase() {
    if (!isBrowser()) return '/api';
    if (window.ENV_API_BASE) return window.ENV_API_BASE;
    const isLocal =
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1';
    return isLocal ? 'http://localhost:8000/api' : '/api';
  }

  const API_BASE = getApiBase();

  function getToken() {
    try { return localStorage.getItem('token'); } catch { return null; }
  }

  function normalizePath(path) {
    if (!path) return '';
    const p = path.startsWith('/') ? path : `/${path}`;
    return p.replace(/\/+$/, '') || '/';
  }

  function requireValidId(id, label = 'id') {
    const value = String(id ?? '').trim();
    if (!value || value === 'undefined' || value === 'null') {
      throw new Error(`${label} ØºÙŠØ± ØµØ­ÙŠØ­`);
    }
    return encodeURIComponent(value);
  }

  function requireId(id, label = 'id') {
    const n = Number(id);
    if (!Number.isInteger(n) || n <= 0) {
      throw new Error(`${label} ØºÙŠØ± ØµØ­ÙŠØ­`);
    }
    return n;
  }

  function clearAuthAndReload() {
    try {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    } catch { }
    if (isBrowser()) window.location.reload();
  }

  async function parseResponse(res) {
    const contentType = res.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    try { return isJson ? await res.json() : await res.text(); } catch { return null; }
  }

  function extractErrorMessage(data, fallback = 'Ø­Ø¯Ø« Ø®Ø·Ø£ ØºÙŠØ± Ù…ØªÙˆÙ‚Ø¹') {
    if (!data) return fallback;
    if (typeof data === 'string') return data.trim() || fallback;
    if (Array.isArray(data)) return data.map(i => extractErrorMessage(i, fallback)).join(' | ');
    if (typeof data === 'object') {
      const detail = data.detail || data.message || data.error || data.details;
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail)) {
        return detail.map(err => {
          if (typeof err === 'string') return err;
          if (err?.msg) {
            const loc = Array.isArray(err.loc) ? err.loc.join('.') : '';
            return loc ? `${loc}: ${err.msg}` : err.msg;
          }
          return JSON.stringify(err);
        }).join(' | ');
      }
      if (typeof detail === 'object' && detail !== null) return JSON.stringify(detail);
      return JSON.stringify(data);
    }
    return fallback;
  }

  async function apiFetch(path, options = {}) {
    const url = `${API_BASE}${normalizePath(path)}`;
    const headers = { ...(options.headers || {}) };
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
    if (!isFormData && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    try {
      const res = await fetch(url, { ...options, headers, cache: options.cache || 'no-store' });
      if (res.status === 401) { clearAuthAndReload(); return null; }
      const data = await parseResponse(res);
      if (!res.ok) throw new Error(extractErrorMessage(data, `HTTP ${res.status}`));
      return data;
    } catch (err) {
      if (err && err.name === 'TypeError') {
        throw new Error('Ù„Ø§ ÙŠÙ…ÙƒÙ† Ø§Ù„Ø§ØªØµØ§Ù„ Ø¨Ø§Ù„Ø®Ø§Ø¯Ù…. ØªØ£ÙƒØ¯ Ù…Ù† ØªØ´ØºÙŠÙ„ Ø§Ù„Ø³ÙŠØ±ÙØ±.');
      }
      throw err;
    }
  }

  const API = {
    // â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    login: (username, password) =>
      apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
    getUsers: () => apiFetch('/auth/users'),
    createUser: data =>
      apiFetch('/auth/users', { method: 'POST', body: JSON.stringify(data) }),
    deleteUser: id =>
      apiFetch(`/auth/users/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù…')}`, { method: 'DELETE' }),

    // â”€â”€ Search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    search: q => apiFetch(`/search?q=${encodeURIComponent(q)}`),

    // â”€â”€ Clients â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getClients: () => apiFetch('/clients'),
    getClient: id => apiFetch(`/clients/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¹Ù…ÙŠÙ„')}`),
    createClient: data =>
      apiFetch('/clients', { method: 'POST', body: JSON.stringify(data) }),
    updateClient: (id, data) =>
      apiFetch(`/clients/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¹Ù…ÙŠÙ„')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteClient: id =>
      apiFetch(`/clients/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¹Ù…ÙŠÙ„')}`, { method: 'DELETE' }),
    getClientStatement: id =>
      apiFetch(`/clients/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¹Ù…ÙŠÙ„')}/statement`),

    // â”€â”€ Invoices â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getInvoices: () => apiFetch('/invoices'),
    createInvoice: data =>
      apiFetch('/invoices', { method: 'POST', body: JSON.stringify(data) }),
    updateInvoice: (id, data) =>
      apiFetch(`/invoices/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ÙØ§ØªÙˆØ±Ø©')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteInvoice: id =>
      apiFetch(`/invoices/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ÙØ§ØªÙˆØ±Ø©')}`, { method: 'DELETE' }),
    approveInvoice: id =>
      apiFetch(`/invoices/${requireId(id, 'معرّف الفاتورة')}/approve`, {
        method: 'POST',
        body: JSON.stringify({}),
      }),
    rejectInvoice: (id, reason) =>
      apiFetch(`/invoices/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ÙØ§ØªÙˆØ±Ø©')}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }),
    // â”€â”€ Expenses / Salaries â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getExpenses: () => apiFetch('/expenses'),
    createExpense: data => apiFetch('/expenses', { method: 'POST', body: JSON.stringify(data) }),
    deleteExpense: id =>
      apiFetch(`/expenses/${requireId(id, 'معرّف المصروف')}`, { method: 'DELETE' }),

    getSalaries: () => apiFetch('/expenses/salaries'),
    createSalary: data => apiFetch('/expenses/salaries', { method: 'POST', body: JSON.stringify(data) }),
    deleteSalary: id =>
      apiFetch(`/expenses/salaries/${requireId(id, 'معرّف الراتب')}`, { method: 'DELETE' }),

    getAdvances: () => apiFetch('/expenses/advances'),
    createAdvance: data => apiFetch('/expenses/advances', { method: 'POST', body: JSON.stringify(data) }),

    // â”€â”€ Payments â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getPayments: () => apiFetch('/payments'),
    createPayment: data =>
      apiFetch('/payments', { method: 'POST', body: JSON.stringify(data) }),
    approvePayment: id =>
      apiFetch(`/payments/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¯ÙØ¹Ø©')}/approve`, { method: 'POST', body: JSON.stringify({}) }),
    rejectPayment: (id, reason) =>
      apiFetch(`/payments/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¯ÙØ¹Ø©')}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }),
    deletePayment: id =>
      apiFetch(`/payments/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¯ÙØ¹Ø©')}`, { method: 'DELETE' }),

    // â”€â”€ Checks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getChecks: () => apiFetch('/checks'),
    createCheck: data =>
      apiFetch('/checks', { method: 'POST', body: JSON.stringify(data) }),
    updateCheckStatus: (id, status) =>
      apiFetch(`/checks/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø´ÙŠÙƒ')}/status`, { method: 'PUT', body: JSON.stringify({ status }) }),
    deleteCheck: id =>
      apiFetch(`/checks/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø´ÙŠÙƒ')}`, { method: 'DELETE' }),

    // â”€â”€ Audit / Stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getStats: () => apiFetch('/audit/stats'),
    getAuditLog: () => apiFetch('/audit/log'),
    getCashbox: () => apiFetch('/audit/cashbox'),
    addCashboxExpense: data =>
      apiFetch('/audit/cashbox/expenses', { method: 'POST', body: JSON.stringify(data) }),

    // â”€â”€ AI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    askAI: (message, history = []) =>
      apiFetch('/ai/chat', { method: 'POST', body: JSON.stringify({ message, history }) }),

    // â”€â”€ Suppliers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getSuppliers: () => apiFetch('/suppliers'),
    createSupplier: data =>
      apiFetch('/suppliers', { method: 'POST', body: JSON.stringify(data) }),
    updateSupplier: (id, data) =>
      apiFetch(`/suppliers/${requireValidId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ù…ÙˆØ±Ø¯')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteSupplier: id =>
      apiFetch(`/suppliers/${requireValidId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ù…ÙˆØ±Ø¯')}`, { method: 'DELETE' }),
    getSupplierStatement: id =>
      apiFetch(`/suppliers/${requireValidId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ù…ÙˆØ±Ø¯')}/statement`),
    addSupplierPayment: (id, data) =>
      apiFetch(`/suppliers/${requireValidId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ù…ÙˆØ±Ø¯')}/payments`, { method: 'POST', body: JSON.stringify(data) }),
    deleteSupplierPayment: id =>
      apiFetch(`/suppliers/payments/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¯ÙØ¹Ø©')}`, { method: 'DELETE' }),

    // â”€â”€ Products â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getProducts: () => apiFetch('/products'),
    getProduct: id => apiFetch(`/products/${requireValidId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ØµÙ†Ù')}`),
    createProduct: data =>
      apiFetch('/products', { method: 'POST', body: JSON.stringify(data) }),
    updateProduct: (id, data) =>
      apiFetch(`/products/${requireValidId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ØµÙ†Ù')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteProduct: id =>
      apiFetch(`/products/${requireValidId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ØµÙ†Ù')}`, { method: 'DELETE' }),
    getStockMovements: productId =>
      apiFetch(`/products/${requireValidId(productId, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ØµÙ†Ù')}/movements`),
    adjustProductStock: (id, data) =>
      apiFetch(`/products/${requireValidId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ØµÙ†Ù')}/adjust`, { method: 'POST', body: JSON.stringify(data) }),
    importProductsExcel: (file, updateExisting = false) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiFetch(
        `/products/import-excel?update_existing=${updateExisting ? 'true' : 'false'}`,
        { method: 'POST', body: formData }
      );
    },
    async exportProductsExcel() {
      const res = await fetch(`${API_BASE}/products/export-excel`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${getToken() || ''}` },
        cache: 'no-store',
      });
      if (res.status === 401) { clearAuthAndReload(); return; }
      if (!res.ok) {
        const data = await parseResponse(res);
        throw new Error(extractErrorMessage(data, 'ÙØ´Ù„ ØªØµØ¯ÙŠØ± Ù…Ù„Ù Excel'));
      }
      const blob = await res.blob();
      let filename = 'ØªØµØ¯ÙŠØ±-Ø§Ù„Ù…Ø³ØªÙˆØ¯Ø¹.xlsx';
      const disposition = res.headers.get('content-disposition') || '';
      const match = disposition.match(/filename\*=UTF-8''([^;]+)/);
      if (match?.[1]) {
        try { filename = decodeURIComponent(match[1]); } catch { filename = match[1]; }
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    },

    // â”€â”€ Purchases â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getPurchases: () => apiFetch('/purchases'),
    createPurchase: data =>
      apiFetch('/purchases', { method: 'POST', body: JSON.stringify(data) }),
    receivePurchase: id =>
      apiFetch(`/purchases/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù ÙØ§ØªÙˆØ±Ø© Ø§Ù„Ø´Ø±Ø§Ø¡')}/receive`, { method: 'PUT' }),
    deletePurchase: id =>
      apiFetch(`/purchases/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù ÙØ§ØªÙˆØ±Ø© Ø§Ù„Ø´Ø±Ø§Ø¡')}`, { method: 'DELETE' }),

    // â”€â”€ Warehouse Categories â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getWarehouseCategories: () => apiFetch('/warehouse-categories'),
    getCategoryProducts: id =>
      apiFetch(`/warehouse-categories/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ÙØ¦Ø©')}/products`),
    createWarehouseCategory: data =>
      apiFetch('/warehouse-categories', { method: 'POST', body: JSON.stringify(data) }),
    updateWarehouseCategory: (id, data) =>
      apiFetch(`/warehouse-categories/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ÙØ¦Ø©')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteWarehouseCategory: id =>
      apiFetch(`/warehouse-categories/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„ÙØ¦Ø©')}`, { method: 'DELETE' }),

    // â”€â”€ Warehouse Invoices â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getWarehouseInvoices: () => apiFetch('/warehouse-invoices'),
    createWarehouseInvoice: data =>
      apiFetch('/warehouse-invoices', { method: 'POST', body: JSON.stringify(data) }),
    deleteWarehouseInvoice: id =>
      apiFetch(`/warehouse-invoices/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù ÙØ§ØªÙˆØ±Ø© Ø§Ù„Ù…Ø³ØªÙˆØ¯Ø¹')}`, { method: 'DELETE' }),

    // â”€â”€ Recipients â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    getRecipients: () => apiFetch('/recipients'),
    getRecipientStatement: name =>
      apiFetch(`/recipients/${encodeURIComponent(name)}/statement`),
    getRecipientPayments: () => apiFetch('/recipients/payments'),

    createRecipientPayment: data =>
      apiFetch('/recipients/payments', { method: 'POST', body: JSON.stringify(data) }),
    deleteRecipientPayment: id =>
      apiFetch(`/recipients/payments/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø¯ÙØ¹Ø©')}`, { method: 'DELETE' }),
    // Employees & advances
    getEmployeesList: () => apiFetch('/auth/employees-list'), getAdvances: () => apiFetch('/expenses/advances'),
    createAdvance: data =>
      apiFetch('/expenses/advances', { method: 'POST', body: JSON.stringify(data) }),
    deleteAdvance: id =>
      apiFetch(`/expenses/advances/${requireId(id, 'Ù…Ø¹Ø±Ù‘Ù Ø§Ù„Ø³Ù„ÙØ©')}`, { method: 'DELETE' }),
    getEmployeeStatement: name =>
      apiFetch(`/expenses/employee-statement/${encodeURIComponent(name)}`),

    // Profit
    getProfitAnalysis: () => apiFetch('/products/profit-analysis'),
  };

  window.API_BASE = API_BASE;
  window.getToken = getToken;
  window.apiFetch = apiFetch;
  window.API = API;
})();


