from flask import render_template, jsonify, request, session, redirect, url_for
from app import app, db
from app.models import Admin, Supplier, Lapak, Product, StokHarian, LaporanHarian, LaporanHarianProduk, SupplierBalance, PembayaranSupplier, HARGA_BELI_DEFAULT, HARGA_JUAL_DEFAULT
from werkzeug.security import generate_password_hash, check_password_hash # <--- TAMBAHKAN BARIS INI
import datetime
import re
from datetime import timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func, or_
from sqlalchemy.orm import joinedload
from calendar import monthrange
import logging
import random

# ===================================================================
# ENDPOINTS API
# ===================================================================
@app.route('/')
def index():
    # Jika pengguna sudah login di sesi, arahkan ke dashboard
    if 'user_role' in session:
        return redirect(url_for('dashboard'))
    # Jika tidak, tampilkan halaman login
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Jika pengguna belum login, tendang kembali ke halaman login
    if 'user_role' not in session:
        return redirect(url_for('index'))

    # Render template yang sesuai berdasarkan peran pengguna di sesi
    role = session['user_role']
    if role == 'owner':
        return render_template('owner.html')
    elif role == 'lapak':
        return render_template('lapak.html')
    elif role == 'supplier':
        return render_template('supplier.html')
    else:
        # Jika ada peran yang tidak dikenal, logout saja
        session.clear()
        return redirect(url_for('index'))
    
# Anda juga perlu mengatur sesi saat login berhasil
@app.route('/api/login', methods=['POST'])
def handle_login():
    data = request.json
    username = data.get('username', '').lower()
    password = data.get('password')
    
    # ... (logika pengecekan username/password Anda tetap sama)
    
    # === TAMBAHAN PENTING: Simpan peran di sesi saat login berhasil ===
    # Contoh untuk admin/owner
    admin = Admin.query.filter(db.func.lower(Admin.username) == username).first()
    if admin and check_password_hash(admin.password, password): # <--- UBAH BARIS INI
        role = 'owner' if admin.username == 'owner' else 'lapak'
        session['user_role'] = role # Simpan peran
        session['user_info'] = {"nama_lengkap": admin.nama_lengkap, "id": admin.id} # Simpan info
        return jsonify({"success": True, "role": role, "user_info": session['user_info']})

    # Contoh untuk supplier
    supplier = Supplier.query.filter(db.func.lower(Supplier.username) == username).first()
    if supplier and check_password_hash(supplier.password, password): # <--- UBAH BARIS INI
        session['user_role'] = 'supplier' # Simpan peran
        session['user_info'] = {"nama_supplier": supplier.nama_supplier,"supplier_id": supplier.id} # Simpan info
        return jsonify({"success": True, "role": 'supplier', "user_info": session['user_info']})

    return jsonify({"success": False, "message": "Username atau password salah"}), 401
    
