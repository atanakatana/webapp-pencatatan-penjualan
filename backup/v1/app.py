import datetime
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func, or_
from sqlalchemy.orm import joinedload, aliased
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

class BarangMasuk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    tanggal = db.Column(db.DateTime, default=datetime.datetime.now)
    product = db.relationship('Product')
    lapak = db.relationship('Lapak')

class BarangReturn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    laporan_id = db.Column(db.Integer, db.ForeignKey('laporan_harian.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    catatan = db.Column(db.Text, nullable=True)
    product = db.relationship('Product')

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
    uang_pertama = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='Menunggu Konfirmasi')
    manual_uang_pertama = db.Column(db.Float, nullable=True)
    manual_pendapatan_cash = db.Column(db.Float, nullable=True)
    manual_pendapatan_qris = db.Column(db.Float, nullable=True)
    manual_pendapatan_bca = db.Column(db.Float, nullable=True)
    manual_total_pendapatan = db.Column(db.Float, nullable=True)
    manual_total_produk_terjual = db.Column(db.Integer, nullable=True)
    rincian_produk = db.relationship('LaporanHarianProduk', backref='laporan', lazy=True, cascade="all, delete-orphan")
    returns = db.relationship('BarangReturn', backref='laporan', lazy=True, cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint('lapak_id', 'tanggal', name='_lapak_tanggal_uc'),)

class LaporanHarianProduk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    laporan_id = db.Column(db.Integer, db.ForeignKey('laporan_harian.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    terjual_cash = db.Column(db.Integer, nullable=False, default=0)
    terjual_qris = db.Column(db.Integer, nullable=False, default=0)
    terjual_bca = db.Column(db.Integer, nullable=False, default=0)
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
    metode_pembayaran = db.Column(db.String(20), nullable=False) # DANA, BCA
    supplier = db.relationship('Supplier')

# ===================================================================
# PERINTAH COMMAND LINE DATABASE
# ===================================================================
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Database telah diinisialisasi.")

@app.cli.command("seed-db")
def seed_db_command():
    db.drop_all()
    db.create_all()
    owner = Admin(nama_lengkap="Owner Utama", nik="0000000000000000", username="owner", email="owner@app.com", nomor_kontak="0", password="owner")
    db.session.add(owner)
    db.session.commit()
    print("Database di-seed HANYA dengan akun Owner.")

# ===================================================================
# RUTE HALAMAN HTML
# ===================================================================
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
        lapak_list = [{
            "id": l.id, "lokasi": l.lokasi, 
            "penanggung_jawab": f"{l.penanggung_jawab.nama_lengkap}",
            "nomor_kontak": l.penanggung_jawab.nomor_kontak,
            "user_id": l.user_id,
            "anggota": [{"id": a.id, "nama": a.nama_lengkap} for a in l.anggota],
            "anggota_ids": [a.id for a in l.anggota]
        } for l in lapaks]
        supplier_list = [{"id": s.id, "nama_supplier": s.nama_supplier, "username": s.username, "kontak": s.kontak, "nomor_register": s.nomor_register, "alamat": s.alamat, "password": s.password} for s in suppliers]
        
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        
        total_pendapatan_bulan_ini = db.session.query(func.sum(LaporanHarian.total_pendapatan)).filter(LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        total_biaya_bulan_ini = db.session.query(func.sum(PembayaranSupplier.jumlah_pembayaran)).filter(PembayaranSupplier.tanggal_pembayaran >= start_of_month).scalar() or 0

        return jsonify({
            "admin_data": admin_list, 
            "lapak_data": lapak_list, 
            "supplier_data": supplier_list, 
            "summary": {
                "pendapatan_bulan_ini": total_pendapatan_bulan_ini, 
                "biaya_bulan_ini": total_biaya_bulan_ini
            }
        })
    except Exception as e:
        app.logger.error(f"Error in get_owner_data: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

@app.route('/api/add_admin', methods=['POST'])
def add_admin():
    data = request.json
    if data['password'] != data['password_confirm']:
        return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
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
    if data.get('password') and data['password'] != data['password_confirm']:
        return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        admin.nama_lengkap = data['nama_lengkap']
        admin.nik = data['nik']
        admin.username = data['username']
        admin.email = data['email']
        admin.nomor_kontak = data['nomor_kontak']
        if data.get('password'):
            admin.password = data['password']
        db.session.commit()
        return jsonify({"success": True, "message": "Data Admin berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username, NIK, atau email sudah digunakan oleh admin lain."}), 400

@app.route('/api/delete_admin/<int:admin_id>', methods=['DELETE'])
def delete_admin(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    if Lapak.query.filter_by(user_id=admin_id).first():
        return jsonify({"success": False, "message": "Gagal menghapus: Admin ini adalah Penanggung Jawab sebuah lapak."}), 400
    db.session.delete(admin)
    db.session.commit()
    return jsonify({"success": True, "message": "Admin berhasil dihapus"})

@app.route('/api/add_lapak', methods=['POST'])
def add_lapak():
    data = request.json
    try:
        new_lapak = Lapak(lokasi=data['lokasi'], user_id=data['user_id'])
        anggota_ids = data.get('anggota_ids', [])
        if anggota_ids:
            new_lapak.anggota = Admin.query.filter(Admin.id.in_(anggota_ids)).all()
        db.session.add(new_lapak)
        db.session.commit()
        return jsonify({"success": True, "message": "Lapak berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Nama lokasi lapak sudah ada."}), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in add_lapak: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

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
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in update_lapak: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/api/delete_lapak/<int:lapak_id>', methods=['DELETE'])
def delete_lapak(lapak_id):
    lapak = Lapak.query.get_or_404(lapak_id)
    db.session.delete(lapak)
    db.session.commit()
    return jsonify({"success": True, "message": "Lapak berhasil dihapus"})

@app.route('/api/get_next_supplier_reg_number', methods=['GET'])
def get_next_supplier_reg_number():
    count = Supplier.query.count()
    next_id = count + 1
    return jsonify({"success": True, "reg_number": f"REG{next_id:03d}"})

@app.route('/api/add_supplier', methods=['POST'])
def add_supplier():
    data = request.json
    if data['password'] != data['password_confirm']:
        return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
        
    try:
        new_supplier = Supplier(
            nama_supplier=data['nama_supplier'], username=data.get('username'), kontak=data.get('kontak'), 
            nomor_register=data.get('nomor_register'), alamat=data.get('alamat'), password=data['password']
        )
        new_supplier.balance = SupplierBalance(balance=0.0)
        db.session.add(new_supplier)
        db.session.flush() 

        selected_lapak_ids = data.get('lapak_ids', [])
        lapaks_to_associate = Lapak.query.filter(Lapak.id.in_(selected_lapak_ids)).all()
        
        for p_data in data.get('products', []):
            if p_data.get('name'):
                new_product = Product(
                    nama_produk=p_data['name'], 
                    supplier_id=new_supplier.id,
                    harga_beli=float(p_data.get('harga_beli', HARGA_BELI_DEFAULT)),
                    harga_jual=float(p_data.get('harga_jual', HARGA_JUAL_DEFAULT))
                )
                if lapaks_to_associate:
                    new_product.lapaks.extend(lapaks_to_associate)
                db.session.add(new_product)
        
        db.session.commit()
        return jsonify({"success": True, "message": "Supplier, produk, dan alokasi lapak berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username atau Nomor Register sudah ada."}), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in add_supplier: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/api/update_supplier/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    data = request.json
    supplier = Supplier.query.get_or_404(supplier_id)
    if data.get('password') and data['password'] != data['password_confirm']:
        return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        supplier.nama_supplier = data['nama_supplier']
        supplier.username = data.get('username')
        supplier.kontak = data.get('kontak')
        supplier.nomor_register = data.get('nomor_register')
        supplier.alamat = data.get('alamat')
        if data.get('password'):
            supplier.password = data['password']
        db.session.commit()
        return jsonify({"success": True, "message": "Data Supplier berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username atau Nomor Register sudah digunakan."}), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in update_supplier: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/api/delete_supplier/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({"success": True, "message": "Supplier berhasil dihapus"})

@app.route('/api/get_report_details/<int:report_id>', methods=['GET'])
def get_report_details(report_id):
    try:
        report = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab),
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
        ).get(report_id)

        if not report:
            return jsonify({"success": False, "message": "Laporan tidak ditemukan"}), 404

        details = {
            "id": report.id,
            "lokasi": report.lapak.lokasi,
            "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
            "tanggal": report.tanggal.strftime("%d %B %Y"),
            "status": report.status,
            "rincian_produk": sorted([{
                "nama_produk": r.product.nama_produk,
                "supplier": r.product.supplier.nama_supplier if r.product.supplier else "Manual",
                "stok_awal": r.stok_awal,
                "stok_akhir": r.stok_akhir,
                "terjual": r.jumlah_terjual,
                "harga_jual": r.product.harga_jual,
                "total_pendapatan": r.total_harga_jual
            } for r in report.rincian_produk], key=lambda x: x['nama_produk']),
            "rekap_otomatis": {
                "uang_pertama": report.uang_pertama or 0,
                "terjual_cash": report.pendapatan_cash or 0,
                "terjual_qris": report.pendapatan_qris or 0,
                "terjual_bca": report.pendapatan_bca or 0,
                "total_pendapatan": report.total_pendapatan or 0,
                "total_produk_terjual": report.total_produk_terjual or 0,
                "total_biaya_supplier": report.total_biaya_supplier or 0
            },
            "rekap_manual": {
                "uang_pertama": report.manual_uang_pertama or 0,
                "terjual_cash": report.manual_pendapatan_cash or 0,
                "terjual_qris": report.manual_pendapatan_qris or 0,
                "terjual_bca": report.manual_pendapatan_bca or 0,
                "total_pendapatan": report.manual_total_pendapatan or 0,
                "total_produk_terjual": report.manual_total_produk_terjual or 0,
            }
        }
        return jsonify({"success": True, "data": details})
    except Exception as e:
        app.logger.error(f"Error getting report details: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_laporan_pendapatan_harian', methods=['GET'])
def get_laporan_pendapatan_harian():
    date_str = request.args.get('date', datetime.date.today().isoformat())
    target_date = datetime.date.fromisoformat(date_str)
    
    laporan_query = db.session.query(LaporanHarian).options(
        joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab),
        joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
    ).filter(LaporanHarian.tanggal == target_date, LaporanHarian.status == 'Terkonfirmasi').all()
    
    total_harian = sum(l.total_pendapatan for l in laporan_query)
    laporan_per_lapak = []
    for laporan in laporan_query:
        rincian = [{
            "produk": r.product.nama_produk, 
            "supplier": r.product.supplier.nama_supplier if r.product.supplier else "Manual",
            "jumlah": r.jumlah_terjual, 
            "pendapatan": r.total_harga_jual,
            "stok_awal": r.stok_awal,
            "stok_akhir": r.stok_akhir
        } for r in laporan.rincian_produk]

        laporan_per_lapak.append({
            "lokasi": laporan.lapak.lokasi, "penanggung_jawab": laporan.lapak.penanggung_jawab.nama_lengkap,
            "total_pendapatan": laporan.total_pendapatan,
            "rincian_pendapatan": rincian
        })

    return jsonify({"total_harian": total_harian, "laporan_per_lapak": laporan_per_lapak})

@app.route('/api/get_laporan_biaya_harian', methods=['GET'])
def get_laporan_biaya_harian():
    date_str = request.args.get('date', datetime.date.today().isoformat())
    target_date = datetime.date.fromisoformat(date_str)
    
    biaya_query = db.session.query(
        Lapak, func.sum(LaporanHarian.total_biaya_supplier)
    ).join(LaporanHarian, Lapak.id == LaporanHarian.lapak_id)\
     .filter(LaporanHarian.tanggal == target_date, LaporanHarian.status == 'Terkonfirmasi')\
     .group_by(Lapak.id).all()

    total_biaya_harian = sum(item[1] for item in biaya_query if item[1] is not None)
    laporan_per_lapak = []
    
    for lapak, total_biaya in biaya_query:
        rincian_produk = db.session.query(
            Product.nama_produk, Supplier.nama_supplier,
            LaporanHarianProduk.jumlah_terjual, LaporanHarianProduk.total_harga_beli
        ).join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .outerjoin(Supplier, Supplier.id == Product.supplier_id)\
         .filter(LaporanHarian.lapak_id == lapak.id, LaporanHarian.tanggal == target_date, LaporanHarian.status == 'Terkonfirmasi').all()
        
        laporan_per_lapak.append({
            "lokasi": lapak.lokasi, "penanggung_jawab": lapak.penanggung_jawab.nama_lengkap,
            "total_biaya": total_biaya or 0,
            "rincian_biaya": [{"produk": nama, "supplier": supplier if supplier else "Manual", "jumlah": jumlah, "biaya": biaya} for nama, supplier, jumlah, biaya in rincian_produk]
        })
        
    return jsonify({"total_harian": total_biaya_harian, "laporan_per_lapak": laporan_per_lapak})

@app.route('/api/get_unconfirmed_reports')
def get_unconfirmed_reports():
    try:
        unconfirmed_reports = LaporanHarian.query.options(joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab)).filter_by(status='Menunggu Konfirmasi').order_by(LaporanHarian.tanggal.desc()).all()
        report_list = [{"id": r.id, "lokasi": r.lapak.lokasi, "penanggung_jawab": r.lapak.penanggung_jawab.nama_lengkap, "tanggal": r.tanggal.isoformat(), "total_pendapatan": r.total_pendapatan, "total_produk_terjual": r.total_produk_terjual, "status": r.status} for r in unconfirmed_reports]
        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        app.logger.error(f"Error in get_unconfirmed_reports: {e}", exc_info=True)
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
            if balance:
                balance.balance += cost
            else:
                db.session.add(SupplierBalance(supplier_id=supplier_id, balance=cost))

        db.session.commit()
        return jsonify({"success": True, "message": "Laporan berhasil dikonfirmasi dan tagihan supplier diperbarui."})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in confirm_report: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500
        
# --- LAPAK API ---
@app.route('/api/get_barang_masuk_today/<int:lapak_id>', methods=['GET'])
def get_barang_masuk_today(lapak_id):
    try:
        today = datetime.date.today()
        barang_masuk_hari_ini = db.session.query(
            BarangMasuk.id,
            Product.nama_produk,
            BarangMasuk.jumlah,
            BarangMasuk.tanggal
        ).join(Product, Product.id == BarangMasuk.product_id)\
         .filter(
            BarangMasuk.lapak_id == lapak_id,
            func.date(BarangMasuk.tanggal) == today
        ).order_by(BarangMasuk.tanggal.desc()).all()

        barang_masuk_list = [{
            "id": entry.id,
            "nama_produk": entry.nama_produk,
            "jumlah": entry.jumlah,
            "waktu": entry.tanggal.strftime('%H:%M:%S')
        } for entry in barang_masuk_hari_ini]

        return jsonify({"success": True, "data": barang_masuk_list})
    except Exception as e:
        app.logger.error(f"Error in get_barang_masuk_today: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/api/delete_barang_masuk/<int:entry_id>', methods=['DELETE'])
def delete_barang_masuk(entry_id):
    try:
        entry = BarangMasuk.query.get(entry_id)
        if not entry:
            return jsonify({"success": False, "message": "Data barang masuk tidak ditemukan."}), 404

        today = datetime.date.today()
        laporan_terkunci = LaporanHarian.query.filter_by(
            lapak_id=entry.lapak_id,
            tanggal=today
        ).first()

        if laporan_terkunci:
            return jsonify({"success": False, "message": "Gagal menghapus: Laporan harian untuk hari ini sudah dibuat dan dikunci."}), 403

        db.session.delete(entry)
        db.session.commit()
        return jsonify({"success": True, "message": "Data barang masuk berhasil dihapus."})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in delete_barang_masuk: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

@app.route('/api/get_data_lapak/<int:lapak_id>', methods=['GET'])
def get_data_lapak(lapak_id):
    try:
        lapak = Lapak.query.get_or_404(lapak_id)
        suppliers_from_products = Supplier.query.join(Product).join(product_lapak_association).filter(
            product_lapak_association.c.lapak_id == lapak_id
        ).distinct().all()
        manual_products = Product.query.filter(Product.lapaks.any(id=lapak_id), Product.is_manual==True).all()
        
        products_by_supplier = {str(s.id): [{"id": p.id, "name": p.nama_produk} for p in s.products if lapak in p.lapaks] for s in suppliers_from_products}
        
        if manual_products:
            products_by_supplier['manual'] = [{"id": p.id, "name": p.nama_produk} for p in manual_products]
        
        supplier_list = [{"id": str(s.id), "nama_supplier": s.nama_supplier} for s in suppliers_from_products]
        if manual_products:
            supplier_list.append({"id": "manual", "nama_supplier": "Produk Manual"})

        return jsonify({
            "products_by_supplier": products_by_supplier, 
            "suppliers": supplier_list
        })
    except Exception as e:
        app.logger.error(f"Error in get_data_lapak: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan internal server: {e}"}), 500
    
@app.route('/api/add_manual_product', methods=['POST'])
def add_manual_product():
    data = request.json
    lapak_id = data.get('lapak_id')
    jumlah_stok = int(data.get('jumlah_stok', 0))
    try:
        new_product = Product(nama_produk=data['nama_produk'], harga_beli=float(data['harga_beli']), harga_jual=float(data['harga_jual']), is_manual=True, supplier_id=None)
        lapak = Lapak.query.get(lapak_id)
        if not lapak: return jsonify({"success": False, "message": "Lapak tidak ditemukan."}), 404
        new_product.lapaks.append(lapak)
        db.session.add(new_product)
        db.session.flush()

        if jumlah_stok > 0:
            barang_masuk = BarangMasuk(product_id=new_product.id, lapak_id=lapak_id, jumlah=jumlah_stok)
            db.session.add(barang_masuk)

        db.session.commit()
        return jsonify({"success": True, "message": f"Produk '{new_product.nama_produk}' dengan stok {jumlah_stok} berhasil ditambahkan."})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in add_manual_product: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Gagal menambahkan produk: {str(e)}"}), 500

@app.route('/api/get_data_buat_catatan/<int:lapak_id>', methods=['GET'])
def get_data_buat_catatan(lapak_id):
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    existing_report = LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first()
    if existing_report:
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah dibuat.", "already_exists": True}), 409

    products_at_lapak = Product.query.filter(Product.lapaks.any(id=lapak_id)).all()
    product_details = []
    for p in products_at_lapak:
        sisa_kemarin_entry = StokHarian.query.filter_by(product_id=p.id, lapak_id=lapak_id, tanggal=yesterday).first()
        sisa_kemarin = sisa_kemarin_entry.jumlah_sisa if sisa_kemarin_entry else 0
        
        masuk_hari_ini = db.session.query(func.sum(BarangMasuk.jumlah)).filter(
            BarangMasuk.product_id == p.id, BarangMasuk.lapak_id == lapak_id,
            func.date(BarangMasuk.tanggal) == today
        ).scalar() or 0
        
        stok_awal = sisa_kemarin + masuk_hari_ini
        supplier_name = p.supplier.nama_supplier if p.supplier else "Manual"
        product_details.append({"id": p.id, "name": p.nama_produk, "harga_jual": p.harga_jual, "harga_beli": p.harga_beli, "stok_awal": stok_awal, "supplier_name": supplier_name})
        
    return jsonify({"success": True, "products": product_details})

@app.route('/api/add_barang_masuk', methods=['POST'])
def add_barang_masuk():
    data = request.json
    lapak_id = data.get('lapak_id')
    products = data.get('products', [])
    try:
        for p in products:
            if p.get('qty') and int(p.get('qty')) > 0:
                db.session.add(BarangMasuk(product_id=p['id'], lapak_id=lapak_id, jumlah=p['qty']))
        db.session.commit()
        return jsonify({"success": True, "message": "Penerimaan barang berhasil dicatat!"})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in add_barang_masuk: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Gagal mencatat: {str(e)}"}), 500

@app.route('/api/submit_catatan_harian', methods=['POST'])
def submit_catatan_harian():
    data = request.json
    lapak_id = data.get('lapak_id')
    today = datetime.date.today()
    if LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first():
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah pernah dibuat."}), 400
    try:
        total_pendapatan_auto, total_biaya_auto, total_cash_auto, total_qris_auto, total_bca_auto, total_terjual_auto = 0.0, 0.0, 0.0, 0.0, 0.0, 0
        
        product_ids = [p['id'] for p in data.get('products', [])]
        products_in_db = {p.id: p for p in Product.query.filter(Product.id.in_(product_ids)).all()}

        for prod_data in data.get('products', []):
            product = products_in_db.get(int(prod_data['id']))
            if not product: continue

            terjual_cash = int(prod_data.get('terjual_cash') or 0)
            terjual_qris = int(prod_data.get('terjual_qris') or 0)
            terjual_bca = int(prod_data.get('terjual_bca') or 0)
            total_terjual_produk = terjual_cash + terjual_qris + terjual_bca

            if total_terjual_produk > 0:
                pendapatan_produk = total_terjual_produk * product.harga_jual
                biaya_produk = total_terjual_produk * product.harga_beli

                total_pendapatan_auto += pendapatan_produk
                total_biaya_auto += biaya_produk
                total_cash_auto += terjual_cash * product.harga_jual
                total_qris_auto += terjual_qris * product.harga_jual
                total_bca_auto += terjual_bca * product.harga_jual
                total_terjual_auto += total_terjual_produk
        
        new_report = LaporanHarian(
            lapak_id=lapak_id,
            tanggal=today,
            uang_pertama=data.get('uang_pertama'),
            total_pendapatan=total_pendapatan_auto,
            total_biaya_supplier=total_biaya_auto,
            pendapatan_cash=total_cash_auto,
            pendapatan_qris=total_qris_auto,
            pendapatan_bca=total_bca_auto,
            total_produk_terjual=total_terjual_auto,
            manual_uang_pertama=data['rekap_manual'].get('uang_pertama'),
            manual_pendapatan_cash=data['rekap_manual'].get('total_cash'),
            manual_pendapatan_qris=data['rekap_manual'].get('total_qris'),
            manual_pendapatan_bca=data['rekap_manual'].get('total_bca'),
            manual_total_pendapatan=data['rekap_manual'].get('total_uang'),
            manual_total_produk_terjual=data['rekap_manual'].get('total_barang')
        )
        db.session.add(new_report)
        db.session.flush()

        for prod_data in data.get('products', []):
            product = products_in_db.get(int(prod_data['id']))
            if not product: continue
            
            stok_akhir = int(prod_data.get('sisa_akhir') or 0)
            db.session.add(StokHarian(lapak_id=lapak_id, product_id=product.id, jumlah_sisa=stok_akhir, tanggal=today))
            
            terjual_cash = int(prod_data.get('terjual_cash') or 0)
            terjual_qris = int(prod_data.get('terjual_qris') or 0)
            terjual_bca = int(prod_data.get('terjual_bca') or 0)
            total_terjual_produk = terjual_cash + terjual_qris + terjual_bca

            if total_terjual_produk > 0:
                rincian = LaporanHarianProduk(
                    laporan_id=new_report.id, product_id=product.id,
                    stok_awal=int(prod_data.get('stok_awal') or 0), stok_akhir=stok_akhir,
                    terjual_cash=terjual_cash, terjual_qris=terjual_qris, terjual_bca=terjual_bca,
                    jumlah_terjual=total_terjual_produk, total_harga_jual=total_terjual_produk * product.harga_jual,
                    total_harga_beli=total_terjual_produk * product.harga_beli
                )
                db.session.add(rincian)
        
        for return_data in data.get('returns', []):
            if return_data.get('product_id') and int(return_data.get('jumlah') or 0) > 0:
                db.session.add(BarangReturn(laporan_id=new_report.id, product_id=return_data['product_id'], jumlah=return_data['jumlah'], catatan=return_data.get('catatan')))
        
        db.session.commit()
        return jsonify({"success": True, "message": "Laporan harian berhasil dikirim!"})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error submitting daily report: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Gagal menyimpan laporan: {str(e)}"}), 500


@app.route('/api/get_history_laporan/<int:lapak_id>', methods=['GET'])
def get_history_laporan(lapak_id):
    try:
        reports = LaporanHarian.query.filter_by(lapak_id=lapak_id).order_by(LaporanHarian.tanggal.desc()).all()
        report_list = [{"id": r.id, "tanggal": r.tanggal.isoformat(), "total_pendapatan": r.total_pendapatan, "total_produk_terjual": r.total_produk_terjual, "status": r.status} for r in reports]
        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        app.logger.error(f"Error in get_history_laporan: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

# --- SUPPLIER API ---
@app.route('/api/get_data_supplier/<int:supplier_id>', methods=['GET'])
def get_data_supplier(supplier_id):
    try:
        today = datetime.date.today()
        start_of_month = today.replace(day=1)

        # 1. Mengambil total tagihan saat ini dari SupplierBalance
        balance_info = SupplierBalance.query.filter_by(supplier_id=supplier_id).first()
        total_tagihan = balance_info.balance if balance_info else 0.0

        # 2. Menghitung total penjualan (berdasarkan harga beli) bulan ini
        penjualan_bulan_ini = db.session.query(
            func.sum(LaporanHarianProduk.total_harga_beli)
        ).join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .filter(
            Product.supplier_id == supplier_id,
            LaporanHarian.tanggal >= start_of_month,
            LaporanHarian.status == 'Terkonfirmasi'
        ).scalar() or 0
        
        return jsonify({
            "success": True,
            "summary": {
                "total_tagihan": total_tagihan,
                "penjualan_bulan_ini": penjualan_bulan_ini
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting supplier dashboard data: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_supplier_history/<int:supplier_id>', methods=['GET'])
def get_supplier_history(supplier_id):
    try:
        payments = PembayaranSupplier.query.filter_by(supplier_id=supplier_id).order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        payment_list = [{
            "tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'),
            "jumlah": p.jumlah_pembayaran,
            "metode": p.metode_pembayaran
        } for p in payments]

        sales = db.session.query(
            LaporanHarian.tanggal,
            Lapak.lokasi,
            Product.nama_produk,
            LaporanHarianProduk.jumlah_terjual,
            LaporanHarianProduk.total_harga_beli
        ).select_from(LaporanHarianProduk)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Lapak, Lapak.id == LaporanHarian.lapak_id)\
         .filter(Product.supplier_id == supplier_id, LaporanHarian.status == 'Terkonfirmasi')\
         .order_by(LaporanHarian.tanggal.desc(), Lapak.lokasi).all()

        sales_list = [{
            "tanggal": s.tanggal.strftime('%Y-%m-%d'),
            "lokasi": s.lokasi,
            "nama_produk": s.nama_produk,
            "terjual": s.jumlah_terjual,
            "total_harga_beli": s.total_harga_beli
        } for s in sales]

        return jsonify({
            "success": True,
            "payments": payment_list,
            "sales": sales_list
        })
    except Exception as e:
        app.logger.error(f"Error getting supplier history: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

# --- API PEMBAYARAN SUPPLIER ---
@app.route('/api/get_pembayaran_data', methods=['GET'])
def get_pembayaran_data():
    try:
        suppliers = Supplier.query.options(joinedload(Supplier.balance)).all()
        result = []
        for s in suppliers:
            total_tagihan = s.balance.balance if s.balance else 0.0
            
            result.append({
                "supplier_id": s.id,
                "nama_supplier": s.nama_supplier,
                "total_tagihan": total_tagihan
            })
        return jsonify({"success": True, "data": result})
    except Exception as e:
        app.logger.error(f"Error getting payment data: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/submit_pembayaran', methods=['POST'])
def submit_pembayaran():
    data = request.json
    supplier_id = data.get('supplier_id')
    jumlah_dibayar = float(data.get('jumlah_pembayaran', 0))
    metode = data.get('metode_pembayaran')

    if not all([supplier_id, jumlah_dibayar, metode]):
        return jsonify({"success": False, "message": "Data tidak lengkap."}), 400

    balance = SupplierBalance.query.filter_by(supplier_id=supplier_id).first()
    if not balance or balance.balance < (jumlah_dibayar - 0.01):
        return jsonify({"success": False, "message": f"Jumlah pembayaran (Rp {jumlah_dibayar:,.0f}) melebihi total tagihan (Rp {balance.balance:,.0f})."}), 400

    try:
        new_payment = PembayaranSupplier(
            supplier_id=supplier_id,
            jumlah_pembayaran=jumlah_dibayar,
            metode_pembayaran=metode
        )
        db.session.add(new_payment)
        balance.balance -= jumlah_dibayar
        
        db.session.commit()
        return jsonify({"success": True, "message": f"Pembayaran sebesar Rp {jumlah_dibayar:,.0f} kepada supplier berhasil dicatat."})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in submit_pembayaran: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)

