// --- GLOBAL DATA STORE ---
let AppState = {
  currentUser: null,
  lapakData: {},
  ownerData: {},
  reviewData: {},
  ownerReportDate: new Date(),
};

// --- CORE FUNCTIONS ---
async function showPage(pageId) {
  document.querySelectorAll(".page").forEach((e) => (e.style.display = "none"));
  const activePage = document.getElementById(pageId);
  if (!activePage) return;

  activePage.style.display = "block";
  if (pageId === "login-page") activePage.style.display = "flex";

  if (AppState.currentUser?.role === "owner") {
    if (pageId.startsWith("owner-data") || pageId === "owner-dashboard")
      await populateOwnerDashboard();
    if (pageId === "owner-laporan-utang-page") await populateLaporanBiaya();
    if (pageId === "owner-laporan-pendapatan-page")
      await populateLaporanPendapatan();
  }
  if (AppState.currentUser?.role === "lapak") {
    if (pageId === "penjualan-page") await populatePenjualanPage();
    if (pageId === "terima-barang-page") populateSupplierSelect();
    if (pageId === "review-harian-page") await populateReviewPage();
    if (pageId === "lapor-return-page") populateLaporReturnSelects();
  }
  if (pageId === "supplier-dashboard") populateSupplierDashboard();
}

function updateDate() {
  const e = { weekday: "long", year: "numeric", month: "long", day: "numeric" },
    t = new Date().toLocaleDateString("id-ID", e);
  ["current-date-lapak", "current-date-owner", "current-date-supplier"].forEach(
    (e) => {
      const a = document.getElementById(e);
      a && (a.textContent = t);
    }
  );
}

async function handleLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  try {
    const response = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const result = await response.json();
    if (result.success) {
      AppState.currentUser = result;
      if (result.role === "lapak") {
        const dataResp = await fetch("/get_data_lapak");
        AppState.lapakData = await dataResp.json();
        document.getElementById("lapak-name").textContent =
          result.user_info.nama_lengkap;
        showPage("lapak-dashboard");
      } else if (result.role === "owner") {
        showPage("owner-dashboard");
      } else if (result.role === "supplier") {
        document.getElementById("supplier-name").textContent =
          result.user_info.nama_supplier;
        showPage("supplier-dashboard");
      }
      updateDate();
    } else {
      showToast(result.message || "Login Gagal", false);
    }
  } catch (e) {
    console.error("Login error:", e);
    showToast("Terjadi kesalahan koneksi.", false);
  }
}

function handleLogout() {
  document.body.classList.remove("dark-mode");
  const e = document.getElementById("theme-switcher");
  e && (e.checked = !1),
    document.getElementById("login-form").reset(),
    (AppState = {
      currentUser: null,
      lapakData: {},
      ownerData: {},
      ownerReportDate: new Date(),
    }),
    showPage("login-page");
}
function toggleTheme() {
  document.body.classList.toggle("dark-mode");
}
function showToast(message, isSuccess = true) {
  const toastEl = document.getElementById("liveToast");
  const toastBody = document.getElementById("toast-body");
  const toastIcon = document.getElementById("toast-icon");
  const toastTitle = document.getElementById("toast-title");

  toastBody.textContent = message;
  toastEl.classList.remove("bg-danger", "bg-success", "text-white");
  if (isSuccess) {
    toastEl.classList.add("bg-success", "text-white");
    toastIcon.className = "bi bi-check-circle-fill me-2";
    toastTitle.textContent = "Sukses";
  } else {
    toastEl.classList.add("bg-danger", "text-white");
    toastIcon.className = "bi bi-exclamation-triangle-fill me-2";
    toastTitle.textContent = "Gagal";
  }
  const toast = new bootstrap.Toast(toastEl);
  toast.show();
}

