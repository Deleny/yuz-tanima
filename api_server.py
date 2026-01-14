"""
Yoklama Sistemi REST API Server
Flask + MySQL + JWT Authentication
Tüm tablo ve alan isimleri Türkçe
"""

import os
import io
import time
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import mysql.connector
from mysql.connector import pooling
import jwt
import bcrypt

try:
    import cv2
    import face_recognition
    import numpy as np
except ImportError as exc:
    print("Eksik kutuphane:", exc)
    print("Kurulum: pip install opencv-python face_recognition numpy flask flask-cors mysql-connector-python pyjwt bcrypt")
    exit(1)

# ==================== CONFIG ====================

app = Flask(__name__)
CORS(app)

# JWT Config
JWT_SECRET = os.environ.get("JWT_SECRET", "yoklama-secret-key-2024")
JWT_EXPIRY_HOURS = 24

# MySQL Config
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "root"),
    "database": os.environ.get("DB_NAME", "yoklama_db"),
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
}

# Connection Pool
db_pool = None

# Face Recognition Config
BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "yuz_verileri"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
TOLERANCE = 0.5

# ==================== DATABASE ====================

def init_db_pool():
    """MySQL connection pool başlat"""
    global db_pool
    try:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="yoklama_pool",
            pool_size=5,
            **DB_CONFIG
        )
        print("✅ MySQL bağlantısı başarılı")
        return True
    except Exception as e:
        print(f"❌ MySQL bağlantı hatası: {e}")
        return False


def get_db():
    """Veritabanı bağlantısı al"""
    if "db" not in g:
        g.db = db_pool.get_connection()
    return g.db


