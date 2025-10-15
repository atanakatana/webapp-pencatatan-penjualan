import datetime
import re
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func, or_
from sqlalchemy.orm import joinedload
import logging

# Inisialisasi aplikasi Flask
app = Flask(__name__)
# Konfigurasi database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///penjualan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Setup logging
logging.basicConfig(level=logging.INFO)

# Inisialisasi SQLAlchemy
db = SQLAlchemy(app)

# --- HARGA KONSTAN (SEBAGAI DEFAULT) ---
HARGA_BELI_DEFAULT = 8000
HARGA_JUAL_DEFAULT = 10000

# ===================================================================
# DEFINISI MODEL DATABASE
# ===================================================================

product_lapak_association = db.Table('product_lapak',
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True),
    db.Column('lapak_id', db.Integer, db.ForeignKey('lapak.id'), primary_key=True)
)

lapak_anggota_association = db.Table('lapak_anggota',
    db.Column('lapak_id', db.Integer, db.ForeignKey('lapak.id'), primary_key=True),
    db.Column('admin_id', db.Integer, db.ForeignKey('admin.id'), primary_key=True)
)

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    nama_lengkap = db.Column(db.String(100), nullable=False)
    nik = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nomor_kontak = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(120), nullable=False)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_supplier = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False) 
    kontak = db.Column(db.String(20), nullable=True)
    nomor_register = db.Column(db.String(50), unique=True, nullable=True)
    alamat = db.Column(db.Text, nullable=True)
    password = db.Column(db.String(120), nullable=False)
    # --- REVISI: Kolom baru untuk info pembayaran ---
    metode_pembayaran = db.Column(db.String(20), nullable=True)
    nomor_rekening = db.Column(db.String(50), nullable=True)
    products = db.relationship('Product', backref='supplier', lazy=True, cascade="all, delete-orphan")
    balance = db.relationship('SupplierBalance', backref='supplier', uselist=False, cascade="all, delete-orphan")

