from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import logging

# 1. Buat instance ekstensi di luar fungsi
db = SQLAlchemy()

def create_app():
    # 2. Buat instance aplikasi di dalam fungsi
    app = Flask(__name__)
    
    # 3. Atur semua konfigurasi di sini
    app.config['SECRET_KEY'] = 'kunci-rahasia-katanya'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///penjualan.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 4. Hubungkan ekstensi dengan aplikasi
    db.init_app(app)
    
    logging.basicConfig(level=logging.INFO)

    with app.app_context():
        # 5. Impor bagian-bagian aplikasi lainnya
        from . import routes
        from . import models
        from . import commands # Impor file commands baru kita
        
        # 6. Daftarkan CLI Commands dari file commands.py
        app.cli.add_command(commands.init_db_command)
        app.cli.add_command(commands.seed_db_command)

    return app