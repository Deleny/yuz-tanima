"""
Yuz Tanima REST API Server
Flask ile mobil uygulama icin yuz kayit ve tanima API'si
"""

import io
import time
import pickle
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

try:
    import cv2
    import face_recognition
    import numpy as np
except ImportError as exc:
    print("Eksik kutuphane:", exc)
    print("Kurulum: pip install opencv-python face_recognition numpy flask flask-cors")
    exit(1)

app = Flask(__name__)
CORS(app)  # Mobil uygulamadan erişim için

BASE_DIR = Path(__file__).resolve().parent
ENCODINGS_PATH = BASE_DIR / "encodings.pkl"
IMAGES_DIR = BASE_DIR / "face_data"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

TOLERANCE = 0.5  # Yüz eşleştirme toleransı


def load_encodings():
    """Kayıtlı yüz encoding'lerini yükle"""
    if not ENCODINGS_PATH.exists():
        return {"names": [], "encodings": []}
    try:
        with ENCODINGS_PATH.open("rb") as handle:
            data = pickle.load(handle)
        if "names" not in data or "encodings" not in data:
            return {"names": [], "encodings": []}
        return data
    except Exception as e:
        print(f"Encoding yuklenirken hata: {e}")
        return {"names": [], "encodings": []}


def save_encodings(data):
    """Yüz encoding'lerini kaydet"""
    with ENCODINGS_PATH.open("wb") as handle:
        pickle.dump(data, handle)


def safe_name(name):
    """Dosya adı için güvenli isim oluştur"""
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in ("_", "-", " "))
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned or "user"


def process_image(image_bytes):
    """Byte dizisinden OpenCV image oluştur"""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    # BGR -> RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return rgb, img


@app.route("/", methods=["GET"])
def index():
    """API sağlık kontrolü"""
    data = load_encodings()
    unique_names = list(set(data["names"]))
    return jsonify({
        "status": "ok",
        "message": "Yuz Tanima API calisiyor",
        "registered_faces": len(data["names"]),
        "unique_people": len(unique_names),
        "people": unique_names
    })


@app.route("/register", methods=["POST"])
def register():
    """
    Yüz kayıt endpoint'i
    
    Form Data:
        - name: Kişinin adı (string)
        - image: Yüz fotoğrafı (file)
    
    Returns:
        JSON response with success/error status
    """
    # İsim kontrolü
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Isim gerekli"}), 400
    
    # Dosya kontrolü
    if "image" not in request.files:
        return jsonify({"success": False, "error": "Resim dosyasi gerekli"}), 400
    
    image_file = request.files["image"]
    if image_file.filename == "":
        return jsonify({"success": False, "error": "Resim secilmedi"}), 400
    
    try:
        # Resmi oku
        image_bytes = image_file.read()
        result = process_image(image_bytes)
        if result is None:
            return jsonify({"success": False, "error": "Resim okunamadi"}), 400
        
        rgb, bgr = result
        
        # Yüz bul
        locations = face_recognition.face_locations(rgb)
        
        if len(locations) == 0:
            return jsonify({"success": False, "error": "Yuz bulunamadi"}), 400
        
        if len(locations) > 1:
            return jsonify({"success": False, "error": "Birden fazla yuz algilandi. Tek yuz gosterin."}), 400
        
        # Encoding hesapla
        encodings = face_recognition.face_encodings(rgb, locations)
        if len(encodings) == 0:
            return jsonify({"success": False, "error": "Yuz encoding'i olusturulamadi"}), 400
        
        encoding = encodings[0]
        
        # Resmi kaydet
        person_dir = IMAGES_DIR / safe_name(name)
        person_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        image_path = person_dir / f"{timestamp}.jpg"
        cv2.imwrite(str(image_path), bgr)
        
        # Encoding'i kaydet
        data = load_encodings()
        data["names"].append(name)
        data["encodings"].append(encoding)
        save_encodings(data)
        
        return jsonify({
            "success": True,
            "message": f"{name} basariyla kaydedildi",
            "total_samples": len(data["names"]),
            "saved_image": str(image_path)
        })
        
    except Exception as e:
        print(f"Kayit hatasi: {e}")
        return jsonify({"success": False, "error": f"Sunucu hatasi: {str(e)}"}), 500


