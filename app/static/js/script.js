const { jsPDF } = window.jspdf;
// --- GLOBAL STATE & MODAL INSTANCES ---
let AppState = {
  currentUser: null,
  ownerData: {},
  catatanData: { products: [] },
  lapakSuppliers: [],
};
let pendapatanChartInstance = null;
let biayaChartInstance = null;
let modals = {};

// --- HELPER & CORE FUNCTIONS ---
function formatCurrency(value) {
  return `Rp ${new Intl.NumberFormat("id-ID").format(value)}`;
}
function formatNumberInput(e) {
  let input = e.target;
  // 1. Ambil nilai input dan hapus semua karakter selain angka
  let value = input.value.replace(/\D/g, "");

  // 2. Jika nilainya kosong, biarkan kosong
  if (value === "") {
    input.value = "";
    return;
  }

  // 3. Ubah menjadi angka, lalu format dengan pemisah ribuan (titik)
  let formattedValue = new Intl.NumberFormat("id-ID").format(value);

  // 4. Setel kembali nilai input dengan yang sudah diformat
  input.value = formattedValue;
}
function manageFooterVisibility() {
  const footer = document.getElementById("rekap-footer");
  const handle = document.getElementById("footer-handle");
  const icon = document.getElementById("footer-toggle-icon");

  if (!footer || !handle || !icon) return;

  handle.onclick = function () {
    // Toggle kelas 'footer-hidden'
    footer.classList.toggle("footer-hidden");

    // Cek status setelah di-toggle, lalu ganti ikonnya
    if (footer.classList.contains("footer-hidden")) {
      icon.classList.remove("bi-chevron-down");
      icon.classList.add("bi-chevron-up");
    } else {
      icon.classList.remove("bi-chevron-up");
      icon.classList.add("bi-chevron-down");
    }
  };
}

