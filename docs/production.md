# Production Deployment Guide

Bu belge, uygulamayı production ortamına alırken izlenecek canonical akıştır.

## 1. Önemli çalışma prensipleri

- Default user seed’leri production startup’ında kapalı tutulmalıdır.
- Docs, metrics ve detaylı health endpoint’leri internal token arkasında olmalıdır.
- `health/live` public probe olarak kullanılmalıdır.
- `docker-compose.prod.yml`, tek host deployment için örnek sağlar; gerçek multi-replica ve zero-downtime için orchestrator gerekir.

## 2. Hazırlık

JWT key üret:

```bash
mkdir -p keys
openssl genrsa -out keys/private.pem 4096
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
chmod 600 keys/private.pem
```

Secret üret:

```bash
openssl rand -hex 32
openssl rand -hex 32   # INTERNAL_ACCESS_TOKEN için de kullanılabilir
```

## 3. Production `.env` örneği

Minimum kritik alanlar:

```env
APP_ENV=production
APP_DEBUG=false
APP_URL=https://api.example.com
FRONTEND_URL=https://app.example.com
SECRET_KEY=<strong-random-value>
ALLOWED_HOSTS=["api.example.com"]
CORS_ORIGINS=["https://app.example.com"]
COOKIE_SECURE=true
ADMIN_SESSION_COOKIE_SECURE=true
DOCS_ACCESS_MODE=internal
METRICS_ACCESS_MODE=internal
HEALTH_DETAIL_ACCESS_MODE=internal
INTERNAL_ACCESS_TOKEN=<strong-random-token>
SEED_SYSTEM_ROLES_ON_STARTUP=false
SEED_DEFAULT_SUPERADMIN=false
SEED_DEFAULT_APP_USER=false
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=
```

## 4. Compose ile başlatma

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Migration:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head
```

Canonical role sync gerekiyorsa:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api python -c "import asyncio; from app.admin.seed import seed_system_roles; asyncio.run(seed_system_roles())"
```

## 5. İlk admin bootstrap

Production’da default admin seed yerine explicit bootstrap önerilir:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
  python scripts/make_admin.py --create --email admin@example.com --password 'StrongAdminPass123!'
```

Mevcut kullanıcıyı admin yapmak:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
  python scripts/make_admin.py --email existing.user@example.com
```

## 6. Runtime access policy kullanımı

### Docs

Tarayıcıdan docs açmak için:

```text
https://api.example.com/docs?access_token=<INTERNAL_ACCESS_TOKEN>
https://api.example.com/schema/admin/docs?access_token=<INTERNAL_ACCESS_TOKEN>
```

### Metrics

```bash
curl -H "X-Internal-Access-Token: $INTERNAL_ACCESS_TOKEN" \
  https://api.example.com/metrics
```

### Detailed health

```bash
curl -H "X-Internal-Access-Token: $INTERNAL_ACCESS_TOKEN" \
  https://api.example.com/health/ready
```

Public probe:

```bash
curl https://api.example.com/health/live
```

## 7. Nginx ve TLS

Nginx:

- TLS termination yapar
- auth endpoint’lerinde rate limit uygular
- `X-Internal-Access-Token` header’ını backend’e forward eder

Sertifika dosyaları:

- `/etc/nginx/certs/fullchain.pem`
- `/etc/nginx/certs/privkey.pem`

Compose örneği mount üzerinden bu dosyaları bekler. Let’s Encrypt, certbot veya kurum içi PKI ile bu lifecycle sizin altyapınızda yönetilmelidir.

## 8. Compose sınırları

`docker-compose.prod.yml` şunları sağlar:

- prod-target image
- host’a kapatılmış db/redis/minio portları
- nginx reverse proxy
- API healthcheck

Şunları garanti etmez:

- gerçek auto-scaling
- zero-downtime rollout
- cross-host high availability
- managed secret rotation

Bu ihtiyaçlar için Kubernetes, Nomad veya Swarm benzeri bir orchestrator gerekir.

## 9. Production checklist

- `SECRET_KEY` ve `INTERNAL_ACCESS_TOKEN` güçlü değerlerle üretildi
- `ALLOWED_HOSTS` wildcard içermiyor
- `CORS_ORIGINS` gerçek frontend origin’leriyle sınırlandı
- `COOKIE_SECURE=true`
- `ADMIN_SESSION_COOKIE_SECURE=true`
- `DOCS_ACCESS_MODE`, `METRICS_ACCESS_MODE`, `HEALTH_DETAIL_ACCESS_MODE` prod politikasına göre ayarlandı
- seed flag’leri default kapalı
- migration uygulandı
- ilk admin explicit komutla oluşturuldu
- `health/live` load balancer probe olarak tanımlandı
- log toplama ve backup stratejisi aktif
