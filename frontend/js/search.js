// frontend/js/search.js
// ─────────────────────────────────────────────────────────────
// Global search bar logic.
// Include in index.html AFTER dashboard.js:
//   <script src="js/search.js"></script>
//
// HTML to add inside the topbar in index.html
// (before the user avatar div):
//
//  <div class="global-search" id="global-search-wrap" style="display:none">
//    <div style="position:relative">
//      <input id="global-search-input" type="text"
//        placeholder="🔍 بحث شامل..."
//        oninput="handleGlobalSearch(this.value)"
//        onblur="setTimeout(()=>closeSearchDropdown(),200)"
//        autocomplete="off"
//        style="
//          width:280px; padding:8px 14px 8px 36px;
//          border:1px solid rgba(255,255,255,.15);
//          border-radius:20px; background:rgba(255,255,255,.1);
//          color:white; font-family:inherit; font-size:13px;
//          outline:none; direction:rtl;
//        "
//      />
//      <div id="search-dropdown" style="
//        display:none; position:absolute; top:42px; right:0;
//        width:420px; max-height:460px; overflow-y:auto;
//        background:white; border-radius:12px;
//        box-shadow:0 8px 32px rgba(0,0,0,.18);
//        border:1px solid rgba(0,0,0,.08); z-index:9999;
//      "></div>
//    </div>
//  </div>
//
// Show the search bar after login by calling showGlobalSearch()
// from setupApp() in dashboard.js.
// ─────────────────────────────────────────────────────────────

let _searchTimer = null;

function showGlobalSearch() {
  const wrap = document.getElementById("global-search-wrap");
  if (wrap) wrap.style.display = "block";

  // Ctrl+K / Cmd+K shortcut
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      document.getElementById("global-search-input")?.focus();
    }
    if (e.key === "Escape") closeSearchDropdown();
  });
}

function handleGlobalSearch(val) {
  clearTimeout(_searchTimer);
  const dd = document.getElementById("search-dropdown");
  if (!dd) return;

  if (!val || val.length < 2) {
    dd.style.display = "none";
    return;
  }

  // Show loading state immediately
  dd.style.display = "block";
  dd.innerHTML = `
    <div style="padding:16px; text-align:center; color:#9e9a94; font-size:13px">
      <div style="display:inline-block;width:16px;height:16px;border:2px solid #ddd;border-top-color:#1a4fd6;border-radius:50%;animation:spin 0.7s linear infinite;margin-left:6px"></div>
      جاري البحث...
    </div>`;

  _searchTimer = setTimeout(() => doGlobalSearch(val), 300);
}

async function doGlobalSearch(q) {
  const dd = document.getElementById("search-dropdown");
  if (!dd) return;

  try {
    const res = await API.search(q);
    renderSearchDropdown(res, q, dd);
  } catch (e) {
    dd.innerHTML = `<div style="padding:16px; color:var(--rd); font-size:13px">❌ ${e.message}</div>`;
  }
}

