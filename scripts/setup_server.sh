#!/bin/bash
# EC2 Sunucu Kurulum Scripti
# Ubuntu 22.04 LTS için

set -e

echo "=========================================="
echo "Yoklama Sistemi - Sunucu Kurulumu"
echo "=========================================="

# Sistem güncellemesi
echo ">>> Sistem güncelleniyor..."
sudo apt update && sudo apt upgrade -y

# Temel paketler
echo ">>> Temel paketler kuruluyor..."
sudo apt install -y python3 python3-pip python3-venv git cmake build-essential

# face_recognition için gerekli kütüphaneler
echo ">>> Face recognition bağımlılıkları kuruluyor..."
sudo apt install -y libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev

# MariaDB kurulumu
echo ">>> MariaDB kuruluyor..."
sudo apt install -y mariadb-server mariadb-client

# MariaDB servisini başlat
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Repo'yu klonla
echo ">>> Repo klonlanıyor..."
cd ~
if [ -d "yuz-tanima" ]; then
    cd yuz-tanima
    git pull origin main
else
    git clone https://github.com/Deleny/yuz-tanima.git
    cd yuz-tanima
fi

# Virtual environment oluştur
echo ">>> Python virtual environment oluşturuluyor..."
python3 -m venv venv
source venv/bin/activate

# Python paketlerini kur
echo ">>> Python paketleri kuruluyor (bu biraz sürebilir)..."
pip install --upgrade pip
pip install -r requirements.txt

# Veritabanını oluştur
echo ">>> Veritabanı oluşturuluyor..."
sudo mysql -u root << EOF
CREATE DATABASE IF NOT EXISTS yoklama_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'yoklama_user'@'localhost' IDENTIFIED BY 'YoklamaPass123!';
GRANT ALL PRIVILEGES ON yoklama_db.* TO 'yoklama_user'@'localhost';
FLUSH PRIVILEGES;
EOF

# Schema'yı çalıştır
sudo mysql -u root yoklama_db < database/schema.sql

# Systemd service dosyası oluştur
echo ">>> Systemd servisi oluşturuluyor..."
sudo tee /etc/systemd/system/yoklama-api.service > /dev/null << EOF
[Unit]
Description=Yoklama Sistemi API
After=network.target mariadb.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/yuz-tanima
Environment="PATH=/home/ubuntu/yuz-tanima/venv/bin"
Environment="DB_HOST=localhost"
Environment="DB_USER=yoklama_user"
Environment="DB_PASSWORD=YoklamaPass123!"
Environment="DB_NAME=yoklama_db"
Environment="JWT_SECRET=production-secret-key-change-this"
ExecStart=/home/ubuntu/yuz-tanima/venv/bin/python api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Servisi etkinleştir ve başlat
sudo systemctl daemon-reload
sudo systemctl enable yoklama-api
sudo systemctl start yoklama-api

echo "=========================================="
echo "Kurulum tamamlandı!"
echo "=========================================="
echo ""
echo "API durumu: sudo systemctl status yoklama-api"
echo "API logları: sudo journalctl -u yoklama-api -f"
echo ""
echo "API URL: http://$(curl -s ifconfig.me):5000"
echo "=========================================="
