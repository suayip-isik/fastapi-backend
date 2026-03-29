# 🚀 FastAPI Production Backend

> Modular · Scalable · API-First · Production-Ready

## Tech Stack

| Layer            | Technology                                |
| ---------------- | ----------------------------------------- |
| Framework        | FastAPI + Python 3.12                     |
| Database         | PostgreSQL 16 + SQLAlchemy 2.0 (async)    |
| Migrations       | Alembic                                   |
| Cache            | Redis 7                                   |
| Auth             | OAuth2 + JWT (RS256)                      |
| Background       | ARQ (Redis-based)                         |
| Storage          | S3-compatible (MinIO local / AWS S3 prod) |
| WebSocket        | FastAPI native                            |
| Rate Limit       | slowapi (Redis-backed)                    |
| Validation       | Pydantic v2                               |
| Admin Panel      | SQLAdmin (role-based, JWT auth)           |
| Containerization | Docker + Docker Compose                   |
| Testing          | pytest + pytest-asyncio                   |
| Linting          | ruff 0.6.9 (linter + formatter)           |
| Type Checking    | mypy 1.11.2 (strict mode)                 |
| Code Quality     | pre-commit hooks                          |
| CI               | GitHub Actions                            |
| Docs             | OpenAPI (auto)                            |

## Proje Yapısı

```
app/
├── api/
│   ├── v1/
│   │   └── endpoints/      # Route handler'ları (ince katman)
│   └── dependencies/       # FastAPI Depends() injection'ları
├── core/
│   ├── config.py           # Tüm ayarlar (Pydantic Settings)
│   ├── security.py         # JWT RS256, bcrypt, token utils
│   ├── exceptions.py       # Global exception handler'lar
│   ├── logging.py          # Structured logging (structlog)
│   └── middleware.py       # Custom middleware'ler
├── db/
│   ├── models/             # SQLAlchemy ORM modelleri
│   ├── repositories/
│   │   ├── base.py         # Generic BaseRepository[ModelType]
│   │   ├── user.py         # UserRepository
│   │   ├── oauth_account.py # OAuthAccountRepository
│   │   └── audit_log.py    # AuditLogRepository
│   └── session.py          # Async DB session factory
├── services/
│   ├── base.py             # AuditableMixin (paylaşılan audit_log)
│   ├── _keys.py            # Redis anahtar sabitleri (DRY)
│   ├── auth.py             # AuthService — email/password + token yönetimi
│   ├── oauth.py            # OAuthService — Google & GitHub callback
│   ├── account.py          # AccountService — email doğrulama + şifre sıfırlama
│   ├── user.py             # UserService — kullanıcı yönetimi
│   └── audit.py            # AuditService — denetim log'ları
├── schemas/                # Pydantic request/response şemaları
├── admin/                  # SQLAdmin panel (views, auth backend)
├── tasks/                  # ARQ background task'ları
├── websockets/             # WebSocket handler'ları (room-based)
├── storage/                # File upload abstraction (MinIO / S3)
└── utils/                  # Yardımcı fonksiyonlar
```

## Mimari Prensipler

- **Repository Pattern**: DB erişimi tamamen soyutlandı; servisler asla SQLAlchemy kullanmaz
- **Service Layer (SRP)**: Her servis tek sorumluluğu yönetir — `AuthService` / `OAuthService` / `AccountService` / `UserService`
- **Dependency Injection**: FastAPI `Depends()` ile loose coupling; servis constructor'larına inject edilir
- **AuditableMixin**: `base.py`'deki `AuditableMixin` ile audit log kodu tekrarlanmaz
- **Redis Key Sabitleri**: `_keys.py`'deki format string sabitleri magic string tekrarını önler
- **DRY**: Shared utilities, base classes, generic `BaseRepository[ModelType]`
- **12-Factor App**: Config env'den, stateless, log stdout'a

## Hızlı Başlangıç

```bash
# 1. Ortamı hazırla
cp .env.example .env
# .env dosyasını düzenle (özellikle ADMIN_EMAIL ve ADMIN_PASSWORD)

# 2. Pre-commit hook'larını kur (bir kez)
pip install pre-commit
pre-commit install

# 3. Çalıştır
docker compose up -d

# 4. Migrations
docker compose exec api alembic upgrade head

# 5. API Docs
open http://localhost:8000/docs

# 5. Admin Panel
open http://localhost:8000/admin
```