@app.route("/recognize", methods=["POST"])
def recognize():
    """
    Yüz tanıma endpoint'i
    
    Form Data:
        - image: Tanınacak yüz fotoğrafı (file)
    
    Returns:
        JSON response with recognized name or unknown status
    """
    # Kayıtlı yüz kontrolü
    data = load_encodings()
    if not data["encodings"]:
        return jsonify({
            "success": False, 
            "error": "Kayitli yuz yok. Once yuz kaydi yapin."
        }), 400
    
    # Dosya kontrolü
    if "image" not in request.files:
        return jsonify({"success": False, "error": "Resim dosyasi gerekli"}), 400
    
    image_file = request.files["image"]
    if image_file.filename == "":
        return jsonify({"success": False, "error": "Resim secilmedi"}), 400
    
    try:
        # Resmi oku
        image_bytes = image_file.read()
        result = process_image(image_bytes)
        if result is None:
            return jsonify({"success": False, "error": "Resim okunamadi"}), 400
        
        rgb, _ = result
        
        # Yüz bul
        locations = face_recognition.face_locations(rgb)
        
        if len(locations) == 0:
            return jsonify({"success": False, "error": "Yuz bulunamadi"}), 400
        
        if len(locations) > 1:
            return jsonify({
                "success": False, 
                "error": "Birden fazla yuz algilandi"
            }), 400
        
        # Encoding hesapla
        encodings = face_recognition.face_encodings(rgb, locations)
        if len(encodings) == 0:
            return jsonify({"success": False, "error": "Yuz encoding'i olusturulamadi"}), 400
        
        encoding = encodings[0]
        
        # Eşleştir
        matches = face_recognition.compare_faces(data["encodings"], encoding, tolerance=TOLERANCE)
        
        if not any(matches):
            return jsonify({
                "success": True,
                "recognized": False,
                "name": None,
                "message": "Yuz taninamadi"
            })
        
        # En iyi eşleşmeyi bul
        distances = face_recognition.face_distance(data["encodings"], encoding)
        best_index = int(np.argmin(distances))
        
        if matches[best_index]:
            name = data["names"][best_index]
            confidence = 1 - distances[best_index]
            return jsonify({
                "success": True,
                "recognized": True,
                "name": name,
                "confidence": round(confidence * 100, 2),
                "message": f"Hosgeldin {name}!"
            })
        else:
            return jsonify({
                "success": True,
                "recognized": False,
                "name": None,
                "message": "Yuz taninamadi"
            })
        
    except Exception as e:
        print(f"Tanima hatasi: {e}")
        return jsonify({"success": False, "error": f"Sunucu hatasi: {str(e)}"}), 500


@app.route("/list", methods=["GET"])
def list_faces():
    """Kayıtlı kişileri listele"""
    data = load_encodings()
    unique_names = list(set(data["names"]))
    counts = {name: data["names"].count(name) for name in unique_names}
    
    return jsonify({
        "success": True,
        "people": [{"name": name, "sample_count": counts[name]} for name in unique_names],
        "total_samples": len(data["names"]),
        "total_people": len(unique_names)
    })


@app.route("/delete/<name>", methods=["DELETE"])
def delete_face(name):
    """Kişiyi sil"""
    data = load_encodings()
    
    # İsmi bul ve sil
    indices_to_remove = [i for i, n in enumerate(data["names"]) if n == name]
    
    if not indices_to_remove:
        return jsonify({"success": False, "error": f"{name} bulunamadi"}), 404
    
    # Tersten sil (index kaymaması için)
    for i in sorted(indices_to_remove, reverse=True):
        del data["names"][i]
        del data["encodings"][i]
    
    save_encodings(data)
    
    return jsonify({
        "success": True,
        "message": f"{name} silindi",
        "removed_samples": len(indices_to_remove)
    })


if __name__ == "__main__":
    print("=" * 50)
    print("Yuz Tanima API Sunucusu")
    print("=" * 50)
    
    data = load_encodings()
    unique_names = list(set(data["names"]))
    print(f"Kayitli yuz sayisi: {len(data['names'])}")
    print(f"Kayitli kisi sayisi: {len(unique_names)}")
    if unique_names:
        print(f"Kisiler: {', '.join(unique_names)}")
    
    print()
    print("Endpointler:")
    print("  GET  /          - API durumu")
    print("  POST /register  - Yuz kaydet (name + image)")
    print("  POST /recognize - Yuz tani (image)")
    print("  GET  /list      - Kayitli kisileri listele")
    print("  DELETE /delete/<name> - Kisiyi sil")
    print()
    print("Sunucu baslatiliyor: http://0.0.0.0:5000")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=5000, debug=True)