function updateDate() {
  const today = new Date().toLocaleDateString("id-ID", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  ["current-date-lapak", "current-date-owner", "current-date-supplier"].forEach(
    (id) => {
      if (document.getElementById(id))
        document.getElementById(id).textContent = today;
    }
  );
}
function showToast(message, isSuccess = true) {
  const toastEl = document.getElementById("liveToast");
  if (!toastEl) return;
  const toast = bootstrap.Toast.getOrCreateInstance(toastEl);
  document.getElementById("toast-body").textContent = message;
  toastEl.className = `toast ${
    isSuccess ? "bg-success" : "bg-danger"
  } text-white`;
  document.getElementById("toast-icon").className = `bi ${
    isSuccess ? "bi-check-circle-fill" : "bi-exclamation-triangle-fill"
  } me-2`;
  document.getElementById("toast-title").textContent = isSuccess
    ? "Sukses"
    : "Gagal";
  toast.show();
}
function togglePasswordVisibility(button, fieldId) {
  const field = document.getElementById(fieldId);
  const icon = button.querySelector("i");
  if (field.type === "password") {
    field.type = "text";
    icon.classList.replace("bi-eye-slash", "bi-eye");
  } else {
    field.type = "password";
    icon.classList.replace("bi-eye", "bi-eye-slash");
  }
}
function toggleTablePasswordVisibility(icon) {
  const passSpan = icon.closest("td").querySelector(".password-text");
  if (passSpan.textContent.includes("•")) {
    passSpan.textContent = passSpan.dataset.password;
    icon.classList.replace("bi-eye-slash", "bi-eye");
  } else {
    passSpan.textContent = "••••••••";
    icon.classList.replace("bi-eye", "bi-eye-slash");
  }
}

// --- LOGIN, ROUTING & PAGE MANAGEMENT ---
async function showPage(pageId) {
  // Tampilkan/sembunyikan footer rekap untuk halaman lapak
  const rekapFooter = document.getElementById("rekap-footer");
  if (rekapFooter) {
    rekapFooter.style.display =
      pageId === "lapak-dashboard" && AppState.currentUser?.role === "lapak"
        ? "block"
        : "none";
  }
  const { role } = AppState.currentUser || {};
  if (role === "owner") {
    if (pageId === "owner-dashboard") await populateOwnerDashboard();
    if (pageId.startsWith("owner-laporan")) {
      const dpPendapatan = document.getElementById(
        "laporan-pendapatan-datepicker"
      );
      if (dpPendapatan) dpPendapatan.dispatchEvent(new Event("change"));
      const dpBiaya = document.getElementById("laporan-biaya-datepicker");
      if (dpBiaya) dpBiaya.dispatchEvent(new Event("change"));
    }
    if (pageId === "owner-manage-reports-page")
      await populateManageReportsPage();
    if (pageId === "owner-pembayaran-page") await populatePembayaranPage();
    if (pageId === "owner-supplier-history-page")
      await populateOwnerSupplierHistoryPage(); // <-- Tambahan
    if (pageId === "owner-chart-page") await populateChartPage();
  } else if (role === "lapak") {
    if (pageId === "lapak-dashboard") await populateLapakDashboard();
    if (pageId === "history-laporan-page") await populateHistoryLaporanPage();
  } else if (role === "supplier") {
    if (pageId === "supplier-dashboard") await populateSupplierDashboard();
    if (pageId === "supplier-history-page") await populateSupplierHistoryPage();
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById("username").value.trim(),
    password = document.getElementById("password").value;
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const result = await response.json();
    if (response.ok && result.success) {
      localStorage.setItem("userSession", JSON.stringify(result));
      AppState.currentUser = result;
      window.location.href = "/dashboard";
    } else {
      showToast(result.message || "Login Gagal", false);
    }
  } catch (e) {
    showToast("Terjadi kesalahan koneksi.", false);
  }
}
async function handleAuthRouting() {
    // 1. Tanya server siapa yang sedang login
    try {
        const response = await fetch('/api/get_session_info');
        const result = await response.json();

        if (result.is_logged_in) {
            // 2. Jika ada yang login, simpan datanya di AppState
            AppState.currentUser = {
                role: result.role,
                user_info: result.user_info
            };
            // 3. Jalankan fungsi untuk memuat data di halaman yang relevan
            await routeUser(result.role);
        } else {
            // Jika tidak ada sesi di server, dan kita tidak di halaman login,
            // paksa kembali ke halaman login.
            if (window.location.pathname !== "/") {
                window.location.href = "/";
            }
        }
    } catch (error) {
        console.error("Gagal memeriksa sesi:", error);
        showToast("Gagal terhubung ke server untuk verifikasi sesi.", false);
    }
}
function showLoginPage() {
  document
    .querySelectorAll("main")
    .forEach((main) => (main.style.display = "none"));
  showPage("login-page");
}
async function routeUser(role) {
  // Langsung panggil showPage untuk memuat data, tanpa menyembunyikan apapun
  if (role === "owner") {
    showPage("owner-dashboard");
    const ownerNameEl = document.getElementById("owner-name");
    if(ownerNameEl) ownerNameEl.textContent = AppState.currentUser.user_info.nama_lengkap;
  } else if (role === "lapak") {
    showPage("lapak-dashboard");
    const lapakNameEl = document.getElementById("lapak-name");
    if(lapakNameEl) lapakNameEl.textContent = AppState.currentUser.user_info.nama_lengkap;
  } else if (role === "supplier") {
    showPage("supplier-dashboard");
    const supplierNameEl = document.getElementById("supplier-name");
    if(supplierNameEl) supplierNameEl.textContent = AppState.currentUser.user_info.nama_supplier;
  }
}
function handleLogout() {
    // Hapus sisa data lama dari browser
    localStorage.removeItem("userSession"); 
    // Arahkan ke endpoint logout di server
    window.location.href = "/logout";
}

// --- OWNER FUNCTIONS ---
async function populateChartPage() {
  // Fungsi ini hanya berjalan sekali saat halaman dibuka untuk mengisi filter
  const monthSelect = document.getElementById("chart-month-select");
  const yearSelect = document.getElementById("chart-year-select");
  const currentMonth = new Date().getMonth() + 1;
  const currentYear = new Date().getFullYear();

  // Set bulan & tahun saat ini sebagai default
  monthSelect.value = currentMonth;

  // Isi pilihan tahun dari 2023 hingga tahun ini
  yearSelect.innerHTML = "";
  for (let y = currentYear; y >= 2023; y--) {
    yearSelect.innerHTML += `<option value="${y}">${y}</option>`;
  }
  yearSelect.value = currentYear;

  // Langsung panggil fungsi untuk menggambar grafik dengan filter default
  await fetchAndDrawCharts();
}

async function fetchAndDrawCharts() {
  const loadingEl = document.getElementById("chart-loading");
  const contentEl = document.getElementById("chart-content");
  loadingEl.style.display = "block";
  contentEl.style.display = "none";

  const month = document.getElementById("chart-month-select").value;
  const year = document.getElementById("chart-year-select").value;

  try {
    const resp = await fetch(`/api/get_chart_data?month=${month}&year=${year}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    const chartOptions = {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: function (value) {
              return formatCurrency(value);
            },
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function (context) {
              return context.dataset.label + ": " + formatCurrency(context.raw);
            },
          },
        },
      },
    };

    // Hancurkan grafik lama sebelum menggambar yang baru
    if (pendapatanChartInstance) pendapatanChartInstance.destroy();
    if (biayaChartInstance) biayaChartInstance.destroy();

    // Gambar Grafik Pendapatan
    const ctxPendapatan = document
      .getElementById("pendapatanChart")
      .getContext("2d");
    pendapatanChartInstance = new Chart(ctxPendapatan, {
      type: "line",
      data: {
        labels: result.labels,
        datasets: [
          {
            label: "Pendapatan",
            data: result.pendapatanData,
            borderColor: "rgba(25, 135, 84, 1)",
            backgroundColor: "rgba(25, 135, 84, 0.2)",
            fill: true,
            tension: 0.1,
          },
        ],
      },
      options: chartOptions,
    });

    // Gambar Grafik Biaya
    const ctxBiaya = document.getElementById("biayaChart").getContext("2d");
    biayaChartInstance = new Chart(ctxBiaya, {
      type: "line",
      data: {
        labels: result.labels,
        datasets: [
          {
            label: "Biaya Supplier",
            data: result.biayaData,
            borderColor: "rgba(220, 53, 69, 1)",
            backgroundColor: "rgba(220, 53, 69, 0.2)",
            fill: true,
            tension: 0.1,
          },
        ],
      },
      options: chartOptions,
    });

    contentEl.style.display = "block";
  } catch (e) {
    showToast("Gagal memuat data grafik: " + e.message, false);
  } finally {
    loadingEl.style.display = "none";
  }
}

async function populateOwnerSupplierHistoryPage() {
  // Fungsi ini mengisi dropdown supplier saat halaman pertama kali dibuka
  const selectEl = document.getElementById("owner-supplier-select");
  // PERBAIKAN: Pastikan placeholder memiliki value=""
  selectEl.innerHTML =
    '<option selected value="">-- Pilih Supplier --</option>';

  // Kita gunakan data supplier dari AppState yang sudah ada
  if (AppState.ownerData && AppState.ownerData.supplier_data) {
    AppState.ownerData.supplier_data.forEach((s) => {
      selectEl.innerHTML += `<option value="${s.id}">${s.nama_supplier}</option>`;
    });
  }
  // Sembunyikan konten & loading di awal
  document.getElementById("owner-supplier-history-content").style.display =
    "none";
  document.getElementById("owner-supplier-history-loading").style.display =
    "none";
}

async function fetchAndDisplayOwnerSupplierHistory() {
  const supplierId = document.getElementById("owner-supplier-select").value;
  // Jika belum ada supplier yang dipilih, sembunyikan konten dan jangan lakukan apa-apa
  if (!supplierId) {
    document.getElementById("owner-supplier-history-content").style.display =
      "none";
    return;
  }

  const loadingEl = document.getElementById("owner-supplier-history-loading"),
    contentEl = document.getElementById("owner-supplier-history-content"),
    salesBody = document.getElementById("owner-supplier-sales-body"),
    paymentsBody = document.getElementById("owner-supplier-payment-body");

  loadingEl.style.display = "block";
  contentEl.style.display = "none";

  // Mengambil nilai tanggal dari input
  const startDate = document.getElementById("owner-history-start-date").value;
  const endDate = document.getElementById("owner-history-end-date").value;

  // Membangun query string
  const params = new URLSearchParams();
  if (startDate) params.append("start_date", startDate);
  if (endDate) params.append("end_date", endDate);
  const queryString = params.toString();

  try {
    const apiUrl = `/api/get_owner_supplier_history/${supplierId}?${queryString}`;
    const resp = await fetch(apiUrl);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    paymentsBody.innerHTML =
      result.payments.length === 0
        ? `<tr><td colspan="3" class="text-center text-muted">Tidak ada pembayaran.</td></tr>`
        : result.payments
            .map(
              (p) =>
                `<tr><td>${new Date(p.tanggal + "T00:00:00").toLocaleDateString(
                  "id-ID"
                )}</td><td>${formatCurrency(
                  p.jumlah
                )}</td><td><span class="badge bg-info">${
                  p.metode
                }</span></td></tr>`
            )
            .join("");

    salesBody.innerHTML =
      result.sales.length === 0
        ? `<tr><td colspan="5" class="text-center text-muted">Tidak ada penjualan.</td></tr>`
        : result.sales
            .map(
              (s) =>
                `<tr><td>${new Date(s.tanggal + "T00:00:00").toLocaleDateString(
                  "id-ID"
                )}</td><td>${s.lokasi}</td><td>${s.nama_produk}</td><td>${
                  s.terjual
                } Pcs</td><td class="text-end">${formatCurrency(
                  s.total_harga_beli
                )}</td></tr>`
            )
            .join("");

    loadingEl.style.display = "none";
    contentEl.style.display = "block";
  } catch (e) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

async function populateOwnerDashboard() {
  try {
    const dataResp = await fetch("/api/get_data_owner");
    if (!dataResp.ok) throw new Error("Gagal mengambil data owner");
    AppState.ownerData = await dataResp.json();
    document.getElementById("owner-pendapatan-card").textContent =
      formatCurrency(AppState.ownerData.summary.pendapatan_bulan_ini);
    document.getElementById("owner-biaya-card").textContent = formatCurrency(
      AppState.ownerData.summary.biaya_bulan_ini
    );
    await populateOwnerDataPages();
  } catch (error) {
    showToast("Gagal memuat data owner.", false);
  }
}
async function populateOwnerDataPages() {
  const { admin_data, lapak_data, supplier_data } = AppState.ownerData;
  document.getElementById("admin-table-body").innerHTML = admin_data
    .map(
      (u) =>
        `<tr><td>${u.nama_lengkap}</td><td>${u.nik}</td><td>${u.username}</td><td>${u.email}</td><td>${u.nomor_kontak}</td><td class="password-cell"><span class="password-text me-2" data-password="${u.password}">••••••••</span><i class="bi bi-eye-slash" style="cursor: pointer;" onclick="toggleTablePasswordVisibility(this)"></i></td><td><div class="btn-group"><button class="btn btn-sm btn-warning btn-action" onclick='openEditModal("admin", ${u.id})'><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-danger btn-action" onclick='handleDelete("admin", ${u.id})'><i class="bi bi-trash-fill"></i></button></div></td></tr>`
    )
    .join("");
  document.getElementById("lapak-table-body").innerHTML = lapak_data
    .map(
      (l) =>
        `<tr><td>${l.lokasi}</td><td>${l.penanggung_jawab}</td><td>${
          l.anggota
            .map(
              (a) => `<span class="badge bg-secondary me-1">${a.nama}</span>`
            )
            .join("") || "-"
        }</td><td><div class="btn-group"><button class="btn btn-sm btn-warning btn-action" onclick='openEditModal("lapak", ${
          l.id
        })'><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-danger btn-action" onclick='handleDelete("lapak", ${
          l.id
        })'><i class="bi bi-trash-fill"></i></button></div></td></tr>`
    )
    .join("");
  document.getElementById("supplier-table-body").innerHTML = supplier_data
    .map(
      (s) =>
        `<tr><td>${s.nama_supplier}</td><td>${s.username || "-"}</td><td>${
          s.kontak
        }</td><td>${
          s.nomor_register || "-"
        }</td><td class="password-cell"><span class="password-text me-2" data-password="${
          s.password
        }">••••••••</span><i class="bi bi-eye-slash" style="cursor: pointer;" onclick="toggleTablePasswordVisibility(this)"></i></td><td><div class="btn-group"><button class="btn btn-sm btn-warning btn-action" onclick='openEditModal("supplier", ${
          s.id
        })'><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-danger btn-action" onclick='handleDelete("supplier", ${
          s.id
        })'><i class="bi bi-trash-fill"></i></button></div></td></tr>`
    )
    .join("");
}
async function showReportDetails(reportId) {
  const container = document.getElementById("invoice-content");
  container.innerHTML = `<div class="text-center p-5"><div class="spinner-border"></div></div>`;
  modals.reportDetail.show();
  try {
    const resp = await fetch(`/api/get_report_details/${reportId}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    const data = result.data;

    let rincianHtml = "";
    const suppliers = Object.keys(data.rincian_per_supplier);

    if (suppliers.length === 0) {
      rincianHtml =
        '<p class="text-center text-muted">Tidak ada rincian produk untuk laporan ini.</p>';
    } else {
      suppliers.forEach((supplierName) => {
        const products = data.rincian_per_supplier[supplierName];
        let supplierSubtotal = 0;

        // Membuat tabel untuk setiap supplier
        rincianHtml += `
                      <h5 class="mt-4">${supplierName}</h5>
                      <table class="table table-sm table-bordered">
                          <thead class="table-light">
                              <tr class="heading">
                                  <td>No.</td>
                                  <td>Produk</td>
                                  <td class="text-center">Stok Awal</td>
                                  <td class="text-center">Stok Akhir</td>
                                  <td class="text-center">Terjual</td>
                                  <td class="text-end">Subtotal</td>
                              </tr>
                          </thead>
                          <tbody>
                  `;

        // Mengisi baris produk untuk supplier ini
        products.forEach((p, index) => {
          supplierSubtotal += p.total_pendapatan;
          rincianHtml += `
                          <tr class="item">
                              <td>${index + 1}</td>
                              <td>${p.nama_produk}</td>
                              <td class="text-center">${p.stok_awal}</td>
                              <td class="text-center">${p.stok_akhir}</td>
                              <td class="text-center">${p.terjual}</td>
                              <td class="text-end">${formatCurrency(
                                p.total_pendapatan
                              )}</td>
                          </tr>
                      `;
        });

        // Menambahkan baris subtotal untuk supplier ini
        rincianHtml += `
                          <tr class="total">
                              <td colspan="5" class="text-end fw-bold">Subtotal ${supplierName}</td>
                              <td class="text-end fw-bold">${formatCurrency(
                                supplierSubtotal
                              )}</td>
                          </tr>
                          </tbody>
                      </table>
                  `;
      });
    }
    const compareHtml = `
              <tr><td>Terjual (Cash)</td><td class="text-end">${formatCurrency(
                data.rekap_otomatis.terjual_cash
              )}</td><td class="text-end">${formatCurrency(
      data.rekap_manual.terjual_cash
    )}</td></tr>
              <tr><td>Terjual (QRIS)</td><td class="text-end">${formatCurrency(
                data.rekap_otomatis.terjual_qris
              )}</td><td class="text-end">${formatCurrency(
      data.rekap_manual.terjual_qris
    )}</td></tr>
              <tr><td>Terjual (BCA)</td><td class="text-end">${formatCurrency(
                data.rekap_otomatis.terjual_bca
              )}</td><td class="text-end">${formatCurrency(
      data.rekap_manual.terjual_bca
    )}</td></tr>
              <tr class="fw-bold"><td>Total Produk Terjual</td><td class="text-end">${
                data.rekap_otomatis.total_produk_terjual
              } Pcs</td><td class="text-end">${
      data.rekap_manual.total_produk_terjual
    } Pcs</td></tr>
              <tr class="fw-bold table-group-divider"><td>Total Pendapatan</td><td class="text-end">${formatCurrency(
                data.rekap_otomatis.total_pendapatan
              )}</td><td class="text-end">${formatCurrency(
      data.rekap_manual.total_pendapatan
    )}</td></tr>
            `;

    container.innerHTML = `
              <table>
                <tr class="top"><td colspan="2"><table><tr><td class="title"><h4>Laporan Penjualan</h4></td><td style="text-align: right;">ID Laporan: #${
                  data.id
                }<br>Tanggal: ${data.tanggal}<br>Status: ${
      data.status
    }</td></tr></table></td></tr>
                <tr class="information"><td colspan="2"><table><tr><td>Lapak: <strong>${
                  data.lokasi
                }</strong><br>Penanggung Jawab:<br>${
      data.penanggung_jawab
    }</td></tr></table></td></tr>
              </table>
              
              ${rincianHtml}
              
              <table class="mt-4">
                 <tr class="total"><td class="text-end fw-bold">Total Pendapatan (Sistem)</td><td class="text-end fw-bold" style="width:25%">${formatCurrency(
                   data.rekap_otomatis.total_pendapatan
                 )}</td></tr>
                 <tr class="total"><td class="text-end fw-bold">Total Biaya Supplier</td><td class="text-end fw-bold" style="width:25%">${formatCurrency(
                   data.rekap_otomatis.total_biaya_supplier
                 )}</td></tr>
              </table>
              <h5 class="mt-5 mb-3">Perbandingan Rekapitulasi</h5>
              <table class="table table-bordered"><thead class="table-light"><tr><th>Deskripsi</th><th class="text-end">Otomatis (Sistem)</th><th class="text-end">Manual (Karyawan)</th></tr></thead><tbody>${compareHtml}</tbody></table>
            `;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}
async function downloadReportAsPDF() {
  const invoiceElement = document.getElementById("invoice-content");
  const reportId = invoiceElement
    .querySelector('td[style="text-align: right;"]')
    .innerText.split("\n")[0]
    .split("#")[1];
  const modalBody = document.querySelector("#report-detail-modal .modal-body");
  const originalOverflow = modalBody.style.overflow;
  modalBody.style.overflow = "visible";

  await html2canvas(invoiceElement, { scale: 2 }).then((canvas) => {
    const imgData = canvas.toDataURL("image/png");
    const pdf = new jsPDF({ orientation: "p", unit: "mm", format: "a4" });
    const imgProps = pdf.getImageProperties(imgData);
    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
    pdf.addImage(imgData, "PNG", 0, 0, pdfWidth, pdfHeight);
    pdf.save(`laporan-harian-${reportId}.pdf`);
  });

  modalBody.style.overflow = originalOverflow;
  showToast("PDF berhasil diunduh.");
}
async function populateLaporanPendapatan() {
  const date = document.getElementById("laporan-pendapatan-datepicker").value;
  const accordionEl = document.getElementById("laporan-pendapatan-accordion");
  accordionEl.innerHTML = `<div class="text-center p-5"><div class="spinner-border text-primary"></div></div>`;
  try {
    const resp = await fetch(`/api/get_laporan_pendapatan_harian?date=${date}`);
    if (!resp.ok) throw new Error("Gagal mengambil data");
    const data = await resp.json();
    document.getElementById("total-pendapatan-harian").textContent =
      formatCurrency(data.total_harian);
    accordionEl.innerHTML = "";
    if (data.laporan_per_lapak.length === 0) {
      accordionEl.innerHTML =
        '<div class="alert alert-warning text-center">Tidak ada laporan untuk tanggal ini.</div>';
    } else {
      data.laporan_per_lapak.forEach((lapak, index) => {
        const productList = lapak.rincian_pendapatan
          .map(
            (p) =>
              `<li class="list-group-item d-flex justify-content-between"><div>${p.produk} <small class="text-muted">(${p.supplier})</small></div><div><span class="badge text-bg-light me-2">Awal: ${p.stok_awal}</span><span class="badge text-bg-light me-2">Akhir: ${p.stok_akhir}</span><span class="badge bg-primary rounded-pill">${p.jumlah} Pcs</span></div></li>`
          )
          .join("");
        accordionEl.innerHTML += `<div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button ${
          index !== 0 ? "collapsed" : ""
        }" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-lp-${index}"><strong>${
          lapak.lokasi
        }</strong> <span class="ms-auto me-3">${formatCurrency(
          lapak.total_pendapatan
        )}</span></button></h2><div id="collapse-lp-${index}" class="accordion-collapse collapse ${
          index === 0 ? "show" : ""
        }"><div class="accordion-body"><p>PJ: <strong>${
          lapak.penanggung_jawab
        }</strong></p><ul class="list-group list-group-flush">${productList}</ul></div></div></div>`;
      });
    }
  } catch (error) {
    accordionEl.innerHTML =
      '<div class="alert alert-danger text-center">Gagal memuat.</div>';
  }
}
async function populateLaporanBiaya() {
  const date = document.getElementById("laporan-biaya-datepicker").value;
  const accordionEl = document.getElementById("laporan-biaya-accordion");
  accordionEl.innerHTML = `<div class="text-center p-5"><div class="spinner-border text-warning"></div></div>`;
  try {
    const resp = await fetch(`/api/get_laporan_biaya_harian?date=${date}`);
    if (!resp.ok) throw new Error("Gagal mengambil data");
    const data = await resp.json();
    document.getElementById("total-biaya-harian").textContent = formatCurrency(
      data.total_harian
    );
    accordionEl.innerHTML = "";
    if (data.laporan_per_lapak.length === 0) {
      accordionEl.innerHTML =
        '<div class="alert alert-warning text-center">Tidak ada laporan untuk tanggal ini.</div>';
    } else {
      data.laporan_per_lapak.forEach((lapak, index) => {
        const productList = lapak.rincian_biaya
          .map(
            (p) =>
              `<li class="list-group-item d-flex justify-content-between"><div>${
                p.produk
              } <small class="text-muted">(${
                p.supplier
              })</small></div><div><span class="badge bg-primary rounded-pill me-2">${
                p.jumlah
              } Pcs</span><span class="fw-bold">${formatCurrency(
                p.biaya
              )}</span></div></li>`
          )
          .join("");
        accordionEl.innerHTML += `<div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button ${
          index !== 0 ? "collapsed" : ""
        }" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-lb-${index}"><strong>${
          lapak.lokasi
        }</strong> <span class="ms-auto me-3">${formatCurrency(
          lapak.total_biaya
        )}</span></button></h2><div id="collapse-lb-${index}" class="accordion-collapse collapse ${
          index === 0 ? "show" : ""
        }"><div class="accordion-body"><p>PJ: <strong>${
          lapak.penanggung_jawab
        }</strong></p><ul class="list-group list-group-flush">${productList}</ul></div></div></div>`;
      });
    }
  } catch (error) {
    accordionEl.innerHTML =
      '<div class="alert alert-danger text-center">Gagal memuat.</div>';
  }
}
async function populateManageReportsPage() {
  const loadingEl = document.getElementById("manage-reports-loading"),
    contentEl = document.getElementById("manage-reports-content");
  const tableBody = document.getElementById("unconfirmed-reports-table-body");
  const supplierSelect = document.getElementById(
    "manage-reports-supplier-filter"
  );

  // --- PERUBAHAN DI SINI: Mengisi dropdown supplier saat pertama kali dijalankan ---
  if (supplierSelect.options.length <= 1) {
    // Cek agar tidak diisi berulang kali
    if (AppState.ownerData && AppState.ownerData.supplier_data) {
      AppState.ownerData.supplier_data.forEach((s) => {
        supplierSelect.innerHTML += `<option value="${s.id}">${s.nama_supplier}</option>`;
      });
    }
  }

  loadingEl.style.display = "block";
  contentEl.style.display = "none";

  // Ambil semua nilai dari filter
  const startDate = document.getElementById("manage-reports-start-date").value;
  const endDate = document.getElementById("manage-reports-end-date").value;
  const supplierId = supplierSelect.value; // <-- Ambil nilai supplier_id

  const params = new URLSearchParams();
  if (startDate) params.append("start_date", startDate);
  if (endDate) params.append("end_date", endDate);
  if (supplierId) params.append("supplier_id", supplierId); // <-- Tambahkan ke parameter API

  try {
    const resp = await fetch(`/api/get_manage_reports?${params.toString()}`);
    const result = await resp.json();
    if (result.success) {
      if (result.reports.length === 0) {
        tableBody.innerHTML =
          '<tr><td colspan="8" class="text-center text-muted">Tidak ada laporan yang cocok dengan filter.</td></tr>';
      } else {
        tableBody.innerHTML = result.reports
          .map((r) => {
            const statusBadge =
              r.status === "Terkonfirmasi"
                ? `<span class="badge bg-success">${r.status}</span>`
                : `<span class="badge bg-warning text-dark">${r.status}</span>`;

            const confirmButton =
              r.status !== "Terkonfirmasi"
                ? `<button class="btn btn-sm btn-success" onclick="confirmReport(${r.id})"><i class="bi bi-check-circle-fill"></i></button>`
                : `<button class="btn btn-sm btn-secondary" disabled><i class="bi bi-check-circle-fill"></i></button>`;

            return `<tr>
                    <td>${r.id}</td><td>${r.lokasi}</td><td>${
              r.penanggung_jawab
            }</td>
                    <td>${new Date(r.tanggal).toLocaleDateString("id-ID")}</td>
                    <td>${formatCurrency(r.total_pendapatan)}</td><td>${
              r.total_produk_terjual
            } Pcs</td>
                    <td>${statusBadge}</td>
                    <td>
                      <div class="btn-group">
                        <button class="btn btn-sm btn-info" onclick="showReportDetails(${
                          r.id
                        })"><i class="bi bi-eye-fill"></i></button>
                        ${confirmButton}
                      </div>
                    </td></tr>`;
          })
          .join("");
      }
      loadingEl.style.display = "none";
      contentEl.style.display = "block";
    } else {
      throw new Error(result.message);
    }
  } catch (error) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${
      error.message || "Gagal memuat data"
    }</div>`;
  }
}
async function confirmReport(reportId) {
  if (
    !confirm(
      "Apakah Anda yakin ingin mengkonfirmasi laporan ini? Tindakan ini akan memperbarui saldo tagihan supplier."
    )
  )
    return;
  try {
    const resp = await fetch(`/api/confirm_report/${reportId}`, {
      method: "POST",
    });
    const result = await resp.json();
    showToast(result.message, result.success);
    if (result.success) {
      await populateManageReportsPage();
      await populateOwnerDashboard();
    }
  } catch (e) {
    showToast("Gagal terhubung ke server.", false);
  }
}
async function openEditModal(type, id = null) {
  const isEdit = id !== null;
  let data = {};
  if (isEdit) {
    const dataArray = AppState.ownerData[`${type}_data`];
    data = dataArray.find((item) => item.id === id);
    if (!data) return showToast("Data tidak ditemukan.", false);
  }
  if (type === "admin") {
    const form = document.getElementById("edit-admin-form");
    form.reset();
    document.getElementById("admin-modal-title").textContent = isEdit
      ? "Edit Admin"
      : "Tambah Admin Baru";
    document.getElementById("edit-admin-id").value = id || "";
    if (isEdit) {
      document.getElementById("edit-admin-nama").value = data.nama_lengkap;
      document.getElementById("edit-admin-nik").value = data.nik;
      document.getElementById("edit-admin-username").value = data.username;
      document.getElementById("edit-admin-email").value = data.email;
      document.getElementById("edit-admin-kontak").value = data.nomor_kontak;
    }
    modals.admin.show();
  } else if (type === "lapak") {
    const form = document.getElementById("edit-lapak-form");
    form.reset();
    document.getElementById("lapak-modal-title").textContent = isEdit
      ? "Edit Lapak"
      : "Tambah Lapak Baru";
    document.getElementById("edit-lapak-id").value = id || "";

    const pjSelect = document.getElementById("lapak-pj-select");
    const anggotaContainer = document.getElementById("lapak-anggota-selection");
    pjSelect.innerHTML =
      '<option value="" selected disabled>-- Pilih PJ --</option>' +
      AppState.ownerData.admin_data
        .map((a) => `<option value="${a.id}">${a.nama_lengkap}</option>`)
        .join("");
    anggotaContainer.innerHTML = AppState.ownerData.admin_data
      .map(
        (a) =>
          `<div class="form-check"><input class="form-check-input" type="checkbox" value="${a.id}" id="anggota-${a.id}"><label class="form-check-label" for="anggota-${a.id}">${a.nama_lengkap}</label></div>`
      )
      .join("");

    if (isEdit) {
      document.getElementById("edit-lapak-lokasi").value = data.lokasi;
      pjSelect.value = data.user_id;
      data.anggota_ids.forEach((anggotaId) => {
        const checkbox = document.getElementById(`anggota-${anggotaId}`);
        if (checkbox) checkbox.checked = true;
      });
    }
    modals.lapak.show();
  } else if (type === "supplier") {
    const form = document.getElementById("edit-supplier-form");
    form.reset();
    document.getElementById("supplier-modal-title").textContent = isEdit
      ? "Edit Supplier"
      : "Tambah Supplier Baru";
    document.getElementById("edit-supplier-id").value = id || "";

    // BARIS PENTING: Tidak ada lagi yang disembunyikan. Semua field selalu terlihat.

    // Isi data dasar supplier
    if (isEdit) {
      document.getElementById("edit-supplier-nama").value = data.nama_supplier;
      document.getElementById("edit-supplier-username").value = data.username;
      document.getElementById("edit-supplier-kontak").value = data.kontak;
      document.getElementById("edit-supplier-register").value =
        data.nomor_register;
      document.getElementById("edit-supplier-alamat").value = data.alamat;
      document.getElementById("edit-supplier-metode").value =
        data.metode_pembayaran;
      document.getElementById("edit-supplier-rekening").value =
        data.nomor_rekening;
    } else {
      // Dapatkan nomor register baru untuk supplier baru
      const resp = await fetch("/api/get_next_supplier_reg_number");
      const result = await resp.json();
      document.getElementById("edit-supplier-register").value =
        result.reg_number;
    }

    modals.supplier.show();
  }
}
async function handleFormSubmit(type, e) {
  e.preventDefault();
  const form = e.target;
  const id = form.querySelector(`input[type=hidden]`).value;
  const isEdit = id !== "";
  let url = isEdit ? `/api/update_${type}/${id}` : `/api/add_${type}`;
  let method = isEdit ? "PUT" : "POST";
  let payload = {};
  if (type === "admin") {
    const password = form.elements["edit-admin-password"].value;
    if (
      password &&
      password !== form.elements["edit-admin-password-confirm"].value
    )
      return showToast("Password dan konfirmasi tidak cocok.", false);
    payload = {
      nama_lengkap: form.elements["edit-admin-nama"].value,
      nik: form.elements["edit-admin-nik"].value,
      username: form.elements["edit-admin-username"].value,
      email: form.elements["edit-admin-email"].value,
      nomor_kontak: form.elements["edit-admin-kontak"].value,
      password: password,
      password_confirm: form.elements["edit-admin-password-confirm"].value,
    };
  } else if (type === "lapak") {
    const anggota_ids = Array.from(
      form.querySelectorAll("#lapak-anggota-selection input:checked")
    ).map((cb) => cb.value);
    payload = {
      lokasi: form.elements["edit-lapak-lokasi"].value,
      user_id: form.elements["lapak-pj-select"].value,
      anggota_ids,
    };
  } else if (type === "supplier") {
    const password = form.elements["edit-supplier-password"].value;
    if (
      password &&
      password !== form.elements["edit-supplier-password-confirm"].value
    )
      return showToast("Password dan konfirmasi tidak cocok.", false);

    payload = {
      nama_supplier: form.elements["edit-supplier-nama"].value,
      username: form.elements["edit-supplier-username"].value,
      kontak: form.elements["edit-supplier-kontak"].value,
      nomor_register: form.elements["edit-supplier-register"].value,
      alamat: form.elements["edit-supplier-alamat"].value,
      password,
      password_confirm: form.elements["edit-supplier-password-confirm"].value,
      metode_pembayaran: form.elements["edit-supplier-metode"].value,
      nomor_rekening: form.elements["edit-supplier-rekening"].value,
    };
  }
  const resp = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await resp.json();
  showToast(result.message, resp.ok);
  if (resp.ok) {
    modals[type].hide();
    await populateOwnerDashboard();
  }
}
async function handleDelete(type, id) {
  if (
    !confirm(
      `Apakah Anda yakin ingin menghapus data ini? Tindakan ini tidak dapat dibatalkan.`
    )
  )
    return;
  const resp = await fetch(`/api/delete_${type}/${id}`, {
    method: "DELETE",
  });
  const result = await resp.json();
  showToast(result.message, resp.ok);
  if (resp.ok) await populateOwnerDashboard();
}

