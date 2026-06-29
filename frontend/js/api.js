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
    if (isBrowser()) window.location.reload();
  }

  async function parseResponse(res) {
    const contentType = res.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    try { return isJson ? await res.json() : await res.text(); } catch { return null; }
  }

  function extractErrorMessage(data, fallback = 'حدث خطأ غير متوقع') {
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
        throw new Error('لا يمكن الاتصال بالخادم. تأكد من تشغيل السيرفر.');
      }
      throw err;
    }
  }

  const API = {
    // ── Auth ──────────────────────────────────────────────────────
    login: (username, password) =>
      apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
    getUsers: () => apiFetch('/auth/users'),
    createUser: data =>
      apiFetch('/auth/users', { method: 'POST', body: JSON.stringify(data) }),
    updateUser: (id, data) =>
      apiFetch(`/auth/users/${requireId(id, 'معرّف المستخدم')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteUser: id =>
      apiFetch(`/auth/users/${requireId(id, 'معرّف المستخدم')}`, { method: 'DELETE' }),
    getEmployeesList: () => apiFetch('/auth/employees-list'),
    getShops: () => apiFetch('/shops'),

    // ── Search ────────────────────────────────────────────────────
    search: q => apiFetch(`/search?q=${encodeURIComponent(q)}`),

    // ── Clients ───────────────────────────────────────────────────
    getClients: () => apiFetch('/clients'),
    getClient: id => apiFetch(`/clients/${requireId(id, 'معرّف العميل')}`),
    createClient: data =>
      apiFetch('/clients', { method: 'POST', body: JSON.stringify(data) }),
    updateClient: (id, data) =>
      apiFetch(`/clients/${requireId(id, 'معرّف العميل')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteClient: id =>
      apiFetch(`/clients/${requireId(id, 'معرّف العميل')}`, { method: 'DELETE' }),
    getClientStatement: id =>
      apiFetch(`/clients/${requireId(id, 'معرّف العميل')}/statement`),

    // ── Invoices ──────────────────────────────────────────────────
    getInvoices: () => apiFetch('/invoices'),
    createInvoice: data =>
      apiFetch('/invoices', { method: 'POST', body: JSON.stringify(data) }),
    updateInvoice: (id, data) =>
      apiFetch(`/invoices/${requireId(id, 'معرّف الفاتورة')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteInvoice: id =>
      apiFetch(`/invoices/${requireId(id, 'معرّف الفاتورة')}`, { method: 'DELETE' }),
    approveInvoice: id =>
      apiFetch(`/invoices/${requireId(id, 'معرّف الفاتورة')}/approve`, {
        method: 'POST',
        body: JSON.stringify({}),
      }),
    rejectInvoice: (id, reason) =>
      apiFetch(`/invoices/${requireId(id, 'معرّف الفاتورة')}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }),
    // ── Expenses / Salaries / Advances ─────────────────────────────
    getEmployeeStatement: (userId) => apiFetch(`/expenses/employee/${requireId(userId, 'معرّف الموظف')}/statement`),
    getExpenses: () => apiFetch('/expenses'),
    createExpense: data =>
      apiFetch('/expenses', { method: 'POST', body: JSON.stringify(data) }),
    updateExpense: (id, data) =>
      apiFetch(`/expenses/${requireId(id, 'معرّف المصروف')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteExpense: id =>
      apiFetch(`/expenses/${requireId(id, 'معرّف المصروف')}`, { method: 'DELETE' }),

    getUnlinkedEmployeeNames: () => apiFetch('/expenses/unlinked-names'),
    getSalaries: () => apiFetch('/expenses/salaries'),
    createSalary: data =>
      apiFetch('/expenses/salaries', { method: 'POST', body: JSON.stringify(data) }),
    updateSalary: (id, data) =>
      apiFetch(`/expenses/salaries/${requireId(id, 'معرّف الراتب')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteSalary: id =>
      apiFetch(`/expenses/salaries/${requireId(id, 'معرّف الراتب')}`, { method: 'DELETE' }),

    getAdvances: () => apiFetch('/expenses/advances'),
    createAdvance: data =>
      apiFetch('/expenses/advances', { method: 'POST', body: JSON.stringify(data) }),
    updateAdvance: (id, data) =>
      apiFetch(`/expenses/advances/${requireId(id, 'معرّف السلفة')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteAdvance: id =>
      apiFetch(`/expenses/advances/${requireId(id, 'معرّف السلفة')}`, { method: 'DELETE' }),

    // ── Payments ──────────────────────────────────────────────────
    getPayments: () => apiFetch('/payments'),
    createPayment: data =>
      apiFetch('/payments', { method: 'POST', body: JSON.stringify(data) }),
    approvePayment: id =>
      apiFetch(`/payments/${requireId(id, 'معرّف الدفعة')}/approve`, { method: 'POST', body: JSON.stringify({}) }),
    rejectPayment: (id, reason) =>
      apiFetch(`/payments/${requireId(id, 'معرّف الدفعة')}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }),
    updatePayment: (id, data) =>
      apiFetch(`/payments/${requireId(id, 'معرّف الدفعة')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deletePayment: id =>
      apiFetch(`/payments/${requireId(id, 'معرّف الدفعة')}`, { method: 'DELETE' }),

    // ── Checks ────────────────────────────────────────────────────
    getChecks: () => apiFetch('/checks'),
    createCheck: data =>
      apiFetch('/checks', { method: 'POST', body: JSON.stringify(data) }),
    updateCheckStatus: (id, status) =>
      apiFetch(`/checks/${requireId(id, 'معرّف الشيك')}/status`, { method: 'PUT', body: JSON.stringify({ status }) }),
    deleteCheck: id =>
      apiFetch(`/checks/${requireId(id, 'معرّف الشيك')}`, { method: 'DELETE' }),

    // ── Audit / Stats ─────────────────────────────────────────────
    getStats: () => apiFetch('/audit/stats'),
    getAuditLog: () => apiFetch('/audit/log'),
    getCashbox: () => apiFetch('/audit/cashbox'),
    addCashboxExpense: data =>
      apiFetch('/audit/cashbox/expenses', { method: 'POST', body: JSON.stringify(data) }),

    // ── AI ────────────────────────────────────────────────────────
    askAI: (message, history = []) =>
      apiFetch('/ai/chat', { method: 'POST', body: JSON.stringify({ message, history }) }),

    // ── Suppliers ─────────────────────────────────────────────────
    getSuppliers: () => apiFetch('/suppliers'),
    createSupplier: data =>
      apiFetch('/suppliers', { method: 'POST', body: JSON.stringify(data) }),
    updateSupplier: (id, data) =>
      apiFetch(`/suppliers/${requireValidId(id, 'معرّف المورد')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteSupplier: id =>
      apiFetch(`/suppliers/${requireValidId(id, 'معرّف المورد')}`, { method: 'DELETE' }),
    getSupplierStatement: id =>
      apiFetch(`/suppliers/${requireValidId(id, 'معرّف المورد')}/statement`),
    addSupplierPayment: (id, data) =>
      apiFetch(`/suppliers/${requireValidId(id, 'معرّف المورد')}/payments`, { method: 'POST', body: JSON.stringify(data) }),
    deleteSupplierPayment: id =>
      apiFetch(`/suppliers/payments/${requireId(id, 'معرّف الدفعة')}`, { method: 'DELETE' }),

    // ── Products ──────────────────────────────────────────────────
    getProducts: () => apiFetch('/products'),
    getProduct: id => apiFetch(`/products/${requireValidId(id, 'معرّف الصنف')}`),
    createProduct: data =>
      apiFetch('/products', { method: 'POST', body: JSON.stringify(data) }),
    updateProduct: (id, data) =>
      apiFetch(`/products/${requireValidId(id, 'معرّف الصنف')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteProduct: id =>
      apiFetch(`/products/${requireValidId(id, 'معرّف الصنف')}`, { method: 'DELETE' }),
    getStockMovements: productId =>
      apiFetch(`/products/${requireValidId(productId, 'معرّف الصنف')}/movements`),
    deleteStockMovement: (productId, movementId) =>
      apiFetch(`/products/${requireValidId(productId, 'معرّف الصنف')}/movements/${movementId}`, { method: 'DELETE' }),
    adjustProductStock: (id, data) =>
      apiFetch(`/products/${requireValidId(id, 'معرّف الصنف')}/adjust`, { method: 'POST', body: JSON.stringify(data) }),
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
        throw new Error(extractErrorMessage(data, 'فشل تصدير ملف Excel'));
      }
      const blob = await res.blob();
      let filename = 'تصدير-المستودع.xlsx';
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

    // ── Purchases ─────────────────────────────────────────────────
    getPurchases: () => apiFetch('/purchases'),
    createPurchase: data =>
      apiFetch('/purchases', { method: 'POST', body: JSON.stringify(data) }),
    updatePurchase: (id, data) =>
      apiFetch(`/purchases/${encodeURIComponent(String(id))}`, { method: 'PUT', body: JSON.stringify(data) }),
    receivePurchase: id =>
      apiFetch(`/purchases/${encodeURIComponent(String(id))}/receive`, { method: 'PUT' }),
    deletePurchase: id =>
      apiFetch(`/purchases/${encodeURIComponent(String(id))}`, { method: 'DELETE' }),

    // ── Warehouse Categories ──────────────────────────────────────
    getWarehouseCategories: () => apiFetch('/warehouse-categories'),
    getCategoryProducts: id =>
      apiFetch(`/warehouse-categories/${requireId(id, 'معرّف الفئة')}/products`),
    createWarehouseCategory: data =>
      apiFetch('/warehouse-categories', { method: 'POST', body: JSON.stringify(data) }),
    updateWarehouseCategory: (id, data) =>
      apiFetch(`/warehouse-categories/${requireId(id, 'معرّف الفئة')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteWarehouseCategory: id =>
      apiFetch(`/warehouse-categories/${requireId(id, 'معرّف الفئة')}`, { method: 'DELETE' }),
    getCategoryAnalytics: id =>
      apiFetch(`/warehouse-categories/${requireId(id, 'معرّف الفئة')}/analytics`),

    // ── Warehouse Invoices ────────────────────────────────────────
    getWarehouseInvoices: () => apiFetch('/warehouse-invoices'),
    createWarehouseInvoice: data =>
      apiFetch('/warehouse-invoices', { method: 'POST', body: JSON.stringify(data) }),
    deleteWarehouseInvoice: id =>
      apiFetch(`/warehouse-invoices/${requireId(id, 'معرّف فاتورة المستودع')}`, { method: 'DELETE' }),

    // ── Recipients ────────────────────────────────────────────────
    getRecipients: () => apiFetch('/recipients'),
    getRecipientPayments: () => apiFetch('/recipients/payments'),
    getRecipientStatement: name =>
      apiFetch(`/recipients/${encodeURIComponent(name)}/statement`),
    createRecipientPayment: data =>
      apiFetch('/recipients/payments', { method: 'POST', body: JSON.stringify(data) }),
    updateRecipientPayment: (id, data) =>
      apiFetch(`/recipients/payments/${requireId(id, 'معرّف المقبوضة')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteRecipientPayment: id =>
      apiFetch(`/recipients/payments/${requireId(id, 'معرّف الدفعة')}`, { method: 'DELETE' }),

    // ── China Section ─────────────────────────────────────────────
    getChinaInvestors: () => apiFetch('/china/investors'),
    createChinaInvestor: data =>
      apiFetch('/china/investors', { method: 'POST', body: JSON.stringify(data) }),
    updateChinaInvestor: (id, data) =>
      apiFetch(`/china/investors/${requireValidId(id, 'معرّف المستثمر')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteChinaInvestor: id =>
      apiFetch(`/china/investors/${requireValidId(id, 'معرّف المستثمر')}`, { method: 'DELETE' }),

    getChinaInvestorTransactions: investorId =>
      apiFetch(`/china/investors/${requireValidId(investorId, 'معرّف المستثمر')}/transactions`),
    createChinaInvestorTransaction: (investorId, data) =>
      apiFetch(`/china/investors/${requireValidId(investorId, 'معرّف المستثمر')}/transactions`, { method: 'POST', body: JSON.stringify(data) }),
    deleteChinaInvestorTransaction: id =>
      apiFetch(`/china/transactions/${requireValidId(id, 'معرّف الحركة')}`, { method: 'DELETE' }),

    getChinaPayments: () => apiFetch('/china/payments'),
    createChinaPayment: data =>
      apiFetch('/china/payments', { method: 'POST', body: JSON.stringify(data) }),
    updateChinaPayment: (id, data) =>
      apiFetch(`/china/payments/${requireValidId(id, 'معرّف الدفعة')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteChinaPayment: id =>
      apiFetch(`/china/payments/${requireValidId(id, 'معرّف الدفعة')}`, { method: 'DELETE' }),

    getChinaPurchases: () => apiFetch('/china/purchases'),
    createChinaPurchase: data =>
      apiFetch('/china/purchases', { method: 'POST', body: JSON.stringify(data) }),
    updateChinaPurchase: (id, data) =>
      apiFetch(`/china/purchases/${requireValidId(id, 'معرّف عملية الشراء')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteChinaPurchase: id =>
      apiFetch(`/china/purchases/${requireValidId(id, 'معرّف عملية الشراء')}`, { method: 'DELETE' }),

    getChinaSales: () => apiFetch('/china/sales'),
    createChinaSale: data =>
      apiFetch('/china/sales', { method: 'POST', body: JSON.stringify(data) }),
    updateChinaSale: (id, data) =>
      apiFetch(`/china/sales/${requireValidId(id, 'معرّف عملية البيع')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteChinaSale: id =>
      apiFetch(`/china/sales/${requireValidId(id, 'معرّف عملية البيع')}`, { method: 'DELETE' }),

    getChinaSummary: () => apiFetch('/china/summary'),

    // China suppliers
    getChinaSuppliers: () => apiFetch('/china/suppliers'),
    createChinaSupplier: data =>
      apiFetch('/china/suppliers', { method: 'POST', body: JSON.stringify(data) }),
    updateChinaSupplier: (id, data) =>
      apiFetch(`/china/suppliers/${requireValidId(id, 'معرّف المورد')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteChinaSupplier: id =>
      apiFetch(`/china/suppliers/${requireValidId(id, 'معرّف المورد')}`, { method: 'DELETE' }),
    getChinaSupplierStatement: id =>
      apiFetch(`/china/suppliers/${requireValidId(id, 'معرّف المورد')}/statement`),

    // ── Warehouse Rent (إيجار المستودع) ─────────────────────────────
    getWarehouseRents: () => apiFetch('/expenses/warehouse-rents'),
    createWarehouseRent: data =>
      apiFetch('/expenses/warehouse-rents', { method: 'POST', body: JSON.stringify(data) }),
    updateWarehouseRent: (id, data) =>
      apiFetch(`/expenses/warehouse-rents/${requireId(id, 'معرّف الإيجار')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteWarehouseRent: id =>
      apiFetch(`/expenses/warehouse-rents/${requireId(id, 'معرّف الإيجار')}`, { method: 'DELETE' }),
    getWarehouseRentPayments: id =>
      apiFetch(`/expenses/warehouse-rents/${requireId(id, 'معرّف الإيجار')}/payments`),
    toggleWarehouseRentPayment: (id, data) =>
      apiFetch(`/expenses/warehouse-rents/${requireId(id, 'معرّف الإيجار')}/payments/toggle`, { method: 'POST', body: JSON.stringify(data) }),

    /* ── Warehouse Investors (مستثمرو المستودع) ── */
    getWarehouseInvestors: () => apiFetch('/warehouse-investors/investors'),
    getWarehouseInvestor: id =>
      apiFetch(`/warehouse-investors/investors/${requireId(id, 'معرّف المستثمر')}`),
    createWarehouseInvestor: data =>
      apiFetch('/warehouse-investors/investors', { method: 'POST', body: JSON.stringify(data) }),
    updateWarehouseInvestor: (id, data) =>
      apiFetch(`/warehouse-investors/investors/${requireId(id, 'معرّف المستثمر')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteWarehouseInvestor: id =>
      apiFetch(`/warehouse-investors/investors/${requireId(id, 'معرّف المستثمر')}`, { method: 'DELETE' }),
    getCategoryInvestments: catId =>
      apiFetch(`/warehouse-investors/categories/${requireId(catId, 'معرّف الفئة')}/investments`),
    setCategoryInvestment: (catId, data) =>
      apiFetch(`/warehouse-investors/categories/${requireId(catId, 'معرّف الفئة')}/investments`, { method: 'POST', body: JSON.stringify(data) }),
    deleteCategoryInvestment: (catId, investmentId) =>
      apiFetch(`/warehouse-investors/categories/${requireId(catId, 'معرّف الفئة')}/investments/${requireId(investmentId, 'معرّف المساهمة')}`, { method: 'DELETE' }),
    getCategoryProfitShare: catId =>
      apiFetch(`/warehouse-investors/categories/${requireId(catId, 'معرّف الفئة')}/profit-share`),
    getWarehouseInvestorsSummary: () => apiFetch('/warehouse-investors/summary'),

    // ── Personal Lending (الأمانات الشخصية) ───────────────────────
    getPersonalPeople: () => apiFetch('/personal/people'),
    createPersonalPerson: data =>
      apiFetch('/personal/people', { method: 'POST', body: JSON.stringify(data) }),
    updatePersonalPerson: (id, data) =>
      apiFetch(`/personal/people/${requireId(id, 'معرّف الشخص')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deletePersonalPerson: id =>
      apiFetch(`/personal/people/${requireId(id, 'معرّف الشخص')}`, { method: 'DELETE' }),
    getPersonalTransactions: () => apiFetch('/personal/transactions'),
    createPersonalTransaction: data =>
      apiFetch('/personal/transactions', { method: 'POST', body: JSON.stringify(data) }),
    updatePersonalTransaction: (id, data) =>
      apiFetch(`/personal/transactions/${requireId(id, 'معرّف العملية')}`, { method: 'PUT', body: JSON.stringify(data) }),
    deletePersonalTransaction: id =>
      apiFetch(`/personal/transactions/${requireId(id, 'معرّف العملية')}`, { method: 'DELETE' }),
    getPersonalStatement: id =>
      apiFetch(`/personal/people/${requireId(id, 'معرّف الشخص')}/statement`),
  };

  window.API_BASE = API_BASE;
  window.getToken = getToken;
  window.apiFetch = apiFetch;
  window.API = API;
})();