// --- OWNER FUNCTIONS ---
async function populateOwnerDashboard() {
  try {
    const dataResp = await fetch("/get_data_owner");
    AppState.ownerData = await dataResp.json();
    document.getElementById(
      "owner-pendapatan-card"
    ).textContent = `Rp ${AppState.ownerData.summary.pendapatan_bulan_ini.toLocaleString(
      "id-ID"
    )}`;
    document.getElementById(
      "owner-biaya-card"
    ).textContent = `Rp ${AppState.ownerData.summary.biaya_bulan_ini.toLocaleString(
      "id-ID"
    )}`;
    await populateOwnerDataPages();
  } catch (e) {
    console.error("Failed to populate owner dashboard:", e);
  }
}
async function populateOwnerDataPages() {
  const { user_data: e, lapak_data: t, supplier_data: a } = AppState.ownerData,
    o = document.getElementById("user-table-body");
  (o.innerHTML = ""),
    e.forEach((e) => {
      o.innerHTML += `<tr><td>${e.nama_lengkap}</td><td>${e.nik}</td><td>${e.username}</td><td>${e.email}</td><td>${e.nomor_kontak}</td><td><button class="btn btn-sm btn-outline-primary me-1"><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash-fill"></i></button></td></tr>`;
    });
  const n = document.getElementById("lapak-table-body");
  (n.innerHTML = ""),
    t.forEach((e) => {
      n.innerHTML += `<tr><td>${e.lokasi}</td><td>${e.penanggung_jawab}</td><td>${e.nomor_kontak}</td><td><button class="btn btn-sm btn-outline-primary me-1"><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash-fill"></i></button></td></tr>`;
    });
  const d = document.getElementById("lapak-pj-select");
  (d.innerHTML = '<option selected value="">-- Pilih User --</option>'),
    e.forEach((e) => {
      d.innerHTML += `<option value="${e.username}">${e.nama_lengkap} (${e.username})</option>`;
    });
  const i = document.getElementById("supplier-table-body");
  (i.innerHTML = ""),
    a.forEach((e) => {
      i.innerHTML += `<tr><td>${e.nama_supplier}</td><td>${e.kontak}</td><td>${e.nomor_register}</td><td><button class="btn btn-sm btn-outline-primary me-1"><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash-fill"></i></button></td></tr>`;
    });
}
async function changeOwnerReportDate(days, reportType) {
  AppState.ownerReportDate.setDate(AppState.ownerReportDate.getDate() + days);
  if (reportType === "biaya") await populateLaporanBiaya();
  if (reportType === "pendapatan") await populateLaporanPendapatan();
}
async function populateLaporanBiaya() {
  const dateString = AppState.ownerReportDate.toISOString().split("T")[0];
  const response = await fetch(`/get_laporan_biaya_harian?date=${dateString}`);
  const data = await response.json();

  document.getElementById("biaya-date-display").textContent =
    AppState.ownerReportDate.toLocaleDateString("id-ID", {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  const tbody = document.getElementById("biaya-table-body");
  tbody.innerHTML = "";
  data.rincian_biaya.forEach((item) => {
    tbody.innerHTML += `<tr><td><div>${
      item.nama_supplier
    }<small class="d-block text-muted">Reg: ${
      item.reg_supplier
    }</small></div></td><td><div>${
      item.penanggung_jawab_lapak
    }<small class="d-block text-muted">(${
      item.username_lapak
    })</small></div></td><td class="text-end">Rp ${item.nominal.toLocaleString(
      "id-ID"
    )}</td></tr>`;
  });
  document.getElementById(
    "biaya-total-harian"
  ).textContent = `Rp ${data.total_harian.toLocaleString("id-ID")}`;
}
async function populateLaporanPendapatan() {
  const dateString = AppState.ownerReportDate.toISOString().split("T")[0];
  const response = await fetch(
    `/get_laporan_pendapatan_harian?date=${dateString}`
  );
  const data = await response.json();

  document.getElementById("pendapatan-date-display").textContent =
    AppState.ownerReportDate.toLocaleDateString("id-ID", {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  const accordionContainer = document.getElementById(
    "pendapatanLapakAccordion"
  );
  accordionContainer.innerHTML = "";
  data.laporan_per_lapak.forEach((lapak, index) => {
    let rincianHtml = "";
    lapak.rincian.forEach((r) => {
      rincianHtml += `<tr><td>${r.produk} <small class="text-muted d-block">${
        r.supplier
      }</small></td><td class="text-end">${
        r.jumlah
      }</td><td class="text-end">Rp ${r.nominal.toLocaleString(
        "id-ID"
      )}</td></tr>`;
    });
    const collapsed = index > 0 ? "collapsed" : "";
    const show = index === 0 ? "show" : "";
    accordionContainer.innerHTML += `<div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button ${collapsed}" type="button" data-bs-toggle="collapse" data-bs-target="#collapseLapak${index}"><div class="d-flex justify-content-between w-100 pe-3"><strong>${
      lapak.lokasi
    } <small class="text-muted d-block">${lapak.penanggung_jawab} (${
      lapak.username
    })</small></strong><strong class="text-success">Rp ${lapak.total_pendapatan.toLocaleString(
      "id-ID"
    )}</strong></div></button></h2><div id="collapseLapak${index}" class="accordion-collapse collapse ${show}" data-bs-parent="#pendapatanLapakAccordion"><div class="accordion-body"><div class="table-responsive"><table class="table table-sm table-borderless"><thead><tr><th>Produk</th><th class="text-end">Jumlah</th><th class="text-end">Nominal</th></tr></thead><tbody>${rincianHtml}</tbody></table></div></div></div></div>`;
  });
  document.getElementById(
    "pendapatan-total-harian"
  ).textContent = `Rp ${data.total_harian.toLocaleString("id-ID")}`;
}

// --- FORM SUBMISSION HANDLERS ---
document
  .getElementById("add-user-form")
  .addEventListener("submit", async function (e) {
    e.preventDefault();
    const t = {
      nama_lengkap: document.getElementById("add-user-nama").value,
      nik: document.getElementById("add-user-nik").value,
      username: document.getElementById("add-user-username").value,
      email: document.getElementById("add-user-email").value,
      nomor_kontak: document.getElementById("add-user-kontak").value,
      password: document.getElementById("add-user-password").value,
    };
    try {
      const a = await fetch("/add_user", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(t),
        }),
        o = await a.json();
      showToast(o.message, o.success);
      if (o.success) {
        this.reset();
        const e = await fetch("/get_data_owner");
        (AppState.ownerData = await e.json()), showPage("owner-data-user-page");
      }
    } catch (e) {
      showToast("Koneksi error.", !1);
    }
  });
document
  .getElementById("add-lapak-form")
  .addEventListener("submit", async function (e) {
    e.preventDefault();
    const t = {
      lokasi: document.getElementById("add-lapak-lokasi").value,
      penanggung_jawab: document.getElementById("lapak-pj-select").value,
    };
    try {
      const a = await fetch("/add_lapak", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(t),
        }),
        o = await a.json();
      showToast(o.message, o.success);
      if (o.success) {
        this.reset();
        const e = await fetch("/get_data_owner");
        (AppState.ownerData = await e.json()),
          showPage("owner-data-lapak-page");
      }
    } catch (e) {
      showToast("Koneksi error.", !1);
    }
  });
document
  .getElementById("add-supplier-form")
  .addEventListener("submit", async function (e) {
    e.preventDefault();
    const t = Array.from(document.querySelectorAll(".product-input-field"))
        .map((e) => e.value)
        .filter((e) => e.trim()),
      a = {
        nama_supplier: document.getElementById("add-supplier-nama").value,
        nama_alias: document.getElementById("add-supplier-alias").value,
        kontak: document.getElementById("add-supplier-kontak").value,
        nomor_register: document.getElementById("add-supplier-register").value,
        alamat: document.getElementById("add-supplier-alamat").value,
        bank: document.getElementById("add-supplier-bank").value,
        nomor_rekening: document.getElementById("add-supplier-rekening").value,
        password: document.getElementById("add-supplier-password").value,
        products: t,
      };
    try {
      const o = await fetch("/add_supplier", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(a),
        }),
        n = await o.json();
      showToast(n.message, n.success);
      if (n.success) {
        this.reset();
        document.getElementById("product-fields-container").innerHTML = "";
        const e = await fetch("/get_data_owner");
        (AppState.ownerData = await e.json()),
          showPage("owner-data-supplier-page");
      }
    } catch (e) {
      showToast("Koneksi error.", !1);
    }
  });
function addProductField() {
  const e = document.createElement("div");
  (e.className = "input-group mb-2"),
    (e.innerHTML =
      '<input type="text" class="form-control product-input-field" placeholder="Nama Produk"><button class="btn btn-outline-danger" type="button" onclick="this.parentElement.remove()">-</button>'),
    document.getElementById("product-fields-container").appendChild(e);
}

// --- LAPAK FUNCTIONS ---
function populateSupplierSelect() {
  const e = document.getElementById("supplier-select-barang-masuk");
  (e.innerHTML = '<option selected value="">-- Pilih Supplier --</option>'),
    AppState.lapakData.suppliers.forEach((t) => {
      e.innerHTML += `<option value="${t.id}">${t.nama_supplier}</option>`;
    });
}
function updateProductList() {
  const e = document.getElementById("supplier-select-barang-masuk").value,
    t = document.getElementById("product-list-container"),
    a = document.getElementById("product-list-header");
  if (((t.innerHTML = ""), (a.style.display = "none"), e)) {
    a.style.display = "block";
    const o = AppState.lapakData.products_by_supplier[e] || [];
    if (o.length > 0) {
      const e = document.createElement("ul");
      (e.className = "list-group"),
        o.forEach((a) => {
          const o = document.createElement("li");
          (o.className =
            "list-group-item d-flex justify-content-between align-items-center"),
            (o.innerHTML = `<span>${a.name}</span><div class="input-group" style="width: 120px;"><button class="btn btn-outline-secondary" type="button" onclick="changeQuantity('qty-${a.id}', -1)">-</button><input type="text" class="form-control text-center" value="0" id="qty-${a.id}" readonly><button class="btn btn-outline-secondary" type="button" onclick="changeQuantity('qty-${a.id}', 1)">+</button></div>`),
            e.appendChild(o);
        }),
        t.appendChild(e);
    } else
      t.innerHTML =
        '<p class="text-muted">Tidak ada produk untuk supplier ini.</p>';
  }
}
function changeQuantity(e, t) {
  const a = document.getElementById(e);
  let o = parseInt(a.value, 10),
    n = o + t;
  n < 0 && (n = 0), (a.value = n);
}
async function populatePenjualanPage() {
  await populatePenjualanList();
  await populatePenjualanHarian();
}
async function populatePenjualanList() {
  const e = document.getElementById("penjualan-product-list-container");
  e.innerHTML = "";
  const t = document.createElement("ul");
  t.className = "list-group";
  for (const a in AppState.lapakData.all_products) {
    const o = AppState.lapakData.all_products[a],
      n = AppState.lapakData.stock_data[a] || 0,
      d = document.createElement("li");
    (d.className =
      "list-group-item d-flex justify-content-between align-items-center"),
      (d.innerHTML = `<div><h6 class="mb-0">${o.name}</h6><small class="text-muted">Stok: <span id="stock-display-${a}">${n}</span> Pcs</small></div><div class="input-group" style="width: 120px;"><button class="btn btn-outline-secondary" type="button" onclick="changeSaleQuantity('${a}', -1)">-</button><input type="text" class="form-control text-center" value="0" id="sale-qty-${a}" readonly data-stock="${n}"><button class="btn btn-outline-secondary" type="button" onclick="changeSaleQuantity('${a}', 1)">+</button></div>`),
      t.appendChild(d);
  }
  e.appendChild(t);
}
async function populatePenjualanHarian() {
  const e = document.getElementById("penjualan-harian-tbody");
  e.innerHTML = "";
  const t = AppState.currentUser.user_info.lapak_id;
  try {
    const a = await fetch(`/get_penjualan_harian/${t}`),
      o = await a.json();
    o.forEach((t) => {
      const a = "cash" === t.payment ? "success" : "primary";
      e.innerHTML += `<tr><td><strong>${
        t.product_name
      }</strong><small class="d-block text-muted">${t.qty} Pcs - ${
        t.time
      }</small></td><td class="text-center align-middle"><span class="badge bg-${a}">${t.payment.toUpperCase()}</span></td><td class="text-end align-middle">Rp ${t.total.toLocaleString(
        "id-ID"
      )}</td></tr>`;
    });
  } catch (e) {
    console.error(e);
  }
}
document
  .getElementById("simpan-penjualan-btn")
  .addEventListener("click", async function () {
    const e = [];
    document
      .querySelectorAll("#penjualan-product-list-container input")
      .forEach((t) => {
        const a = parseInt(t.value, 10);
        a > 0 && e.push({ id: t.id.replace("sale-qty-", ""), qty: a });
      });
    if (0 === e.length)
      return void showToast("Tidak ada produk yang dipilih untuk dijual.", !1);
    const t = document.querySelector(
        'input[name="paymentMethod"]:checked'
      ).value,
      a = {
        products: e,
        payment: t,
        lapak_id: AppState.currentUser.user_info.lapak_id,
      };
    try {
      const e = await fetch("/add_penjualan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(a),
        }),
        t = await e.json();
      showToast(t.message, t.success),
        t.success &&
          ((AppState.lapakData = await (await fetch("/get_data_lapak")).json()),
          await populatePenjualanPage());
    } catch (e) {
      showToast("Koneksi error.", !1);
    }
  });
