import datetime
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from sqlalchemy.orm import joinedload

# Inisialisasi aplikasi Flask
app = Flask(__name__)
# Konfigurasi database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///penjualan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inisialisasi SQLAlchemy
db = SQLAlchemy(app)

# ===================================================================
# DEFINISI MODEL DATABASE
# ===================================================================

class User(db.Model):
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
    nama_alias = db.Column(db.String(20), unique=True, nullable=True)
    kontak = db.Column(db.String(20), nullable=True)
    nomor_register = db.Column(db.String(50), unique=True, nullable=True)
    alamat = db.Column(db.Text, nullable=True)
    bank = db.Column(db.String(50), nullable=True)
    nomor_rekening = db.Column(db.String(50), nullable=True)
    password = db.Column(db.String(120), nullable=False)
    products = db.relationship('Product', backref='supplier', lazy=True, cascade="all, delete-orphan")

class Lapak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lokasi = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('lapak', uselist=False))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_produk = db.Column(db.String(100), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)

class BarangMasuk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    tanggal = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    product = db.relationship('Product')
    lapak = db.relationship('Lapak')

class Penjualan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    metode_pembayaran = db.Column(db.String(10), nullable=False)
    tanggal = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    product = db.relationship('Product')
    lapak = db.relationship('Lapak')

class MasalahReturn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    jenis_laporan = db.Column(db.String(50), nullable=False)
    detail_masalah = db.Column(db.String(100), nullable=True)
    jumlah = db.Column(db.Integer, nullable=True)
    catatan = db.Column(db.Text, nullable=True)
    tanggal = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    product = db.relationship('Product')

class LaporanHarian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    tanggal = db.Column(db.Date, nullable=False, default=datetime.date.today)
    total_pendapatan = db.Column(db.Float, nullable=False)
    pendapatan_cash = db.Column(db.Float, nullable=False)
    pendapatan_qris = db.Column(db.Float, nullable=False)
    total_produk_terjual = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Terkonfirmasi')
    __table_args__ = (db.UniqueConstraint('lapak_id', 'tanggal', name='_lapak_tanggal_uc'),)


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
    owner = User(nama_lengkap="Owner Utama", nik="0000000000000000", username="owner", email="owner@app.com", nomor_kontak="0", password="owner")
    db.session.add(owner)
    db.session.commit()
    print("Database di-seed HANYA dengan akun Owner.")

# ===================================================================
# RUTE / ENDPOINTS APLIKASI
# ===================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def handle_login():
    data = request.json
    username = data.get('username').lower()
    password = data.get('password')
    user = User.query.filter(db.func.lower(User.username) == username).first()
    if user and user.password == password:
        if user.username == 'owner':
            return jsonify({"success": True, "role": "owner"})
        else:
            return jsonify({"success": True, "role": "lapak", "user_info": {"nama_lengkap": user.nama_lengkap, "lapak_id": user.lapak.id if user.lapak else None}})
    supplier = Supplier.query.filter(db.func.lower(Supplier.nama_alias) == username).first()
    if supplier and supplier.password == password:
        return jsonify({"success": True, "role": "supplier", "user_info": {"nama_supplier": supplier.nama_supplier,"supplier_id": supplier.id}})
    return jsonify({"success": False, "message": "Username atau password salah"}), 401

# --- DATA GETTER ENDPOINTS ---
@app.route('/get_data_owner', methods=['GET'])
def get_owner_data():
    users = User.query.filter(User.username != 'owner').all()
    lapaks = Lapak.query.all()
    suppliers = Supplier.query.all()
    user_list = [{"nama_lengkap": u.nama_lengkap, "nik": u.nik, "username": u.username, "email": u.email, "nomor_kontak": u.nomor_kontak} for u in users]
    lapak_list = [{"lokasi": l.lokasi, "penanggung_jawab": f"{l.user.nama_lengkap} ({l.user.username})", "nomor_kontak": l.user.nomor_kontak} for l in lapaks]
    supplier_list = [{"nama_supplier": s.nama_supplier, "kontak": s.kontak, "nomor_register": s.nomor_register} for s in suppliers]
    today = datetime.date.today()
    start_of_month = today.replace(day=1)
    total_pendapatan_bulan_ini = db.session.query(func.sum(LaporanHarian.total_pendapatan)).filter(LaporanHarian.tanggal >= start_of_month).scalar() or 0
    total_biaya_masuk = db.session.query(func.sum(BarangMasuk.jumlah)).filter(func.date(BarangMasuk.tanggal) >= start_of_month).scalar() or 0
    return jsonify({"user_data": user_list, "lapak_data": lapak_list, "supplier_data": supplier_list, "summary": {"pendapatan_bulan_ini": total_pendapatan_bulan_ini, "biaya_bulan_ini": total_biaya_masuk * 8000 }})

