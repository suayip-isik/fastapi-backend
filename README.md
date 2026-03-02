# 🚀 FastAPI Production Backend

> Modular · Scalable · API-First · Production-Ready

## Tech Stack

| Katman           | Teknoloji                                 |
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
│   ├── security.py         # JWT, hashing, token utils
│   ├── exceptions.py       # Global exception handler'lar
│   ├── logging.py          # Structured logging (structlog)
│   └── middleware.py       # Custom middleware'ler
├── db/
│   ├── models/             # SQLAlchemy ORM modelleri
│   ├── repositories/       # Repository pattern (DB erişim katmanı)
│   └── session.py          # Async DB session factory
├── services/               # Business logic katmanı (SOLID)
├── schemas/                # Pydantic request/response şemaları
├── admin/                  # SQLAdmin panel (views, auth backend)
├── tasks/                  # ARQ background task'ları
├── websockets/             # WebSocket handler'ları
├── storage/                # File upload abstraction
└── utils/                  # Yardımcı fonksiyonlar
```

## Mimari Prensipler

- **Repository Pattern**: DB erişimi tamamen soyutlandı
- **Service Layer**: Business logic, route handler'lardan ayrı
- **Dependency Injection**: FastAPI `Depends()` ile loose coupling
- **Interface Segregation**: Abstract base class'lar ile kontrat tanımı
- **DRY**: Shared utilities, base classes, generic repository
- **12-Factor App**: Config env'den, stateless, log stdout'a

## Hızlı Başlangıç

```bash
# 1. Ortamı hazırla
cp .env.example .env
# .env dosyasını düzenle

# 2. Çalıştır
docker compose up -d

# 3. Migrations
docker compose exec api alembic upgrade head

# 4. API Docs
open http://localhost:8000/docs
```

## Admin Panel

`/admin` adresinden erişilir. Yalnızca `UserRole.ADMIN` rolüne sahip kullanıcılar giriş yapabilir.

- Giriş: mevcut email/password + JWT doğrulaması (ayrı hesap gerektirmez)
- Session yönetimi: `SessionMiddleware` + `itsdangerous` ile imzalı cookie
- Mevcut view'lar: **Kullanıcılar** (tam CRUD), **OAuth Hesapları** (salt okunur, export yok)
- Yeni view eklemek için `app/admin/views.py`'e `ModelView` subclass'ı eklemek yeterli — otomatik register edilir

## Güvenlik Özellikleri

- RS256 imzalı JWT token'lar (access + refresh)
- OAuth2 social login (Google, GitHub)
- Redis-backed rate limiting (IP + user bazlı)
- SQL injection koruması (ORM + parameterized queries)
- CORS politikası
- Request ID tracking
- Structured security audit logs
- Admin paneli sadece `ADMIN` rolüne açık, her istekte token + rol doğrulaması yapılır

## Environment Variables

Tüm değişkenler `.env.example` dosyasında belgelenmiştir.