> **Not:** Uygulama ilk başladığında `.env` içindeki `ADMIN_EMAIL` ve `ADMIN_PASSWORD` değerleriyle otomatik olarak bir admin kullanıcısı oluşturulur. Bu kullanıcı zaten mevcut ise tekrar oluşturulmaz.

## Admin Panel

`/admin` adresinden erişilir. Yalnızca `UserRole.ADMIN` rolüne sahip kullanıcılar giriş yapabilir.

### Erişim Bilgileri

Uygulama ilk başlatıldığında `.env` dosyasındaki değerlerle otomatik admin kullanıcısı oluşturulur:

| Alan    | Değer                         |
| ------- | ----------------------------- |
| URL     | `http://localhost:8000/admin` |
| E-posta | `ADMIN_EMAIL` (`.env`)        |
| Şifre   | `ADMIN_PASSWORD` (`.env`)     |

> Varsayılan `.env.example` değerleri: `admin@example.com` / `changeme` — production ortamında mutlaka değiştirin.

### Özellikler

- Giriş: mevcut email/password + JWT doğrulaması (ayrı hesap gerektirmez)
- Session yönetimi: `SessionMiddleware` + `itsdangerous` ile imzalı cookie
- Mevcut view'lar: **Kullanıcılar** (tam CRUD), **OAuth Hesapları** (salt okunur, export yok)
- Yeni view eklemek için `app/admin/views.py`'e `ModelView` subclass'ı eklemek yeterli — otomatik register edilir

## API Dokümantasyonu

| Arayüz       | URL                                  | Açıklama                           |
| ------------ | ------------------------------------ | ---------------------------------- |
| Swagger UI   | `http://localhost:8000/docs`         | Etkileşimli API explorer           |
| ReDoc        | `http://localhost:8000/redoc`        | Okunabilir referans dokümantasyonu |
| OpenAPI JSON | `http://localhost:8000/openapi.json` | Ham şema (CI/SDK üretimi için)     |

## Güvenlik Özellikleri

- RS256 imzalı JWT token'lar (access=30dk, refresh=30gün)
- JWT anahtar çifti uygulama başlangıcında bir kez okunur — istek başına disk I/O yok
- OAuth2 social login (Google, GitHub) — `OAuthAccount` tablosuna kaydedilir, provider izolasyonu sağlanır
- WebSocket auth: token URL'de değil, bağlandıktan sonra ilk mesajla gönderilir (log sızıntısı riski yok)
- Production validator: `APP_ENV=production`'da `SECRET_KEY`, `ADMIN_PASSWORD`, `ALLOWED_HOSTS` ve `APP_DEBUG` güvensiz değerler için uygulama başlamaz
- Redis-backed rate limiting (IP + user bazlı)
- SQL injection koruması (ORM + parameterized queries)
- CORS politikası
- Request ID tracking
- Structured security audit logs
- Admin paneli sadece `ADMIN` rolüne açık, her istekte token + rol doğrulaması yapılır

## Kod Kalitesi

```bash
# Linting
docker compose exec api ruff check app/ tests/ scripts/

# Formatting kontrolü
docker compose exec api ruff format --check app/ tests/ scripts/

# Otomatik düzelt
docker compose exec api ruff check --fix app/ tests/ scripts/
docker compose exec api ruff format app/ tests/ scripts/

# Tip kontrolü (strict mode)
docker compose exec api mypy app/

# Pre-commit — tüm dosyalarda çalıştır
pre-commit run --all-files
```

CI (GitHub Actions) her `push` ve `pull_request`'te `ruff` + `mypy` kontrollerini paralel olarak çalıştırır. PR oluşturabilmek için her iki kontrolün de geçmesi gerekir.

### Önemli: `TYPE_CHECKING` Kullanım Kuralı

Bu projede `from __future__ import annotations` aktif. Bu Python'ın tüm annotation'ları lazy string yapmasını sağlar — çoğu yerde `if TYPE_CHECKING:` ile import döngüleri kırılabilir. Ancak **üç istisna** vardır:

| Bağlam                                 | Neden runtime import gerekli                                 |
| -------------------------------------- | ------------------------------------------------------------ |
| `Pydantic BaseModel` field'ları        | Pydantic `get_type_hints()` ile runtime'da schema oluşturur  |
| `SQLAlchemy Mapped[...]` field'ları    | SQLAlchemy mapper konfigürasyonunda annotation'ları çözümler |
| FastAPI endpoint / dependency imzaları | FastAPI `get_type_hints()` ile bağımlılık grafiğini çözer    |

Bu dosyalar için `TCH001/TCH002/TCH003` kuralları `pyproject.toml`'da per-file-ignore olarak tanımlanmıştır.

## Testler

```bash
pytest tests/                                      # Tüm testleri çalıştır
pytest tests/unit/                                 # Unit testler
pytest tests/integration/                          # Integration testler
pytest tests/ -k "test_login"                      # İsme göre filtrele
pytest tests/ --cov=app --cov-report=term-missing  # Coverage raporu (varsayılan)
```

### Kapsam

| Dosya                                 | Kategori    | Senaryolar                                                                                  |
| ------------------------------------- | ----------- | ------------------------------------------------------------------------------------------- |
| `tests/unit/test_security.py`         | Unit        | JWT oluşturma/decode, expired/tampered token, bcrypt hash/verify                            |
| `tests/unit/test_helpers.py`          | Unit        | Yardımcı fonksiyonlar                                                                       |
| `tests/integration/test_auth.py`      | Integration | Kayıt, login, logout, token refresh, email doğrulama, şifre sıfırlama, OAuth, edge case'ler |
| `tests/integration/test_users.py`     | Integration | Profil güncelleme, şifre değiştirme, yetki kontrolleri                                      |
| `tests/integration/test_uploads.py`   | Integration | Dosya yükleme, silme, yetki                                                                 |
| `tests/integration/test_websocket.py` | Integration | Auth hata senaryoları, ping/pong, broadcast, echo kontrolü                                  |

> Test izolasyonu: Her test transaction rollback ile çalışır. `asyncio_mode = "auto"` — tüm testler asenkron.

## WebSocket

Room tabanlı bağlantı yönetimi — `app/websockets/manager.py`.

### Bağlantı Protokolü

```
1. Client bağlanır:   ws://host/api/v1/ws/{room_id}
2. İlk mesaj (auth):  {"type": "auth", "token": "<access_token>"}
3. Geçerli token →    bağlantı kabul edilir, odaya join olunur
4. Geçersiz/eksik →   4001 kodu ile kapatılır
5. Timeout (10s) →    4008 kodu ile kapatılır
```

> Token URL query param'ında gönderilmez — Nginx/CDN access log'larına yazılmasının önüne geçer.

### Desteklenen Mesaj Tipleri

| `type`    | Açıklama                                            |
| --------- | --------------------------------------------------- |
| `auth`    | Bağlantı doğrulama (ilk mesaj zorunlu)              |
| `ping`    | Bağlantı sağlık kontrolü → `{"type": "pong"}` döner |
| `message` | Odadaki diğer kullanıcılara broadcast (echo yok)    |

### Sunucu Olayları

| `type`        | Ne zaman                           |
| ------------- | ---------------------------------- |
| `user_joined` | Odaya yeni kullanıcı bağlandığında |
| `user_left`   | Kullanıcı bağlantıyı kestiğinde    |

## Environment Variables

Tüm değişkenler `.env.example` dosyasında belgelenmiştir.

## Production Deployment

### 1. Ön Hazırlık

**JWT anahtar çifti üret** (mevcut `keys/` klasörünü yenile):