async function populatePembayaranPage() {
  const loadingEl = document.getElementById("pembayaran-content-loading"),
    mainEl = document.getElementById("pembayaran-content-main");
  const tableBody = document.getElementById("pembayaran-table-body");

  loadingEl.style.display = "block";
  mainEl.style.display = "none";

  try {
    const resp = await fetch(`/api/get_pembayaran_data`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    tableBody.innerHTML = "";
    if (result.supplier_balances.length === 0)
      tableBody.innerHTML =
        '<tr><td colspan="4" class="text-center text-muted">Belum ada data supplier.</td></tr>';
    else
      result.supplier_balances.forEach((item) => {
        // Tentukan apakah tagihan bisa dibayar berdasarkan metode pembayaran
        let isPayable;
        if (item.metode_pembayaran === "BCA") {
          // Untuk BCA, bisa dibayar selama ada tagihan (lebih dari nol)
          isPayable = item.total_tagihan > 0.01;
        } else {
          // Untuk DANA (dan metode lainnya), berlaku minimum 20.000
          isPayable = item.total_tagihan >= 20000;
        }
        const isPaid = item.total_tagihan < 0.01;
        let statusBadge, actionBtn, statusText;

        if (isPaid) {
          statusBadge = `<span class="badge bg-light text-dark">Lunas</span>`;
          actionBtn = `<button class="btn btn-sm btn-secondary" disabled>Lunas</button>`;
        } else if (isPayable) {
          statusBadge = `<span class="badge bg-success">Siap Bayar</span>`;
          actionBtn = `<button class="btn btn-sm btn-primary" onclick='openPaymentModal(${item.supplier_id}, "${item.nama_supplier}", ${item.total_tagihan})'>Bayar Tagihan</button>`;
        } else {
          // Kondisi ini sekarang sebagian besar hanya untuk DANA
          statusBadge = `<span class="badge bg-warning text-dark">Akumulasi</span>`;
          actionBtn = `<button class="btn btn-sm btn-secondary" disabled>Dibawah Minimum</button>`;
        }

        tableBody.innerHTML += `<tr>
                <td>
                  ${item.nama_supplier}
                  <small class="d-block text-muted">${
                    item.metode_pembayaran
                  } - ${item.nomor_rekening}</small>
                </td>
                <td class="fw-bold">${formatCurrency(item.total_tagihan)}</td>
                <td>${statusBadge}</td>
                <td>${actionBtn}</td></tr>`;
      });

    loadingEl.style.display = "none";
    mainEl.style.display = "block";

    // Langsung panggil fungsi untuk memuat riwayat pembayaran
    await populatePaymentHistory();
  } catch (e) {
    showToast(e.message, false);
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

// Fungsi baru untuk memuat riwayat pembayaran
async function populatePaymentHistory() {
  const loadingEl = document.getElementById("payment-history-loading");
  const tableBody = document.getElementById("payment-history-table-body");
  loadingEl.style.display = "block";
  tableBody.innerHTML = "";

  const startDate = document.getElementById("payment-history-start-date").value;
  const endDate = document.getElementById("payment-history-end-date").value;
  const metode = document.getElementById("payment-history-method").value;

  const params = new URLSearchParams();
  if (startDate) params.append("start_date", startDate);
  if (endDate) params.append("end_date", endDate);
  if (metode) params.append("metode", metode);

  try {
    const resp = await fetch(
      `/api/get_all_payment_history?${params.toString()}`
    );
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    if (result.history.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Tidak ada riwayat pembayaran.</td></tr>`;
    } else {
      tableBody.innerHTML = result.history
        .map(
          (p) => `
                    <tr>
                      <td>${new Date(
                        p.tanggal + "T00:00:00"
                      ).toLocaleDateString("id-ID")}</td>
                      <td>${p.nama_supplier}</td>
                      <td>${formatCurrency(p.jumlah)}</td>
                      <td><span class="badge bg-info">${p.metode}</span></td>
                    </tr>
                  `
        )
        .join("");
    }
  } catch (e) {
    tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">Gagal memuat: ${e.message}</td></tr>`;
  } finally {
    loadingEl.style.display = "none";
  }
}
function openPaymentModal(supplierId, supplierName, amount) {
  const supplierData = AppState.ownerData.supplier_data.find(
    (s) => s.id === supplierId
  );
  if (!supplierData || !supplierData.metode_pembayaran) {
    return showToast("Info pembayaran supplier belum diatur.", false);
  }
  document.getElementById("payment-supplier-id").value = supplierId;
  document.getElementById("payment-supplier-amount").value = amount;
  document.getElementById("payment-supplier-name-confirm").textContent =
    supplierName;
  document.getElementById("payment-amount-confirm").textContent =
    formatCurrency(amount);
  document.getElementById(
    "payment-method-info"
  ).textContent = `${supplierData.metode_pembayaran}: ${supplierData.nomor_rekening}`;
  modals.payment.show();
}
async function handlePaymentSubmit(e) {
  e.preventDefault();
  const payload = {
    supplier_id: document.getElementById("payment-supplier-id").value,
    jumlah_pembayaran: document.getElementById("payment-supplier-amount").value,
  };
  const resp = await fetch("/api/submit_pembayaran", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await resp.json();
  showToast(result.message, resp.ok);
  if (resp.ok) {
    modals.payment.hide();
    await populatePembayaranPage();
    await populateOwnerDashboard();
  }
}

// --- Variabel untuk debounce pencarian supplier ---
let searchTimeout;

function setupLapakInputListeners() {
  const supplierInput = document.getElementById("supplier-name-input");
  const suggestionsContainer = document.getElementById("supplier-suggestions");
  const addProductForm = document.getElementById("add-product-form");

  // 1. Event listener untuk input supplier (dengan debounce)
  supplierInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    const query = supplierInput.value;
    if (query.length < 2) {
      suggestionsContainer.innerHTML = "";
      return;
    }
    searchTimeout = setTimeout(async () => {
      const response = await fetch(`/api/search_suppliers?q=${query}`);
      const suppliers = await response.json();
      let suggestionsHTML = "";
      suppliers.forEach((s) => {
        suggestionsHTML += `<a href="#" class="list-group-item list-group-item-action" data-supplier-name="${s.nama_supplier}">${s.nama_supplier}</a>`;
      });
      suggestionsContainer.innerHTML = suggestionsHTML;
    }, 300); // Tunggu 300ms setelah user berhenti mengetik
  });

  // 2. Event listener untuk memilih saran supplier
  suggestionsContainer.addEventListener("click", (e) => {
    e.preventDefault();
    if (e.target.classList.contains("list-group-item")) {
      supplierInput.value = e.target.dataset.supplierName;
      suggestionsContainer.innerHTML = "";
      document.getElementById("product-name-input").focus();
    }
  });

  // 3. Event listener untuk submit form tambah produk
  addProductForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const supplierName = supplierInput.value.trim();
    const productName = document
      .getElementById("product-name-input")
      .value.trim();

    if (supplierName && productName) {
      addProductToReportTable(supplierName, productName);
      addProductForm.reset();
      supplierInput.focus();
    }
  });

  // Sembunyikan suggestions jika klik di luar
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#supplier-name-input")) {
      suggestionsContainer.innerHTML = "";
    }
  });
}