# Anda juga perlu rute untuk logout
@app.route('/logout')
def logout():
    session.clear() # Hapus semua data dari sesi
    return redirect(url_for('index'))

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
        supplier_list = []
        for s in suppliers:
            # Dapatkan produk untuk setiap supplier
            products = Product.query.filter_by(supplier_id=s.id).all()
            product_list = [{
                "id": p.id,
                "name": p.nama_produk,
                "harga_beli": p.harga_beli,
                "harga_jual": p.harga_jual
            } for p in products]

            # Dapatkan alokasi lapak (kita asumsikan semua produk supplier ada di lapak yang sama)
            lapak_ids = []
            if products:
                lapak_ids = [lapak.id for lapak in products[0].lapaks]

            supplier_list.append({
                "id": s.id, "nama_supplier": s.nama_supplier, "username": s.username, 
                "kontak": s.kontak, "nomor_register": s.nomor_register, "alamat": s.alamat, 
                "password": s.password, "metode_pembayaran": s.metode_pembayaran, 
                "nomor_rekening": s.nomor_rekening,
                "products": product_list, # Data produk baru
                "lapak_ids": lapak_ids   # Data alokasi lapak baru
            })
        
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
        hashed_password = generate_password_hash(data['password']) # <--- TAMBAHKAN BARIS INI
        new_admin = Admin(nama_lengkap=data['nama_lengkap'], nik=data['nik'], username=data['username'], email=data['email'], nomor_kontak=data['nomor_kontak'], password=hashed_password) # <--- GUNAKAN HASHED_PASSWORD
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
        if data.get('password'):
            admin.password = generate_password_hash(data['password']) # <--- UBAH BARIS INI
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
    if data['password'] != data['password_confirm']:
        return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    
    try:
        new_supplier = Supplier(
            nama_supplier=data['nama_supplier'],
            username=data.get('username'),
            kontak=data.get('kontak'),
            nomor_register=data.get('nomor_register'),
            alamat=data.get('alamat'),
            password=generate_password_hash(data['password']), # <--- UBAH DISINI
            metode_pembayaran=data.get('metode_pembayaran'),
            nomor_rekening=data.get('nomor_rekening')
        )
        new_supplier.balance = SupplierBalance(balance=0.0)
        db.session.add(new_supplier)
        db.session.commit()
        return jsonify({"success": True, "message": "Supplier berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username atau Nomor Register sudah ada."}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding supplier: {str(e)}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

# --- REVISI: Update metode pembayaran & no rekening ---
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
        supplier.alamat = data.get('alamat')
        supplier.metode_pembayaran = data.get('metode_pembayaran')
        supplier.nomor_rekening = data.get('nomor_rekening')
        if data.get('password'):
            supplier.password = generate_password_hash(data['password']) # <--- UBAH DISINI
        
        db.session.commit()
        return jsonify({"success": True, "message": "Data Supplier berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username sudah digunakan oleh supplier lain."}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating supplier: {str(e)}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

@app.route('/api/delete_supplier/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({"success": True, "message": "Supplier berhasil dihapus"})

@app.route('/api/get_owner_supplier_history/<int:supplier_id>', methods=['GET'])
def get_owner_supplier_history(supplier_id):
    try:
        # Ambil parameter tanggal dari request
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # Query dasar untuk pembayaran
        payments_query = PembayaranSupplier.query.filter_by(supplier_id=supplier_id)
        
        # Query dasar untuk penjualan
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

@app.route('/api/get_manage_reports')
def get_manage_reports():
    try:
        # Ambil semua parameter dari request
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        supplier_id = request.args.get('supplier_id')

        # Query dasar untuk semua laporan
        query = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab)
        )

        # Terapkan filter tanggal jika ada
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(LaporanHarian.tanggal >= start_date)
        
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(LaporanHarian.tanggal <= end_date)
        
        # --- PERUBAHAN LOGIKA DI SINI ---
        # Terapkan filter supplier jika ada
        if supplier_id:
            # Join ke tabel-tabel terkait untuk menemukan supplier_id
            query = query.join(LaporanHarian.rincian_produk)\
                         .join(LaporanHarianProduk.product)\
                         .filter(Product.supplier_id == supplier_id)\
                         .distinct() # Gunakan distinct untuk menghindari duplikat laporan

        reports = query.order_by(LaporanHarian.tanggal.desc()).all()
        
        report_list = [{"id": r.id, "lokasi": r.lapak.lokasi, "penanggung_jawab": r.lapak.penanggung_jawab.nama_lengkap, "tanggal": r.tanggal.isoformat(), "total_pendapatan": r.total_pendapatan, "total_produk_terjual": r.total_produk_terjual, "status": r.status} for r in reports]
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
        # Mengambil data tagihan SEMUA supplier
        suppliers = Supplier.query.options(joinedload(Supplier.balance)).all()
        supplier_list = [{"supplier_id": s.id, "nama_supplier": s.nama_supplier, "total_tagihan": s.balance.balance if s.balance else 0.0, "metode_pembayaran": s.metode_pembayaran, "nomor_rekening": s.nomor_rekening} for s in suppliers]
        
        return jsonify({
            "success": True, 
            "supplier_balances": supplier_list
        })
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

@app.route('/api/get_all_payment_history', methods=['GET'])
def get_all_payment_history():
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        metode = request.args.get('metode')

        query = PembayaranSupplier.query.options(joinedload(PembayaranSupplier.supplier))

        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
        if metode and metode != 'semua':
            query = query.filter(PembayaranSupplier.metode_pembayaran == metode)
        
        payments = query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()

        payment_list = [{
            "tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'),
            "nama_supplier": p.supplier.nama_supplier,
            "jumlah": p.jumlah_pembayaran,
            "metode": p.metode_pembayaran
        } for p in payments]
        
        return jsonify({"success": True, "history": payment_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route('/api/get_chart_data', methods=['GET'])
def get_chart_data():
    try:
        year = int(request.args.get('year', datetime.date.today().year))
        month = int(request.args.get('month', datetime.date.today().month))

        # Tentukan jumlah hari dalam bulan yang dipilih
        _, num_days = monthrange(year, month)
        # Buat label untuk semua hari dalam bulan (misal: "1", "2", ..., "31")
        labels = [str(i) for i in range(1, num_days + 1)]
        
        # Inisialisasi data dengan 0 untuk setiap hari
        pendapatan_data = {day: 0 for day in labels}
        biaya_data = {day: 0 for day in labels}

        # 1. Ambil data pendapatan harian (dari laporan terkonfirmasi)
        pendapatan_results = db.session.query(
            func.extract('day', LaporanHarian.tanggal),
            func.sum(LaporanHarian.total_pendapatan)
        ).filter(
            func.extract('year', LaporanHarian.tanggal) == year,
            func.extract('month', LaporanHarian.tanggal) == month,
            LaporanHarian.status == 'Terkonfirmasi'
        ).group_by(func.extract('day', LaporanHarian.tanggal)).all()

        for day, total in pendapatan_results:
            pendapatan_data[str(int(day))] = total

        # 2. Ambil data biaya harian (dari pembayaran supplier)
        biaya_results = db.session.query(
            func.extract('day', PembayaranSupplier.tanggal_pembayaran),
            func.sum(PembayaranSupplier.jumlah_pembayaran)
        ).filter(
            func.extract('year', PembayaranSupplier.tanggal_pembayaran) == year,
            func.extract('month', PembayaranSupplier.tanggal_pembayaran) == month
        ).group_by(func.extract('day', PembayaranSupplier.tanggal_pembayaran)).all()
        
        for day, total in biaya_results:
            biaya_data[str(int(day))] = total
        
        return jsonify({
            "success": True,
            "labels": labels,
            "pendapatanData": list(pendapatan_data.values()),
            "biayaData": list(biaya_data.values())
        })

    except Exception as e:
        logging.error(f"Error getting chart data: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
# --- LAPAK API ---
# --- REVISI: Kirim info pembayaran ke frontend ---
@app.route('/api/get_data_buat_catatan/<int:lapak_id>', methods=['GET'])
def get_data_buat_catatan(lapak_id):
    today = datetime.date.today()
    # Pengecekan laporan yang sudah ada tetap berlaku
    if LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first():
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah dibuat.", "already_exists": True}), 409
    
    # Ambil SEMUA supplier beserta produk mereka, tanpa filter lapak
    all_suppliers = Supplier.query.options(joinedload(Supplier.products)).order_by(Supplier.nama_supplier).all()
    
    suppliers_data = []
    for s in all_suppliers:
        suppliers_data.append({
            "id": s.id,
            "name": s.nama_supplier,
            "products": [{
                "id": p.id,
                "name": p.nama_produk,
                "harga_jual": p.harga_jual,
                "harga_beli": p.harga_beli
            } for p in s.products]
        })
        
    return jsonify({"success": True, "data": suppliers_data})

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
        # Ambil semua parameter dari request
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        lapak_id = request.args.get('lapak_id') # Parameter baru

        # Query pembayaran tidak berubah
        payments_query = PembayaranSupplier.query.filter_by(supplier_id=supplier_id)
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
        
        payments = payments_query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        payment_list = [{"tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'), "jumlah": p.jumlah_pembayaran, "metode": p.metode_pembayaran} for p in payments]

        # Query dasar untuk penjualan
        sales_query = db.session.query(
            LaporanHarian.tanggal, Lapak.lokasi, Product.nama_produk,
            LaporanHarianProduk.jumlah_terjual
        ).select_from(LaporanHarianProduk)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Lapak, Lapak.id == LaporanHarian.lapak_id)\
         .filter(Product.supplier_id == supplier_id, LaporanHarian.status == 'Terkonfirmasi')

        # Terapkan filter tanggal pada penjualan
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            sales_query = sales_query.filter(LaporanHarian.tanggal >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            sales_query = sales_query.filter(LaporanHarian.tanggal <= end_date)
        
        # --- PERUBAHAN LOGIKA DI SINI ---
        # Terapkan filter lapak jika ada
        if lapak_id:
            sales_query = sales_query.filter(LaporanHarian.lapak_id == lapak_id)

        sales = sales_query.order_by(LaporanHarian.tanggal.desc(), Lapak.lokasi).all()
        sales_list = [{"tanggal": s.tanggal.strftime('%Y-%m-%d'), "lokasi": s.lokasi, "nama_produk": s.nama_produk, "terjual": s.jumlah_terjual} for s in sales]
        
        # Ambil daftar lapak untuk mengisi dropdown di frontend
        all_lapaks = Lapak.query.order_by(Lapak.lokasi).all()
        lapak_list = [{"id": l.id, "lokasi": l.lokasi} for l in all_lapaks]
        
        return jsonify({"success": True, "payments": payment_list, "sales": sales_list, "lapaks": lapak_list})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting supplier history: {e}")
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

        # --- PERUBAHAN LOGIKA DIMULAI DI SINI ---
        # Mengelompokkan produk berdasarkan supplier
        rincian_per_supplier = {}
        for item in report.rincian_produk:
            supplier_name = item.product.supplier.nama_supplier if item.product.supplier else "Produk Manual"
            
            if supplier_name not in rincian_per_supplier:
                rincian_per_supplier[supplier_name] = []
            
            rincian_per_supplier[supplier_name].append({
                "nama_produk": item.product.nama_produk,
                "stok_awal": item.stok_awal,
                "stok_akhir": item.stok_akhir,
                "terjual": item.jumlah_terjual,
                "harga_jual": item.product.harga_jual,
                "total_pendapatan": item.total_harga_jual,
            })
        # --- AKHIR PERUBAHAN LOGIKA ---

        data = {
            "id": report.id,
            "tanggal": report.tanggal.strftime('%d %B %Y'),
            "status": report.status,
            "lokasi": report.lapak.lokasi,
            "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
            "rincian_per_supplier": rincian_per_supplier, # <--- Menggunakan data yang sudah dikelompokkan
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
                # Menggunakan total dari rekap otomatis untuk konsistensi
                "total_produk_terjual": report.total_produk_terjual,
                "total_pendapatan": report.manual_total_pendapatan
            }
        }
        return jsonify({"success": True, "data": data})

    except Exception as e:
        logging.error(f"Error getting report details: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan pada server"}), 500

