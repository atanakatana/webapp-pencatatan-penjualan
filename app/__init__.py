import datetime
import re
import random
from datetime import timedelta
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func, or_
from sqlalchemy.orm import joinedload
from calendar import monthrange
import logging
import random

# Inisialisasi aplikasi Flask
app = Flask(__name__)
# Konfigurasi database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///penjualan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# di app/__init__.py
app.config['SECRET_KEY'] = 'kunci-rahasia-katanya'

# Setup logging
logging.basicConfig(level=logging.INFO)

# Inisialisasi SQLAlchemy
db = SQLAlchemy(app)

# ===================================================================
# CLI COMMANDS UNTUK INISIALISASI & SEEDING DATABASE
# ===================================================================
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Database telah diinisialisasi.")
@app.cli.command("seed-db")
def seed_db_command():
    from app.models import Admin, Supplier, Lapak, Product, SupplierBalance, LaporanHarian, LaporanHarianProduk, PembayaranSupplier
    from werkzeug.security import generate_password_hash # <--- TAMBAHKAN IMPORT INI
    """Menghapus database dan membuat data demo komprehensif untuk 90 hari."""
    db.drop_all()
    db.create_all()
    print("Database dibersihkan...")

    # ===================================================================
    ## 1. Buat Pengguna Inti (Owner & Admin)
    # ===================================================================
    owner = Admin(nama_lengkap="Owner Utama", nik="0000000000000000", username="owner", email="owner@app.com", nomor_kontak="0", password=generate_password_hash("owner"))
    admin_andi = Admin(nama_lengkap="Andi (PJ Kopo)", nik="1111111111111111", username="andi", email="andi@app.com", nomor_kontak="0811", password=generate_password_hash("andi"))
    admin_budi = Admin(nama_lengkap="Budi (PJ Buah Batu)", nik="2222222222222222", username="budi", email="budi@app.com", nomor_kontak="0812", password=generate_password_hash("budi"))
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

    # ===================================================================
    ## 3. Buat Supplier & Produk (LEBIH BANYAK VARIASI)
    # ===================================================================
    # --- Supplier 1 ---
    supplier_roti = Supplier(nama_supplier="Roti Lezat Bakery", username="roti", kontak="0851", nomor_register="REG001", password=generate_password_hash("roti"), metode_pembayaran="BCA", nomor_rekening="112233")
    supplier_roti.balance = SupplierBalance(balance=0.0)
    db.session.add(supplier_roti)
    db.session.flush()
    db.session.add_all([
        Product(nama_produk="Roti Tawar Gandum", supplier_id=supplier_roti.id, harga_beli=12000, harga_jual=15000),
        Product(nama_produk="Roti Sobek Coklat", supplier_id=supplier_roti.id, harga_beli=10000, harga_jual=13000),
        Product(nama_produk="Donat Gula", supplier_id=supplier_roti.id, harga_beli=4000, harga_jual=6000)
    ])

    # --- Supplier 2 ---
    supplier_minuman = Supplier(nama_supplier="Minuman Segar Haus", username="minuman", kontak="0852", nomor_register="REG002", password="minuman", metode_pembayaran="DANA", nomor_rekening="08521234")
    supplier_minuman.balance = SupplierBalance(balance=0.0)
    db.session.add(supplier_minuman)
    db.session.flush()
    db.session.add_all([
        Product(nama_produk="Es Teh Manis", supplier_id=supplier_minuman.id, harga_beli=3000, harga_jual=5000),
        Product(nama_produk="Jus Jambu", supplier_id=supplier_minuman.id, harga_beli=6000, harga_jual=8000),
        Product(nama_produk="Kopi Susu Gula Aren", supplier_id=supplier_minuman.id, harga_beli=15000, harga_jual=18000)
    ])

    # --- Supplier 3 ---
    supplier_snack = Supplier(nama_supplier="Cemilan Gurih Nusantara", username="snack", kontak="0853", nomor_register="REG003", password="snack", metode_pembayaran="BCA", nomor_rekening="445566")
    supplier_snack.balance = SupplierBalance(balance=0.0)
    db.session.add(supplier_snack)
    db.session.flush()
    db.session.add_all([
        Product(nama_produk="Keripik Singkong Balado", supplier_id=supplier_snack.id, harga_beli=8000, harga_jual=10000),
        Product(nama_produk="Tahu Crispy", supplier_id=supplier_snack.id, harga_beli=7000, harga_jual=10000)
    ])
    
    db.session.commit()
    print("=> 3 Supplier dengan total 8 produk berhasil dibuat.")

    # ===================================================================
    ## 4. (DIHAPUS) Alokasi Produk ke Lapak
    # ===================================================================
    print("=> Alokasi produk kini dilakukan oleh Admin Lapak, langkah ini dilewati.")

    # ===================================================================
    ## 5. Buat Data Transaksi Historis (Laporan & Pembayaran) untuk 90 hari
    # ===================================================================
    print("Membuat data transaksi historis (90 hari)...")
    today = datetime.date.today()
    all_lapaks = [lapak_kopo, lapak_buah_batu]
    all_products = Product.query.all()

    for i in range(90, 0, -1):
        current_date = today - timedelta(days=i)
        
        for lapak in all_lapaks:
            if random.random() < 0.85:
                status = 'Menunggu Konfirmasi' if i <= 10 and random.random() < 0.5 else 'Terkonfirmasi'
                
                report = LaporanHarian(lapak_id=lapak.id, tanggal=current_date, status=status,
                                        total_pendapatan=0, total_biaya_supplier=0, total_produk_terjual=0,
                                        pendapatan_cash=0, pendapatan_qris=0, pendapatan_bca=0)
                db.session.add(report)
                db.session.flush()

                total_pendapatan_harian = 0
                total_biaya_harian = 0
                total_terjual_harian = 0
                
                # Pilih beberapa produk secara acak untuk dijual hari itu
                products_for_the_day = random.sample(all_products, k=random.randint(3, 6))

                for product in products_for_the_day:
                    stok_awal = random.randint(10, 30)
                    terjual = random.randint(1, stok_awal - 2)
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
                report.pendapatan_qris = total_pendapatan_harian * 0.5
                report.pendapatan_cash = total_pendapatan_harian * 0.5
                report.manual_total_pendapatan = total_pendapatan_harian
    
        if random.random() < 0.1:
            all_suppliers = [supplier_roti, supplier_minuman, supplier_snack]
            supplier_to_pay = random.choice(all_suppliers)
            payment = PembayaranSupplier(
                supplier=supplier_to_pay,
                tanggal_pembayaran=current_date,
                jumlah_pembayaran=random.randint(50000, 200000),
                metode_pembayaran=supplier_to_pay.metode_pembayaran
            )
            db.session.add(payment)

    db.session.commit()
    print("=> Data historis berhasil dibuat.")
    print("\nDatabase siap untuk demo! Silakan jalankan aplikasi.")

    from app import routes, models