function addProductToReportTable(supplierName, productName) {
  const tableBody = document.getElementById("report-table-body");
  const noDataRow = document.getElementById("no-data-row");

  // Hilangkan pesan "Belum ada data" jika ada
  if (noDataRow) noDataRow.remove();

  const rowCount = tableBody.rows.length + 1;

  // Cek apakah produk dari supplier yang sama sudah ada
  const existingRow = Array.from(tableBody.rows).find(
    (row) =>
      row.dataset.supplierName.toLowerCase() === supplierName.toLowerCase() &&
      row.dataset.productName.toLowerCase() === productName.toLowerCase()
  );

  if (existingRow) {
    showToast("Produk tersebut sudah ada di dalam laporan.", false);
    existingRow.querySelector(".stok-awal").focus();
    return;
  }

  const row = tableBody.insertRow();
  row.className = "product-row";
  row.dataset.supplierName = supplierName;
  row.dataset.productName = productName;
  // Harga jual dan beli diambil dari backend saat submit,
  // tapi kita gunakan default untuk tampilan di frontend
  row.dataset.hargaJual = 10000;
  row.dataset.hargaBeli = 8000;

  const stokInput = (className) => `
        <div class="input-group input-group-sm">
            <input type="number" class="form-control text-center ${className}" placeholder="0" min="0" inputmode="numeric">
        </div>`;

  row.innerHTML = `
        <td class="text-center">${rowCount}</td>
        <td>
            <strong>${productName}</strong><br>
            <small class="text-muted">${supplierName}</small>
        </td>
        <td>${stokInput("stok-awal")}</td>
        <td>${stokInput("stok-akhir")}</td>
        <td class="text-center fw-bold terjual-pcs">0</td>
        <td class="text-end fw-bold pendapatan-rp">${formatCurrency(0)}</td>
        <td class="text-center">
            <button class="btn btn-sm btn-outline-danger btn-action" onclick="removeProductRow(this)">
                <i class="bi bi-trash-fill"></i>
            </button>
        </td>
    `;

  attachEventListenersToRow(row);
  updateGrandTotals();
}

