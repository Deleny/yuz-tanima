#!/usr/bin/env python3
"""
Test kullanıcıları ve ders atamalarını oluşturan script.
EC2'de çalıştırılmalı: python3 scripts/setup_test_data.py
"""

import bcrypt
import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "yoklama_user",
    "password": "YoklamaPass123!",
    "database": "yoklama_db"
}

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def main():
    print("Test verileri oluşturuluyor...")
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    # Şifre hash'le
    sifre_hash = hash_password("123456")
    print(f"Şifre hash oluşturuldu")
    
    # Öğretmen ekle/güncelle
    cursor.execute("""
        INSERT INTO kullanicilar (email, sifre_hash, ad_soyad, rol, onaylandi)
        VALUES ('ogretmen@okul.com', %s, 'Ahmet Öğretmen', 'ogretmen', TRUE)
        ON DUPLICATE KEY UPDATE sifre_hash = VALUES(sifre_hash), onaylandi = TRUE
    """, (sifre_hash,))
    print("✓ Öğretmen eklendi: ogretmen@okul.com / 123456")
    
    # Öğrenci ekle/güncelle
    cursor.execute("""
        INSERT INTO kullanicilar (email, sifre_hash, ad_soyad, rol, onaylandi)
        VALUES ('ogrenci@okul.com', %s, 'Mehmet Öğrenci', 'ogrenci', TRUE)
        ON DUPLICATE KEY UPDATE sifre_hash = VALUES(sifre_hash), onaylandi = TRUE
    """, (sifre_hash,))
    print("✓ Öğrenci eklendi: ogrenci@okul.com / 123456")
    
    # Admin güncelle
    cursor.execute("""
        UPDATE kullanicilar SET sifre_hash = %s WHERE email = 'admin@yoklama.com'
    """, (hash_password("admin123"),))
    print("✓ Admin güncellendi: admin@yoklama.com / admin123")
    
    conn.commit()
    
    # Öğretmen ID'sini al
    cursor.execute("SELECT id FROM kullanicilar WHERE email = 'ogretmen@okul.com'")
    ogretmen = cursor.fetchone()
    ogretmen_id = ogretmen["id"] if ogretmen else None
    
    # Öğrenci ID'sini al
    cursor.execute("SELECT id FROM kullanicilar WHERE email = 'ogrenci@okul.com'")
    ogrenci = cursor.fetchone()
    ogrenci_id = ogrenci["id"] if ogrenci else None
    
    if ogretmen_id:
        # Dersleri öğretmene ata
        cursor.execute("""
            UPDATE dersler SET ogretmen_id = %s WHERE kod IN ('JAVA101', 'PY101')
        """, (ogretmen_id,))
        print(f"✓ Java ve Python dersleri öğretmene atandı")
        conn.commit()
    
    if ogrenci_id:
        # Öğrenciyi derslere kaydet
        cursor.execute("SELECT id FROM dersler WHERE kod IN ('JAVA101', 'PY101')")
        dersler = cursor.fetchall()
        
        for ders in dersler:
            try:
                cursor.execute("""
                    INSERT INTO kayitlar (ogrenci_id, ders_id) VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE kayit_tarihi = NOW()
                """, (ogrenci_id, ders["id"]))
            except:
                pass
        print(f"✓ Öğrenci {len(dersler)} derse kaydedildi")
        conn.commit()
    
    # Özet
    print("\n" + "="*50)
    print("KURULUM TAMAMLANDI!")
    print("="*50)
    print("\nTest Hesapları:")
    print("  👨‍🏫 Öğretmen: ogretmen@okul.com / 123456")
    print("  👨‍🎓 Öğrenci:  ogrenci@okul.com / 123456")
    print("  🔧 Admin:     admin@yoklama.com / admin123")
    print("\nDersler:")
    cursor.execute("SELECT ad, kod, ogretmen_id FROM dersler")
    for d in cursor.fetchall():
        status = "✓" if d["ogretmen_id"] else "○"
        print(f"  {status} {d['ad']} ({d['kod']})")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