document
  .getElementById("simpan-penerimaan-btn")
  .addEventListener("click", async function () {
    const e = [];
    document.querySelectorAll("#product-list-container input").forEach((t) => {
      const a = parseInt(t.value, 10);
      a > 0 && e.push({ id: t.id.replace("qty-", ""), qty: a });
    });
    if (0 === e.length)
      return void showToast("Tidak ada produk yang diterima.", !1);
    const t = {
      products: e,
      lapak_id: AppState.currentUser.user_info.lapak_id,
    };
    try {
      const e = await fetch("/add_barang_masuk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(t),
        }),
        a = await e.json();
      showToast(a.message, a.success),
        a.success &&
          ((AppState.lapakData = await (await fetch("/get_data_lapak")).json()),
          showPage("lapak-dashboard"));
    } catch (e) {
      showToast("Koneksi error.", !1);
    }
  });
document
  .getElementById("konfirmasi-laporan-btn")
  .addEventListener("click", async function () {
    const e = { lapak_id: AppState.currentUser.user_info.lapak_id };
    try {
      const t = await fetch("/konfirmasi_laporan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(e),
        }),
        a = await t.json();
      showToast(a.message, a.success), a.success && showPage("lapak-dashboard");
    } catch (e) {
      showToast("Koneksi error.", !1);
    }
  });