function removeProductRow(button) {
  const row = button.closest("tr");
  row.remove();
  // Update nomor urut
  const tableBody = document.getElementById("report-table-body");
  Array.from(tableBody.rows).forEach((r, index) => {
    r.cells[0].textContent = index + 1;
  });
  // Tampilkan pesan jika tabel kosong
  if (tableBody.rows.length === 0) {
    tableBody.innerHTML = `<tr id="no-data-row"><td colspan="7" class="text-center text-muted p-4">Belum ada produk yang ditambahkan ke laporan hari ini.</td></tr>`;
  }
  updateGrandTotals();
}

// --- LAPAK FUNCTIONS ---
// PERUBAHAN 4: Modifikasi fungsi populateLapakDashboard
// Fungsi untuk membuka modal "Atur Produk"

// Fungsi untuk memperbarui daftar produk berdasarkan supplier yang dipilih

// Fungsi untuk membuat tabel laporan berdasarkan produk yang dipilih

// Fungsi untuk filter/pencarian

async function populateLapakDashboard() {
  const loadingEl = document.getElementById("laporan-loading"),
    contentEl = document.getElementById("laporan-content"),
    existsEl = document.getElementById("laporan-exists");

  loadingEl.style.display = "block";
  contentEl.style.display = "none";
  existsEl.style.display = "none";

  // Reset tabel laporan
  const tableBody = document.getElementById("report-table-body");
  if (tableBody) {
    tableBody.innerHTML = `<tr id="no-data-row"><td colspan="7" class="text-center text-muted p-4">Belum ada produk yang ditambahkan ke laporan hari ini.</td></tr>`;
  }
  updateGrandTotals(); // Reset total

  try {
    const resp = await fetch(
      `/api/get_data_buat_catatan/${AppState.currentUser.user_info.lapak_id}`
    );
    if (!resp.ok && resp.status === 409) {
      existsEl.style.display = "block";
      document.getElementById("rekap-footer").style.display = "none";
    } else {
      contentEl.style.display = "block";
      // Panggil fungsi untuk mengaktifkan listener di form baru
      setupLapakInputListeners();
    }
  } catch (error) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
  } finally {
    loadingEl.style.display = "none";
  }
}

