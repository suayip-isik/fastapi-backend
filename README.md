# FastAPI Production Backend

> Modüler · Ölçeklenebilir · API-First · Production-Ready

[![Lint & Type Check](../../actions/workflows/lint.yml/badge.svg)](../../actions/workflows/lint.yml)
[![Tests](../../actions/workflows/test.yml/badge.svg)](../../actions/workflows/test.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)

FastAPI tabanlı, production kullanımına hazır bir backend boilerplate. Katmanlı mimari, async PostgreSQL, Redis, S3 uyumlu depolama, WebSocket, 2FA, OAuth2, audit log ve daha fazlasını içerir.

---

## İçindekiler

1. [Tech Stack](#tech-stack)
2. [Proje Yapısı](#proje-yapısı)
3. [Mimari Prensipler](#mimari-prensipler)
4. [Ön Gereksinimler](#ön-gereksinimler)
5. [Hızlı Başlangıç](#hızlı-başlangıç)
6. [Makefile Komutları](#makefile-komutları)
7. [Ortam Değişkenleri](#ortam-değişkenleri)
8. [API Endpointleri](#api-endpointleri)
9. [Admin Panel](#admin-panel)
10. [Güvenlik Özellikleri](#güvenlik-özellikleri)
11. [WebSocket Entegrasyonu](#websocket-entegrasyonu)
12. [Bildirim Sistemi](#bildirim-sistemi)
13. [Yeni Özellik Ekleme Rehberi](#yeni-özellik-ekleme-rehberi)
14. [Testler](#testler)
15. [Kod Kalitesi](#kod-kalitesi)
16. [CI/CD Pipeline](#cicd-pipeline)
17. [Production Deployment](#production-deployment)
18. [Troubleshooting](#troubleshooting)
19. [Katkıda Bulunma](#katkıda-bulunma)

---

## Tech Stack

| Katman           | Teknoloji                                        |
| ---------------- | ------------------------------------------------ |
| Framework        | FastAPI + Python 3.12                            |
| Veritabanı       | PostgreSQL 16 + SQLAlchemy 2.0 (async, asyncpg)  |
| Migrations       | Alembic                                          |
| Cache / Queue    | Redis 7 (rate limiting, token blacklist, ARQ)    |
| Background Jobs  | ARQ (Redis-based async task queue)               |
| Auth             | OAuth2 + JWT RS256 + TOTP/2FA + API Key          |
| OAuth Providers  | Google, GitHub                                   |
| Depolama         | S3-uyumlu (MinIO lokal / AWS S3 prod)            |
| WebSocket        | FastAPI native (room tabanlı)                    |
| Rate Limiting    | slowapi (Redis-backed, endpoint-specific)        |
| Validation       | Pydantic v2                                      |
| Admin Panel      | SQLAdmin (rol tabanlı, JWT doğrulamalı)          |
| Metrikler        | Prometheus (`prometheus-fastapi-instrumentator`) |
| Hata Takibi      | Sentry (`sentry-sdk[fastapi]`)                   |
| Loglama          | structlog (JSON formatında yapısal log)          |
| Containerization | Docker + Docker Compose                          |
| Testler          | pytest + pytest-asyncio (asyncio_mode=auto)      |
| Linting          | ruff 0.6.9 (linter + formatter)                  |
| Tip Kontrolü     | mypy 1.11.2 (strict mode)                        |
| Kod Kalitesi     | pre-commit hooks                                 |
| CI               | GitHub Actions (lint + test paralel job'lar)     |
| API Docs         | OpenAPI (Swagger UI + ReDoc — otomatik üretilir) |

---

## Proje Yapısı

```
fastapi-backend/
├── app/
│   ├── main.py                         # FastAPI app factory (lifespan, middleware, exception handler)
│   ├── api/
│   │   ├── dependencies/
│   │   │   └── auth.py                 # Auth bağımlılıkları (JWT + API Key, rol kontrolleri)
│   │   └── v1/
│   │       ├── router.py               # Ana router (tüm endpoint'leri birleştirir)
│   │       └── endpoints/
│   │           ├── auth.py             # Kayıt, giriş, çıkış, OAuth, e-posta doğrulama, şifre sıfırlama
│   │           ├── totp.py             # 2FA kurulum, doğrulama, devre dışı bırakma
│   │           ├── users.py            # Kullanıcı profili ve yönetimi
│   │           ├── api_keys.py         # API key oluşturma, listeleme, iptal
│   │           ├── notifications.py    # Uygulama içi bildirimler
│   │           └── uploads.py          # Dosya yükleme ve silme
│   ├── core/
│   │   ├── config.py                   # Pydantic Settings (tüm env değişkenleri)
│   │   ├── security.py                 # JWT RS256, bcrypt, token yardımcıları
│   │   ├── exceptions.py               # Global exception hiyerarşisi ve handler'lar
│   │   ├── logging.py                  # structlog JSON yapısal loglama + context var'lar
│   │   ├── middleware.py               # RequestID, SecurityHeaders, Timing middleware'leri
│   │   ├── limiter.py                  # Rate limiting (slowapi + Redis)
│   │   ├── redis.py                    # Redis client başlatma ve yönetimi
│   │   ├── email.py                    # SMTP e-posta gönderimi
│   │   ├── health.py                   # DB, Redis, Storage sağlık kontrolleri
│   │   └── metrics.py                  # Prometheus metrik kurulumu
│   ├── db/
│   │   ├── session.py                  # Async DB session factory ve engine
│   │   ├── models/
│   │   │   ├── base.py                 # BaseModel (UUID PK, created_at, updated_at)
│   │   │   ├── user.py                 # User modeli (rol, TOTP, OAuth ilişkileri)
│   │   │   ├── oauth_account.py        # OAuth hesap bağlantıları
│   │   │   ├── api_key.py              # API key saklama (bcrypt hash)
│   │   │   ├── audit_log.py            # Denetim kayıtları
│   │   │   └── notification.py         # Uygulama içi bildirimler
│   │   └── repositories/
│   │       ├── base.py                 # Generic BaseRepository[T] (get_page window fn)
│   │       ├── user.py                 # UserRepository
│   │       ├── oauth_account.py        # OAuthAccountRepository (provider upsert)
│   │       ├── api_key.py              # APIKeyRepository
│   │       ├── audit_log.py            # AuditLogRepository
│   │       └── notification.py         # NotificationRepository
│   ├── services/
│   │   ├── base.py                     # AuditableMixin (audit log paylaşımlı helper)
│   │   ├── _keys.py                    # Redis key sabitleri (magic string'leri önler)
│   │   ├── auth.py                     # AuthService — kayıt, giriş, çıkış, token yönetimi
│   │   ├── oauth.py                    # OAuthService — Google ve GitHub OAuth akışları
│   │   ├── account.py                  # AccountService — e-posta doğrulama, şifre sıfırlama
│   │   ├── user.py                     # UserService — kullanıcı CRUD + sayfalama
│   │   ├── api_key.py                  # APIKeyService — key oluşturma, doğrulama, iptal
│   │   ├── notification.py             # NotificationService — bildirim + WebSocket push
│   │   ├── totp.py                     # TOTPService — 2FA kurulum, doğrulama, yedek kodlar
│   │   └── audit.py                    # AuditService — bağımsız session ile audit log
│   ├── schemas/
│   │   ├── auth.py                     # Auth istek/yanıt şemaları (kayıt, giriş, token vb.)
│   │   ├── user.py                     # Kullanıcı istek/yanıt şemaları
│   │   └── common.py                   # Ortak şemalar (PaginatedResponse, MessageResponse)
│   ├── admin/
│   │   ├── views.py                    # SQLAdmin model view'ları
│   │   ├── auth.py                     # Admin authentication backend
│   │   └── seed.py                     # Varsayılan admin kullanıcı oluşturma
│   ├── websockets/
│   │   └── manager.py                  # ConnectionManager (oda tabanlı broadcast)
│   ├── storage/
│   │   └── backends.py                 # MinIO/S3 depolama backend'i
│   ├── tasks/
│   │   └── worker.py                   # ARQ worker ayarları ve task'lar
│   └── utils/
│       └── helpers.py                  # Yardımcı fonksiyonlar
├── alembic/
│   ├── versions/                       # Migration dosyaları
│   └── env.py                          # Migration ortam konfigürasyonu
├── tests/
│   ├── conftest.py                     # pytest fixture'ları (client, db_session, fake_redis)
│   ├── unit/                           # Unit testler (DB gerektirmez)
│   └── integration/                    # Integration testler (gerçek DB kullanır)
├── scripts/
│   └── create_buckets.py               # S3/MinIO bucket oluşturma scripti
├── docker/
│   └── Dockerfile                      # Multi-stage build (development + production)
├── keys/                               # JWT RSA key çifti (commit edilmez)
│   ├── private.pem
│   └── public.pem
├── docker-compose.yml                  # Geliştirme ortamı (api, worker, db, redis, minio)
├── docker-compose.prod.yml             # Production override'ları
├── Makefile                            # Geliştirme kısayolları
├── pyproject.toml                      # ruff, mypy, pytest konfigürasyonu
├── requirements.txt                    # Production bağımlılıkları
├── requirements-dev.txt                # Geliştirme bağımlılıkları
├── alembic.ini                         # Alembic konfigürasyonu
└── .env.example                        # Ortam değişkeni şablonu
```

---

## Mimari Prensipler

Bu proje katmanlı bir mimari uygular; her katmanın tek bir sorumluluğu vardır.

| Katman             | Konum                   | Sorumluluk                                             |
| ------------------ | ----------------------- | ------------------------------------------------------ |
| API Katmanı        | `app/api/v1/endpoints/` | Sadece HTTP routing — iş mantığı yok, service'e delege |
| Service Katmanı    | `app/services/`         | Tüm iş mantığı — repository'lerden bağımsız            |
| Repository Katmanı | `app/db/repositories/`  | Tüm DB erişimi — service'ler SQLAlchemy kullanmaz      |
| Core               | `app/core/`             | Altyapı: config, security, logging, middleware         |

**Temel Desenler:**

- **Repository Pattern** — DB erişimi tamamen soyutlandı; `BaseRepository[T]` generic CRUD sağlar
- **Service Layer (SRP)** — Her service tek sorumluluğu yönetir (`AuthService`, `UserService` vb.)
- **Dependency Injection** — FastAPI `Depends()` ile loose coupling; service constructor'larına inject edilir
- **AuditableMixin** — `services/base.py`'deki mixin ile audit log kodu tekrarlanmaz
- **Redis Key Sabitleri** — `services/_keys.py`'deki format string sabitleri magic string tekrarını önler
- **DRY** — Shared base class'lar, generic repository, ortak middleware
- **12-Factor App** — Config env'den okunur, stateless, log stdout'a yazılır

---

## Ön Gereksinimler

| Araç           | Versiyon | Kullanım                          |
| -------------- | -------- | --------------------------------- |
| Docker         | 24+      | Container çalıştırma              |
| Docker Compose | 2.20+    | Servis orchestration              |
| openssl        | herhangi | JWT RSA key üretimi (`make keys`) |
| make           | herhangi | Makefile kısayolları (opsiyonel)  |

> Local Python ortamı gerekmez — tüm komutlar container içinde çalışır.

---

## Hızlı Başlangıç

### `make` ile (önerilen)

```bash
# 1. Repoyu klonla
git clone <repo-url>
cd fastapi-backend

# 2. Ortam dosyasını oluştur
make env          # .env.example'ı .env olarak kopyalar
# .env dosyasını ihtiyacına göre düzenle

# 3. JWT RSA key çiftini üret
make keys         # keys/private.pem ve keys/public.pem oluşturur

# 4. Servisleri başlat
make dev          # api, worker, db, redis, minio container'larını başlatır

# 5. Migration uygula
make migrate      # Veritabanı tablolarını oluşturur

# 6. Admin kullanıcı oluştur
make seed         # .env'deki ADMIN_EMAIL ve ADMIN_PASSWORD ile admin oluşturur

# 7. API dokümantasyonunu aç
open http://localhost:8000/docs

# 5. Admin Panel
open http://localhost:8000/admin
```

### `make` olmadan (Docker komutları ile)

```bash
git clone <repo-url>
cd fastapi-backend

cp .env.example .env

mkdir -p keys
openssl genrsa -out keys/private.pem 4096
openssl rsa -in keys/private.pem -pubout -out keys/public.pem

docker compose up -d

docker compose exec api alembic upgrade head

docker compose exec api python -c "
import asyncio
from app.admin.seed import create_default_admin
asyncio.run(create_default_admin())
"
```

### Servis Adresleri

| Servis        | Adres                         |
| ------------- | ----------------------------- |
| API           | http://localhost:8000         |
| Swagger UI    | http://localhost:8000/docs    |
| ReDoc         | http://localhost:8000/redoc   |
| Admin Panel   | http://localhost:8000/admin   |
| MinIO Console | http://localhost:9001         |
| Prometheus    | http://localhost:8000/metrics |
| PostgreSQL    | localhost:5432                |
| Redis         | localhost:6379                |

---

## Makefile Komutları

### Geliştirme

| Komut          | Açıklama                          |
| -------------- | --------------------------------- |
| `make dev`     | Tüm servisleri arka planda başlat |
| `make stop`    | Tüm servisleri durdur             |
| `make restart` | API container'ını yeniden başlat  |
| `make logs`    | API loglarını canlı takip et      |
| `make shell`   | API container'ına bash shell aç   |
| `make ps`      | Çalışan container'ları listele    |

### Test

| Komut                        | Açıklama                                   |
| ---------------------------- | ------------------------------------------ |
| `make test`                  | Tüm testleri coverage raporu ile çalıştır  |
| `make test-fast`             | Testleri coverage olmadan hızlıca çalıştır |
| `make test-file f=tests/...` | Belirli bir test dosyasını çalıştır        |
| `make test-k k=test_login`   | İsim desenine göre test çalıştır           |

### Kod Kalitesi

| Komut            | Açıklama                                  |
| ---------------- | ----------------------------------------- |
| `make lint`      | ruff lint ve format kontrolü çalıştır     |
| `make format`    | ruff ile kodu otomatik formatla ve düzelt |
| `make typecheck` | mypy strict tip kontrolü                  |
| `make check`     | lint + typecheck birlikte                 |

### Veritabanı

| Komut                           | Açıklama                                      |
| ------------------------------- | --------------------------------------------- |
| `make migrate`                  | Bekleyen migration'ları uygula                |
| `make migration msg="açıklama"` | Yeni migration dosyası oluştur (autogenerate) |
| `make rollback`                 | Son migration'ı geri al                       |
| `make dbshell`                  | psql shell aç                                 |

### Kurulum

| Komut          | Açıklama                                   |
| -------------- | ------------------------------------------ |
| `make keys`    | JWT için 4096-bit RSA key çifti üret       |
| `make seed`    | Varsayılan admin kullanıcı oluştur         |
| `make env`     | .env.example'ı .env olarak kopyala (yoksa) |
| `make install` | Dev bağımlılıklarını local'a kur           |

---

## Ortam Değişkenleri

Tüm değerleri `.env.example`'dan `.env`'e kopyaladıktan sonra ihtiyacına göre düzenle.

### Uygulama

| Değişken        | Örnek Değer                 | Açıklama                                  | Zorunlu |
| --------------- | --------------------------- | ----------------------------------------- | ------- |
| `APP_NAME`      | `"My FastAPI App"`          | Uygulama adı                              | Hayır   |
| `APP_ENV`       | `development`               | `development`, `staging`, `production`    | Evet    |
| `APP_DEBUG`     | `true`                      | Debug modu (production'da `false` olmalı) | Hayır   |
| `APP_VERSION`   | `1.0.0`                     | Versiyon string'i                         | Hayır   |
| `APP_URL`       | `http://localhost:8000`     | Base URL                                  | Evet    |
| `SECRET_KEY`    | `change-this-...`           | Session/CSRF için rastgele anahtar        | Evet    |
| `ALLOWED_HOSTS` | `["*"]`                     | İzin verilen host'lar (JSON array)        | Evet    |
| `CORS_ORIGINS`  | `["http://localhost:3000"]` | CORS izin verilen origin'ler (JSON array) | Evet    |

### Veritabanı

| Değişken                | Örnek Değer      | Açıklama               | Zorunlu |
| ----------------------- | ---------------- | ---------------------- | ------- |
| `POSTGRES_HOST`         | `db`             | PostgreSQL host        | Evet    |
| `POSTGRES_PORT`         | `5432`           | PostgreSQL port        | Hayır   |
| `POSTGRES_DB`           | `appdb`          | Veritabanı adı         | Evet    |
| `POSTGRES_USER`         | `appuser`        | Veritabanı kullanıcısı | Evet    |
| `POSTGRES_PASSWORD`     | `strongpassword` | Veritabanı şifresi     | Evet    |
| `DATABASE_POOL_SIZE`    | `10`             | Bağlantı havuzu boyutu | Hayır   |
| `DATABASE_MAX_OVERFLOW` | `20`             | Max ek bağlantı sayısı | Hayır   |

### Redis

| Değişken         | Örnek Değer | Açıklama          | Zorunlu |
| ---------------- | ----------- | ----------------- | ------- |
| `REDIS_HOST`     | `redis`     | Redis host        | Evet    |
| `REDIS_PORT`     | `6379`      | Redis port        | Hayır   |
| `REDIS_PASSWORD` | (boş)       | Redis şifresi     | Hayır   |
| `REDIS_DB`       | `0`         | Redis DB numarası | Hayır   |

### JWT / Auth

| Değişken                      | Örnek Değer          | Açıklama                        | Zorunlu |
| ----------------------------- | -------------------- | ------------------------------- | ------- |
| `JWT_PRIVATE_KEY_PATH`        | `./keys/private.pem` | RSA private key dosya yolu      | Evet    |
| `JWT_PUBLIC_KEY_PATH`         | `./keys/public.pem`  | RSA public key dosya yolu       | Evet    |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30`                 | Access token geçerlilik süresi  | Hayır   |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | `30`                 | Refresh token geçerlilik süresi | Hayır   |

### OAuth2 Sağlayıcıları

| Değişken               | Örnek Değer                                         | Açıklama               |
| ---------------------- | --------------------------------------------------- | ---------------------- |
| `GOOGLE_CLIENT_ID`     | (Google API Console'dan al)                         | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | (Google API Console'dan al)                         | Google OAuth Secret    |
| `GOOGLE_REDIRECT_URI`  | `http://localhost:8000/api/v1/auth/google/callback` | Google callback URL    |
| `GITHUB_CLIENT_ID`     | (GitHub App'ten al)                                 | GitHub OAuth Client ID |
| `GITHUB_CLIENT_SECRET` | (GitHub App'ten al)                                 | GitHub OAuth Secret    |
| `GITHUB_REDIRECT_URI`  | `http://localhost:8000/api/v1/auth/github/callback` | GitHub callback URL    |

### Depolama (S3 / MinIO)

| Değişken               | Örnek Değer                                    | Açıklama                               | Zorunlu |
| ---------------------- | ---------------------------------------------- | -------------------------------------- | ------- |
| `STORAGE_BACKEND`      | `minio`                                        | `minio`, `s3` veya `local`             | Evet    |
| `S3_ENDPOINT_URL`      | `http://minio:9000`                            | S3 endpoint (AWS S3 için boş bırak)    | Hayır   |
| `S3_ACCESS_KEY`        | `minioadmin`                                   | S3 / MinIO access key                  | Evet    |
| `S3_SECRET_KEY`        | `minioadmin`                                   | S3 / MinIO secret key                  | Evet    |
| `S3_BUCKET_NAME`       | `app-uploads`                                  | Bucket adı                             | Evet    |
| `S3_REGION`            | `us-east-1`                                    | AWS bölgesi                            | Hayır   |
| `MAX_UPLOAD_SIZE_MB`   | `10`                                           | Maksimum dosya boyutu (MB)             | Hayır   |
| `ALLOWED_UPLOAD_TYPES` | `["image/jpeg","image/png","application/pdf"]` | İzin verilen MIME türleri (JSON array) | Hayır   |

### Admin Seed

| Değişken         | Örnek Değer         | Açıklama                                    |
| ---------------- | ------------------- | ------------------------------------------- |
| `ADMIN_EMAIL`    | `admin@example.com` | `make seed` ile oluşturulan admin e-postası |
| `ADMIN_PASSWORD` | `changeme`          | Admin şifresi (production'da güçlü ol)      |

### Rate Limiting

| Değişken                | Varsayılan   | Uygulanan Endpoint'ler             |
| ----------------------- | ------------ | ---------------------------------- |
| `RATE_LIMIT_DEFAULT`    | `100/minute` | Tüm endpoint'ler                   |
| `RATE_LIMIT_AUTH`       | `5/minute`   | Login, şifre sıfırlama             |
| `RATE_LIMIT_AUTH_EMAIL` | `3/hour`     | E-posta doğrulama, şifremi unuttum |
| `RATE_LIMIT_REGISTER`   | `3/hour`     | Kayıt                              |
| `RATE_LIMIT_UPLOAD`     | `20/hour`    | Dosya yükleme                      |

### E-posta (SMTP)

| Değişken            | Örnek Değer             | Açıklama                                |
| ------------------- | ----------------------- | --------------------------------------- |
| `SMTP_HOST`         | `smtp.mailprovider.com` | SMTP server host (boş = e-posta kapalı) |
| `SMTP_PORT`         | `587`                   | SMTP port                               |
| `SMTP_USER`         | `user@domain.com`       | SMTP kullanıcı adı                      |
| `SMTP_PASSWORD`     | (SMTP şifresi)          | SMTP şifresi                            |
| `EMAILS_FROM_EMAIL` | `noreply@example.com`   | Gönderen e-posta adresi                 |

### Sentry (opsiyonel)

| Değişken                    | Örnek Değer | Açıklama                            |
| --------------------------- | ----------- | ----------------------------------- |
| `SENTRY_DSN`                | (boş)       | Sentry proje DSN (boş = devre dışı) |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1`       | Trace örnekleme oranı (0.0–1.0)     |

### Loglama

| Değişken     | Varsayılan | Seçenekler                          |
| ------------ | ---------- | ----------------------------------- |
| `LOG_LEVEL`  | `INFO`     | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `json`     | `json` (production), `text` (dev)   |

---

## API Endpointleri

Tüm API endpoint'leri `/api/v1` prefix'i ile başlar. Tam detay, istek/yanıt şemaları ve deneme için: **http://localhost:8000/docs**

### Auth (`/auth`)

| Method | Path                        | Açıklama                                 | Auth  |
| ------ | --------------------------- | ---------------------------------------- | ----- |
| POST   | `/auth/register`            | Yeni kullanıcı kaydı                     | Hayır |
| POST   | `/auth/login`               | E-posta/şifre ile giriş (TOTP opsiyonel) | Hayır |
| POST   | `/auth/refresh`             | Access token yenile (rotation ile)       | Hayır |
| POST   | `/auth/logout`              | Çıkış (token blacklist'e eklenir)        | Evet  |
| GET    | `/auth/google`              | Google OAuth akışını başlat              | Hayır |
| GET    | `/auth/google/callback`     | Google OAuth callback                    | Hayır |
| GET    | `/auth/github`              | GitHub OAuth akışını başlat              | Hayır |
| GET    | `/auth/github/callback`     | GitHub OAuth callback                    | Hayır |
| POST   | `/auth/verify-email`        | E-posta adresini doğrula                 | Hayır |
| POST   | `/auth/resend-verification` | Doğrulama e-postasını tekrar gönder      | Hayır |
| POST   | `/auth/forgot-password`     | Şifre sıfırlama e-postası gönder         | Hayır |
| POST   | `/auth/reset-password`      | Token ile şifre sıfırla                  | Hayır |
| GET    | `/auth/me`                  | Mevcut kullanıcı bilgileri               | Evet  |

### TOTP / 2FA (`/auth/totp`)

| Method | Path                 | Açıklama                                             | Auth |
| ------ | -------------------- | ---------------------------------------------------- | ---- |
| POST   | `/auth/totp/setup`   | 2FA kurulumu başlat (QR kodu + secret döner)         | Evet |
| POST   | `/auth/totp/verify`  | Kodu doğrula ve 2FA'yı aktif et (yedek kodlar döner) | Evet |
| POST   | `/auth/totp/disable` | 2FA'yı devre dışı bırak                              | Evet |

### Kullanıcılar (`/users`)

| Method | Path               | Açıklama                  | Auth  |
| ------ | ------------------ | ------------------------- | ----- |
| GET    | `/users/me`        | Mevcut kullanıcı profili  | Evet  |
| PATCH  | `/users/me`        | Profili güncelle          | Evet  |
| GET    | `/users`           | Tüm kullanıcıları listele | Admin |
| GET    | `/users/{user_id}` | Belirli kullanıcıyı getir | Admin |
| DELETE | `/users/{user_id}` | Kullanıcıyı deaktif et    | Admin |

### API Keys (`/api-keys`)

| Method | Path                 | Açıklama             | Auth |
| ------ | -------------------- | -------------------- | ---- |
| POST   | `/api-keys`          | Yeni API key oluştur | Evet |
| GET    | `/api-keys`          | API key'leri listele | Evet |
| DELETE | `/api-keys/{key_id}` | API key'i iptal et   | Evet |

### Bildirimler (`/notifications`)

| Method | Path                               | Açıklama                         | Auth |
| ------ | ---------------------------------- | -------------------------------- | ---- |
| GET    | `/notifications`                   | Bildirimleri listele (sayfalı)   | Evet |
| GET    | `/notifications/unread-count`      | Okunmamış bildirim sayısı        | Evet |
| PATCH  | `/notifications/read-all`          | Tüm bildirimleri okundu işaretle | Evet |
| PATCH  | `/notifications/{notification_id}` | Tek bildirimi okundu işaretle    | Evet |
| DELETE | `/notifications/{notification_id}` | Bildirimi sil                    | Evet |

### Dosya Yükleme (`/uploads`)

| Method | Path       | Açıklama                                    | Auth |
| ------ | ---------- | ------------------------------------------- | ---- |
| POST   | `/uploads` | Dosya yükle (max 10MB, izinli MIME türleri) | Evet |
| DELETE | `/uploads` | Dosya sil (sahip veya admin)                | Evet |

### WebSocket

| Tip       | Path                   | Açıklama                            |
| --------- | ---------------------- | ----------------------------------- |
| WebSocket | `/api/v1/ws/{room_id}` | Oda tabanlı gerçek zamanlı bağlantı |

### Sistem

| Method | Path            | Açıklama                                  |
| ------ | --------------- | ----------------------------------------- |
| GET    | `/health`       | Tam sağlık durumu (DB, Redis, Storage)    |
| GET    | `/health/live`  | Canlılık probe'u (Kubernetes)             |
| GET    | `/health/ready` | Hazırlık probe'u (bağımlılık kontrolleri) |
| GET    | `/metrics`      | Prometheus metrikleri                     |
| GET    | `/docs`         | Swagger UI                                |
| GET    | `/redoc`        | ReDoc dokümantasyonu                      |

> API key kimlik doğrulaması desteklenir: `Authorization: Bearer <token>` yerine `X-API-Key: sk_live_<key>` header'ı kullanılabilir.

---

## Admin Panel

**Adres:** http://localhost:8000/admin

Yalnızca `ADMIN` rolüne sahip kullanıcılar giriş yapabilir. Giriş bilgileri mevcut hesapla (e-posta + şifre) aynıdır — ayrı bir hesap gerekmez.

**Varsayılan Giriş Bilgileri** (`.env` dosyasındaki değerler):

- E-posta: `ADMIN_EMAIL` (varsayılan: `admin@example.com`)
- Şifre: `ADMIN_PASSWORD` (varsayılan: `changeme`)

> `make seed` komutunu çalıştırmadan admin kullanıcı oluşturulmaz.

**Mevcut View'lar:**

| View            | İzinler     |
| --------------- | ----------- |
| Kullanıcılar    | Tam CRUD    |
| OAuth Hesapları | Salt okunur |

**Yeni view eklemek:** `app/admin/views.py`'e `ModelView` subclass'ı ekle — otomatik kaydedilir.

---

## API Dokümantasyonu

| Arayüz       | URL                                  | Açıklama                           |
| ------------ | ------------------------------------ | ---------------------------------- |
| Swagger UI   | `http://localhost:8000/docs`         | Etkileşimli API explorer           |
| ReDoc        | `http://localhost:8000/redoc`        | Okunabilir referans dokümantasyonu |
| OpenAPI JSON | `http://localhost:8000/openapi.json` | Ham şema (CI/SDK üretimi için)     |

## Güvenlik Özellikleri

- **RS256 JWT** — Private/public key çifti ile imzalanmış token'lar. Key'ler uygulama başlangıcında bir kez okunur (istek başına disk I/O yok)
- **Token Blacklisting** — Çıkış yapıldığında token'lar Redis'te kara listeye alınır
- **Refresh Token Rotation** — Her yenileme isteğinde eski token geçersizleşir, yeni çift verilir
- **TOTP / 2FA** — TOTP doğrulaması + yedek kodlar. Secret Fernet şifreleme ile DB'de saklanır
- **API Key Auth** — `sk_live_` prefix'li key'ler bcrypt ile hash'lenerek saklanır; `X-API-Key` header'ı ile kimlik doğrulama
- **OAuth2** — Google ve GitHub; `OAuthAccount` tablosuna kaydedilir, sağlayıcı izolasyonu sağlanır
- **OAuth CSRF Koruması** — State parametresi: her OAuth isteğinde kriptografik rastgele bir `state` üretilir, Redis'te 10 dakika TTL ile saklanır; callback'te atomik `GETDEL` ile tek seferde doğrulanıp tüketilir — race condition olmadan replay saldırılarına karşı koruma. OAuth URL parametreleri `urllib.parse.urlencode` ile encode edilir (`redirect_uri` gibi değerlerdeki `:`, `/` karakterlerinin bozmaması için)
- **Rate Limiting** — Redis-backed, endpoint bazlı (login, kayıt, yükleme için farklı limitler)
- **WebSocket Token Güvenliği** — Token URL query param'ında değil, bağlandıktan sonra ilk mesajla iletilir (Nginx log sızıntısı riski yok)
- **Production Validator** — `APP_ENV=production`'da `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `APP_DEBUG` güvensiz değerler için uygulama başlamaz; `ADMIN_PASSWORD` zayıf veya boş değerler (`""`, `changeme`, `admin`, `password`, `123456`) için de reddedilir
- **CORS** — Konfigüre edilmiş origin listesi ile kısıtlı
- **SQL Injection Koruması** — ORM + parameterized query
- **Request ID Tracking** — Her isteğe benzersiz ID atanır, loglar ve response header'larında taşınır
- **Audit Log** — Tüm önemli işlemler (giriş, çıkış, şifre sıfırlama, dosya yükleme vb.) DB'ye kaydedilir

---

## WebSocket Entegrasyonu

### Bağlantı Protokolü

```
1. İstemci bağlanır:  ws://localhost:8000/api/v1/ws/{room_id}
2. İlk mesaj (auth): {"type": "auth", "token": "<access_token>"}
3. Geçerli token    → bağlantı kabul edilir, odaya katılınır
4. Geçersiz/eksik  → 4001 kodu ile kapatılır
5. 10s timeout     → 4008 kodu ile kapatılır
```

### Python Örneği

```python
import json
import websocket  # pip install websocket-client

ws = websocket.WebSocket()
ws.connect("ws://localhost:8000/api/v1/ws/room-123")

# 1. Kimlik doğrula
ws.send(json.dumps({"type": "auth", "token": "<access_token>"}))

# 2. Mesaj gönder (odadaki diğer kullanıcılara iletilir, echo yok)
ws.send(json.dumps({"type": "message", "content": "Merhaba!"}))

# 3. Bağlantı sağlık kontrolü
ws.send(json.dumps({"type": "ping"}))
response = json.loads(ws.recv())  # {"type": "pong"}

ws.close()
```

### JavaScript Örneği

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/ws/room-123");

ws.onopen = () => {
  // 1. Kimlik doğrula
  ws.send(JSON.stringify({ type: "auth", token: "<access_token>" }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
  // { type: "user_joined", user_id: "..." }
  // { type: "message", from: "...", content: "Merhaba!", room_id: "room-123" }
};

// Mesaj gönder
ws.send(JSON.stringify({ type: "message", content: "Selam!" }));
```

### Desteklenen Mesaj Tipleri

| `type`    | Yön              | Açıklama                                         |
| --------- | ---------------- | ------------------------------------------------ |
| `auth`    | İstemci → Sunucu | İlk bağlantı doğrulama (zorunlu)                 |
| `ping`    | İstemci → Sunucu | Bağlantı sağlık kontrolü                         |
| `pong`    | Sunucu → İstemci | Ping'e yanıt                                     |
| `message` | İstemci → Sunucu | Odadaki diğer kullanıcılara broadcast (echo yok) |

### Sunucu Olayları

| `type`        | Ne Zaman                                  |
| ------------- | ----------------------------------------- |
| `user_joined` | Odaya yeni kullanıcı bağlandığında        |
| `user_left`   | Kullanıcı bağlantıyı kestiğinde           |
| `message`     | Odadaki bir kullanıcı mesaj gönderdiğinde |

---

## Bildirim Sistemi

Bildirimler hem veritabanında saklanır hem de bağlı WebSocket istemcilerine anlık iletilir.

### Bildirim Tipleri

| Tip              | Kullanım Amacı              |
| ---------------- | --------------------------- |
| `INFO`           | Genel bilgi mesajları       |
| `SUCCESS`        | Başarılı işlem bildirimleri |
| `WARNING`        | Uyarı bildirimleri          |
| `ERROR`          | Hata bildirimleri           |
| `SYSTEM`         | Sistem geneli duyurular     |
| `MENTION`        | Kullanıcı bahsedilmesi      |
| `FILE_PROCESSED` | Dosya işleme tamamlandı     |

### Bildirim Akışı

```
Servis → NotificationService.create() çağrılır
         ↓
         Bildirim DB'ye yazılır
         ↓
         Kullanıcı WebSocket'e bağlıysa anlık iletilir
         ↓
GET /notifications  → Sayfalı liste (okunmamış önce)
PATCH /notifications/{id}  → Okundu işaretle
PATCH /notifications/read-all  → Tümünü okundu işaretle
DELETE /notifications/{id}  → Sil
```

### WebSocket ile Gerçek Zamanlı Bildirim

```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "notification") {
    // data.notification içinde: id, type, title, body, data
    console.log("Yeni bildirim:", data.notification.title);
  }
};
```

---

## Yeni Özellik Ekleme Rehberi

Projenin katmanlı mimarisine uygun 8 adımlı akış. Örnek olarak "Blog Yazısı" özelliği ekleniyor:

### 1. Model — `app/db/models/post.py`

```python
from app.db.models.base import BaseModel
from sqlalchemy.orm import Mapped, mapped_column

class Post(BaseModel):
    __tablename__ = "posts"

    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
```

`app/db/models/__init__.py`'e import ekle.

### 2. Migration

```bash
make migration msg="add posts table"
make migrate
```

### 3. Repository — `app/db/repositories/post.py`

```python
from app.db.repositories.base import BaseRepository
from app.db.models.post import Post

class PostRepository(BaseRepository[Post]):
    pass  # Ek sorgular buraya
```

### 4. Service — `app/services/post.py`

```python
from app.services.base import AuditableMixin

class PostService(AuditableMixin):
    def __init__(self, repo: PostRepository, audit: AuditService | None = None):
        super().__init__(audit)
        self._repo = repo

    async def create(self, data: PostCreateRequest, user_id: UUID) -> Post:
        # İş mantığı burada
        ...
```

### 5. Schema — `app/schemas/post.py`

```python
from pydantic import BaseModel

class PostCreateRequest(BaseModel):
    title: str
    content: str

class PostResponse(BaseModel):
    id: UUID
    title: str
    content: str
    created_at: datetime
```

### 6. Endpoint — `app/api/v1/endpoints/posts.py`

```python
router = APIRouter(prefix="/posts", tags=["posts"])

@router.post("", response_model=PostResponse)
async def create_post(
    data: PostCreateRequest,
    current_user: CurrentUserDep,
    session: AsyncSession = Depends(get_session),
) -> Post:
    service = PostService(PostRepository(session))
    return await service.create(data, current_user.id)
```

### 7. Router — `app/api/v1/router.py`

```python
from app.api.v1.endpoints.posts import router as posts_router
api_router.include_router(posts_router)
```

### 8. Testler — `tests/integration/test_posts.py`

```python
async def test_create_post(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/posts",
        json={"title": "Test", "content": "İçerik"},
        headers=auth_headers,
    )
    assert response.status_code == 200
```

---

## Testler

### Çalıştırma

```bash
make test                              # Tüm testler + coverage raporu (≥%80 zorunlu)
make test-fast                         # Hızlı çalıştırma, coverage yok
make test-file f=tests/integration/test_auth.py  # Tek dosya
make test-k k=test_login               # İsim desenine göre
```

### Test Fixture'ları

| Fixture        | Açıklama                                                 |
| -------------- | -------------------------------------------------------- |
| `client`       | Async httpx.AsyncClient (DB override dahil)              |
| `db_session`   | Test başına taze AsyncSession (transaction rollback ile) |
| `fake_redis`   | fakeredis (gerçek Redis gerekmez)                        |
| `mock_enqueue` | ARQ task'larını mock'lar (background job çalışmaz)       |

### Test Matrisi

| Dosya                                 | Kategori    | Kapsadığı Senaryolar                                                                                      |
| ------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------- |
| `tests/unit/test_security.py`         | Unit        | JWT oluşturma/decode, süresi dolmuş/değiştirilmiş token, bcrypt hash/verify                               |
| `tests/unit/test_helpers.py`          | Unit        | Yardımcı fonksiyonlar                                                                                     |
| `tests/unit/test_middleware.py`       | Unit        | RequestIDMiddleware (UUID üretim, header koruma), TimingMiddleware, SecurityHeadersMiddleware (CSP, HSTS) |
| `tests/unit/test_repository_base.py`  | Unit        | `BaseRepository.get_page()` sayfalama: boş tablo, ilk/son sayfa, limit > toplam                           |
| `tests/unit/test_health.py`           | Unit        | `check_redis`, `check_storage` — başarılı ve hatalı senaryolar; degraded/503 endpoint                     |
| `tests/integration/test_auth.py`      | Integration | Kayıt, giriş, çıkış, token refresh, e-posta doğrulama, şifre sıfırlama                                    |
| `tests/integration/test_oauth.py`     | Integration | Google ve GitHub OAuth akışları, state CSRF koruması, geçersiz/eksik state                                |
| `tests/integration/test_users.py`     | Integration | Profil güncelleme, şifre değiştirme, yetki kontrolleri                                                    |
| `tests/integration/test_uploads.py`   | Integration | Dosya yükleme, silme, sahiplik kontrolü                                                                   |
| `tests/integration/test_websocket.py` | Integration | Auth hata senaryoları, ping/pong, broadcast, echo kontrolü                                                |
| `tests/integration/test_audit_log.py` | Integration | REGISTER, LOGIN_SUCCESS/FAILED, LOGOUT, TOKEN_REFRESHED aksiyonları audit edilmeli                        |
| `tests/integration/test_admin.py`     | Integration | Admin panel erişim kontrolü: yetkisiz redirect, login sayfası, mocked auth                                |

**Kurallar:**

- `asyncio_mode = "auto"` — tüm testler async
- Her test transaction rollback ile izole çalışır
- Coverage eşiği: `--cov-fail-under=80`
- `AuditService` test izolasyonu: bağımsız `AsyncSessionFactory` kullandığından `_audit_log` mock'lanır
- `fake_redis` fixture'ı autouse — tüm testlerde gerçek Redis gerekmez

---

## Kod Kalitesi

### Komutlar

```bash
# Lint + format kontrolü
make lint

# Otomatik formatla ve hataları düzelt
make format

# Tip kontrolü (strict mode)
make typecheck

# Her ikisi birlikte
make check

# Pre-commit hook'larını kur (bir kez)
pip install pre-commit
pre-commit install

# Tüm dosyalarda çalıştır
pre-commit run --all-files
```

### Pre-commit Hook'ları

`.pre-commit-config.yaml` üç hook içerir:

| Hook          | Ne Yapar                                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------ |
| `ruff`        | Lint kontrolü — `ruff check --fix`                                                                           |
| `ruff-format` | Format kontrolü — `ruff format`                                                                              |
| `mypy`        | Tip kontrolü — `mypy --strict --ignore-missing-imports` (strict mode, `alembic/versions/` ve `tests/` hariç) |

```bash
# Hook'ları kur (bir kez)
pip install pre-commit
pre-commit install

# Tüm dosyalarda çalıştır
pre-commit run --all-files
```

### `TYPE_CHECKING` Kuralı

Bu projede `from __future__ import annotations` aktif. Çoğu yerde `if TYPE_CHECKING:` ile import döngüleri kırılabilir. Ancak **üç istisna** vardır ve bu dosyalar için ilgili ruff kuralları `pyproject.toml`'da devre dışı bırakılmıştır:

| Bağlam                                 | Neden Runtime Import Gerekli                                 |
| -------------------------------------- | ------------------------------------------------------------ |
| `Pydantic BaseModel` field'ları        | Pydantic `get_type_hints()` ile runtime'da schema oluşturur  |
| `SQLAlchemy Mapped[...]` field'ları    | SQLAlchemy mapper konfigürasyonunda annotation'ları çözümler |
| FastAPI endpoint / dependency imzaları | FastAPI `get_type_hints()` ile bağımlılık grafiğini çözer    |

---

## CI/CD Pipeline

GitHub Actions her `push` ve `pull_request` (master, dev branch'leri) üzerinde otomatik çalışır.

### `.github/workflows/lint.yml` — Lint & Type Check

İki paralel job:

| Job         | Ne Yapar                                        |
| ----------- | ----------------------------------------------- |
| `lint`      | `ruff check` + `ruff format --check` çalıştırır |
| `typecheck` | `mypy app/` strict mode ile çalıştırır          |

```
push/PR → lint job (ruff)    ─┐
       → typecheck job (mypy) ─┘ (paralel, biri başarısız olursa PR bloklanır)
```

### `.github/workflows/test.yml` — Tests

```
push/PR → PostgreSQL service container ayağa kalkar
        → pip cache restore
        → bağımlılıklar kurulur
        → JWT key'leri üretilir
        → alembic upgrade head
        → pytest (coverage dahil)
        → coverage.xml artifact olarak yüklenir (7 gün saklanır)
```

**Not:** Testlerde fakeredis kullanılır — CI'da ayrı bir Redis servisine gerek yok.

### PR Kuralı

Tüm 3 job (`lint`, `typecheck`, `test`) başarıyla geçmedikçe PR merge edilemez.

---

## Production Deployment

### 1. JWT Key Çifti Üret

```bash
mkdir -p keys
openssl genrsa -out keys/private.pem 4096
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

> `keys/` klasörü `.gitignore`'da — bu dosyalar **asla** commit edilmez.

### 2. Gizli Anahtar Üret

```bash
openssl rand -hex 32   # → SECRET_KEY değeri olarak kullan
```

### 3. .env Production Değerleri

| Değişken                                      | Dev                     | Production                              |
| --------------------------------------------- | ----------------------- | --------------------------------------- |
| `APP_ENV`                                     | `development`           | `production`                            |
| `APP_DEBUG`                                   | `true`                  | `false`                                 |
| `APP_URL`                                     | `http://localhost:8000` | `https://api.yourdomain.com`            |
| `SECRET_KEY`                                  | rastgele                | `openssl rand -hex 32` çıktısı          |
| `POSTGRES_PASSWORD`                           | zayıf                   | güçlü, rastgele                         |
| `REDIS_PASSWORD`                              | boş                     | güçlü şifre                             |
| `CORS_ORIGINS`                                | `["*"]`                 | `["https://yourdomain.com"]`            |
| `ALLOWED_HOSTS`                               | `["*"]`                 | `["api.yourdomain.com"]`                |
| `SMTP_HOST`                                   | boş                     | `smtp.provider.com` (SES, SendGrid vb.) |
| `STORAGE_BACKEND`                             | `minio`                 | `s3`                                    |
| `S3_ENDPOINT_URL`                             | `http://minio:9000`     | boş bırak (AWS otomatik)                |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY`             | `minioadmin`            | AWS IAM credentials                     |
| `ADMIN_PASSWORD`                              | `changeme`              | güçlü şifre (`changeme` → hata verir)   |
| `GOOGLE_REDIRECT_URI` / `GITHUB_REDIRECT_URI` | `localhost`             | production domain                       |

### 4. Başlatma

```bash
# Image'ı build et
docker compose -f docker-compose.prod.yml build

# Tüm servisleri başlat
docker compose -f docker-compose.prod.yml up -d

# Log takibi
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f worker
```

### 5. Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass         http://localhost:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # WebSocket desteği
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
    }
}
```

### 6. Güvenlik Kontrol Listesi

Canlıya almadan önce:

- [ ] `SECRET_KEY` rastgele üretildi (`openssl rand -hex 32`)
- [ ] `ADMIN_PASSWORD` güçlü bir değerle değiştirildi (`changeme` production'da hata verir)
- [ ] `POSTGRES_PASSWORD` ve `REDIS_PASSWORD` rastgele üretildi
- [ ] `APP_ENV=production` ve `APP_DEBUG=false` ayarlandı
- [ ] `CORS_ORIGINS` yalnızca gerçek domain'i içeriyor (`["*"]` production'da hata verir)
- [ ] `ALLOWED_HOSTS` yalnızca gerçek domain'i içeriyor (`["*"]` production'da hata verir)
- [ ] JWT key dosyaları (`keys/private.pem`, `keys/public.pem`) yeniden üretildi
- [ ] `keys/` ve `.env` dosyalarının `.gitignore`'da olduğu doğrulandı
- [ ] `SMTP_HOST` gerçek bir SMTP sağlayıcısıyla dolduruldu
- [ ] `STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL` boş, S3 credentials doğru
- [ ] OAuth redirect URI'leri production domain'ine güncellendi
- [ ] Nginx SSL sertifikası aktif ve yenilenebilir (Let's Encrypt vb.)
- [ ] Rate limit eşikleri gözden geçirildi ve gerekirse sıkılaştırıldı

> `APP_ENV=production` ile başlatıldığında uygulama, kritik güvensiz değerleri otomatik olarak kontrol eder ve başlamayı reddeder.

---

## Troubleshooting

| Hata / Belirti                                             | Neden                                         | Çözüm                                                       |
| ---------------------------------------------------------- | --------------------------------------------- | ----------------------------------------------------------- |
| `FileNotFoundError: keys/private.pem`                      | RSA key üretilmedi                            | `make keys` çalıştır                                        |
| `ValueError: ADMIN_PASSWORD is too simple` (production)    | `changeme` production'da geçersiz             | Güçlü bir şifre ile `ADMIN_PASSWORD` değiştir               |
| `ValueError: CORS_ORIGINS=["*"] not allowed` (production)  | Production validator reddetti                 | Gerçek domain listesi ile güncelle                          |
| `ValueError: ALLOWED_HOSTS=["*"] not allowed` (production) | Production validator reddetti                 | Gerçek host listesi ile güncelle                            |
| Container başlamıyor, health check fail                    | DB / Redis henüz hazır değil                  | `docker compose logs db` ile incele, birkaç saniye bekle    |
| `alembic.util.exc.CommandError: Can't locate revision`     | Migration uygulanmamış veya sürüm uyuşmazlığı | `make migrate` çalıştır                                     |
| `relation "users" does not exist`                          | Migration hiç uygulanmamış                    | `make migrate` çalıştır                                     |
| MinIO bucket bulunamadı                                    | `init` container'ı bucket'ı oluşturmadı       | `docker compose up init` veya `make dev` ile yeniden başlat |
| `mypy` strict hatası                                       | Eksik veya yanlış tip annotation              | `make typecheck` ile hata listesini gör, annotation ekle    |
| `ruff` format hatası CI'da                                 | Kod formatlanmamış                            | `make format` ile yerel olarak formatla, commit'e ekle      |
| WebSocket bağlantısı anında kapanıyor (4001)               | Geçersiz veya süresi dolmuş token             | Yeni access token ile tekrar auth mesajı gönder             |
| WebSocket bağlantısı 10 saniyede kapanıyor (4008)          | Auth mesajı timeout içinde gelmedi            | Bağlandıktan sonra hemen `{"type": "auth", ...}` gönder     |
| Testler `fakeredis` hatası veriyor                         | Redis key formatı uyuşmazlığı                 | `make test-fast` ile coverage atla, fixture'a bak           |
| `docker compose exec api` → `no such service`              | Container adı yanlış                          | `make ps` ile container'ları kontrol et                     |

---

## Katkıda Bulunma

### Kurulum

```bash
git clone <repo-url>
cd fastapi-backend
make env && make keys && make dev && make migrate
```

### Geliştirme Akışı

```bash
# 1. Feature branch oluştur
git checkout -b feat/my-feature

# 2. Değişiklik yap

# 3. Testleri çalıştır
make test

# 4. Lint + tip kontrolü
make check

# 5. PR aç (hedef: dev branch)
```

### Branch İsimlendirme

| Prefix      | Kullanım                           |
| ----------- | ---------------------------------- |
| `feat/`     | Yeni özellik                       |
| `fix/`      | Hata düzeltme                      |
| `refactor/` | Yeniden yapılandırma               |
| `docs/`     | Yalnızca dokümantasyon değişikliği |
| `test/`     | Test ekleme/düzeltme               |
| `chore/`    | Bağımlılık güncelleme, config vb.  |

### Commit Mesajı Formatı

[Conventional Commits](https://www.conventionalcommits.org/) standardı:

```
feat: TOTP 2FA desteği ekle
fix: token expiry edge case düzelt
refactor: e-posta doğrulamasını helper'a taşı
test: API key kimlik doğrulama integration testleri ekle
docs: CHANGELOG güncelle
```

### PR Kontrol Listesi

- [ ] `make test` geçiyor (coverage ≥ %80)
- [ ] `make check` geçiyor (lint + mypy temiz)
- [ ] Yeni özellikler için integration test yazıldı
- [ ] Yeni servisler için `AuditableMixin` kullanıldı
- [ ] Servislerden doğrudan SQLAlchemy çağrısı yok (repository kullan)
- [ ] Endpoint'lerde iş mantığı yok (service'e delege et)