function changeSaleQuantity(e, t) {
  const a = document.getElementById(`sale-qty-${e}`),
    o = parseInt(a.getAttribute("data-stock"), 10),
    n = document.getElementById(`stock-display-${e}`);
  let d = parseInt(a.value, 10),
    i = d + t;
  i < 0 && (i = 0), i > o && (i = o), (a.value = i), (n.textContent = o - i);
}

// --- REVIEW & HISTORY PAGES ---
function toggleLaporanForm() {
  const e = document.getElementById("jenis-laporan-select").value,
    t = document.getElementById("form-return"),
    a = document.getElementById("form-masalah-supply");
  (t.style.display = "return" === e ? "block" : "none"),
    (a.style.display = "masalah" === e ? "block" : "none");
}
async function populateReviewPage() {
  try {
    const e = await fetch(
        `/get_review_data/${AppState.currentUser.user_info.lapak_id}`
      ),
      t = await e.json();
    AppState.reviewData = t;
    const a = document.getElementById("review-penjualan-list");
    (a.innerHTML = ""),
      t.penjualan_harian.forEach((e) => {
        const o = t.all_products[e.productId],
          n =
            "cash" === e.payment
              ? '<span class="badge bg-success">Cash</span>'
              : '<span class="badge bg-primary">QRIS</span>',
          d = document.createElement("li");
        (d.className =
          "list-group-item d-flex justify-content-between align-items-center"),
          (d.innerHTML = `<div><h6 class="mb-0">${o.name}</h6><small class="text-muted">${n} - ${e.time}</small></div><div class="input-group" style="width: 120px;"><button class="btn btn-outline-secondary btn-sm" type="button" onclick="changeReviewQuantity(${e.id}, -1)">-</button><input type="text" class="form-control form-control-sm text-center" value="${e.qty}" id="review-qty-${e.id}" readonly><button class="btn btn-outline-secondary btn-sm" type="button" onclick="changeReviewQuantity(${e.id}, 1)">+</button></div>`),
          a.appendChild(d);
      });
    const reviewMasukList = document.getElementById("review-barang-masuk-list");
    reviewMasukList.innerHTML = "";
    if (t.barang_masuk_harian.length > 0) {
      const ul = document.createElement("ul");
      t.barang_masuk_harian.forEach((bm) => {
        ul.innerHTML += `<li>${bm.productName} (${bm.jumlah} Pcs) dari ${bm.supplierName} <small class="text-muted ms-2">(${bm.time})</small></li>`;
      });
      reviewMasukList.appendChild(ul);
    } else {
      reviewMasukList.innerHTML =
        '<p class="text-muted p-3">Tidak ada barang masuk hari ini.</p>';
    }
    updateReviewSummary();
  } catch (e) {
    console.error("Gagal memuat data review:", e);
  }
}
function changeReviewQuantity(e, t) {
  const a = AppState.reviewData.penjualan_harian.find((t) => t.id === e);
  if (!a) return;
  let o = a.qty + t;
  if (o < 0) return;
  const n = AppState.reviewData.stock_awal_hari[a.productId] || 0,
    d = AppState.reviewData.barang_masuk_harian
      .filter((e) => e.productId === a.productId)
      .reduce((e, t) => e + t.jumlah, 0),
    i = n + d,
    l = AppState.reviewData.penjualan_harian
      .filter((e) => e.productId === a.productId && e.id !== a.id)
      .reduce((e, t) => e + t.qty, 0);
  o > i - l &&
    ((o = a.qty), showToast("Jumlah melebihi stok yang tersedia!", !1)),
    (a.qty = o),
    (document.getElementById(`review-qty-${a.id}`).value = a.qty),
    updateReviewSummary();
}
function updateReviewSummary() {
  let e = 0,
    t = 0,
    a = 0;
  const o = Object.values(AppState.reviewData.stock_awal_hari || {}).reduce(
      (e, t) => e + t,
      0
    ),
    n = (AppState.reviewData.barang_masuk_harian || []).reduce(
      (e, t) => e + t.jumlah,
      0
    );
  (AppState.reviewData.penjualan_harian || []).forEach((o) => {
    const n = AppState.reviewData.all_products[o.productId],
      d = o.qty * n.price;
    "cash" === o.payment ? (e += d) : (t += d), (a += o.qty);
  });
  const d = e + t,
    i = o + n - a;
  (document.getElementById(
    "review-pendapatan-cash"
  ).textContent = `Rp ${e.toLocaleString("id-ID")}`),
    (document.getElementById(
      "review-pendapatan-qris"
    ).textContent = `Rp ${t.toLocaleString("id-ID")}`),
    (document.getElementById(
      "review-total-pendapatan"
    ).textContent = `Rp ${d.toLocaleString("id-ID")}`),
    (document.getElementById(
      "review-total-produk-terjual"
    ).textContent = `${a} Pcs`),
    (document.getElementById(
      "review-total-sisa-produk"
    ).textContent = `${i} Pcs`);
}