@app.route('/get_laporan_biaya_harian')
def get_laporan_biaya_harian():
    date_str = request.args.get('date', datetime.date.today().isoformat())
    target_date = datetime.date.fromisoformat(date_str)
    start_of_day = datetime.datetime.combine(target_date, datetime.time.min)
    end_of_day = datetime.datetime.combine(target_date, datetime.time.max)

    biaya_query = db.session.query(
        Supplier.nama_supplier,
        Supplier.nomor_register,
        Lapak.lokasi,
        User.username,
        User.nama_lengkap,
        func.sum(BarangMasuk.jumlah).label('total_jumlah')
    ).join(Product, BarangMasuk.product_id == Product.id)\
     .join(Supplier, Product.supplier_id == Supplier.id)\
     .join(Lapak, BarangMasuk.lapak_id == Lapak.id)\
     .join(User, Lapak.user_id == User.id)\
     .filter(BarangMasuk.tanggal.between(start_of_day, end_of_day))\
     .group_by(Supplier.nama_supplier, Supplier.nomor_register, Lapak.lokasi, User.username, User.nama_lengkap)\
     .all()

    rincian = [
        {
            "nama_supplier": row.nama_supplier,
            "reg_supplier": row.nomor_register,
            "username_lapak": row.username,
            "penanggung_jawab_lapak": row.nama_lengkap,
            "nominal": row.total_jumlah * 8000
        } for row in biaya_query
    ]
    total_harian = sum(item['nominal'] for item in rincian)
    return jsonify({"total_harian": total_harian, "rincian_biaya": rincian})


@app.route('/get_laporan_pendapatan_harian')
def get_laporan_pendapatan_harian():
    date_str = request.args.get('date', datetime.date.today().isoformat())
    target_date = datetime.date.fromisoformat(date_str)
    start_of_day = datetime.datetime.combine(target_date, datetime.time.min)
    end_of_day = datetime.datetime.combine(target_date, datetime.time.max)

    sales = db.session.query(Penjualan).options(
        joinedload(Penjualan.lapak).joinedload(Lapak.user),
        joinedload(Penjualan.product).joinedload(Product.supplier)
    ).filter(Penjualan.tanggal.between(start_of_day, end_of_day)).all()

    laporan_per_lapak = {}
    for sale in sales:
        lapak_id = sale.lapak.id
        if lapak_id not in laporan_per_lapak:
            laporan_per_lapak[lapak_id] = {
                "lokasi": sale.lapak.lokasi,
                "username": sale.lapak.user.username,
                "penanggung_jawab": sale.lapak.user.nama_lengkap,
                "total_pendapatan": 0,
                "rincian": []
            }
        
        nominal = sale.jumlah * 15000
        laporan_per_lapak[lapak_id]['total_pendapatan'] += nominal
        laporan_per_lapak[lapak_id]['rincian'].append({
            "produk": sale.product.nama_produk,
            "supplier": sale.product.supplier.nama_supplier,
            "jumlah": sale.jumlah,
            "nominal": nominal
        })
    
    total_harian = sum(l['total_pendapatan'] for l in laporan_per_lapak.values())

    return jsonify({
        "total_harian": total_harian,
        "laporan_per_lapak": list(laporan_per_lapak.values())
    })


