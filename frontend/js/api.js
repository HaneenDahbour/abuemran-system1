// js/api.js — HTTP layer (fixed + safer)

(function () {
  function isBrowser() {
    return typeof window !== 'undefined';
  }

  function getApiBase() {
    if (!isBrowser()) return '/api';
    if (window.ENV_API_BASE) return window.ENV_API_BASE;
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    return isLocal ? 'http://localhost:8000/api' : '/api';
  }

  const API_BASE = getApiBase();

  function getToken() {
    try {
      return localStorage.getItem('token');
    } catch {
      return null;
    }
  }

  function normalizePath(path) {
    if (!path) return '';
    return path.startsWith('/') ? path : `/${path}`;
  }

  function requireValidId(id, label = 'id') {
    const value = String(id ?? '').trim();
    if (!value || value === 'undefined' || value === 'null') {
      throw new Error(`${label} غير صحيح`);
    }
    return encodeURIComponent(value);
  }

  function requireId(id, label = 'id') {
    const n = Number(id);
    if (!Number.isInteger(n) || n <= 0) {
      throw new Error(`${label} غير صحيح`);
    }
    return n;
  }

  function clearAuthAndReload() {
    try {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    } catch { }
    if (isBrowser()) {
      window.location.reload();
    }
  }

  async function parseResponse(res) {
    const contentType = res.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    try {
      return isJson ? await res.json() : await res.text();
    } catch {
      return null;
    }
  }

  function extractErrorMessage(data, fallback = 'حدث خطأ غير متوقع') {
    if (!data) return fallback;

    if (typeof data === 'string') {
      return data.trim() || fallback;
    }

    if (Array.isArray(data)) {
      return data.map(item => extractErrorMessage(item, fallback)).join(' | ');
    }

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

      if (typeof detail === 'object' && detail !== null) {
        return JSON.stringify(detail);
      }

      return JSON.stringify(data);
    }

    return fallback;
  }

  async function apiFetch(path, options = {}) {
    const normalizedPath = normalizePath(path);
    const url = `${API_BASE}${normalizedPath}`;

    const headers = {
      ...(options.headers || {})
    };

    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;

    if (!isFormData && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    try {
      const res = await fetch(url, {
        ...options,
        headers
      });

      if (res.status === 401) {
        clearAuthAndReload();
        return null;
      }

      const data = await parseResponse(res);

      if (!res.ok) {
        throw new Error(extractErrorMessage(data, `HTTP ${res.status}`));
      }

      return data;
    } catch (err) {
      if (err && err.name === 'TypeError') {
        throw new Error('لا يمكن الاتصال بالخادم. تأكد من تشغيل السيرفر.');
      }
      throw err;
    }
  }
  

  const API = {
    // Auth
    search: (q) => apiFetch(`/search?q=${encodeURIComponent(q)}`),

    login: (username, password) =>
      apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      }),

    getUsers: () => apiFetch('/auth/users'),

    createUser: (data) =>
      apiFetch('/auth/users', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    deleteUser: (id) =>
      apiFetch(`/auth/users/${id}`, {
        method: 'DELETE'
      }),

    // Clients
    getClients: () => apiFetch('/clients'),

    getClient: (id) => apiFetch(`/clients/${requireId(id, 'معرّف العميل')}`),

    createClient: (data) =>
      apiFetch('/clients', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    updateClient: (id, data) =>
      apiFetch(`/clients/${requireId(id, 'معرّف العميل')}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      }),

    deleteClient: (id) =>
      apiFetch(`/clients/${requireId(id, 'معرّف العميل')}`, {
        method: 'DELETE'
      }),

    getClientStatement: (id) =>
      apiFetch(`/clients/${requireId(id, 'معرّف العميل')}/statement`),

    // Invoices
    getInvoices: () => apiFetch('/invoices'),

    createInvoice: (data) =>
      apiFetch('/invoices', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    updateInvoice: (id, data) =>
      apiFetch(`/invoices/${requireId(id, 'معرّف الفاتورة')}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      }),


    deleteInvoice: (id) =>
      apiFetch(`/invoices/${requireId(id, 'معرّف الفاتورة')}`, {
        method: 'DELETE'
      }),

    // Payments
    getPayments: () => apiFetch('/payments'),

    createPayment: (data) =>
      apiFetch('/payments', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    deletePayment: (id) =>
      apiFetch(`/payments/${requireId(id, 'معرّف الدفعة')}`, {
        method: 'DELETE'
      }),

    // Checks
    getChecks: () => apiFetch('/checks'),

    createCheck: (data) =>
      apiFetch('/checks', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    updateCheckStatus: (id, status) =>
      apiFetch(`/checks/${requireId(id, 'معرّف الشيك')}/status`, {
        method: 'PUT',
        body: JSON.stringify({ status })
      }),

    deleteCheck: (id) =>
      apiFetch(`/checks/${requireId(id, 'معرّف الشيك')}`, {
        method: 'DELETE'
      }),

    // Audit / Stats
    getStats: () => apiFetch('/audit/stats'),
    getAuditLog: () => apiFetch('/audit/log'),

    // AI
    askAI: (message, history = []) =>
      apiFetch('/ai/chat', {
        method: 'POST',
        body: JSON.stringify({ message, history })
      }),

    // Suppliers
    getSuppliers: () => apiFetch('/suppliers'),

    createSupplier: (data) =>
      apiFetch('/suppliers', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    deleteSupplier: (id) =>
      apiFetch(`/suppliers/${id}`, {
        method: 'DELETE'
      }),
    getSupplierStatement: (id) =>
    apiFetch(`/suppliers/${requireValidId(id, 'معرّف المورد')}/statement`),

addSupplierPayment: (id, data) =>
    apiFetch(`/suppliers/${requireValidId(id, 'معرّف المورد')}/payments`, {
        method: 'POST',
        body: JSON.stringify(data)
    }),

deleteSupplierPayment: (id) =>
    apiFetch(`/suppliers/payments/${requireId(id, 'معرّف الدفعة')}`, {
        method: 'DELETE'
    }),

getCashbox: () => apiFetch('/audit/cashbox'),

addCashboxExpense: (data) =>
    apiFetch('/audit/cashbox/expenses', {
        method: 'POST',
        body: JSON.stringify(data)
    }),

    // Products
    getProducts: () => apiFetch('/products'),

    getProduct: (id) =>
      apiFetch(`/products/${requireValidId(id, 'معرّف الصنف')}`),

    createProduct: (data) =>
      apiFetch('/products', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    updateProduct: (id, data) =>
      apiFetch(`/products/${requireValidId(id, 'معرّف الصنف')}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      }),

    deleteProduct: (id) =>
      apiFetch(`/products/${requireValidId(id, 'معرّف الصنف')}`, {
        method: 'DELETE'
      }),

    getStockMovements: (productId) =>
      apiFetch(`/products/${requireValidId(productId, 'معرّف الصنف')}/movements`),

    adjustProductStock: (id, data) =>
      apiFetch(`/products/${requireValidId(id, 'معرّف الصنف')}/adjust`, {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    // Purchases
    getPurchases: () => apiFetch('/purchases'),

    createPurchase: (data) =>
      apiFetch('/purchases', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    receivePurchase: (id) =>
      apiFetch(`/purchases/${requireId(id, 'معرّف فاتورة الشراء')}/receive`, {
        method: 'PUT'
      }),

    deletePurchase: (id) =>
      apiFetch(`/purchases/${requireId(id, 'معرّف فاتورة الشراء')}`, {
        method: 'DELETE'
      }),

    // Warehouse Categories
    getWarehouseCategories: () => apiFetch('/warehouse-categories'),

    getCategoryProducts: (id) =>
      apiFetch(`/warehouse-categories/${requireId(id, 'معرّف الفئة')}/products`),

    createWarehouseCategory: (data) =>
      apiFetch('/warehouse-categories', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    updateWarehouseCategory: (id, data) =>
      apiFetch(`/warehouse-categories/${requireId(id, 'معرّف الفئة')}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      }),

    deleteWarehouseCategory: (id) =>
      apiFetch(`/warehouse-categories/${id}`, {
        method: 'DELETE'
      }),

    // Warehouse Invoices
        // Warehouse Invoices
    getWarehouseInvoices: () => apiFetch('/warehouse-invoices'),

    createWarehouseInvoice: (data) =>
      apiFetch('/warehouse-invoices', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    deleteWarehouseInvoice: (id) =>
      apiFetch(`/warehouse-invoices/${requireId(id, 'معرّف فاتورة المستودع')}`, {
        method: 'DELETE'
      }),

    // Recipients
    getRecipients: () => apiFetch('/recipients'),

    getRecipientStatement: (name) =>
      apiFetch(`/recipients/${encodeURIComponent(name)}/statement`),

    createRecipientPayment: (data) =>
      apiFetch('/recipients/payments', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    deleteRecipientPayment: (id) =>
      apiFetch(`/recipients/payments/${requireId(id, 'معرّف الدفعة')}`, {
        method: 'DELETE'
      }),
  };

  // expose globally for non-module scripts
  window.API_BASE = API_BASE;
  window.getToken = getToken;
  window.apiFetch = apiFetch;
  window.API = API;
})();