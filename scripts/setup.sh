#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — İlk kurulum scripti
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "🔑 RS256 JWT key'leri oluşturuluyor..."
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
chmod 600 keys/private.pem
echo "✅ Key'ler oluşturuldu: keys/private.pem, keys/public.pem"

echo ""
echo "📋 .env dosyası hazırlanıyor..."
if [ ! -f .env ]; then
    cp .env.example .env
    # Rastgele SECRET_KEY üret
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/change-this-to-a-random-secret-key-in-production/$SECRET_KEY/" .env
    echo "✅ .env oluşturuldu — SECRET_KEY otomatik ayarlandı"
else
    echo "⚠️  .env zaten mevcut, atlanıyor"
fi

echo ""
echo "🐳 Docker servisleri başlatılıyor..."
docker compose up -d

echo ""
echo "⏳ DB hazır olana kadar bekleniyor..."
sleep 5

echo ""
echo "🗃️  Migration çalıştırılıyor..."
docker compose exec api alembic upgrade head

echo ""
echo "✅ Kurulum tamamlandı!"
echo ""
echo "📚 API Docs: http://localhost:8000/docs"
echo "🗄️  MinIO:   http://localhost:9001  (kullanıcı: minioadmin)"
echo "🔴 Redis:   localhost:6379"
echo "🐘 Postgres: localhost:5432"