```bash
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

> `keys/` klasörü `.gitignore`'da — bu dosyalar asla commit edilmez.

**Gizli anahtar üret:**

```bash
openssl rand -hex 32   # → SECRET_KEY değeri
```

---

### 2. .env Production Değerleri

| Değişken                                      | Dev                              | Production                              |
| --------------------------------------------- | -------------------------------- | --------------------------------------- |
| `APP_ENV`                                     | `development`                    | `production`                            |
| `APP_DEBUG`                                   | `true`                           | `false`                                 |
| `APP_URL`                                     | `http://localhost:8000`          | `https://api.yourdomain.com`            |
| `SECRET_KEY`                                  | rastgele                         | `openssl rand -hex 32` çıktısı          |
| `POSTGRES_PASSWORD`                           | zayıf                            | güçlü, rastgele                         |
| `REDIS_PASSWORD`                              | boş                              | güçlü şifre                             |
| `CORS_ORIGINS`                                | `["*"]`                          | `["https://yourdomain.com"]`            |
| `SMTP_HOST`                                   | boş                              | `smtp.provider.com` (SES, SendGrid vb.) |
| `SMTP_USER` / `SMTP_PASSWORD`                 | boş                              | gerçek SMTP credentials                 |
| `STORAGE_BACKEND`                             | `minio`                          | `s3`                                    |
| `S3_ENDPOINT_URL`                             | `http://minio:9000`              | boş bırak (AWS otomatik)                |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY`             | `minioadmin`                     | AWS IAM credentials                     |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD`              | `admin@example.com` / `changeme` | güçlü değerler                          |
| `GOOGLE_REDIRECT_URI` / `GITHUB_REDIRECT_URI` | `localhost`                      | production domain                       |

---

### 3. docker-compose.prod.yml

Dev compose'dan farklar: `target: production` (non-root user, 4 uvicorn worker), volume mount yok, MinIO yok (AWS S3), Redis auth açık.

```yaml
services:
  init:
    build:
      context: .
      dockerfile: docker/Dockerfile
      target: production
    container_name: fastapi_init
    restart: "no"
    command: >
      bash -c "
        alembic upgrade head &&
        python scripts/create_buckets.py
      "
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app_network

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
      target: production
    container_name: fastapi_api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      init:
        condition: service_completed_successfully
    networks:
      - app_network

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile
      target: production
    container_name: fastapi_worker
    restart: unless-stopped
    command: arq app.tasks.worker.WorkerSettings
    env_file:
      - .env
    depends_on:
      redis:
        condition: service_healthy
      db:
        condition: service_healthy
      init:
        condition: service_completed_successfully
    networks:
      - app_network

  db:
    image: postgres:16-alpine
    container_name: fastapi_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - app_network

  redis:
    image: redis:7-alpine
    container_name: fastapi_redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD} --save 20 1 --loglevel warning
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - app_network

volumes:
  postgres_data:
  redis_data:

networks:
  app_network:
    driver: bridge
```

---

### 4. Başlatma

```bash
# Image'ı build et
docker compose -f docker-compose.prod.yml build

# Tüm servisleri başlat (init migration + bucket kurulumu çalıştırır)
docker compose -f docker-compose.prod.yml up -d

# Log'ları takip et
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f worker
```

---

### 5. Reverse Proxy (Nginx)

API doğrudan dışa açılmamalı. Minimal Nginx konfigürasyonu:

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

---

### 6. Güvenlik Kontrol Listesi

Canlıya almadan önce:

- [ ] `SECRET_KEY` rastgele üretildi (`openssl rand -hex 32`)
- [ ] `ADMIN_PASSWORD` güçlü bir değerle değiştirildi (`changeme` → hata verir)
- [ ] `POSTGRES_PASSWORD` ve `REDIS_PASSWORD` rastgele üretildi
- [ ] `APP_ENV=production` ve `APP_DEBUG=false` set edildi
- [ ] `CORS_ORIGINS` yalnızca gerçek domain'i içeriyor (`["*"]` → hata verir)
- [ ] `ALLOWED_HOSTS` yalnızca gerçek domain'i içeriyor (`["*"]` → hata verir)
- [ ] JWT key dosyaları (`keys/private.pem`, `keys/public.pem`) yeniden üretildi
- [ ] `keys/` ve `.env` dosyalarının `.gitignore`'da olduğu doğrulandı
- [ ] `SMTP_HOST` gerçek bir SMTP sağlayıcısıyla dolduruldu
- [ ] `STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL` boş, S3 credentials doğru
- [ ] OAuth redirect URI'leri production domain'ine güncellendi
- [ ] Reverse proxy SSL sertifikası aktif
- [ ] Rate limit eşikleri (`RATE_LIMIT_AUTH=3/minute` vb.) gözden geçirildi

> **Not:** `APP_ENV=production` ile başlatıldığında uygulama, kritik güvensiz değerleri otomatik olarak kontrol eder ve başlamayı reddeder.