function renderSearchDropdown(data, q, dd) {
  const { clients = [], invoices = [], checks = [], products = [] } = data;
  const total =
    clients.length + invoices.length + checks.length + products.length;

  if (total === 0) {
    dd.innerHTML = `
      <div style="padding:24px; text-align:center; color:#9e9a94">
        <div style="font-size:24px; margin-bottom:8px">🔍</div>
        <div style="font-size:13px">لا توجد نتائج لـ "${escHtml(q)}"</div>
      </div>`;
    return;
  }

  const hl = (text) => {
    // Highlight matched portion
    const s = String(text || "");
    const idx = s.toLowerCase().indexOf(q.toLowerCase());
    if (idx === -1) return escHtml(s);
    return (
      escHtml(s.slice(0, idx)) +
      `<mark style="background:#fef08a; border-radius:2px; padding:0 1px">${escHtml(s.slice(idx, idx + q.length))}</mark>` +
      escHtml(s.slice(idx + q.length))
    );
  };

  const fmt = (n) =>
    parseFloat(n || 0).toLocaleString("ar-JO", { minimumFractionDigits: 2 });

  let html = `<div style="padding:8px 12px; font-size:11px; color:#9e9a94; border-bottom:1px solid #f0ede8">${total} نتيجة</div>`;

  // ── Clients ───────────────────────────────────────────────
  if (clients.length) {
    html += sectionHeader("👥 العملاء");
    clients.forEach((c) => {
      const bal = parseFloat(c.balance || 0);
      const balColor = bal > 0 ? "#c21515" : "#057a55";
      html += `
        <div class="sr-row" onclick="navigateTo('clients'); closeSearchDropdown();"
             style="padding:10px 16px; cursor:pointer; display:flex; align-items:center; gap:10px; transition:background .1s"
             onmouseenter="this.style.background='#f7f6f3'" onmouseleave="this.style.background='white'">
          <div style="width:34px;height:34px;background:#e8f0fe;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0">👤</div>
          <div style="flex:1;min-width:0">
            <div style="font-weight:600;font-size:13px">${hl(c.name)}</div>
            ${c.phone ? `<div style="font-size:11px;color:#9e9a94">${hl(c.phone)}</div>` : ""}
          </div>
          <div style="text-align:left;flex-shrink:0">
            <div style="font-size:12px;font-weight:700;color:${balColor}">${fmt(c.balance)} د.أ</div>
            <div style="font-size:10px;color:#9e9a94">رصيد</div>
          </div>
        </div>`;
    });
  }

  // ── Invoices ──────────────────────────────────────────────
  // ── Invoices ──────────────────────────────────────────────
  if (invoices.length) {
    html += sectionHeader("🧾 الفواتير");
    invoices.forEach((inv) => {
      const writer = inv.attributed_employee_name || inv.created_by_name || '';
      const recip = inv.recipient_name || '';
      html += `
        <div class="sr-row" onclick="navigateTo('invoices'); closeSearchDropdown();"
             style="padding:10px 16px; cursor:pointer; display:flex; align-items:center; gap:10px"
             onmouseenter="this.style.background='#f7f6f3'" onmouseleave="this.style.background='white'">
          <div style="width:34px;height:34px;background:#fef3c7;border-radius:8px;
                      display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0">
            🧾
          </div>
          <div style="flex:1;min-width:0">
            <div style="font-weight:700;font-size:13px">${hl(inv.invoice_number)}</div>
            <div style="font-size:11px;color:#9e9a94;margin-top:2px">
              ${recip
          ? `المطلوب من السادة: <strong>${hl(recip)}</strong>`
          : hl(inv.client_name)}
            </div>
            ${writer
          ? `<div style="font-size:10px;color:#b0aaa4">كتبها: ${hl(writer)}</div>`
          : ''}
          </div>
          <div style="text-align:left;flex-shrink:0">
            <div style="font-size:12px;font-weight:700">${fmt(inv.total_amount)} د.أ</div>
            <div style="font-size:10px;color:#9e9a94">
              ${inv.date ? new Date(inv.date).toLocaleDateString("ar-JO") : ""}
            </div>
          </div>
        </div>`;
    });
  }

  // ── Checks ────────────────────────────────────────────────
  if (checks.length) {
    html += sectionHeader("🏦 الشيكات");
    const statusLabel = {
      pending: "معلّق",
      cashed: "محصَّل",
      returned: "مرتجع",
    };
    const statusColor = {
      pending: "#9a4500",
      cashed: "#057a55",
      returned: "#c21515",
    };
    checks.forEach((ch) => {
      html += `
        <div class="sr-row" onclick="navigateTo('checks'); closeSearchDropdown();"
             style="padding:10px 16px; cursor:pointer; display:flex; align-items:center; gap:10px"
             onmouseenter="this.style.background='#f7f6f3'" onmouseleave="this.style.background='white'">
          <div style="width:34px;height:34px;background:#e0f2fe;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0">🏦</div>
          <div style="flex:1;min-width:0">
            <div style="font-weight:600;font-size:13px;font-family:monospace">${hl(ch.check_number)}</div>
            <div style="font-size:11px;color:#9e9a94">${hl(ch.client_name)}</div>
          </div>
          <div style="text-align:left;flex-shrink:0">
            <div style="font-size:12px;font-weight:700">${fmt(ch.amount)} د.أ</div>
            <div style="font-size:10px;color:${statusColor[ch.status] || "#9e9a94"};font-weight:600">${statusLabel[ch.status] || ch.status}</div>
          </div>
        </div>`;
    });
  }

  // ── Products ──────────────────────────────────────────────
  if (products.length) {
    html += sectionHeader("📦 المستودع");
    products.forEach((p) => {
      const isLow = parseFloat(p.current_stock) === 0;
      html += `
        <div class="sr-row" onclick="navigateTo('warehouse'); closeSearchDropdown();"
             style="padding:10px 16px; cursor:pointer; display:flex; align-items:center; gap:10px"
             onmouseenter="this.style.background='#f7f6f3'" onmouseleave="this.style.background='white'">
          <div style="width:34px;height:34px;background:#dcfce7;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0">📦</div>
          <div style="flex:1;min-width:0">
            <div style="font-weight:600;font-size:13px">${hl(p.name)}</div>
            <div style="font-size:11px;color:#9e9a94">${p.category_name || ""} ${p.sku ? "· " + p.sku : ""}</div>
          </div>
          <div style="text-align:left;flex-shrink:0">
            <div style="font-size:12px;font-weight:700;color:${isLow ? "#c21515" : "#057a55"}">${p.current_stock} ${p.unit}</div>
            <div style="font-size:10px;color:#9e9a94">مخزون</div>
          </div>
        </div>`;
    });
  }

  dd.innerHTML = html;
}

function sectionHeader(label) {
  return `<div style="padding:6px 16px; font-size:10px; font-weight:700; color:#9e9a94; background:#faf9f7; letter-spacing:.5px; text-transform:uppercase; border-bottom:1px solid #f0ede8">${label}</div>`;
}

function closeSearchDropdown() {
  const dd = document.getElementById("search-dropdown");
  const inp = document.getElementById("global-search-input");
  if (dd) dd.style.display = "none";
  if (inp) inp.value = "";
}