// PERUBAHAN 5: Modifikasi fungsi createProductRow
function createProductRow(
  itemNumber,
  productId,
  productName,
  supplierName,
  supplierReg, // Parameter ini tetap ada agar tidak merusak pemanggilan fungsi, tapi tidak akan digunakan
  hargaJual,
  hargaBeli,
  paymentInfo, // Parameter ini juga tidak akan digunakan
  isManualEntry = false
) {
  // Tampilan Nama Produk & Supplier yang lebih simpel
  const productNameHtml = `<strong>${productName}</strong>`;
  // PERUBAHAN DI SINI: Menambahkan kelas "d-block" agar supplier di atas produk
  const supplierInfoHtml = `<small class="fw-bold d-block">${supplierName}</small>`;

  // Spinner stok atas-bawah untuk mobile
  const stokInput = (className) => `
              <div class="d-inline-flex flex-column">
                  <button class="btn btn-outline-secondary btn-plus py-0" type="button" style="border-radius: 5px 5px 0 0;"><i class="bi bi-caret-up-fill"></i></button>
                  <input type="number" class="form-control form-control-sm text-center input-stok ${className}" placeholder="0" min="0" style="border-radius: 0;">
                  <button class="btn btn-outline-secondary btn-minus py-0" type="button" style="border-radius: 0 0 5px 5px;"><i class="bi bi-caret-down-fill"></i></button>
              </div>`;

  return `
              <tr class="product-row" data-product-id="${
                productId || ""
              }" data-harga-jual="${hargaJual}" data-harga-beli="${hargaBeli}">
                  <td class="text-center">${itemNumber}</td>
                  <td class="product-supplier-info">
                    ${supplierInfoHtml}
                    ${productNameHtml}
                  </td>
                  <td>${stokInput("stok-awal")}</td>
                  <td>${stokInput("stok-akhir")}</td>
                  <td class="text-center fw-bold terjual-pcs">0</td>
                  <td class="text-end fw-bold pendapatan-rp">${formatCurrency(
                    0
                  )}</td>
                  <td class="text-end fw-bold biaya-supplier-rp">${formatCurrency(
                    0
                  )}</td>
              </tr>`;
}

