-- Yoklama Sistemi Veritabanı Şeması
-- MySQL / MariaDB
-- Tüm tablo ve alan isimleri Türkçe

CREATE DATABASE IF NOT EXISTS yoklama_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE yoklama_db;

-- Mevcut tabloları sil (yeniden oluşturmak için)
-- Eski İngilizce tablolar
DROP TABLE IF EXISTS attendances;
DROP TABLE IF EXISTS attendance_sessions;
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS users;

-- Yeni Türkçe tablolar
DROP TABLE IF EXISTS yoklamalar;
DROP TABLE IF EXISTS yoklama_oturumlari;
DROP TABLE IF EXISTS kayitlar;
DROP TABLE IF EXISTS dersler;
DROP TABLE IF EXISTS kullanicilar;

-- Kullanıcılar tablosu
CREATE TABLE IF NOT EXISTS kullanicilar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    sifre_hash VARCHAR(255) NOT NULL,
    ad_soyad VARCHAR(255) NOT NULL,
    rol ENUM('ogrenci', 'ogretmen', 'admin') NOT NULL DEFAULT 'ogrenci',
    yuz_encoding BLOB,
    onaylandi BOOLEAN DEFAULT FALSE,
    olusturma_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    guncelleme_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_rol (rol)
) ENGINE=InnoDB;

-- Dersler tablosu
CREATE TABLE IF NOT EXISTS dersler (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ad VARCHAR(255) NOT NULL,
    kod VARCHAR(50) NOT NULL UNIQUE,
    ogretmen_id INT,
    olusturma_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    guncelleme_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (ogretmen_id) REFERENCES kullanicilar(id) ON DELETE SET NULL,
    INDEX idx_ogretmen (ogretmen_id)
) ENGINE=InnoDB;

-- Öğrenci-Ders kayıtları
CREATE TABLE IF NOT EXISTS kayitlar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ogrenci_id INT NOT NULL,
    ders_id INT NOT NULL,
    kayit_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ogrenci_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
    FOREIGN KEY (ders_id) REFERENCES dersler(id) ON DELETE CASCADE,
    UNIQUE KEY benzersiz_kayit (ogrenci_id, ders_id),
    INDEX idx_ogrenci (ogrenci_id),
    INDEX idx_ders (ders_id)
) ENGINE=InnoDB;

-- Yoklama oturumları
CREATE TABLE IF NOT EXISTS yoklama_oturumlari (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ders_id INT NOT NULL,
    baslangic_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    bitis_tarihi DATETIME,
    aktif BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (ders_id) REFERENCES dersler(id) ON DELETE CASCADE,
    INDEX idx_ders (ders_id),
    INDEX idx_aktif (aktif)
) ENGINE=InnoDB;

-- Yoklama kayıtları
CREATE TABLE IF NOT EXISTS yoklamalar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    oturum_id INT NOT NULL,
    ogrenci_id INT NOT NULL,
    katilim_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
    yuz_dogrulandi BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (oturum_id) REFERENCES yoklama_oturumlari(id) ON DELETE CASCADE,
    FOREIGN KEY (ogrenci_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
    UNIQUE KEY benzersiz_yoklama (oturum_id, ogrenci_id),
    INDEX idx_oturum (oturum_id),
    INDEX idx_ogrenci (ogrenci_id)
) ENGINE=InnoDB;

-- =====================================================
-- BAŞLANGIÇ VERİLERİ
-- =====================================================

-- Varsayılan Admin kullanıcısı
-- Şifre: admin123 (bcrypt hash)
INSERT INTO kullanicilar (email, sifre_hash, ad_soyad, rol, onaylandi) VALUES
('admin@yoklama.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz0PtwNJ6kJsQzGJGpC6x5cHjO1z0Gy', 'Sistem Admin', 'admin', TRUE)
ON DUPLICATE KEY UPDATE ad_soyad = ad_soyad;

-- Başlangıç dersleri
INSERT INTO dersler (ad, kod) VALUES
('Java Programlama', 'JAVA101'),
('İleri İnternet Programlama', 'WEB301'),
('Makine Öğrenmesi', 'ML201'),
('Bilişim Hukuku', 'LAW101'),
('Python Programlama', 'PY101')
ON DUPLICATE KEY UPDATE ad = VALUES(ad);

-- =====================================================
-- YARDIMCI GÖRÜNÜMLER (VIEWS)
-- =====================================================

-- Aktif yoklama oturumları görünümü
CREATE OR REPLACE VIEW aktif_oturumlar_view AS
SELECT 
    yo.id AS oturum_id,
    yo.baslangic_tarihi,
    d.id AS ders_id,
    d.ad AS ders_adi,
    d.kod AS ders_kodu,
    k.ad_soyad AS ogretmen_adi
FROM yoklama_oturumlari yo
JOIN dersler d ON yo.ders_id = d.id
LEFT JOIN kullanicilar k ON d.ogretmen_id = k.id
WHERE yo.aktif = TRUE;

-- Ders bazlı yoklama istatistikleri
CREATE OR REPLACE VIEW ders_yoklama_istatistikleri AS
SELECT 
    d.id AS ders_id,
    d.ad AS ders_adi,
    COUNT(DISTINCT ky.ogrenci_id) AS toplam_ogrenci,
    COUNT(DISTINCT yo.id) AS toplam_oturum,
    COUNT(DISTINCT y.id) AS toplam_yoklama
FROM dersler d
LEFT JOIN kayitlar ky ON d.id = ky.ders_id
LEFT JOIN yoklama_oturumlari yo ON d.id = yo.ders_id
LEFT JOIN yoklamalar y ON yo.id = y.oturum_id
GROUP BY d.id, d.ad;