@app.route('/get_data_lapak', methods=['GET'])
def get_lapak_data():
    suppliers = Supplier.query.all()
    products = Product.query.all()
    all_products_dict = {p.id: {"name": p.nama_produk, "price": 15000} for p in products}
    products_by_supplier = {s.id: [{"id": p.id, "name": p.nama_produk} for p in s.products] for s in suppliers}
    stock_data = {}
    for p in products:
        total_masuk = db.session.query(func.sum(BarangMasuk.jumlah)).filter_by(product_id=p.id).scalar() or 0
        total_terjual = db.session.query(func.sum(Penjualan.jumlah)).filter_by(product_id=p.id).scalar() or 0
        stock_data[p.id] = total_masuk - total_terjual
    return jsonify({"all_products": all_products_dict, "stock_data": stock_data, "products_by_supplier": products_by_supplier, "suppliers": [{"id": s.id, "nama_supplier": s.nama_supplier} for s in suppliers]})

@app.route('/get_penjualan_harian/<int:lapak_id>', methods=['GET'])
def get_penjualan_harian(lapak_id):
    today = datetime.date.today()
    start_of_day = datetime.datetime.combine(today, datetime.time.min)
    end_of_day = datetime.datetime.combine(today, datetime.time.max)
    sales = Penjualan.query.filter(Penjualan.lapak_id == lapak_id, Penjualan.tanggal.between(start_of_day, end_of_day)).order_by(Penjualan.tanggal.desc()).all()
    sales_list = [{"product_name": sale.product.nama_produk, "qty": sale.jumlah, "payment": sale.metode_pembayaran, "time": sale.tanggal.strftime('%H:%M WIB'), "total": sale.jumlah * 15000} for sale in sales]
    return jsonify(sales_list)
    
@app.route('/get_review_data/<int:lapak_id>')
def get_review_data(lapak_id):
    today = datetime.date.today()
    start_of_day = datetime.datetime.combine(today, datetime.time.min)
    end_of_day = datetime.datetime.combine(today, datetime.time.max)
    
    sales_today = Penjualan.query.filter(Penjualan.lapak_id == lapak_id, Penjualan.tanggal.between(start_of_day, end_of_day)).all()
    sales_list = [{"id": s.id, "productId": s.product_id, "qty": s.jumlah, "payment": s.metode_pembayaran, "time": s.tanggal.strftime('%H:%M WIB')} for s in sales_today]
    
    all_products = {p.id: {"name": p.nama_produk, "price": 15000} for p in Product.query.all()}
    
    stock_awal_hari = {}
    barang_masuk_harian = []
    
    for product_id in all_products.keys():
        total_masuk_sebelumnya = db.session.query(func.sum(BarangMasuk.jumlah)).filter(BarangMasuk.product_id == product_id, BarangMasuk.lapak_id == lapak_id, func.date(BarangMasuk.tanggal) < today).scalar() or 0
        total_terjual_sebelumnya = db.session.query(func.sum(Penjualan.jumlah)).filter(Penjualan.product_id == product_id, Penjualan.lapak_id == lapak_id, func.date(Penjualan.tanggal) < today).scalar() or 0
        stock_awal_hari[product_id] = total_masuk_sebelumnya - total_terjual_sebelumnya
        
        masuk_hari_ini_query = BarangMasuk.query.filter(BarangMasuk.lapak_id == lapak_id, BarangMasuk.product_id == product_id, BarangMasuk.tanggal.between(start_of_day, end_of_day)).all()
        for bm in masuk_hari_ini_query:
            barang_masuk_harian.append({"productId": bm.product_id, "jumlah": bm.jumlah, "productName": bm.product.nama_produk, "supplierName": bm.product.supplier.nama_supplier, "time": bm.tanggal.strftime('%H:%M WIB')})

    return jsonify({"penjualan_harian": sales_list, "stock_awal_hari": stock_awal_hari, "barang_masuk_harian": barang_masuk_harian, "all_products": all_products})