// PERUBAHAN 6: Tambahkan fungsi baru untuk menangani form modal
function handleAddManualProductForm(e) {
  e.preventDefault();

  const manualSection = document.getElementById("manual-products-section");
  const manualTableBody = document.getElementById("manual-catatan-table-body");
  const mainTableBody = document.getElementById("catatan-table-body");

  const productName = document.getElementById("manual-product-name").value;
  const supplierId = document.getElementById("manual-product-supplier").value;
  const hargaBeli = document.getElementById("manual-harga-beli").value;
  const hargaJual = document.getElementById("manual-harga-jual").value;

  if (!productName) {
    return showToast("Nama produk manual tidak boleh kosong.", false);
  }

  const selectedSupplier = AppState.lapakSuppliers.find(
    (s) => s.id == supplierId
  );
  const supplierName = selectedSupplier
    ? selectedSupplier.name
    : "Produk Manual";

  // Tampilkan section tabel manual jika ini adalah produk manual pertama
  if (manualSection.style.display === "none") {
    manualSection.style.display = "block";
  }

  const totalRowCount = mainTableBody.rows.length + manualTableBody.rows.length;

  const newRowHtml = createProductRow(
    totalRowCount + 1,
    null, // ID Produk null karena ini manual
    productName,
    supplierName,
    null,
    hargaJual,
    hargaBeli,
    null,
    true
  );

  // Buat elemen <tr> dari string HTML
  const tempDiv = document.createElement("div");
  tempDiv.innerHTML = `<table><tbody>${newRowHtml}</tbody></table>`;
  const newRowElement = tempDiv.querySelector("tr");

  // Simpan supplier_id di dataset jika dipilih
  if (supplierId) {
    newRowElement.dataset.supplierId = supplierId;
  }

  manualTableBody.appendChild(newRowElement);
  attachEventListenersToRow(newRowElement);

  document.getElementById("add-manual-product-form").reset();
  modals.addManualProduct.hide();
  showToast(`Produk "${productName}" berhasil ditambahkan ke tabel.`);
}

function updateRowAndTotals(row) {
  const awal = parseInt(row.querySelector(".stok-awal").value) || 0;
  let akhirInput = row.querySelector(".stok-akhir");
  let akhir = parseInt(akhirInput.value) || 0;
  if (akhir > awal) {
    akhir = awal;
    akhirInput.value = awal;
  }
  const hargaJual = parseFloat(row.dataset.hargaJual);
  const hargaBeli = parseFloat(row.dataset.hargaBeli);
  const terjual = awal - akhir;
  const pendapatan = terjual * hargaJual;
  const biayaSupplier = terjual * hargaBeli;

  row.querySelector(".terjual-pcs").textContent = terjual;
  row.querySelector(".pendapatan-rp").textContent = formatCurrency(pendapatan);
  row.querySelector(".biaya-supplier-rp").textContent =
    formatCurrency(biayaSupplier);
  updateGrandTotals();
}

function updateGrandTotals() {
  let totalAwal = 0,
    totalAkhir = 0,
    totalTerjual = 0,
    totalPendapatan = 0,
    totalBiaya = 0;

  // Ambil dari SEMUA baris produk, baik utama maupun manual
  document.querySelectorAll(".product-row").forEach((row) => {
    totalAwal += parseInt(row.querySelector(".stok-awal").value) || 0;
    totalAkhir += parseInt(row.querySelector(".stok-akhir").value) || 0;
    totalTerjual +=
      parseInt(row.querySelector(".terjual-pcs").textContent) || 0;

    const pendapatanText = row.querySelector(".pendapatan-rp").textContent;
    totalPendapatan += parseFloat(pendapatanText.replace(/\D/g, ""));

    const biayaText = row.querySelector(".biaya-supplier-rp").textContent;
    totalBiaya += parseFloat(biayaText.replace(/\D/g, ""));
  });

  // Update baris total di dalam tfoot
  document.getElementById("total-terjual").textContent = totalTerjual;
  document.getElementById("total-pendapatan").textContent =
    formatCurrency(totalPendapatan);

  // Update footer rekapitulasi (logika yang sudah ada)
  document.getElementById("total-sistem").textContent =
    formatCurrency(totalPendapatan);

  const qrisValue = document
    .getElementById("rekap-qris")
    .value.replace(/\D/g, "");
  const bcaValue = document
    .getElementById("rekap-bca")
    .value.replace(/\D/g, "");
  const cashValue = document
    .getElementById("rekap-cash")
    .value.replace(/\D/g, "");

  const qris = parseFloat(qrisValue) || 0;
  const bca = parseFloat(bcaValue) || 0;
  const cash = parseFloat(cashValue) || 0;
  const totalManual = qris + bca + cash;
  document.getElementById("total-manual").textContent =
    formatCurrency(totalManual);

  checkReconciliation(totalPendapatan, totalManual);
}

function checkReconciliation(totalSistem, totalManual) {
  const warningEl = document.getElementById("reconciliation-warning");
  const submitBtn = document.getElementById("kirim-laporan-btn");
  const isMatched = Math.abs(totalSistem - totalManual) < 0.01;
  if (isMatched && totalSistem > 0) {
    warningEl.style.display = "none";
    submitBtn.disabled = false;
    submitBtn.classList.remove("btn-danger");
    submitBtn.classList.add("btn-primary");
  } else {
    warningEl.style.display = totalSistem > 0 && !isMatched ? "block" : "none";
    submitBtn.disabled = true;
    if (totalSistem > 0) {
      submitBtn.classList.add("btn-danger");
      submitBtn.classList.remove("btn-primary");
    }
  }
}

function attachAllEventListeners() {
  document.querySelectorAll(".product-row").forEach((row) => {
    attachEventListenersToRow(row);
  });

  // --- PERUBAHAN DI SINI ---
  document.querySelectorAll(".rekap-input").forEach((input) => {
    // Event 'input' untuk memformat angka saat diketik
    input.addEventListener("input", formatNumberInput);
    // Event 'keyup' untuk mengkalkulasi ulang total setelah angka diformat
    input.addEventListener("keyup", updateGrandTotals);
  });
}

function attachEventListenersToRow(row) {
  row.querySelectorAll(".stok-awal, .stok-akhir").forEach((input) => {
    input.addEventListener("input", () => updateRowAndTotals(row));
  });

  row.querySelectorAll(".btn-plus, .btn-minus").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.parentElement.querySelector("input[type=number]");
      let currentValue = parseInt(input.value) || 0;
      if (button.classList.contains("btn-plus")) {
        currentValue++;
      } else {
        currentValue = Math.max(0, currentValue - 1);
      }
      input.value = currentValue;
      input.dispatchEvent(new Event("input"));
    });
  });
}