class Lapak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lokasi = db.Column(db.String(200), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False) # Penanggung Jawab
    penanggung_jawab = db.relationship('Admin', foreign_keys=[user_id], backref=db.backref('lapak_pj', uselist=False))
    anggota = db.relationship('Admin', secondary=lapak_anggota_association, lazy='subquery',
                              backref=db.backref('lapak_anggota', lazy=True))
    reports = db.relationship('LaporanHarian', backref='lapak', lazy=True, cascade="all, delete-orphan")

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_produk = db.Column(db.String(100), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    harga_beli = db.Column(db.Float, nullable=False, default=HARGA_BELI_DEFAULT)
    harga_jual = db.Column(db.Float, nullable=False, default=HARGA_JUAL_DEFAULT)
    is_manual = db.Column(db.Boolean, default=False, nullable=False)
    lapaks = db.relationship('Lapak', secondary=product_lapak_association, lazy='subquery',
                             backref=db.backref('products', lazy=True))

class StokHarian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    jumlah_sisa = db.Column(db.Integer, nullable=False)
    tanggal = db.Column(db.Date, default=datetime.date.today, nullable=False)
    __table_args__ = (db.UniqueConstraint('lapak_id', 'product_id', 'tanggal', name='_lapak_product_date_uc'),)

class LaporanHarian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    tanggal = db.Column(db.Date, nullable=False, default=datetime.date.today)
    total_pendapatan = db.Column(db.Float, nullable=False)
    total_biaya_supplier = db.Column(db.Float, nullable=False, default=0)
    pendapatan_cash = db.Column(db.Float, nullable=False)
    pendapatan_qris = db.Column(db.Float, nullable=False)
    pendapatan_bca = db.Column(db.Float, nullable=False) 
    total_produk_terjual = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Menunggu Konfirmasi')
    manual_pendapatan_cash = db.Column(db.Float, nullable=True)
    manual_pendapatan_qris = db.Column(db.Float, nullable=True)
    manual_pendapatan_bca = db.Column(db.Float, nullable=True)
    manual_total_pendapatan = db.Column(db.Float, nullable=True)
    rincian_produk = db.relationship('LaporanHarianProduk', backref='laporan', lazy=True, cascade="all, delete-orphan")

class LaporanHarianProduk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    laporan_id = db.Column(db.Integer, db.ForeignKey('laporan_harian.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    stok_awal = db.Column(db.Integer, nullable=False)
    stok_akhir = db.Column(db.Integer, nullable=False)
    jumlah_terjual = db.Column(db.Integer, nullable=False)
    total_harga_jual = db.Column(db.Float, nullable=False)
    total_harga_beli = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class SupplierBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), unique=True, nullable=False)
    balance = db.Column(db.Float, nullable=False, default=0.0)

class PembayaranSupplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    tanggal_pembayaran = db.Column(db.Date, nullable=False, default=datetime.date.today)
    jumlah_pembayaran = db.Column(db.Float, nullable=False)
    metode_pembayaran = db.Column(db.String(20), nullable=False) 
    supplier = db.relationship('Supplier')

# ===================================================================
# CLI & Rute Halaman
# ===================================================================
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Database telah diinisialisasi.")
@app.cli.command("seed-db")
def seed_db_command():
    db.drop_all()
    db.create_all()
    # 1. Buat Owner
    owner = Admin(nama_lengkap="Owner Utama", nik="0000000000000000", username="owner", email="owner@app.com", nomor_kontak="0", password="owner")
    db.session.add(owner)
    
    # 2. Buat Admin untuk Lapak
    admin1 = Admin(nama_lengkap="Admin Lapak Satu", nik="1234567890123456", username="admin1", email="admin1@app.com", nomor_kontak="08123456789", password="admin1")
    db.session.add(admin1)
    db.session.commit() # Commit untuk mendapatkan ID

    # 3. Buat Lapak dan tugaskan admin sebagai PJ
    lapak1 = Lapak(lokasi="Lapak Kopo", user_id=admin1.id)
    db.session.add(lapak1)

    # 4. Buat Supplier
    supplier1 = Supplier(
        nama_supplier="Supplier Roti", username="supplier1", kontak="08987654321", 
        nomor_register="REG001", alamat="Jl. Roti No. 1", password="supplier1",
        metode_pembayaran="BCA", nomor_rekening="1122334455"
    )
    supplier1.balance = SupplierBalance(balance=0.0)
    db.session.add(supplier1)
    db.session.commit() # Commit untuk mendapatkan ID

    # 5. Buat Produk untuk supplier dan alokasikan ke lapak
    product1 = Product(nama_produk="Roti Tawar", supplier_id=supplier1.id, harga_beli=8000, harga_jual=10000)
    product2 = Product(nama_produk="Roti Coklat", supplier_id=supplier1.id, harga_beli=9000, harga_jual=12000)
    product1.lapaks.append(lapak1)
    product2.lapaks.append(lapak1)
    db.session.add_all([product1, product2])

    db.session.commit()
    print("Database di-seed dengan data Owner, Admin, Lapak, dan Supplier.")
@app.route('/')
def login_page():
    return render_template('index.html')
# ===================================================================
# ENDPOINTS API
# ===================================================================
@app.route('/api/login', methods=['POST'])
def handle_login():
    data = request.json
    username = data.get('username', '').lower()
    password = data.get('password')
    admin = Admin.query.filter(db.func.lower(Admin.username) == username).first()
    if admin and admin.password == password:
        if admin.username == 'owner':
            return jsonify({"success": True, "role": "owner", "user_info": {"nama_lengkap": admin.nama_lengkap, "id": admin.id}})
        else:
            lapak_info = Lapak.query.filter(or_(Lapak.user_id == admin.id, Lapak.anggota.any(id=admin.id))).first()
            return jsonify({"success": True, "role": "lapak", "user_info": {"nama_lengkap": admin.nama_lengkap, "lapak_id": lapak_info.id if lapak_info else None, "id": admin.id}})
    supplier = Supplier.query.filter(db.func.lower(Supplier.username) == username).first()
    if supplier and supplier.password == password:
        return jsonify({"success": True, "role": "supplier", "user_info": {"nama_supplier": supplier.nama_supplier,"supplier_id": supplier.id}})
    return jsonify({"success": False, "message": "Username atau password salah"}), 401
# --- OWNER API ---
@app.route('/api/get_data_owner', methods=['GET'])
def get_owner_data():
    try:
        admins = Admin.query.filter(Admin.username != 'owner').all()
        lapaks = Lapak.query.options(joinedload(Lapak.penanggung_jawab), joinedload(Lapak.anggota)).all()
        suppliers = Supplier.query.all()
        
        admin_list = [{"id": u.id, "nama_lengkap": u.nama_lengkap, "nik": u.nik, "username": u.username, "email": u.email, "nomor_kontak": u.nomor_kontak, "password": u.password} for u in admins]
        lapak_list = [{"id": l.id, "lokasi": l.lokasi, "penanggung_jawab": f"{l.penanggung_jawab.nama_lengkap}", "user_id": l.user_id, "anggota": [{"id": a.id, "nama": a.nama_lengkap} for a in l.anggota], "anggota_ids": [a.id for a in l.anggota]} for l in lapaks]
        # --- REVISI: Sertakan info pembayaran ---
        supplier_list = [{"id": s.id, "nama_supplier": s.nama_supplier, "username": s.username, "kontak": s.kontak, "nomor_register": s.nomor_register, "alamat": s.alamat, "password": s.password, "metode_pembayaran": s.metode_pembayaran, "nomor_rekening": s.nomor_rekening} for s in suppliers]
        
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        total_pendapatan_bulan_ini = db.session.query(func.sum(LaporanHarian.total_pendapatan)).filter(LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        total_biaya_bulan_ini = db.session.query(func.sum(PembayaranSupplier.jumlah_pembayaran)).filter(PembayaranSupplier.tanggal_pembayaran >= start_of_month).scalar() or 0
        return jsonify({"admin_data": admin_list, "lapak_data": lapak_list, "supplier_data": supplier_list, "summary": {"pendapatan_bulan_ini": total_pendapatan_bulan_ini, "biaya_bulan_ini": total_biaya_bulan_ini}})
    except Exception as e:
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

@app.route('/api/add_admin', methods=['POST'])
def add_admin():
    data = request.json
    if data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        new_admin = Admin(nama_lengkap=data['nama_lengkap'], nik=data['nik'], username=data['username'], email=data['email'], nomor_kontak=data['nomor_kontak'], password=data['password'])
        db.session.add(new_admin)
        db.session.commit()
        return jsonify({"success": True, "message": "Admin berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username, NIK, atau email sudah ada."}), 400

@app.route('/api/update_admin/<int:admin_id>', methods=['PUT'])
def update_admin(admin_id):
    data = request.json
    admin = Admin.query.get_or_404(admin_id)
    if data.get('password') and data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        admin.nama_lengkap = data['nama_lengkap']
        admin.nik = data['nik']
        admin.username = data['username']
        admin.email = data['email']
        admin.nomor_kontak = data['nomor_kontak']
        if data.get('password'): admin.password = data['password']
        db.session.commit()
        return jsonify({"success": True, "message": "Data Admin berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username, NIK, atau email sudah digunakan oleh admin lain."}), 400

@app.route('/api/delete_admin/<int:admin_id>', methods=['DELETE'])
def delete_admin(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    if Lapak.query.filter_by(user_id=admin_id).first(): return jsonify({"success": False, "message": "Gagal menghapus: Admin ini adalah Penanggung Jawab sebuah lapak."}), 400
    db.session.delete(admin)
    db.session.commit()
    return jsonify({"success": True, "message": "Admin berhasil dihapus"})

@app.route('/api/add_lapak', methods=['POST'])
def add_lapak():
    data = request.json
    try:
        new_lapak = Lapak(lokasi=data['lokasi'], user_id=data['user_id'])
        anggota_ids = data.get('anggota_ids', [])
        if anggota_ids: new_lapak.anggota = Admin.query.filter(Admin.id.in_(anggota_ids)).all()
        db.session.add(new_lapak)
        db.session.commit()
        return jsonify({"success": True, "message": "Lapak berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Nama lokasi lapak sudah ada."}), 400

@app.route('/api/update_lapak/<int:lapak_id>', methods=['PUT'])
def update_lapak(lapak_id):
    data = request.json
    lapak = Lapak.query.get_or_404(lapak_id)
    try:
        lapak.lokasi = data['lokasi']
        lapak.user_id = data['user_id']
        anggota_ids = data.get('anggota_ids', [])
        lapak.anggota = Admin.query.filter(Admin.id.in_(anggota_ids)).all()
        db.session.commit()
        return jsonify({"success": True, "message": "Data Lapak berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Nama lokasi lapak sudah digunakan."}), 400

@app.route('/api/delete_lapak/<int:lapak_id>', methods=['DELETE'])
def delete_lapak(lapak_id):
    lapak = Lapak.query.get_or_404(lapak_id)
    db.session.delete(lapak)
    db.session.commit()
    return jsonify({"success": True, "message": "Lapak berhasil dihapus"})

# --- REVISI: Logika baru untuk nomor registrasi ---
@app.route('/api/get_next_supplier_reg_number', methods=['GET'])
def get_next_supplier_reg_number():
    used_numbers = set()
    suppliers = Supplier.query.filter(Supplier.nomor_register.like('REG%')).all()
    for s in suppliers:
        num_part = re.search(r'\d+', s.nomor_register)
        if num_part:
            used_numbers.add(int(num_part.group()))
    
    next_id = 1
    while next_id in used_numbers:
        next_id += 1
        
    return jsonify({"success": True, "reg_number": f"REG{next_id:03d}"})

# --- REVISI: Tambahkan metode pembayaran & no rekening ---
@app.route('/api/add_supplier', methods=['POST'])
def add_supplier():
    data = request.json
    if data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        new_supplier = Supplier(
            nama_supplier=data['nama_supplier'], username=data.get('username'), kontak=data.get('kontak'), 
            nomor_register=data.get('nomor_register'), alamat=data.get('alamat'), password=data['password'],
            metode_pembayaran=data.get('metode_pembayaran'), nomor_rekening=data.get('nomor_rekening')
        )
        new_supplier.balance = SupplierBalance(balance=0.0)
        db.session.add(new_supplier)
        db.session.flush() 
        selected_lapak_ids = data.get('lapak_ids', [])
        lapaks_to_associate = Lapak.query.filter(Lapak.id.in_(selected_lapak_ids)).all()
        for p_data in data.get('products', []):
            if p_data.get('name'):
                new_product = Product(
                    nama_produk=p_data['name'], supplier_id=new_supplier.id,
                    harga_beli=float(p_data.get('harga_beli', HARGA_BELI_DEFAULT)),
                    harga_jual=float(p_data.get('harga_jual', HARGA_JUAL_DEFAULT))
                )
                if lapaks_to_associate: new_product.lapaks.extend(lapaks_to_associate)
                db.session.add(new_product)
        db.session.commit()
        return jsonify({"success": True, "message": "Supplier berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username atau Nomor Register sudah ada."}), 400

# --- REVISI: Update metode pembayaran & no rekening ---
@app.route('/api/update_supplier/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    data = request.json
    supplier = Supplier.query.get_or_404(supplier_id)

    # Validasi password jika diubah
    if data.get('password') and data['password'] != data['password_confirm']:
        return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400

    try:
        # Update field yang diizinkan
        supplier.nama_supplier = data['nama_supplier']
        supplier.username = data.get('username')
        supplier.kontak = data.get('kontak')
        supplier.alamat = data.get('alamat')
        supplier.metode_pembayaran = data.get('metode_pembayaran')
        supplier.nomor_rekening = data.get('nomor_rekening')

        # Hanya update password jika field diisi
        if data.get('password'):
            supplier.password = data['password']

        # Commit perubahan ke database
        db.session.commit()
        return jsonify({"success": True, "message": "Data Supplier berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username sudah digunakan oleh supplier lain."}), 400

@app.route('/api/delete_supplier/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({"success": True, "message": "Supplier berhasil dihapus"})
# --- OWNER API (Laporan & Pembayaran) ---
# TAMBAHKAN DUA FUNGSI BARU INI DI app.py

@app.route('/api/get_laporan_pendapatan_harian')
def get_laporan_pendapatan_harian():
    try:
        date_str = request.args.get('date')
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

        reports = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak),
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
        ).filter(
            LaporanHarian.tanggal == target_date,
            LaporanHarian.status == 'Terkonfirmasi'
        ).all()

        total_harian = sum(r.total_pendapatan for r in reports)
        laporan_per_lapak = []

        for report in reports:
            rincian_pendapatan = []
            for item in report.rincian_produk:
                if item.jumlah_terjual > 0:
                    rincian_pendapatan.append({
                        "produk": item.product.nama_produk,
                        "supplier": item.product.supplier.nama_supplier if item.product.supplier else "N/A",
                        "stok_awal": item.stok_awal,
                        "stok_akhir": item.stok_akhir,
                        "jumlah": item.jumlah_terjual
                    })
            
            if rincian_pendapatan:
                 laporan_per_lapak.append({
                    "lokasi": report.lapak.lokasi,
                    "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
                    "total_pendapatan": report.total_pendapatan,
                    "rincian_pendapatan": rincian_pendapatan
                })

        return jsonify({
            "total_harian": total_harian,
            "laporan_per_lapak": laporan_per_lapak
        })

    except Exception as e:
        logging.error(f"Error fetching pendapatan harian: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_laporan_biaya_harian')
def get_laporan_biaya_harian():
    try:
        date_str = request.args.get('date')
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

        reports = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak),
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
        ).filter(
            LaporanHarian.tanggal == target_date,
            LaporanHarian.status == 'Terkonfirmasi'
        ).all()

        total_harian = sum(r.total_biaya_supplier for r in reports)
        laporan_per_lapak = []

        for report in reports:
            rincian_biaya = []
            for item in report.rincian_produk:
                 if item.jumlah_terjual > 0:
                    rincian_biaya.append({
                        "produk": item.product.nama_produk,
                        "supplier": item.product.supplier.nama_supplier if item.product.supplier else "N/A",
                        "jumlah": item.jumlah_terjual,
                        "biaya": item.total_harga_beli
                    })
            
            if rincian_biaya:
                laporan_per_lapak.append({
                    "lokasi": report.lapak.lokasi,
                    "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
                    "total_biaya": report.total_biaya_supplier,
                    "rincian_biaya": rincian_biaya
                })

        return jsonify({
            "total_harian": total_harian,
            "laporan_per_lapak": laporan_per_lapak
        })

    except Exception as e:
        logging.error(f"Error fetching biaya harian: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_unconfirmed_reports')
def get_unconfirmed_reports():
    try:
        unconfirmed_reports = LaporanHarian.query.options(joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab)).filter_by(status='Menunggu Konfirmasi').order_by(LaporanHarian.tanggal.desc()).all()
        report_list = [{"id": r.id, "lokasi": r.lapak.lokasi, "penanggung_jawab": r.lapak.penanggung_jawab.nama_lengkap, "tanggal": r.tanggal.isoformat(), "total_pendapatan": r.total_pendapatan, "total_produk_terjual": r.total_produk_terjual, "status": r.status} for r in unconfirmed_reports]
        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/confirm_report/<int:report_id>', methods=['POST'])
def confirm_report(report_id):
    try:
        report = LaporanHarian.query.options(joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product)).get(report_id)
        if not report: return jsonify({"success": False, "message": "Laporan tidak ditemukan."}), 404
        if report.status == 'Terkonfirmasi': return jsonify({"success": False, "message": "Laporan ini sudah dikonfirmasi."}), 400
        report.status = 'Terkonfirmasi'
        supplier_costs = {}
        for rincian in report.rincian_produk:
            if rincian.product.supplier_id:
                sid = rincian.product.supplier_id
                cost = rincian.total_harga_beli
                supplier_costs[sid] = supplier_costs.get(sid, 0) + cost
        for supplier_id, cost in supplier_costs.items():
            balance = SupplierBalance.query.filter_by(supplier_id=supplier_id).first()
            if balance: balance.balance += cost
            else: db.session.add(SupplierBalance(supplier_id=supplier_id, balance=cost))
        db.session.commit()
        return jsonify({"success": True, "message": "Laporan berhasil dikonfirmasi."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
        
@app.route('/api/get_pembayaran_data', methods=['GET'])
def get_pembayaran_data():
    try:
        suppliers = Supplier.query.options(joinedload(Supplier.balance)).all()
        result = [{"supplier_id": s.id, "nama_supplier": s.nama_supplier, "total_tagihan": s.balance.balance if s.balance else 0.0, "metode_pembayaran": s.metode_pembayaran, "nomor_rekening": s.nomor_rekening} for s in suppliers]
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- REVISI: Hapus pemilihan metode, ambil dari data supplier ---
@app.route('/api/submit_pembayaran', methods=['POST'])
def submit_pembayaran():
    data = request.json
    supplier_id = data.get('supplier_id')
    jumlah_dibayar = float(data.get('jumlah_pembayaran', 0))
    supplier = Supplier.query.get(supplier_id)
    if not supplier or not supplier.metode_pembayaran:
        return jsonify({"success": False, "message": "Metode pembayaran untuk supplier ini belum diatur."}), 400
    balance = supplier.balance
    if not balance or balance.balance < (jumlah_dibayar - 0.01):
        return jsonify({"success": False, "message": f"Jumlah pembayaran melebihi total tagihan."}), 400
    try:
        new_payment = PembayaranSupplier(
            supplier_id=supplier_id, 
            jumlah_pembayaran=jumlah_dibayar, 
            metode_pembayaran=supplier.metode_pembayaran
        )
        db.session.add(new_payment)
        balance.balance -= jumlah_dibayar
        db.session.commit()
        return jsonify({"success": True, "message": f"Pembayaran berhasil dicatat."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

# --- LAPAK API ---
# --- REVISI: Kirim info pembayaran ke frontend ---
@app.route('/api/get_data_buat_catatan/<int:lapak_id>', methods=['GET'])
def get_data_buat_catatan(lapak_id):
    today = datetime.date.today()
    if LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first():
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah dibuat.", "already_exists": True}), 409
    products = Product.query.options(joinedload(Product.supplier)).filter(Product.lapaks.any(id=lapak_id)).order_by(Product.supplier_id).all()
    suppliers_data = {}
    for p in products:
        supplier = p.supplier
        supplier_id = supplier.id if supplier else 'manual'
        supplier_name = supplier.nama_supplier if supplier else 'Produk Manual'
        supplier_reg = supplier.nomor_register if supplier else 'N/A'
        metode_pembayaran = f"{supplier.metode_pembayaran} - {supplier.nomor_rekening}" if supplier and supplier.metode_pembayaran and supplier.nomor_rekening else ""
        
        if supplier_id not in suppliers_data:
            suppliers_data[supplier_id] = {
                "id": supplier_id,
                "name": supplier_name,
                "reg_number": supplier_reg,
                "payment_info": metode_pembayaran,
                "products": []
            }
        
        suppliers_data[supplier_id]['products'].append({ "id": p.id, "name": p.nama_produk, "harga_jual": p.harga_jual, "harga_beli": p.harga_beli })
        
    return jsonify({"success": True, "data": list(suppliers_data.values())})

@app.route('/api/submit_catatan_harian', methods=['POST'])
def submit_catatan_harian():
    data = request.json
    lapak_id = data.get('lapak_id')
    today = datetime.date.today()
    if LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first():
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah pernah dibuat."}), 400
    try:
        total_pendapatan_auto, total_biaya_auto, total_terjual_auto = 0.0, 0.0, 0
        
        new_report = LaporanHarian(lapak_id=lapak_id, tanggal=today, total_pendapatan=0, total_biaya_supplier=0,
            pendapatan_cash=float(data['rekap_pembayaran'].get('cash') or 0),
            pendapatan_qris=float(data['rekap_pembayaran'].get('qris') or 0),
            pendapatan_bca=float(data['rekap_pembayaran'].get('bca') or 0), total_produk_terjual=0,
            manual_pendapatan_cash=float(data['rekap_pembayaran'].get('cash') or 0),
            manual_pendapatan_qris=float(data['rekap_pembayaran'].get('qris') or 0),
            manual_pendapatan_bca=float(data['rekap_pembayaran'].get('bca') or 0),
            manual_total_pendapatan=float(data['rekap_pembayaran'].get('total') or 0)
        )
        db.session.add(new_report)
        db.session.flush()
        for prod_data in data.get('products', []):
            product_id = prod_data.get('id')
            stok_awal = int(prod_data.get('stok_awal') or 0)
            stok_akhir = int(prod_data.get('stok_akhir') or 0)
            if stok_awal == 0 and stok_akhir == 0: continue
            
            if not product_id:
                if prod_data.get('nama_produk'):
                    lapak = Lapak.query.get(lapak_id)
                    new_product = Product(nama_produk=prod_data['nama_produk'],
                        supplier_id=prod_data.get('supplier_id') if str(prod_data.get('supplier_id')).lower() != 'manual' else None,
                        harga_beli=HARGA_BELI_DEFAULT, harga_jual=HARGA_JUAL_DEFAULT, is_manual=True)
                    new_product.lapaks.append(lapak)
                    db.session.add(new_product)
                    db.session.flush()
                    product_id = new_product.id
                else: continue 

            product = Product.query.get(product_id)
            if not product: continue
            
            jumlah_terjual = max(0, stok_awal - stok_akhir)
            total_harga_jual = jumlah_terjual * product.harga_jual
            total_harga_beli = jumlah_terjual * product.harga_beli

            rincian = LaporanHarianProduk(laporan_id=new_report.id, product_id=product.id, stok_awal=stok_awal, stok_akhir=stok_akhir, jumlah_terjual=jumlah_terjual, total_harga_jual=total_harga_jual, total_harga_beli=total_harga_beli)
            db.session.add(rincian)
            db.session.add(StokHarian(lapak_id=lapak_id, product_id=product.id, jumlah_sisa=stok_akhir, tanggal=today))
            total_pendapatan_auto += total_harga_jual
            total_biaya_auto += total_harga_beli
            total_terjual_auto += jumlah_terjual
        
        new_report.total_pendapatan = total_pendapatan_auto
        new_report.total_biaya_supplier = total_biaya_auto
        new_report.total_produk_terjual = total_terjual_auto

        db.session.commit()
        return jsonify({"success": True, "message": "Laporan harian berhasil dikirim!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Gagal menyimpan laporan: {str(e)}"}), 500

@app.route('/api/get_history_laporan/<int:lapak_id>', methods=['GET'])
def get_history_laporan(lapak_id):
    try:
        reports = LaporanHarian.query.filter_by(lapak_id=lapak_id).order_by(LaporanHarian.tanggal.desc()).all()
        report_list = [{"id": r.id, "tanggal": r.tanggal.isoformat(), "total_pendapatan": r.total_pendapatan, "total_produk_terjual": r.total_produk_terjual, "status": r.status} for r in reports]
        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- SUPPLIER API ---
@app.route('/api/get_data_supplier/<int:supplier_id>', methods=['GET'])
def get_data_supplier(supplier_id):
    try:
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        balance_info = SupplierBalance.query.filter_by(supplier_id=supplier_id).first()
        total_tagihan = balance_info.balance if balance_info else 0.0
        penjualan_bulan_ini = db.session.query(
            func.sum(LaporanHarianProduk.total_harga_beli)
        ).join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .filter(Product.supplier_id == supplier_id, LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        return jsonify({"success": True, "summary": {"total_tagihan": total_tagihan, "penjualan_bulan_ini": penjualan_bulan_ini}})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_supplier_history/<int:supplier_id>', methods=['GET'])
def get_supplier_history(supplier_id):
    try:
        # Ambil parameter tanggal dari request
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # Query dasar
        payments_query = PembayaranSupplier.query.filter_by(supplier_id=supplier_id)
        sales_query = db.session.query(
            LaporanHarian.tanggal, Lapak.lokasi, Product.nama_produk,
            LaporanHarianProduk.jumlah_terjual, LaporanHarianProduk.total_harga_beli
        ).select_from(LaporanHarianProduk)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Lapak, Lapak.id == LaporanHarian.lapak_id)\
         .filter(Product.supplier_id == supplier_id, LaporanHarian.status == 'Terkonfirmasi')

        # Terapkan filter tanggal jika ada
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
            sales_query = sales_query.filter(LaporanHarian.tanggal >= start_date)
        
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
            sales_query = sales_query.filter(LaporanHarian.tanggal <= end_date)

        # Eksekusi query setelah filter diterapkan
        payments = payments_query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        sales = sales_query.order_by(LaporanHarian.tanggal.desc(), Lapak.lokasi).all()

        # Proses hasil
        payment_list = [{"tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'), "jumlah": p.jumlah_pembayaran, "metode": p.metode_pembayaran} for p in payments]
        sales_list = [{"tanggal": s.tanggal.strftime('%Y-%m-%d'), "lokasi": s.lokasi, "nama_produk": s.nama_produk, "terjual": s.jumlah_terjual, "total_harga_beli": s.total_harga_beli} for s in sales]
        
        return jsonify({"success": True, "payments": payment_list, "sales": sales_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_report_details/<int:report_id>')
def get_report_details(report_id):
    try:
        report = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab),
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
        ).get(report_id)

        if not report:
            return jsonify({"success": False, "message": "Laporan tidak ditemukan"}), 404

        rincian_produk = []
        for item in report.rincian_produk:
            rincian_produk.append({
                "nama_produk": item.product.nama_produk,
                "supplier": item.product.supplier.nama_supplier if item.product.supplier else "Manual",
                "stok_awal": item.stok_awal,
                "stok_akhir": item.stok_akhir,
                "terjual": item.jumlah_terjual,
                "harga_jual": item.product.harga_jual,
                "total_pendapatan": item.total_harga_jual,
            })

        data = {
            "id": report.id,
            "tanggal": report.tanggal.strftime('%d %B %Y'),
            "status": report.status,
            "lokasi": report.lapak.lokasi,
            "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
            "rincian_produk": rincian_produk,
            "rekap_otomatis": {
                "terjual_cash": report.pendapatan_cash,
                "terjual_qris": report.pendapatan_qris,
                "terjual_bca": report.pendapatan_bca,
                "total_produk_terjual": report.total_produk_terjual,
                "total_pendapatan": report.total_pendapatan,
                "total_biaya_supplier": report.total_biaya_supplier
            },
            "rekap_manual": {
                "terjual_cash": report.manual_pendapatan_cash,
                "terjual_qris": report.manual_pendapatan_qris,
                "terjual_bca": report.manual_pendapatan_bca,
                "total_produk_terjual": sum(p['terjual'] for p in rincian_produk),
                "total_pendapatan": report.manual_total_pendapatan
            }
        }
        return jsonify({"success": True, "data": data})

    except Exception as e:
        logging.error(f"Error getting report details: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan pada server"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)