# --- DATA MODIFICATION ENDPOINTS ---
@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.json
    try:
        new_user = User(nama_lengkap=data['nama_lengkap'], nik=data['nik'], username=data['username'], email=data['email'], nomor_kontak=data['nomor_kontak'], password=data['password'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"success": True, "message": "User berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username, NIK, atau email sudah ada."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/add_lapak', methods=['POST'])
def add_lapak():
    data = request.json
    try:
        user = User.query.filter_by(username=data['penanggung_jawab']).first()
        if not user:
            return jsonify({"success": False, "message": "User penanggung jawab tidak ditemukan."}), 404
        new_lapak = Lapak(lokasi=data['lokasi'], user_id=user.id)
        db.session.add(new_lapak)
        db.session.commit()
        return jsonify({"success": True, "message": "Lapak berhasil ditambahkan"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/add_supplier', methods=['POST'])
def add_supplier():
    data = request.json
    try:
        new_supplier = Supplier(nama_supplier=data['nama_supplier'], nama_alias=data.get('nama_alias'), kontak=data.get('kontak'), nomor_register=data.get('nomor_register'), alamat=data.get('alamat'), bank=data.get('bank'), nomor_rekening=data.get('nomor_rekening'), password=data['password'])
        db.session.add(new_supplier)
        db.session.flush() 
        for product_name in data.get('products', []):
            if product_name:
                new_product = Product(nama_produk=product_name, supplier_id=new_supplier.id)
                db.session.add(new_product)
        db.session.commit()
        return jsonify({"success": True, "message": "Supplier dan produk berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Nama Alias atau Nomor Register sudah ada."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/add_penjualan', methods=['POST'])
def add_penjualan():
    data = request.json
    try:
        for item in data.get('products', []):
            sale = Penjualan(product_id=int(item['id']), lapak_id=int(data['lapak_id']), jumlah=int(item['qty']), metode_pembayaran=data['payment'])
            db.session.add(sale)
        db.session.commit()
        return jsonify({"success": True, "message": "Penjualan berhasil disimpan!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {e}"}), 500

@app.route('/add_barang_masuk', methods=['POST'])
def add_barang_masuk():
    data = request.json
    try:
        for item in data.get('products', []):
            masuk = BarangMasuk(product_id=int(item['id']), lapak_id=int(data['lapak_id']), jumlah=int(item['qty']))
            db.session.add(masuk)
        db.session.commit()
        return jsonify({"success": True, "message": "Penerimaan barang berhasil disimpan!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {e}"}), 500

@app.route('/add_masalah_return', methods=['POST'])
def add_masalah_return():
    data = request.json
    try:
        laporan = MasalahReturn(
            lapak_id=data['lapak_id'], product_id=data.get('product_id'),
            jenis_laporan=data['jenis_laporan'], detail_masalah=data.get('detail_masalah'),
            jumlah=data.get('jumlah'), catatan=data.get('catatan'))
        db.session.add(laporan)
        db.session.commit()
        return jsonify({"success": True, "message": "Laporan berhasil dikirim"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/konfirmasi_laporan', methods=['POST'])
def konfirmasi_laporan():
    data = request.json
    lapak_id = data.get('lapak_id')
    today = datetime.date.today()
    existing_report = LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first()
    if existing_report:
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah dikonfirmasi."}), 400
    start_of_day = datetime.datetime.combine(today, datetime.time.min)
    end_of_day = datetime.datetime.combine(today, datetime.time.max)
    sales_today = Penjualan.query.filter(Penjualan.lapak_id == lapak_id, Penjualan.tanggal.between(start_of_day, end_of_day)).all()
    if not sales_today:
        return jsonify({"success": False, "message": "Tidak ada penjualan untuk dikonfirmasi hari ini."}), 400
    
    total_pendapatan, pendapatan_cash, pendapatan_qris, total_produk_terjual = 0.0, 0.0, 0.0, 0
    PRODUCT_PRICE = 15000 

    for sale in sales_today:
        sale_total = sale.jumlah * PRODUCT_PRICE
        total_pendapatan += sale_total
        total_produk_terjual += sale.jumlah
        if sale.metode_pembayaran == 'cash':
            pendapatan_cash += sale_total
        else:
            pendapatan_qris += sale_total
    
    new_report = LaporanHarian(lapak_id=lapak_id, tanggal=today, total_pendapatan=total_pendapatan, pendapatan_cash=pendapatan_cash, pendapatan_qris=pendapatan_qris, total_produk_terjual=total_produk_terjual)
    try:
        db.session.add(new_report)
        db.session.commit()
        return jsonify({"success": True, "message": "Laporan harian berhasil dikonfirmasi!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Gagal menyimpan laporan: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)