@app.teardown_appcontext
def close_db(error):
    """Request sonunda bağlantıyı kapat"""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False, commit=False):
    """Veritabanı sorgusu çalıştır"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(query, args)
    if commit:
        db.commit()
        return cursor.lastrowid
    rv = cursor.fetchall()
    cursor.close()
    return (rv[0] if rv else None) if one else rv


# ==================== AUTH HELPERS ====================

def hash_password(password):
    """Şifre hash'le"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password, hashed):
    """Şifre doğrula"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id, role):
    """JWT token oluştur"""
    payload = {
        "kullanici_id": user_id,
        "rol": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token):
    """JWT token çöz"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """Token gerektiren endpoint decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"basarili": False, "hata": "Token gerekli"}), 401
        
        payload = decode_token(token)
        if not payload:
            return jsonify({"basarili": False, "hata": "Geçersiz veya süresi dolmuş token"}), 401
        
        g.kullanici_id = payload["kullanici_id"]
        g.rol = payload["rol"]
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Rol gerektiren endpoint decorator"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.rol not in roles:
                return jsonify({"basarili": False, "hata": "Yetkisiz erişim"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ==================== FACE RECOGNITION ====================

def process_image(image_bytes):
    """Byte dizisinden OpenCV image oluştur"""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return rgb, img


def get_face_encoding(rgb_image):
    """Görüntüden yüz encoding'i çıkar"""
    locations = face_recognition.face_locations(rgb_image)
    if len(locations) == 0:
        return None, "Yüz bulunamadı"
    if len(locations) > 1:
        return None, "Birden fazla yüz algılandı"
    
    encodings = face_recognition.face_encodings(rgb_image, locations)
    if len(encodings) == 0:
        return None, "Yüz verisi oluşturulamadı"
    
    return encodings[0], None


# ==================== AUTH ENDPOINTS ====================

@app.route("/", methods=["GET"])
def index():
    """API sağlık kontrolü"""
    return jsonify({
        "durum": "ok",
        "mesaj": "Yoklama Sistemi API",
        "versiyon": "2.0"
    })


@app.route("/auth/kayit", methods=["POST"])
def register():
    """Kullanıcı kayıt"""
    data = request.get_json()
    
    email = data.get("email", "").strip().lower()
    sifre = data.get("sifre", "")
    ad_soyad = data.get("ad_soyad", "").strip()
    rol = data.get("rol", "ogrenci")
    
    # Validasyon
    if not email or not sifre or not ad_soyad:
        return jsonify({"basarili": False, "hata": "Tüm alanlar gerekli"}), 400
    
    if rol not in ["ogrenci", "ogretmen"]:
        rol = "ogrenci"
    
    if len(sifre) < 6:
        return jsonify({"basarili": False, "hata": "Şifre en az 6 karakter olmalı"}), 400
    
    # Email kontrolü
    existing = query_db("SELECT id FROM kullanicilar WHERE email = %s", (email,), one=True)
    if existing:
        return jsonify({"basarili": False, "hata": "Bu email zaten kayıtlı"}), 400
    
    # Kullanıcı oluştur
    sifre_hash = hash_password(sifre)
    onaylandi = rol == "ogretmen"
    
    kullanici_id = query_db(
        "INSERT INTO kullanicilar (email, sifre_hash, ad_soyad, rol, onaylandi) VALUES (%s, %s, %s, %s, %s)",
        (email, sifre_hash, ad_soyad, rol, onaylandi),
        commit=True
    )
    
    return jsonify({
        "basarili": True,
        "mesaj": "Kayıt başarılı" if onaylandi else "Kayıt başarılı, admin onayı bekleniyor",
        "kullanici_id": kullanici_id,
        "onaylandi": onaylandi
    })


@app.route("/auth/giris", methods=["POST"])
def login():
    """Kullanıcı giriş"""
    data = request.get_json()
    
    email = data.get("email", "").strip().lower()
    sifre = data.get("sifre", "")
    
    if not email or not sifre:
        return jsonify({"basarili": False, "hata": "Email ve şifre gerekli"}), 400
    
    # Kullanıcıyı bul
    kullanici = query_db(
        "SELECT id, email, sifre_hash, ad_soyad, rol, onaylandi, yuz_encoding IS NOT NULL as yuz_var FROM kullanicilar WHERE email = %s",
        (email,),
        one=True
    )
    
    if not kullanici:
        return jsonify({"basarili": False, "hata": "Email veya şifre hatalı"}), 401
    
    if not check_password(sifre, kullanici["sifre_hash"]):
        return jsonify({"basarili": False, "hata": "Email veya şifre hatalı"}), 401
    
    if not kullanici["onaylandi"]:
        return jsonify({"basarili": False, "hata": "Hesabınız henüz onaylanmadı"}), 403
    
    # Token oluştur
    token = create_token(kullanici["id"], kullanici["rol"])
    
    return jsonify({
        "basarili": True,
        "token": token,
        "kullanici": {
            "id": kullanici["id"],
            "email": kullanici["email"],
            "ad_soyad": kullanici["ad_soyad"],
            "rol": kullanici["rol"],
            "yuz_var": bool(kullanici["yuz_var"])
        }
    })


@app.route("/auth/ben", methods=["GET"])
@token_required
def get_me():
    """Mevcut kullanıcı bilgisi"""
    kullanici = query_db(
        "SELECT id, email, ad_soyad, rol, onaylandi, yuz_encoding IS NOT NULL as yuz_var, olusturma_tarihi FROM kullanicilar WHERE id = %s",
        (g.kullanici_id,),
        one=True
    )
    
    if not kullanici:
        return jsonify({"basarili": False, "hata": "Kullanıcı bulunamadı"}), 404
    
    return jsonify({
        "basarili": True,
        "kullanici": {
            "id": kullanici["id"],
            "email": kullanici["email"],
            "ad_soyad": kullanici["ad_soyad"],
            "rol": kullanici["rol"],
            "yuz_var": bool(kullanici["yuz_var"]),
            "olusturma_tarihi": kullanici["olusturma_tarihi"].isoformat() if kullanici["olusturma_tarihi"] else None
        }
    })


# ==================== FACE ENDPOINTS ====================

@app.route("/yuz/kayit", methods=["POST"])
@token_required
@role_required("ogrenci")
def register_face():
    """Öğrenci yüz kaydı"""
    if "resim" not in request.files:
        return jsonify({"basarili": False, "hata": "Resim dosyası gerekli"}), 400
    
    resim_dosya = request.files["resim"]
    if resim_dosya.filename == "":
        return jsonify({"basarili": False, "hata": "Resim seçilmedi"}), 400
    
    try:
        image_bytes = resim_dosya.read()
        result = process_image(image_bytes)
        if result is None:
            return jsonify({"basarili": False, "hata": "Resim okunamadı"}), 400
        
        rgb, bgr = result
        encoding, error = get_face_encoding(rgb)
        
        if error:
            return jsonify({"basarili": False, "hata": error}), 400
        
        # Encoding'i veritabanına kaydet
        encoding_bytes = pickle.dumps(encoding)
        query_db(
            "UPDATE kullanicilar SET yuz_encoding = %s WHERE id = %s",
            (encoding_bytes, g.kullanici_id),
            commit=True
        )
        
        # Resmi dosya sistemine de kaydet
        kullanici = query_db("SELECT ad_soyad FROM kullanicilar WHERE id = %s", (g.kullanici_id,), one=True)
        if kullanici:
            safe_name = "".join(c for c in kullanici["ad_soyad"] if c.isalnum() or c in "_ ").replace(" ", "_")
            person_dir = IMAGES_DIR / safe_name
            person_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(str(person_dir / f"{timestamp}.jpg"), bgr)
        
        return jsonify({
            "basarili": True,
            "mesaj": "Yüz başarıyla kaydedildi"
        })
        
    except Exception as e:
        print(f"Yüz kayıt hatası: {e}")
        return jsonify({"basarili": False, "hata": f"Sunucu hatası: {str(e)}"}), 500


@app.route("/yuz/dogrula", methods=["POST"])
@token_required
@role_required("ogrenci")
def verify_face():
    """Yüz doğrulama"""
    if "resim" not in request.files:
        return jsonify({"basarili": False, "hata": "Resim dosyası gerekli"}), 400
    
    # Kullanıcının kayıtlı yüzünü al
    kullanici = query_db(
        "SELECT yuz_encoding FROM kullanicilar WHERE id = %s",
        (g.kullanici_id,),
        one=True
    )
    
    if not kullanici or not kullanici["yuz_encoding"]:
        return jsonify({"basarili": False, "hata": "Kayıtlı yüz bulunamadı"}), 400
    
    try:
        stored_encoding = pickle.loads(kullanici["yuz_encoding"])
        
        resim_dosya = request.files["resim"]
        image_bytes = resim_dosya.read()
        result = process_image(image_bytes)
        
        if result is None:
            return jsonify({"basarili": False, "hata": "Resim okunamadı"}), 400
        
        rgb, _ = result
        current_encoding, error = get_face_encoding(rgb)
        
        if error:
            return jsonify({"basarili": False, "hata": error}), 400
        
        # Yüzleri karşılaştır
        distance = face_recognition.face_distance([stored_encoding], current_encoding)[0]
        is_match = distance <= TOLERANCE
        confidence = round((1 - distance) * 100, 2)
        
        return jsonify({
            "basarili": True,
            "dogrulandi": is_match,
            "guven": confidence,
            "mesaj": "Yüz doğrulandı" if is_match else "Yüz eşleşmedi"
        })
        
    except Exception as e:
        print(f"Yüz doğrulama hatası: {e}")
        return jsonify({"basarili": False, "hata": f"Sunucu hatası: {str(e)}"}), 500


# ==================== COURSE ENDPOINTS ====================

@app.route("/dersler", methods=["GET"])
@token_required
def get_courses():
    """Dersleri listele"""
    if g.rol == "admin":
        dersler = query_db("""
            SELECT d.*, k.ad_soyad as ogretmen_adi,
                   (SELECT COUNT(*) FROM kayitlar ky WHERE ky.ders_id = d.id) as ogrenci_sayisi
            FROM dersler d
            LEFT JOIN kullanicilar k ON d.ogretmen_id = k.id
            ORDER BY d.ad
        """)
    elif g.rol == "ogretmen":
        dersler = query_db("""
            SELECT d.*, k.ad_soyad as ogretmen_adi,
                   (SELECT COUNT(*) FROM kayitlar ky WHERE ky.ders_id = d.id) as ogrenci_sayisi
            FROM dersler d
            LEFT JOIN kullanicilar k ON d.ogretmen_id = k.id
            WHERE d.ogretmen_id = %s
            ORDER BY d.ad
        """, (g.kullanici_id,))
    else:
        dersler = query_db("""
            SELECT d.*, k.ad_soyad as ogretmen_adi
            FROM dersler d
            LEFT JOIN kullanicilar k ON d.ogretmen_id = k.id
            JOIN kayitlar ky ON d.id = ky.ders_id
            WHERE ky.ogrenci_id = %s
            ORDER BY d.ad
        """, (g.kullanici_id,))
    
    return jsonify({
        "basarili": True,
        "dersler": dersler
    })


@app.route("/dersler", methods=["POST"])
@token_required
@role_required("admin")
def create_course():
    """Ders ekle"""
    data = request.get_json()
    
    ad = data.get("ad", "").strip()
    kod = data.get("kod", "").strip().upper()
    ogretmen_id = data.get("ogretmen_id")
    
    if not ad or not kod:
        return jsonify({"basarili": False, "hata": "Ders adı ve kodu gerekli"}), 400
    
    existing = query_db("SELECT id FROM dersler WHERE kod = %s", (kod,), one=True)
    if existing:
        return jsonify({"basarili": False, "hata": "Bu ders kodu zaten kullanılıyor"}), 400
    
    if ogretmen_id:
        ogretmen = query_db("SELECT id FROM kullanicilar WHERE id = %s AND rol = 'ogretmen'", (ogretmen_id,), one=True)
        if not ogretmen:
            return jsonify({"basarili": False, "hata": "Geçersiz öğretmen"}), 400
    
    ders_id = query_db(
        "INSERT INTO dersler (ad, kod, ogretmen_id) VALUES (%s, %s, %s)",
        (ad, kod, ogretmen_id),
        commit=True
    )
    
    return jsonify({
        "basarili": True,
        "mesaj": "Ders oluşturuldu",
        "ders_id": ders_id
    })


@app.route("/dersler/<int:ders_id>", methods=["PUT"])
@token_required
@role_required("admin")
def update_course(ders_id):
    """Ders güncelle"""
    data = request.get_json()
    
    ders = query_db("SELECT id FROM dersler WHERE id = %s", (ders_id,), one=True)
    if not ders:
        return jsonify({"basarili": False, "hata": "Ders bulunamadı"}), 404
    
    updates = []
    params = []
    
    if "ad" in data:
        updates.append("ad = %s")
        params.append(data["ad"].strip())
    
    if "kod" in data:
        kod = data["kod"].strip().upper()
        existing = query_db("SELECT id FROM dersler WHERE kod = %s AND id != %s", (kod, ders_id), one=True)
        if existing:
            return jsonify({"basarili": False, "hata": "Bu ders kodu zaten kullanılıyor"}), 400
        updates.append("kod = %s")
        params.append(kod)
    
    if "ogretmen_id" in data:
        ogretmen_id = data["ogretmen_id"]
        if ogretmen_id:
            ogretmen = query_db("SELECT id FROM kullanicilar WHERE id = %s AND rol = 'ogretmen'", (ogretmen_id,), one=True)
            if not ogretmen:
                return jsonify({"basarili": False, "hata": "Geçersiz öğretmen"}), 400
        updates.append("ogretmen_id = %s")
        params.append(ogretmen_id)
    
    if updates:
        params.append(ders_id)
        query_db(f"UPDATE dersler SET {', '.join(updates)} WHERE id = %s", tuple(params), commit=True)
    
    return jsonify({"basarili": True, "mesaj": "Ders güncellendi"})


@app.route("/dersler/<int:ders_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_course(ders_id):
    """Ders sil"""
    ders = query_db("SELECT id FROM dersler WHERE id = %s", (ders_id,), one=True)
    if not ders:
        return jsonify({"basarili": False, "hata": "Ders bulunamadı"}), 404
    
    query_db("DELETE FROM dersler WHERE id = %s", (ders_id,), commit=True)
    
    return jsonify({"basarili": True, "mesaj": "Ders silindi"})


# ==================== ENROLLMENT ENDPOINTS ====================

@app.route("/kayitlar", methods=["POST"])
@token_required
@role_required("admin")
def create_enrollment():
    """Öğrenci derse kaydet"""
    data = request.get_json()
    
    ogrenci_id = data.get("ogrenci_id")
    ders_id = data.get("ders_id")
    
    if not ogrenci_id or not ders_id:
        return jsonify({"basarili": False, "hata": "Öğrenci ve ders id gerekli"}), 400
    
    ogrenci = query_db("SELECT id FROM kullanicilar WHERE id = %s AND rol = 'ogrenci'", (ogrenci_id,), one=True)
    if not ogrenci:
        return jsonify({"basarili": False, "hata": "Geçersiz öğrenci"}), 400
    
    ders = query_db("SELECT id FROM dersler WHERE id = %s", (ders_id,), one=True)
    if not ders:
        return jsonify({"basarili": False, "hata": "Geçersiz ders"}), 400
    
    existing = query_db(
        "SELECT id FROM kayitlar WHERE ogrenci_id = %s AND ders_id = %s",
        (ogrenci_id, ders_id),
        one=True
    )
    if existing:
        return jsonify({"basarili": False, "hata": "Öğrenci zaten bu derse kayıtlı"}), 400
    
    kayit_id = query_db(
        "INSERT INTO kayitlar (ogrenci_id, ders_id) VALUES (%s, %s)",
        (ogrenci_id, ders_id),
        commit=True
    )
    
    return jsonify({
        "basarili": True,
        "mesaj": "Öğrenci derse kaydedildi",
        "kayit_id": kayit_id
    })


@app.route("/kayitlar/<int:kayit_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_enrollment(kayit_id):
    """Kayıt sil"""
    kayit = query_db("SELECT id FROM kayitlar WHERE id = %s", (kayit_id,), one=True)
    if not kayit:
        return jsonify({"basarili": False, "hata": "Kayıt bulunamadı"}), 404
    
    query_db("DELETE FROM kayitlar WHERE id = %s", (kayit_id,), commit=True)
    
    return jsonify({"basarili": True, "mesaj": "Kayıt silindi"})


@app.route("/dersler/<int:ders_id>/ogrenciler", methods=["GET"])
@token_required
@role_required("admin", "ogretmen")
def get_course_students(ders_id):
    """Derse kayıtlı öğrenciler"""
    ogrenciler = query_db("""
        SELECT k.id, k.email, k.ad_soyad, ky.kayit_tarihi,
               k.yuz_encoding IS NOT NULL as yuz_var
        FROM kullanicilar k
        JOIN kayitlar ky ON k.id = ky.ogrenci_id
        WHERE ky.ders_id = %s
        ORDER BY k.ad_soyad
    """, (ders_id,))
    
    return jsonify({
        "basarili": True,
        "ogrenciler": [{
            **o,
            "yuz_var": bool(o["yuz_var"]),
            "kayit_tarihi": o["kayit_tarihi"].isoformat() if o["kayit_tarihi"] else None
        } for o in ogrenciler]
    })


# ==================== ATTENDANCE ENDPOINTS ====================

@app.route("/yoklama/baslat", methods=["POST"])
@token_required
@role_required("ogretmen")
def start_attendance():
    """Yoklama başlat"""
    data = request.get_json()
    ders_id = data.get("ders_id")
    
    if not ders_id:
        return jsonify({"basarili": False, "hata": "Ders id gerekli"}), 400
    
    ders = query_db(
        "SELECT id, ad FROM dersler WHERE id = %s AND ogretmen_id = %s",
        (ders_id, g.kullanici_id),
        one=True
    )
    if not ders:
        return jsonify({"basarili": False, "hata": "Ders bulunamadı veya yetkisiz"}), 404
    
    aktif = query_db(
        "SELECT id FROM yoklama_oturumlari WHERE ders_id = %s AND aktif = TRUE",
        (ders_id,),
        one=True
    )
    if aktif:
        return jsonify({"basarili": False, "hata": "Bu ders için aktif yoklama zaten var"}), 400
    
    oturum_id = query_db(
        "INSERT INTO yoklama_oturumlari (ders_id) VALUES (%s)",
        (ders_id,),
        commit=True
    )
    
    return jsonify({
        "basarili": True,
        "mesaj": f"{ders['ad']} için yoklama başlatıldı",
        "oturum_id": oturum_id
    })


@app.route("/yoklama/bitir/<int:oturum_id>", methods=["POST"])
@token_required
@role_required("ogretmen")
def end_attendance(oturum_id):
    """Yoklama bitir"""
    oturum = query_db("""
        SELECT yo.id, yo.aktif, d.ogretmen_id
        FROM yoklama_oturumlari yo
        JOIN dersler d ON yo.ders_id = d.id
        WHERE yo.id = %s
    """, (oturum_id,), one=True)
    
    if not oturum:
        return jsonify({"basarili": False, "hata": "Yoklama oturumu bulunamadı"}), 404
    
    if oturum["ogretmen_id"] != g.kullanici_id:
        return jsonify({"basarili": False, "hata": "Yetkisiz erişim"}), 403
    
    if not oturum["aktif"]:
        return jsonify({"basarili": False, "hata": "Bu yoklama zaten bitmiş"}), 400
    
    query_db(
        "UPDATE yoklama_oturumlari SET aktif = FALSE, bitis_tarihi = NOW() WHERE id = %s",
        (oturum_id,),
        commit=True
    )
    
    count = query_db(
        "SELECT COUNT(*) as sayi FROM yoklamalar WHERE oturum_id = %s",
        (oturum_id,),
        one=True
    )
    
    return jsonify({
        "basarili": True,
        "mesaj": "Yoklama bitirildi",
        "katilim_sayisi": count["sayi"] if count else 0
    })


@app.route("/yoklama/aktif", methods=["GET"])
@token_required
def get_active_sessions():
    """Aktif yoklamalar"""
    if g.rol == "ogrenci":
        oturumlar = query_db("""
            SELECT yo.id as oturum_id, yo.baslangic_tarihi, d.id as ders_id, d.ad as ders_adi, d.kod,
                   k.ad_soyad as ogretmen_adi,
                   (SELECT COUNT(*) FROM yoklamalar y WHERE y.oturum_id = yo.id AND y.ogrenci_id = %s) > 0 as katildi
            FROM yoklama_oturumlari yo
            JOIN dersler d ON yo.ders_id = d.id
            LEFT JOIN kullanicilar k ON d.ogretmen_id = k.id
            JOIN kayitlar ky ON d.id = ky.ders_id
            WHERE yo.aktif = TRUE AND ky.ogrenci_id = %s
        """, (g.kullanici_id, g.kullanici_id))
    elif g.rol == "ogretmen":
        oturumlar = query_db("""
            SELECT yo.id as oturum_id, yo.baslangic_tarihi, d.id as ders_id, d.ad as ders_adi, d.kod,
                   (SELECT COUNT(*) FROM yoklamalar y WHERE y.oturum_id = yo.id) as katilim_sayisi
            FROM yoklama_oturumlari yo
            JOIN dersler d ON yo.ders_id = d.id
            WHERE yo.aktif = TRUE AND d.ogretmen_id = %s
        """, (g.kullanici_id,))
    else:
        oturumlar = query_db("""
            SELECT yo.id as oturum_id, yo.baslangic_tarihi, d.id as ders_id, d.ad as ders_adi, d.kod,
                   k.ad_soyad as ogretmen_adi,
                   (SELECT COUNT(*) FROM yoklamalar y WHERE y.oturum_id = yo.id) as katilim_sayisi
            FROM yoklama_oturumlari yo
            JOIN dersler d ON yo.ders_id = d.id
            LEFT JOIN kullanicilar k ON d.ogretmen_id = k.id
            WHERE yo.aktif = TRUE
        """)
    
    return jsonify({
        "basarili": True,
        "oturumlar": [{
            **o,
            "baslangic_tarihi": o["baslangic_tarihi"].isoformat() if o["baslangic_tarihi"] else None
        } for o in oturumlar]
    })


@app.route("/yoklama/katil/<int:oturum_id>", methods=["POST"])
@token_required
@role_required("ogrenci")
def join_attendance(oturum_id):
    """Yoklamaya katıl"""
    kullanici = query_db(
        "SELECT yuz_encoding FROM kullanicilar WHERE id = %s",
        (g.kullanici_id,),
        one=True
    )
    if not kullanici or not kullanici["yuz_encoding"]:
        return jsonify({"basarili": False, "hata": "Önce yüz kaydı yapmanız gerekiyor"}), 400
    
    oturum = query_db("""
        SELECT yo.id, yo.aktif, yo.ders_id
        FROM yoklama_oturumlari yo
        WHERE yo.id = %s AND yo.aktif = TRUE
    """, (oturum_id,), one=True)
    
    if not oturum:
        return jsonify({"basarili": False, "hata": "Aktif yoklama bulunamadı"}), 404
    
    kayit = query_db(
        "SELECT id FROM kayitlar WHERE ogrenci_id = %s AND ders_id = %s",
        (g.kullanici_id, oturum["ders_id"]),
        one=True
    )
    if not kayit:
        return jsonify({"basarili": False, "hata": "Bu derse kayıtlı değilsiniz"}), 403
    
    existing = query_db(
        "SELECT id FROM yoklamalar WHERE oturum_id = %s AND ogrenci_id = %s",
        (oturum_id, g.kullanici_id),
        one=True
    )
    if existing:
        return jsonify({"basarili": False, "hata": "Zaten yoklamaya katıldınız"}), 400
    
    if "resim" not in request.files:
        return jsonify({"basarili": False, "hata": "Yüz doğrulama için resim gerekli"}), 400
    
    try:
        stored_encoding = pickle.loads(kullanici["yuz_encoding"])
        
        resim_dosya = request.files["resim"]
        image_bytes = resim_dosya.read()
        result = process_image(image_bytes)
        
        if result is None:
            return jsonify({"basarili": False, "hata": "Resim okunamadı"}), 400
        
        rgb, _ = result
        current_encoding, error = get_face_encoding(rgb)
        
        if error:
            return jsonify({"basarili": False, "hata": error}), 400
        
        distance = face_recognition.face_distance([stored_encoding], current_encoding)[0]
        is_match = distance <= TOLERANCE
        
        if not is_match:
            return jsonify({
                "basarili": False,
                "hata": "Yüz doğrulanamadı. Kayıtlı yüzünüzle eşleşmiyor."
            }), 400
        
        yoklama_id = query_db(
            "INSERT INTO yoklamalar (oturum_id, ogrenci_id, yuz_dogrulandi) VALUES (%s, %s, TRUE)",
            (oturum_id, g.kullanici_id),
            commit=True
        )
        
        return jsonify({
            "basarili": True,
            "mesaj": "Yoklamaya başarıyla katıldınız",
            "yoklama_id": yoklama_id
        })
        
    except Exception as e:
        print(f"Yoklama katılım hatası: {e}")
        return jsonify({"basarili": False, "hata": f"Sunucu hatası: {str(e)}"}), 500


@app.route("/yoklama/oturum/<int:oturum_id>", methods=["GET"])
@token_required
@role_required("admin", "ogretmen")
def get_session_details(oturum_id):
    """Yoklama oturumu detayları"""
    oturum = query_db("""
        SELECT yo.*, d.ad as ders_adi, d.kod as ders_kodu
        FROM yoklama_oturumlari yo
        JOIN dersler d ON yo.ders_id = d.id
        WHERE yo.id = %s
    """, (oturum_id,), one=True)
    
    if not oturum:
        return jsonify({"basarili": False, "hata": "Oturum bulunamadı"}), 404
    
    yoklamalar = query_db("""
        SELECT y.id, y.katilim_tarihi, y.yuz_dogrulandi, k.ad_soyad, k.email
        FROM yoklamalar y
        JOIN kullanicilar k ON y.ogrenci_id = k.id
        WHERE y.oturum_id = %s
        ORDER BY y.katilim_tarihi
    """, (oturum_id,))
    
    return jsonify({
        "basarili": True,
        "oturum": {
            **oturum,
            "baslangic_tarihi": oturum["baslangic_tarihi"].isoformat() if oturum["baslangic_tarihi"] else None,
            "bitis_tarihi": oturum["bitis_tarihi"].isoformat() if oturum["bitis_tarihi"] else None
        },
        "yoklamalar": [{
            **y,
            "katilim_tarihi": y["katilim_tarihi"].isoformat() if y["katilim_tarihi"] else None
        } for y in yoklamalar]
    })


# ==================== ADMIN ENDPOINTS ====================

@app.route("/admin/kullanicilar", methods=["GET"])
@token_required
@role_required("admin")
def get_users():
    """Tüm kullanıcıları listele"""
    rol_filtre = request.args.get("rol")
    
    if rol_filtre:
        kullanicilar = query_db("""
            SELECT id, email, ad_soyad, rol, onaylandi, 
                   yuz_encoding IS NOT NULL as yuz_var, olusturma_tarihi
            FROM kullanicilar
            WHERE rol = %s
            ORDER BY olusturma_tarihi DESC
        """, (rol_filtre,))
    else:
        kullanicilar = query_db("""
            SELECT id, email, ad_soyad, rol, onaylandi,
                   yuz_encoding IS NOT NULL as yuz_var, olusturma_tarihi
            FROM kullanicilar
            ORDER BY rol, olusturma_tarihi DESC
        """)
    
    return jsonify({
        "basarili": True,
        "kullanicilar": [{
            **k,
            "yuz_var": bool(k["yuz_var"]),
            "olusturma_tarihi": k["olusturma_tarihi"].isoformat() if k["olusturma_tarihi"] else None
        } for k in kullanicilar]
    })


@app.route("/admin/kullanicilar/<int:kullanici_id>/onayla", methods=["POST"])
@token_required
@role_required("admin")
def approve_user(kullanici_id):
    """Kullanıcı onayla"""
    kullanici = query_db("SELECT id, onaylandi FROM kullanicilar WHERE id = %s", (kullanici_id,), one=True)
    if not kullanici:
        return jsonify({"basarili": False, "hata": "Kullanıcı bulunamadı"}), 404
    
    query_db("UPDATE kullanicilar SET onaylandi = TRUE WHERE id = %s", (kullanici_id,), commit=True)
    
    return jsonify({"basarili": True, "mesaj": "Kullanıcı onaylandı"})


@app.route("/admin/ogretmenler", methods=["GET"])
@token_required
@role_required("admin")
def get_teachers():
    """Öğretmenleri listele"""
    ogretmenler = query_db("""
        SELECT id, email, ad_soyad
        FROM kullanicilar
        WHERE rol = 'ogretmen' AND onaylandi = TRUE
        ORDER BY ad_soyad
    """)
    
    return jsonify({"basarili": True, "ogretmenler": ogretmenler})



# ==================== ÖĞRETMEN ENDPOINTLERİ ====================

@app.route("/ogretmen/derslerim", methods=["GET"])
@token_required
@role_required("ogretmen")
def get_teacher_courses():
    """Öğretmenin kendi derslerini listele"""
    ogretmen_id = g.kullanici_id
    
    dersler = query_db("""
        SELECT d.id, d.ad, d.kod,
               (SELECT COUNT(*) FROM kayitlar WHERE ders_id = d.id) as ogrenci_sayisi,
               (SELECT COUNT(*) FROM yoklama_oturumlari WHERE ders_id = d.id AND aktif = TRUE) as aktif_oturum
        FROM dersler d
        WHERE d.ogretmen_id = %s
        ORDER BY d.ad
    """, (ogretmen_id,))
    
    return jsonify({
        "basarili": True,
        "dersler": [{
            "id": d["id"],
            "ad": d["ad"],
            "kod": d["kod"],
            "ogrenci_sayisi": d["ogrenci_sayisi"],
            "aktif_oturum": d["aktif_oturum"] > 0
        } for d in dersler]
    })


@app.route("/ogretmen/yoklama/baslat", methods=["POST"])
@token_required
@role_required("ogretmen")
def teacher_start_attendance():
    """Öğretmen için yoklama başlat"""
    ogretmen_id = g.kullanici_id
    data = request.get_json() or {}
    ders_id = data.get("ders_id")
    
    if not ders_id:
        return jsonify({"basarili": False, "hata": "Ders ID gerekli"}), 400
    
    # Dersin bu öğretmene ait olduğunu kontrol et
    ders = query_db("SELECT id, ad FROM dersler WHERE id = %s AND ogretmen_id = %s", 
                    (ders_id, ogretmen_id), one=True)
    if not ders:
        return jsonify({"basarili": False, "hata": "Bu ders size ait değil"}), 403
    
    # Aktif oturum var mı kontrol et
    aktif = query_db("SELECT id FROM yoklama_oturumlari WHERE ders_id = %s AND aktif = TRUE", 
                     (ders_id,), one=True)
    if aktif:
        return jsonify({"basarili": False, "hata": "Bu dersin zaten aktif bir yoklaması var"}), 400
    
    # Yeni oturum oluştur
    oturum_id = query_db(
        "INSERT INTO yoklama_oturumlari (ders_id, aktif) VALUES (%s, TRUE)",
        (ders_id,), commit=True
    )
    
    return jsonify({
        "basarili": True,
        "mesaj": f"{ders['ad']} için yoklama başlatıldı",
        "oturum_id": oturum_id
    })


@app.route("/ogretmen/yoklama/bitir", methods=["POST"])
@token_required
@role_required("ogretmen")
def teacher_end_attendance():
    """Öğretmen için yoklama bitir"""
    ogretmen_id = g.kullanici_id
    data = request.get_json() or {}
    oturum_id = data.get("oturum_id")
    
    if not oturum_id:
        return jsonify({"basarili": False, "hata": "Oturum ID gerekli"}), 400
    
    # Oturumun bu öğretmene ait olduğunu kontrol et
    oturum = query_db("""
        SELECT yo.id, d.ad as ders_adi
        FROM yoklama_oturumlari yo
        JOIN dersler d ON yo.ders_id = d.id
        WHERE yo.id = %s AND d.ogretmen_id = %s AND yo.aktif = TRUE
    """, (oturum_id, ogretmen_id), one=True)
    
    if not oturum:
        return jsonify({"basarili": False, "hata": "Aktif oturum bulunamadı"}), 404
    
    # Oturumu kapat
    query_db(
        "UPDATE yoklama_oturumlari SET aktif = FALSE, bitis_tarihi = NOW() WHERE id = %s",
        (oturum_id,), commit=True
    )
    
    # Katılımcı sayısını getir
    katilimci_sayisi = query_db(
        "SELECT COUNT(*) as sayi FROM yoklamalar WHERE oturum_id = %s",
        (oturum_id,), one=True
    )["sayi"]
    
    return jsonify({
        "basarili": True,
        "mesaj": f"{oturum['ders_adi']} yoklaması bitirildi",
        "katilimci_sayisi": katilimci_sayisi
    })


@app.route("/ogretmen/yoklama/aktif", methods=["GET"])
@token_required
@role_required("ogretmen")
def teacher_active_attendance():
    """Öğretmenin aktif yoklaması ve katılımcıları"""
    ogretmen_id = g.kullanici_id
    
    # Aktif oturumu bul
    oturum = query_db("""
        SELECT yo.id as oturum_id, yo.baslangic_tarihi, d.id as ders_id, d.ad as ders_adi
        FROM yoklama_oturumlari yo
        JOIN dersler d ON yo.ders_id = d.id
        WHERE d.ogretmen_id = %s AND yo.aktif = TRUE
        LIMIT 1
    """, (ogretmen_id,), one=True)
    
    if not oturum:
        return jsonify({"basarili": True, "aktif_oturum": None})
    
    # Katılımcıları getir
    katilimcilar = query_db("""
        SELECT k.ad_soyad, y.katilim_tarihi, y.yuz_dogrulandi
        FROM yoklamalar y
        JOIN kullanicilar k ON y.ogrenci_id = k.id
        WHERE y.oturum_id = %s
        ORDER BY y.katilim_tarihi DESC
    """, (oturum["oturum_id"],))
    
    return jsonify({
        "basarili": True,
        "aktif_oturum": {
            "oturum_id": oturum["oturum_id"],
            "ders_id": oturum["ders_id"],
            "ders_adi": oturum["ders_adi"],
            "baslangic": oturum["baslangic_tarihi"].isoformat() if oturum["baslangic_tarihi"] else None,
            "katilimci_sayisi": len(katilimcilar),
            "katilimcilar": [{
                "ad_soyad": k["ad_soyad"],
                "saat": k["katilim_tarihi"].strftime("%H:%M") if k["katilim_tarihi"] else None,
                "yuz_dogrulandi": bool(k["yuz_dogrulandi"])
            } for k in katilimcilar]
        }
    })


# ==================== ÖĞRENCİ ENDPOINTLERİ ====================

@app.route("/ogrenci/derslerim", methods=["GET"])
@token_required
@role_required("ogrenci")
def get_student_courses():
    """Öğrencinin kayıtlı olduğu dersler"""
    ogrenci_id = g.kullanici_id
    
    dersler = query_db("""
        SELECT d.id, d.ad, d.kod, k.ad_soyad as ogretmen_adi
        FROM kayitlar ky
        JOIN dersler d ON ky.ders_id = d.id
        LEFT JOIN kullanicilar k ON d.ogretmen_id = k.id
        WHERE ky.ogrenci_id = %s
        ORDER BY d.ad
    """, (ogrenci_id,))
    
    return jsonify({"basarili": True, "dersler": dersler})


@app.route("/ogrenci/aktif-yoklamalar", methods=["GET"])
@token_required
@role_required("ogrenci")
def get_student_active_sessions():
    """Öğrencinin katılabileceği aktif yoklamalar"""
    ogrenci_id = g.kullanici_id
    
    # Öğrencinin kayıtlı olduğu derslerdeki aktif yoklamaları getir
    aktif_yoklamalar = query_db("""
        SELECT yo.id as oturum_id, d.id as ders_id, d.ad as ders_adi, 
               d.kod as ders_kodu, yo.baslangic_tarihi,
               k.ad_soyad as ogretmen_adi
        FROM yoklama_oturumlari yo
        JOIN dersler d ON yo.ders_id = d.id
        JOIN kayitlar ky ON d.id = ky.ders_id
        LEFT JOIN kullanicilar k ON d.ogretmen_id = k.id
        WHERE ky.ogrenci_id = %s AND yo.aktif = TRUE
    """, (ogrenci_id,))
    
    # Öğrencinin zaten katıldığı oturumları kontrol et
    result = []
    for y in aktif_yoklamalar:
        katildi = query_db(
            "SELECT id FROM yoklamalar WHERE oturum_id = %s AND ogrenci_id = %s",
            (y["oturum_id"], ogrenci_id), one=True
        )
        result.append({
            "oturum_id": y["oturum_id"],
            "ders_id": y["ders_id"],
            "ders_adi": y["ders_adi"],
            "ders_kodu": y["ders_kodu"],
            "ogretmen_adi": y["ogretmen_adi"],
            "baslangic": y["baslangic_tarihi"].isoformat() if y["baslangic_tarihi"] else None,
            "katildi": katildi is not None
        })
    
    return jsonify({"basarili": True, "yoklamalar": result})


@app.route("/ogrenci/yoklama/katil", methods=["POST"])
@token_required
@role_required("ogrenci")
def student_join_attendance():
    """Öğrenci yüz doğrulaması ile yoklamaya katıl"""
    ogrenci_id = g.kullanici_id
    oturum_id = request.form.get("oturum_id")
    
    if not oturum_id:
        return jsonify({"basarili": False, "hata": "Oturum ID gerekli"}), 400
    
    if "image" not in request.files:
        return jsonify({"basarili": False, "hata": "Yüz resmi gerekli"}), 400
    
    # Oturumun aktif ve öğrencinin kayıtlı olduğunu kontrol et
    oturum = query_db("""
        SELECT yo.id, d.ad as ders_adi
        FROM yoklama_oturumlari yo
        JOIN dersler d ON yo.ders_id = d.id
        JOIN kayitlar ky ON d.id = ky.ders_id
        WHERE yo.id = %s AND yo.aktif = TRUE AND ky.ogrenci_id = %s
    """, (oturum_id, ogrenci_id), one=True)
    
    if not oturum:
        return jsonify({"basarili": False, "hata": "Aktif oturum bulunamadı veya bu derse kayıtlı değilsiniz"}), 404
    
    # Zaten katıldı mı?
    zaten_katildi = query_db(
        "SELECT id FROM yoklamalar WHERE oturum_id = %s AND ogrenci_id = %s",
        (oturum_id, ogrenci_id), one=True
    )
    if zaten_katildi:
        return jsonify({"basarili": False, "hata": "Bu yoklamaya zaten katıldınız"}), 400
    
    # Öğrencinin kayıtlı yüzünü al
    ogrenci = query_db("SELECT yuz_encoding FROM kullanicilar WHERE id = %s", (ogrenci_id,), one=True)
    if not ogrenci or not ogrenci["yuz_encoding"]:
        return jsonify({"basarili": False, "hata": "Yüzünüz kayıtlı değil. Önce yüz kaydı yapın."}), 400
    
    kayitli_encoding = pickle.loads(ogrenci["yuz_encoding"])
    
    # Gönderilen resmi işle
    try:
        resim_dosya = request.files["image"]
        image_bytes = resim_dosya.read()
        result = process_image(image_bytes)
        
        if result is None:
            return jsonify({"basarili": False, "hata": "Resim okunamadı"}), 400
        
        rgb, _ = result
        locations = face_recognition.face_locations(rgb)
        
        if not locations:
            return jsonify({"basarili": False, "hata": "Yüz bulunamadı"}), 400
        
        gelen_encoding = face_recognition.face_encodings(rgb, locations)[0]
        
        # Yüz karşılaştır
        distance = face_recognition.face_distance([kayitli_encoding], gelen_encoding)[0]
        
        if distance > TOLERANCE:
            return jsonify({
                "basarili": False, 
                "hata": "Yüz doğrulanamadı. Kayıtlı yüzünüzle eşleşmiyor."
            }), 400
        
        # Yoklamaya ekle
        query_db(
            "INSERT INTO yoklamalar (oturum_id, ogrenci_id, yuz_dogrulandi) VALUES (%s, %s, TRUE)",
            (oturum_id, ogrenci_id), commit=True
        )
        
        confidence = round((1 - distance) * 100, 1)
        
        return jsonify({
            "basarili": True,
            "mesaj": f"{oturum['ders_adi']} yoklamasına katıldınız!",
            "guven_orani": confidence
        })
        
    except Exception as e:
        print(f"Yoklama katılım hatası: {e}")
        return jsonify({"basarili": False, "hata": str(e)}), 500


# ==================== MOBILE COMPATIBILITY ENDPOINTS ====================
# Bu endpointler mobil uygulamanın login olmadan test edilebilmesi içindir.
# İleride mobil uygulamaya login ekranı eklenince kaldırılabilir.

@app.route("/mobil/kayit", methods=["POST"])
def mobile_register():
    """Mobil uygulama için hızlı kayıt (Auth'sız)"""
    name = request.form.get("name")
    if not name:
        return jsonify({"success": False, "error": "İsim gerekli"}), 400
    
    if "image" not in request.files:
        return jsonify({"success": False, "error": "Resim gerekli"}), 400
        
    try:
        # Resmi işle
        resim_dosya = request.files["image"]
        image_bytes = resim_dosya.read()
        result = process_image(image_bytes)
        
        if result is None:
            return jsonify({"success": False, "error": "Resim okunamadı"}), 400
        
        rgb, bgr = result
        encoding, error = get_face_encoding(rgb)
        
        if error:
            return jsonify({"success": False, "error": error}), 400
            
        encoding_bytes = pickle.dumps(encoding)
        
        # Kullanıcıyı oluştur veya güncelle
        # Email unique olduğu için isme göre fake email oluşturuyoruz
        safe_name = "".join(c for c in name if c.isalnum()).lower()
        fake_email = f"{safe_name}@mobile.com"
        
        existing = query_db("SELECT id FROM kullanicilar WHERE email = %s", (fake_email,), one=True)
        
        if existing:
            query_db(
                "UPDATE kullanicilar SET ad_soyad = %s, yuz_encoding = %s WHERE id = %s",
                (name, encoding_bytes, existing["id"]),
                commit=True
            )
            msg = "Kullanıcı güncellendi"
        else:
            sifre_hash = hash_password("123456")
            query_db(
                "INSERT INTO kullanicilar (email, sifre_hash, ad_soyad, rol, onaylandi, yuz_encoding) VALUES (%s, %s, %s, 'ogrenci', TRUE, %s)",
                (fake_email, sifre_hash, name, encoding_bytes),
                commit=True
            )
            msg = "Kullanıcı oluşturuldu"
            
        # Resmi kaydet (Opsiyonel)
        person_dir = IMAGES_DIR / safe_name
        person_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        cv2.imwrite(str(person_dir / f"{timestamp}.jpg"), bgr)
        
        return jsonify({"success": True, "message": msg})
        
    except Exception as e:
        print(f"Mobil kayıt hatası: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/mobil/tanima", methods=["POST"])
def mobile_recognize():
    """Mobil uygulama için kimlik tespiti (1-N)"""
    if "image" not in request.files:
        return jsonify({"success": False, "error": "Resim gerekli"}), 400
        
    try:
        resim_dosya = request.files["image"]
        image_bytes = resim_dosya.read()
        result = process_image(image_bytes)
        
        if result is None:
            return jsonify({"success": False, "error": "Resim okunamadı"}), 400
            
        rgb, _ = result
        # Yüzü bul
        locations = face_recognition.face_locations(rgb)
        if not locations:
            return jsonify({"success": False, "error": "Yüz bulunamadı"}), 400
            
        unknown_encoding = face_recognition.face_encodings(rgb, locations)[0]
        
        # Tüm kayıtlı yüzleri getir
        kullanicilar = query_db("SELECT ad_soyad, yuz_encoding FROM kullanicilar WHERE yuz_encoding IS NOT NULL")
        
        best_match = None
        best_distance = TOLERANCE
        
        for k in kullanicilar:
            known_encoding = pickle.loads(k["yuz_encoding"])
            distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]
            
            if distance < best_distance:
                best_distance = distance
                best_match = k["ad_soyad"]
        
        if best_match:
            confidence = round((1 - best_distance) * 100, 1)
            return jsonify({
                "success": True,
                "recognized": True,
                "name": best_match,
                "confidence": confidence,
                "message": f"Tanındı: {best_match}"
            })
        else:
            return jsonify({
                "success": True,
                "recognized": False,
                "message": "Tanınamadı"
            })
            
    except Exception as e:
        print(f"Mobil tanıma hatası: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== MAIN ====================
if __name__ == "__main__":
    print("=" * 60)
    print("Yoklama Sistemi API Sunucusu v2.0")
    print("=" * 60)
    
    if not init_db_pool():
        print("\n⚠️  MySQL bağlantısı kurulamadı!")
        print("Lütfen MySQL'in çalıştığından ve veritabanının oluşturulduğundan emin olun:")
        print("  1. MySQL/MariaDB'yi başlatın")
        print("  2. database/schema.sql dosyasını çalıştırın")
        print("=" * 60)
        exit(1)
    
    print("\nEndpoints:")
    print("  Auth:       POST /auth/kayit, /auth/giris, GET /auth/ben")
    print("  Yüz:        POST /yuz/kayit, /yuz/dogrula")
    print("  Dersler:    GET/POST /dersler, PUT/DELETE /dersler/:id")
    print("  Kayıtlar:   POST /kayitlar, DELETE /kayitlar/:id")
    print("  Yoklama:    POST /yoklama/baslat, /yoklama/bitir/:id")
    print("              GET /yoklama/aktif, POST /yoklama/katil/:id")
    print("  Admin:      GET /admin/kullanicilar, POST /admin/kullanicilar/:id/onayla")
    print()
    print("Sunucu başlatılıyor: http://0.0.0.0:5000")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=5000, debug=True)