// --- SUPPLIER DASHBOARD (Simulasi Frontend) ---
function populateSupplierDashboard() {
  const e = document.getElementById("supplierReportAccordion");
  e.innerHTML = "";
  let t = 0;
  const a = AppState.ownerData ? AppState.ownerData.supplier_report_data : {};
  for (const o in a) {
    const n = a[o],
      d = `supplier-report-${t}`,
      i = document.createElement("div");
    i.className = "accordion-item";
    let l = "";
    n.forEach((e) => {
      const t = AppState.ownerData.all_products[e.productId]
        ? AppState.ownerData.all_products[e.productId].name
        : "Produk Tidak Dikenal";
      l += `<tr><td>${t}</td><td class="text-end">${e.stokAwal}</td><td class="text-end">${e.terjual}</td><td class="text-end fw-bold">${e.sisa}</td></tr>`;
    }),
      (i.innerHTML = `<h2 class="accordion-header"><button class="accordion-button ${
        0 === t ? "" : "collapsed"
      }" type="button" data-bs-toggle="collapse" data-bs-target="#${d}">${o}</button></h2><div id="${d}" class="accordion-collapse collapse ${
        0 === t ? "show" : ""
      }" data-bs-parent="#supplierReportAccordion"><div class="accordion-body table-responsive"><table class="table table-sm table-striped"><thead><tr><th>Produk</th><th class="text-end">Stok Awal</th><th class="text-end">Terjual</th><th class="text-end">Sisa</th></tr></thead><tbody>${l}</tbody></table></div></div>`),
      e.appendChild(i),
      t++;
  }
}

// --- ON STARTUP ---
document.addEventListener("DOMContentLoaded", () => {
  showPage("login-page");
  updateDate();
});
