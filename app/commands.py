import click
from flask.cli import with_appcontext
import random
import datetime
from datetime import timedelta

# Impor db dan semua model yang dibutuhkan
from app import db
from app.models import Admin, Supplier, Lapak, Product, SupplierBalance, LaporanHarian, LaporanHarianProduk, PembayaranSupplier

@click.command(name='init-db')
@with_appcontext
def init_db_command():
    db.create_all()
    print("Database telah diinisialisasi.")

@click.command(name='seed-db')
@with_appcontext
def seed_db_command():
    from app.models import Admin, Supplier, Lapak, Product, SupplierBalance, LaporanHarian, LaporanHarianProduk, PembayaranSupplier
    """Menghapus database dan membuat data demo komprehensif untuk 90 hari."""
    db.drop_all()
    db.create_all()
    print("Database dibersihkan...")

    # ===================================================================
    ## 1. Buat Pengguna Inti (Owner & Admin)
    # ===================================================================
    owner = Admin(nama_lengkap="Owner Utama", nik="0000000000000000", username="owner", email="owner@app.com", nomor_kontak="0", password="owner")
    admin_andi = Admin(nama_lengkap="Andi (PJ Kopo)", nik="1111111111111111", username="andi", email="andi@app.com", nomor_kontak="0811", password="andi")
    admin_budi = Admin(nama_lengkap="Budi (PJ Buah Batu)", nik="2222222222222222", username="budi", email="budi@app.com", nomor_kontak="0812", password="budi")
    db.session.add_all([owner, admin_andi, admin_budi])
    db.session.commit()
    print("=> Pengguna (Owner, Admin) berhasil dibuat.")

    # ===================================================================
    ## 2. Buat Lapak
    # ===================================================================
    lapak_kopo = Lapak(lokasi="Lapak Kopo", penanggung_jawab=admin_andi)
    lapak_buah_batu = Lapak(lokasi="Lapak Buah Batu", penanggung_jawab=admin_budi)
    db.session.add_all([lapak_kopo, lapak_buah_batu])
    db.session.commit()
    print("=> Lapak (Kopo, Buah Batu) berhasil dibuat.")

    ## 3. (DIHAPUS) Supplier & Produk tidak lagi dibuat di awal
    # ===================================================================
    print("=> Supplier & Produk akan dibuat secara organik selama pembuatan riwayat.")


    # ===================================================================
    ## 4. Buat Data Transaksi Historis (Laporan & Pembayaran) untuk 90 hari
    # ===================================================================
    print("Membuat data transaksi historis (90 hari)...")
    today = datetime.date.today()
    all_lapaks = [lapak_kopo, lapak_buah_batu]

    # Kita siapkan daftar "calon" supplier dan produk untuk simulasi
    demo_catalog = {
        "Roti Lezat Bakery": ["Roti Tawar Gandum", "Roti Sobek Coklat", "Donat Gula"],
        "Minuman Segar Haus": ["Es Teh Manis", "Jus Jambu", "Kopi Susu Gula Aren"],
        "Cemilan Gurih Nusantara": ["Keripik Singkong Balado", "Tahu Crispy"]
    }

    for i in range(90, 0, -1):
        current_date = today - timedelta(days=i)
        
        for lapak in all_lapaks:
            if random.random() < 0.9: # 90% kemungkinan ada laporan setiap hari
                status = 'Menunggu Konfirmasi' if i <= 10 and random.random() < 0.5 else 'Terkonfirmasi'
                
                report = LaporanHarian(lapak_id=lapak.id, tanggal=current_date, status=status,
                                        total_pendapatan=0, total_biaya_supplier=0, total_produk_terjual=0,
                                        pendapatan_cash=0, pendapatan_qris=0, pendapatan_bca=0)
                db.session.add(report)
                db.session.flush()

                total_pendapatan_harian = 0
                total_biaya_harian = 0
                total_terjual_harian = 0
                
                # Pilih beberapa supplier secara acak untuk dijual hari itu
                suppliers_for_the_day = random.sample(list(demo_catalog.keys()), k=random.randint(1, 2))

                for supplier_name in suppliers_for_the_day:
                    product_name = random.choice(demo_catalog[supplier_name])

                    # === LOGIKA BARU: CARI ATAU BUAT SUPPLIER & PRODUK ===
                    # 1. Cari atau buat Supplier
                    supplier = Supplier.query.filter(Supplier.nama_supplier == supplier_name).first()
                    if not supplier:
                        supplier = Supplier(
                            nama_supplier=supplier_name,
                            username=supplier_name.lower().replace(" ", "") + str(random.randint(10,99)),
                            password="demopassword",
                            metode_pembayaran=random.choice(["BCA", "DANA"]),
                            nomor_rekening="12345678"
                        )
                        supplier.balance = SupplierBalance(balance=0.0)
                        db.session.add(supplier)
                        db.session.flush()
                    
                    # 2. Cari atau buat Produk
                    product = Product.query.filter_by(nama_produk=product_name, supplier_id=supplier.id).first()
                    if not product:
                        # Gunakan harga default dari model
                        product = Product(nama_produk=product_name, supplier_id=supplier.id)
                        db.session.add(product)
                        db.session.flush()
                    # === AKHIR LOGIKA BARU ===

                    stok_awal = random.randint(15, 40)
                    terjual = random.randint(5, stok_awal - 3)
                    stok_akhir = stok_awal - terjual
                    
                    total_harga_jual = terjual * product.harga_jual
                    total_harga_beli = terjual * product.harga_beli
                    
                    rincian = LaporanHarianProduk(laporan_id=report.id, product_id=product.id,
                                                  stok_awal=stok_awal, stok_akhir=stok_akhir,
                                                  jumlah_terjual=terjual, total_harga_jual=total_harga_jual,
                                                  total_harga_beli=total_harga_beli)
                    db.session.add(rincian)

                    total_pendapatan_harian += total_harga_jual
                    total_biaya_harian += total_harga_beli
                    total_terjual_harian += terjual

                    if status == 'Terkonfirmasi' and product.supplier:
                        product.supplier.balance.balance += total_harga_beli
                
                report.total_pendapatan = total_pendapatan_harian
                report.total_biaya_supplier = total_biaya_harian
                report.total_produk_terjual = total_terjual_harian
                # Asumsi pembagian pendapatan
                report.pendapatan_qris = total_pendapatan_harian * 0.5 
                report.pendapatan_cash = total_pendapatan_harian * 0.3
                report.pendapatan_bca = total_pendapatan_harian * 0.2
                report.manual_total_pendapatan = total_pendapatan_harian
    
        # Simulasi pembayaran (bisa dibiarkan seperti sebelumnya)
        if i % 10 == 0: # Lakukan pembayaran setiap 10 hari sekali
            all_suppliers = Supplier.query.all()
            if all_suppliers:
                supplier_to_pay = random.choice(all_suppliers)
                if supplier_to_pay.balance and supplier_to_pay.balance.balance > 50000:
                    payment_amount = random.randint(50000, int(supplier_to_pay.balance.balance))
                    payment = PembayaranSupplier(
                        supplier_id=supplier_to_pay.id,
                        tanggal_pembayaran=current_date,
                        jumlah_pembayaran=payment_amount,
                        metode_pembayaran=supplier_to_pay.metode_pembayaran
                    )
                    supplier_to_pay.balance.balance -= payment_amount
                    db.session.add(payment)
    
    db.session.commit()
    print("=> Data historis berhasil dibuat secara organik.")
    print("\nDatabase siap untuk demo! Silakan jalankan aplikasi.")