async function handleKirimLaporan() {
  if (
    !confirm(
      "Apakah Anda yakin ingin mengirim laporan ini? Laporan yang sudah dikirim tidak bisa diubah."
    )
  ) {
    return;
  }

  const productData = [];
  let hasError = false;

  // Mengambil data dari SEMUA baris di kedua tabel (utama & manual)
  document
    .querySelectorAll("#report-table-body .product-row")
    .forEach((row) => {
      const stokAwal = row.querySelector(".stok-awal").value;
      const stokAkhir = row.querySelector(".stok-akhir").value;

      // Hanya kirim data yang diisi
      if (stokAwal > 0 || stokAkhir > 0) {
        let productEntry = {
          // Kirim NAMA, bukan ID. Backend akan menanganinya.
          supplier_name: row.dataset.supplierName,
          product_name: row.dataset.productName,
          stok_awal: parseInt(stokAwal) || 0,
          stok_akhir: parseInt(stokAkhir) || 0,
        };
        productData.push(productEntry);
      }
    });

  if (hasError) return;
  if (productData.length === 0) {
    return showToast("Tidak ada data penjualan yang diisi.", false);
  }

  const rekapData = {
    qris: document.getElementById("rekap-qris").value.replace(/\D/g, "") || "0",
    bca: document.getElementById("rekap-bca").value.replace(/\D/g, "") || "0",
    cash: document.getElementById("rekap-cash").value.replace(/\D/g, "") || "0",
    total:
      document.getElementById("total-manual").textContent.replace(/\D/g, "") ||
      "0",
  };

  const payload = {
    lapak_id: AppState.currentUser.user_info.lapak_id,
    products: productData,
    rekap_pembayaran: rekapData,
  };

  const submitBtn = document.getElementById("kirim-laporan-btn");
  const originalBtnHTML = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Mengirim...`;

  try {
    const response = await fetch("/api/submit_catatan_harian", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    showToast(result.message, response.ok);
    if (response.ok) {
      await populateLapakDashboard(); // Muat ulang dashboard setelah berhasil
    }
  } catch (e) {
    showToast("Gagal terhubung ke server.", false);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalBtnHTML;
    updateGrandTotals();
  }
}
async function populateHistoryLaporanPage() {
  const loadingEl = document.getElementById("history-loading"),
    listEl = document.getElementById("history-list");
  loadingEl.style.display = "block";
  listEl.innerHTML = "";
  const resp = await fetch(
    `/api/get_history_laporan/${AppState.currentUser.user_info.lapak_id}`
  );
  if (!resp.ok) {
    loadingEl.innerHTML =
      '<div class="alert alert-danger">Gagal memuat histori.</div>';
    return;
  }
  const result = await resp.json();
  loadingEl.style.display = "none";
  if (result.reports.length === 0) {
    listEl.innerHTML =
      '<div class="alert alert-info">Belum ada laporan yang dibuat.</div>';
    return;
  }
  result.reports.forEach((r) => {
    const statusBadge =
      r.status === "Terkonfirmasi"
        ? '<span class="badge bg-success">Terkonfirmasi</span>'
        : '<span class="badge bg-warning text-dark">Menunggu Konfirmasi</span>';
    listEl.innerHTML += `<div class="list-group-item"><div class="d-flex w-100 justify-content-between"><h5 class="mb-1">${new Date(
      r.tanggal
    ).toLocaleDateString("id-ID", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    })}</h5>${statusBadge}</div><p class="mb-1">Total pendapatan: <strong>${formatCurrency(
      r.total_pendapatan
    )}</strong></p><small>Total produk terjual: ${
      r.total_produk_terjual
    } Pcs.</small></div>`;
  });
}

// --- SUPPLIER FUNCTIONS ---
async function populateSupplierDashboard() {
  try {
    const supplierId = AppState.currentUser.user_info.supplier_id;
    const resp = await fetch(`/api/get_data_supplier/${supplierId}`);
    if (!resp.ok) throw new Error("Gagal mengambil data dashboard supplier");
    const result = await resp.json();
    if (result.success) {
      document.getElementById("supplier-total-tagihan").textContent =
        formatCurrency(result.summary.total_tagihan);
      document.getElementById("supplier-penjualan-bulan-ini").textContent =
        formatCurrency(result.summary.penjualan_bulan_ini);
    } else {
      throw new Error(result.message);
    }
  } catch (error) {
    showToast(error.message || "Gagal memuat data dashboard.", false);
    document.getElementById("supplier-total-tagihan").textContent = "Error";
    document.getElementById("supplier-penjualan-bulan-ini").textContent =
      "Error";
  }
}
async function populateSupplierHistoryPage() {
  const loadingEl = document.getElementById("supplier-history-loading"),
    contentEl = document.getElementById("supplier-history-content"),
    salesBody = document.getElementById("supplier-sales-history-body"),
    paymentsBody = document.getElementById("supplier-payment-history-body"),
    lapakSelect = document.getElementById("supplier-history-lapak-filter");

  loadingEl.style.display = "block";
  contentEl.style.display = "none";

  // Ambil semua nilai dari filter
  const startDate = document.getElementById(
    "supplier-history-start-date"
  ).value;
  const endDate = document.getElementById("supplier-history-end-date").value;
  const lapakId = lapakSelect.value;

  const params = new URLSearchParams();
  if (startDate) params.append("start_date", startDate);
  if (endDate) params.append("end_date", endDate);
  if (lapakId) params.append("lapak_id", lapakId); // Tambahkan lapak_id ke parameter
  const queryString = params.toString();

  try {
    const apiUrl = `/api/get_supplier_history/${AppState.currentUser.user_info.supplier_id}?${queryString}`;
    const resp = await fetch(apiUrl);
    const result = await resp.json();

    if (!result.success) throw new Error(result.message);

    // --- PERUBAHAN DI SINI: Mengisi dropdown lapak saat pertama kali dijalankan ---
    if (lapakSelect.options.length <= 1) {
      // Cek agar tidak diisi berulang kali
      if (result.lapaks) {
        result.lapaks.forEach((l) => {
          lapakSelect.innerHTML += `<option value="${l.id}">${l.lokasi}</option>`;
        });
      }
    }

    // Bagian untuk mengisi tabel pembayaran (tidak berubah)
    if (result.payments.length === 0) {
      paymentsBody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Belum ada pembayaran.</td></tr>`;
    } else {
      paymentsBody.innerHTML = result.payments
        .map(
          (p) => `
                    <tr>
                        <td>${new Date(
                          p.tanggal + "T00:00:00"
                        ).toLocaleDateString("id-ID")}</td>
                        <td>${formatCurrency(p.jumlah)}</td>
                        <td><span class="badge bg-info">${p.metode}</span></td>
                    </tr>`
        )
        .join("");
    }

    // Bagian untuk mengisi tabel penjualan (tidak berubah)
    if (result.sales.length === 0) {
      salesBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Belum ada penjualan.</td></tr>`;
    } else {
      salesBody.innerHTML = result.sales
        .map(
          (s) => `
                    <tr>
                        <td>${new Date(
                          s.tanggal + "T00:00:00"
                        ).toLocaleDateString("id-ID")}</td>
                        <td>${s.lokasi}</td>
                        <td>${s.nama_produk}</td>
                        <td>${s.terjual} Pcs</td>
                    </tr>`
        )
        .join("");
    }

    loadingEl.style.display = "none";
    contentEl.style.display = "block";
  } catch (e) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

// --- APP INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
    // Selalu jalankan fungsi otentikasi dan tanggal
    handleAuthRouting();
    updateDate();
    
    // --- Logika untuk Halaman Login ---
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", handleLogin);
    }

    // --- Logika untuk Halaman Owner ---
    const editAdminForm = document.getElementById("edit-admin-form");
    if (editAdminForm) editAdminForm.addEventListener("submit", (e) => handleFormSubmit("admin", e));

    const editLapakForm = document.getElementById("edit-lapak-form");
    if (editLapakForm) editLapakForm.addEventListener("submit", (e) => handleFormSubmit("lapak", e));
    
    const editSupplierForm = document.getElementById("edit-supplier-form");
    if (editSupplierForm) editSupplierForm.addEventListener("submit", (e) => handleFormSubmit("supplier", e));

    const paymentForm = document.getElementById("payment-confirmation-form");
    if (paymentForm) paymentForm.addEventListener("submit", handlePaymentSubmit);

    const lpd = document.getElementById("laporan-pendapatan-datepicker");
    if (lpd) lpd.addEventListener("change", populateLaporanPendapatan);

    const lbd = document.getElementById("laporan-biaya-datepicker");
    if (lbd) lbd.addEventListener("change", populateLaporanBiaya);
    
    const manageReportsFilterBtn = document.getElementById('manage-reports-filter-btn');
    if (manageReportsFilterBtn) manageReportsFilterBtn.addEventListener('click', populateManageReportsPage);

    const paymentHistoryFilterBtn = document.getElementById('payment-history-filter-btn');
    if (paymentHistoryFilterBtn) paymentHistoryFilterBtn.addEventListener('click', populatePaymentHistory);

    const ownerSupplierSelect = document.getElementById('owner-supplier-select');
    if (ownerSupplierSelect) ownerSupplierSelect.addEventListener('change', fetchAndDisplayOwnerSupplierHistory);
    
    const chartFilterBtn = document.getElementById('chart-filter-btn');
    if (chartFilterBtn) chartFilterBtn.addEventListener('click', fetchAndDrawCharts);

    const ownerHistoryFilterBtn = document.getElementById('owner-history-filter-btn');
    if (ownerHistoryFilterBtn) ownerHistoryFilterBtn.addEventListener('click', fetchAndDisplayOwnerSupplierHistory);


    // --- Logika untuk Halaman Lapak ---
    const kirimLaporanBtn = document.getElementById("kirim-laporan-btn");
    if (kirimLaporanBtn) kirimLaporanBtn.addEventListener("click", handleKirimLaporan);

    const rekapInputs = document.querySelectorAll(".rekap-input");
    rekapInputs.forEach(input => {
        input.addEventListener("input", formatNumberInput);
        input.addEventListener("keyup", updateGrandTotals);
    });

    // Panggil fungsi ini jika ada di halaman lapak
    if (document.getElementById('rekap-footer')) {
        manageFooterVisibility();
    }
    
    // --- Logika untuk Halaman Supplier ---
    const supplierHistoryFilterBtn = document.getElementById('supplier-history-filter-btn');
    if (supplierHistoryFilterBtn) supplierHistoryFilterBtn.addEventListener('click', populateSupplierHistoryPage);

});
