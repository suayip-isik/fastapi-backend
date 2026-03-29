# Öğrenme Yol Haritası — FastAPI Production Backend

> Bu döküman, projeyi sıfırdan anlayıp geliştirebilecek seviyeye gelmek için
> öğrenilmesi gereken konuları, sırasıyla ve bu projeden somut referanslarla açıklar.
> Her konu başlığında "bu projede nerede kullanılır" bölümü bulunur.

---

## Seviye 0 — Ön Koşullar

Aşağıdaki konulara hakim olmadan bu projeye girmek anlamsızdır.
Bunlar programlamaya giriş niteliğindedir.

### 0.1 Bilgisayar ve Terminal Temelleri

- Dosya sistemi: klasör, dosya, yol (path) kavramı
- Terminal / komut satırı: `cd`, `ls`, `mkdir`, `rm`, `cat`
- Ortam değişkenleri (environment variables) nedir, neden kullanılır
- `.env` dosyası ne işe yarar

### 0.2 Git ve Versiyon Kontrolü

- `git init`, `git add`, `git commit`, `git push`
- Branch, merge, pull request kavramları
- `.gitignore` — neden `keys/` ve `.env` commit edilmez (güvenlik)

**Bu projede:** `keys/private.pem` ve `.env` kasıtlı olarak git'e eklenmez.
Sebebini anlamak için bu konuyu bilmek gerekir.

---

## Seviye 1 — Python Temelleri

### 1.1 Python Syntax

- Değişkenler, veri tipleri (`str`, `int`, `bool`, `list`, `dict`)
- Koşullar (`if/elif/else`), döngüler (`for`, `while`)
- Fonksiyonlar: `def`, parametreler, `return`
- Modüller: `import`, `from x import y`

**Kaynak:** [docs.python.org/3/tutorial](https://docs.python.org/3/tutorial/)

### 1.2 Python'a Özgü Kavramlar

- List comprehension: `[x for x in items if x > 0]`
- Dictionary unpacking: `{**dict_a, **dict_b}`
- `*args` ve `**kwargs`
- `with` ifadesi (context manager)
- Decorator (`@`) — fonksiyon sarmalama

**Bu projede:**

- `app/core/config.py` — `@model_validator`, `@property` decorator'ları
- `app/main.py` — `@asynccontextmanager` ile lifespan yönetimi

### 1.3 Nesne Yönelimli Programlama (OOP)

- Sınıf (`class`), nesne (instance), `__init__`
- Miras (inheritance): `class Child(Parent)`
- `self`, sınıf değişkeni vs. örnek değişkeni
- Abstract sınıflar (`ABC`, `abstractmethod`)
- `@classmethod`, `@staticmethod`

**Bu projede:**

- `app/db/repositories/base.py` — `BaseRepository[ModelType]` generic miras
- `app/services/base.py` — `AuditableMixin`
- `app/admin/views.py` — SQLAdmin `ModelView` subclass'ları

### 1.4 Tip İpuçları (Type Hints)

- `str`, `int`, `list[str]`, `dict[str, int]`
- `Optional[str]` = `str | None`
- `Union[A, B]`
- `TypeVar`, generic tipler: `T = TypeVar("T")`
- `Annotated[T, ...]`

**Bu projede:** Projedeki tüm dosyalar mypy strict modunda yazılmıştır.
`app/db/repositories/base.py`'deki `BaseRepository[ModelType]` buna örnektir.

**Kaynak:** [mypy.readthedocs.io](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)

---

## Seviye 2 — Asenkron Programlama

Bu projenin tamamı asenkron yazılmıştır. Anlamamak ciddi hatalara yol açar.

### 2.1 Senkron vs. Asenkron

- Blocking I/O nedir (ağ, disk okuma)
- Event loop kavramı
- `async def` ve `await` anahtar kelimeleri
- `asyncio.gather()` ile paralel çalıştırma

### 2.2 Python asyncio

```python
# Senkron (blocking)
result = requests.get("https://api.example.com")

# Asenkron (non-blocking)
result = await httpx.AsyncClient().get("https://api.example.com")
```

**Bu projede:**

- `app/db/session.py` — `async_sessionmaker`, asyncpg
- `app/db/repositories/base.py` — tüm metodlar `async def`
- `app/websockets/manager.py` — `async def connect`, `broadcast_to_room`

**Kaynak:** [realpython.com/async-io-python](https://realpython.com/async-io-python/)

---

## Seviye 3 — HTTP ve REST API Temelleri

### 3.1 HTTP Protokolü

- Request / Response döngüsü
- HTTP metodları: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`
- HTTP durum kodları: `200 OK`, `201 Created`, `400 Bad Request`,
  `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `422 Unprocessable Entity`
- Header'lar: `Content-Type`, `Authorization`, `X-Request-ID`

**Bu projede:**

- `app/core/middleware.py` — `X-Request-ID`, `X-Process-Time-Ms` header'ları eklenir
- `app/core/exceptions.py` — her hata tipi farklı HTTP kodu döner

### 3.2 REST API Tasarımı

- Resource (kaynak) kavramı: `/users`, `/users/{id}`
- URL yapısı: `/api/v1/users`
- Query param vs. path param vs. request body
- JSON formatı

**Bu projede:**

- `app/api/v1/endpoints/` — tüm endpoint'ler `/api/v1/` prefix'i altında
- `app/api/v1/router.py` — router kayıtları

### 3.3 OpenAPI / Swagger

- API dokümantasyonunun otomatik üretimi
- `GET /docs` adresinde interaktif test

**Bu projede:** `app/main.py`'deki `/docs` ve `/redoc` endpoint'leri

---

## Seviye 4 — Pydantic v2

Projedeki tüm veri doğrulama ve serileştirme Pydantic ile yapılır.

### 4.1 Temel Kullanım

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str | None = None
```

- `BaseModel`, alan tanımı, varsayılan değerler
- `.model_dump()`, `.model_validate()`
- Otomatik tip dönüşümü ve hata mesajları

### 4.2 Validator'lar

- `@field_validator` — alan seviyesi doğrulama
- `@model_validator(mode="after")` — nesne oluşturulduktan sonra doğrulama

**Bu projede:**

- `app/schemas/auth.py` — şifre güçlük kuralları `@field_validator` ile
- `app/core/config.py` — `validate_production_settings` model_validator'ı

### 4.3 Pydantic Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"
```

**Bu projede:** `app/core/config.py` — tüm uygulama ayarları buradan okunur

### 4.4 Pydantic ve Runtime Annotation Çözümleme

Pydantic v2, `BaseModel` subclass'ı tanımlandığı anda field type'larını `get_type_hints()` ile çözümler. Bu nedenle field'larda kullanılan tipler (örn. `UUID`) modülün runtime namespace'inde mevcut olmalıdır — `if TYPE_CHECKING:` bloğuna alınamaz.

```python
# YANLIŞ — uygulama başlarken PydanticUndefinedAnnotation hatası verir
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from uuid import UUID

class UserResponse(BaseModel):
    id: UUID  # runtime'da UUID tanımsız!

# DOĞRU
from uuid import UUID  # gerçek import

class UserResponse(BaseModel):
    id: UUID  # çalışır
```

Bkz. Seviye 12.3 — `TYPE_CHECKING` ile ilgili ayrıntılı açıklama.

---

## Seviye 5 — FastAPI

### 5.1 Temel Kullanım

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"id": user_id}
```

- Route tanımlama: `@app.get`, `@app.post`
- Path param, query param, request body
- Response model

### 5.2 Dependency Injection

FastAPI'nin en güçlü özelliği. Bağımlılıkları merkezi olarak yönetir.

```python
from fastapi import Depends

async def get_db():
    async with SessionLocal() as session:
        yield session

@app.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    ...
```

**Bu projede:**

- `app/api/dependencies/` — tüm `Depends()` fonksiyonları
- `app/api/dependencies/auth.py` — `CurrentUserDep`, `AdminDep`

### 5.3 Middleware

Request/response döngüsüne kesişen işlemler ekler.

**Bu projede:** `app/core/middleware.py`

- `RequestIDMiddleware` — her isteğe UUID ekler
- `TimingMiddleware` — işlem süresini ölçer
- `SecurityHeadersMiddleware` — tarayıcı güvenlik başlıkları

### 5.4 Exception Handler'lar

**Bu projede:** `app/core/exceptions.py` — global hata yönetimi

### 5.5 WebSocket

```python
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    data = await websocket.receive_json()
```

**Bu projede:** `app/websockets/manager.py` — `ConnectionManager` singleton (oda tabanlı broadcast, `send_to_user_all_rooms` ile bildirim push)

**Kaynak:** [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)

---

## Seviye 6 — Veritabanı

### 6.1 SQL Temelleri

- `SELECT`, `INSERT`, `UPDATE`, `DELETE`
- `WHERE`, `JOIN`, `ORDER BY`, `LIMIT`
- Primary key, foreign key, index
- Transaction: `COMMIT`, `ROLLBACK`

**Kaynak:** [sqlzoo.net](https://sqlzoo.net/) veya [pgexercises.com](https://pgexercises.com/)

### 6.2 PostgreSQL

- SQL standardından farkları
- `asyncpg` — Python için async PostgreSQL sürücüsü
- Connection pool kavramı (neden önemli)

**Bu projede:** `app/db/session.py` — `pool_size=10`, `max_overflow=20`

### 6.3 SQLAlchemy 2.0 (Async)

ORM: Python nesnelerini veritabanı tablolarıyla eşler.

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
```

- `select()`, `insert()`, `update()`, `delete()`
- `AsyncSession`, `async with session.begin()`
- Relationship: `relationship()`, `ForeignKey`
- `selectinload`, `joinedload` — N+1 sorgu problemi

**Bu projede:** `app/db/models/` — tüm ORM modelleri

### 6.4 Alembic — Veritabanı Migrations

Model değişikliklerini veritabanına yansıtır.

```bash
alembic revision --autogenerate -m "add users table"
alembic upgrade head
alembic downgrade -1
```

**Bu projede:** `alembic/versions/` klasörü

### 6.5 Repository Pattern

Servisler veritabanını doğrudan kullanmaz; repository aracılığıyla erişir.

```
Endpoint → Service → Repository → SQLAlchemy → PostgreSQL
```

**Bu projede:** `app/db/repositories/base.py` — generic `BaseRepository[ModelType]`

---

## Seviye 7 — Kimlik Doğrulama ve Güvenlik

### 7.1 Parola Güvenliği

- **Hash nedir?** Tek yönlü dönüşüm — orijinal değer geri alınamaz
- **bcrypt:** Kasıtlı yavaş hash algoritması; brute-force'a dayanıklı
- **Salt:** Her hash'e rastgele ek → aynı şifre farklı hash üretir

```python
hash_password("secret")  # $2b$12$... (her seferinde farklı)
verify_password("secret", hashed)  # True
```

**Bu projede:** `app/core/security.py` — `hash_password`, `verify_password`

### 7.2 JWT (JSON Web Token)

Sunucunun kullanıcıya imzalı bir kimlik kartı vermesi.

```
Header.Payload.Signature
eyJhbGci...  .eyJzdWIi...  .SflKxwRJ...
```

- **Access token:** Kısa ömürlü (30dk), her istekte gönderilir
- **Refresh token:** Uzun ömürlü (30gün), yalnızca token yenilemede
- **RS256:** Asimetrik imza — özel anahtarla imzala, genel anahtarla doğrula

**Bu projede:** `app/core/security.py` — `create_access_token`, `decode_token`
Anahtarlar: `keys/private.pem`, `keys/public.pem`

### 7.3 OAuth2 Social Login

"Google ile giriş" akışı:

```
1. Kullanıcı "Google ile giriş"e tıklar
2. Google'ın login sayfasına yönlendirilir
3. Kullanıcı izin verir, Google bir "code" gönderir
4. Backend, code ile Google'dan kullanıcı bilgisi alır
5. Backend kendi JWT'sini oluşturur ve döner
```

**Bu projede:** `app/services/oauth.py` — Google ve GitHub akışları
`app/db/repositories/oauth_account.py` — provider hesabı kaydı

### 7.4 Güvenlik Başlıkları

- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options`
- `X-Frame-Options`
- `Content-Security-Policy`

**Bu projede:** `app/core/middleware.py` — `SecurityHeadersMiddleware`

### 7.5 Rate Limiting

Brute-force ve DDoS saldırılarını yavaşlatır.

**Bu projede:** `app/core/limiter.py` — slowapi ile IP/kullanıcı bazlı limit

### 7.6 TOTP / İki Faktörlü Kimlik Doğrulama (2FA)

Şifreye ek olarak zamanla değişen 6 haneli kod zorunluluğu. RFC 6238 standardı.

- **TOTP nasıl çalışır?** Shared secret + mevcut zaman → 30 saniyede bir yeni kod
- **TOTP uygulamaları:** Google Authenticator, Authy vb.
- **QR kodu:** Secret, `otpauth://` URI formatında encode edilir
- **Yedek kodlar:** 2FA cihazı kaybolursa tek kullanımlık kodlar
- **Fernet şifreleme:** TOTP secret'ı DB'de düz metin saklamak güvensizdir; `cryptography.fernet` ile şifrelenir

```python
# Basit TOTP doğrulama mantığı
import pyotp
totp = pyotp.TOTP(secret)
totp.verify(user_provided_code)  # True / False
```

**Bu projede:**

- `app/services/totp.py` — `TOTPService` (setup, verify_and_enable, disable)
- `app/db/models/user.py` — `totp_secret` (Fernet encrypted), `totp_enabled`
- `app/core/security.py` — Fernet şifreleme (SECRET_KEY'den türetilir)
- `app/services/_keys.py` — Yedek kodlar Redis'te saklanır (`totp_backup:{}`)

### 7.7 API Key Kimlik Doğrulama

Kullanıcı adı/şifre veya JWT yerine uzun ömürlü anahtar ile kimlik doğrulama. Servisler arası iletişimde veya CLI araçlarında kullanılır.

- **Format:** `sk_live_<80 rastgele hex>` — okunabilir prefix + rastgele gövde
- **Saklama:** Tam key bir kez gösterilir, sonra yalnızca bcrypt hash'i saklanır
- **Lookup:** `key_prefix` (ilk 12 karakter) ile DB'de aday key'ler bulunur, bcrypt ile doğrulanır
- **Scopes:** `read write admin` gibi boşlukla ayrılmış izin listeleri

```python
# İstemci kullanımı
headers = {"X-API-Key": "sk_live_abc123..."}
response = requests.get("/api/v1/users/me", headers=headers)
```

**Bu projede:**

- `app/services/api_key.py` — `APIKeyService` (create, authenticate, revoke)
- `app/db/models/api_key.py` — `APIKey` modeli (key_prefix, key_hash, scopes, expires_at)
- `app/api/dependencies/auth.py` — `get_current_user` hem Bearer token hem X-API-Key kabul eder

---

## Seviye 8 — Redis

### 8.1 Redis Nedir?

In-memory anahtar-değer deposu. PostgreSQL'den çok daha hızlı ama kalıcı değil.

### 8.2 Kullanım Alanları

- **Cache:** Sık okunan veriyi bellekte tut
- **Session store:** Token blacklist, TOTP yedek kodlar
- **Task queue:** Arka plan görevleri için kuyruk
- **Rate limit counter:** slowapi'nin sayacları burada
- **Pub/Sub:** Bildirim push için WebSocket manager ile koordinasyon

**Bu projede:**

- `app/core/redis.py` — singleton Redis client
- `app/services/_keys.py` — tüm Redis key formatları (`email_verify:{}`, `password_reset:{}`, `blacklist:{}`, `totp_backup:{}` vb.)
- ARQ worker kuyrukları (email gönderme, dosya işleme)

### 8.3 ARQ — Async Task Queue

Redis üzerinde çalışan Python arka plan görev kuyruğu.

```python
# Görevi kuyruğa ekle (endpoint'ten)
await redis.enqueue_job("send_verification_email", user_id=user.id)

# Worker çalıştır
arq app.tasks.worker.WorkerSettings
```

**Bu projede:** `app/tasks/` — worker tanımları ve görev fonksiyonları

### 8.4 Bildirimler ve WebSocket Push

Bildirim sistemi iki kanalı birleştirir: kalıcı kayıt (DB) + anlık iletim (WebSocket).

```
NotificationService.create() çağrılır
    ↓
Bildirim PostgreSQL'e yazılır (kalıcı)
    ↓
ConnectionManager.send_to_user_all_rooms() çağrılır
    ↓
Kullanıcı WebSocket'e bağlıysa anlık iletilir
    ↓
Bağlı değilse → sadece DB'de bekler, GET /notifications ile alınır
```

- **Bildirim tipleri:** `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `SYSTEM`, `MENTION`, `FILE_PROCESSED`
- **JSONB payload:** `data` alanı ile her bildirime özel ek veri saklanabilir
- **Okundu takibi:** `is_read` flag'i, `PATCH /notifications/read-all` ile toplu güncelleme

**Bu projede:**

- `app/services/notification.py` — `NotificationService` (create, list, mark_read, count_unread)
- `app/db/models/notification.py` — `Notification` modeli (type enum, JSONB data, is_read)
- `app/db/repositories/notification.py` — `NotificationRepository`
- `app/websockets/manager.py` — `send_to_user_all_rooms()` ile push

---

## Seviye 9 — Docker ve Containerization

### 9.1 Docker Temelleri

- Image vs. Container farkı
- `Dockerfile` — image nasıl inşa edilir
- `docker build`, `docker run`, `docker ps`, `docker logs`
- Volume: container dışı kalıcı depolama
- Port mapping: `-p 8000:8000`

### 9.2 Docker Compose

Birden fazla servisi birlikte yönetir.

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    depends_on: [db, redis]
  db:
    image: postgres:16
  redis:
    image: redis:7
```

**Bu projede:** `docker-compose.yml` (dev), prod konfigürasyonu README'de

### 9.3 Multi-stage Build

Prod image'ını küçük ve güvenli tutar.

**Bu projede:** `docker/Dockerfile` — `development` ve `production` aşamaları

---

## Seviye 10 — Test Yazımı

### 10.1 pytest Temelleri

```python
def test_something():
    result = add(2, 3)
    assert result == 5
```

- Test fonksiyonu `test_` ile başlar
- `assert` ile beklenen sonuç kontrol edilir
- Fixture: tekrar kullanılabilir test bağlamı

### 10.2 pytest-asyncio

Async fonksiyonları test eder.

```python
@pytest.mark.asyncio
async def test_async_thing():
    result = await some_async_function()
    assert result == "expected"
```

**Bu projede:** `asyncio_mode = "auto"` — her test otomatik async

### 10.3 Mock ve Patch

Dış bağımlılıkları (email, Redis, S3) test sırasında taklit eder.

```python
from unittest.mock import AsyncMock, patch

with patch("app.tasks.email.send_email", new=AsyncMock()) as mock_send:
    # Test kodu
    mock_send.assert_called_once()
```

**Bu projede:**

- `tests/conftest.py` — FakeRedis, S3 mock, async DB session
- `tests/integration/test_websocket.py` — lifespan patch'i

### 10.4 Integration Test

Gerçek HTTP isteği simüle eder.

```python
async def test_login(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={...})
    assert resp.status_code == 200
```

**Bu projede:** `tests/integration/` — tüm endpoint'ler test edilir

### 10.5 Test İzolasyonu

Her test kendi transaction'ında çalışır; test sonunda rollback yapılır.
Testler birbirini etkilemez.

**Bu projede:** `tests/conftest.py` — `db_session` fixture'ı

---

## Seviye 11 — Mimari ve Tasarım Örüntüleri

### 11.1 Katmanlı Mimari

```
HTTP İsteği
    ↓
Endpoint (app/api/v1/endpoints/)
    — sadece istek al, servise ilet, yanıt dön
    ↓
Service (app/services/)
    — iş kuralları, doğrulama, orchestration
    ↓
Repository (app/db/repositories/)
    — SQL sorguları, DB erişimi
    ↓
PostgreSQL
```

Neden bu ayrım? Bir katmanı değiştirdiğinizde diğerleri etkilenmez.
Örnek: PostgreSQL'den MongoDB'ye geçmek için yalnızca repository katmanı değişir.

### 11.2 SOLID Prensipleri

| Prensip                       | Açıklama                               | Bu Projede                                           |
| ----------------------------- | -------------------------------------- | ---------------------------------------------------- |
| **S** — Single Responsibility | Bir sınıf tek işi yapar                | `AuthService`, `OAuthService`, `AccountService` ayrı |
| **O** — Open/Closed           | Genişletmeye açık, değiştirmeye kapalı | `BaseRepository` — extend et, değiştirme             |
| **L** — Liskov Substitution   | Alt sınıf üst sınıfın yerine geçebilir | Repository miras zinciri                             |
| **I** — Interface Segregation | Büyük interface yerine küçük olanlar   | Ayrı repository'ler                                  |
| **D** — Dependency Inversion  | Somut değil, soyuta bağımlı ol         | `Depends()` ile injection                            |

### 11.3 DRY (Don't Repeat Yourself)

**Bu projede:**

- `app/services/base.py` — `AuditableMixin` ile audit log kodu tekrarlanmaz
- `app/services/_keys.py` — Redis key formatları bir yerde tanımlı
- `BaseRepository[ModelType]` — CRUD kodu her model için yeniden yazılmaz

### 11.4 12-Factor App

Production-ready uygulama standartları:

| Faktör           | Bu Projede                                      |
| ---------------- | ----------------------------------------------- |
| Config           | `.env` dosyası, `pydantic-settings`             |
| Backing services | PostgreSQL, Redis, S3 — URL ile yapılandırılır  |
| Logs             | stdout'a JSON formatında (structlog)            |
| Stateless        | Her container aynı işi yapar; state Redis/DB'de |

---

## Seviye 12 — Araçlar ve Kalite

### 12.1 Ruff — Linter ve Formatter

```bash
ruff check app/        # Hata bul
ruff check --fix app/  # Otomatik düzelt
ruff format app/       # Formatla
```

Pyflakes, isort, pyupgrade, bugbear, bandit ve daha fazlasını tek araçta birleştirir. Rust ile yazıldığı için flake8 + black + isort kombinasyonundan ~100x hızlıdır.

Aktif kural grupları: `E/W` (pycodestyle), `F` (pyflakes), `I` (isort), `B` (bugbear), `UP` (pyupgrade), `S` (güvenlik), `TCH` (type-checking import optimizasyonu), `PERF`, `C4`, `N`, `G`.

**Bu projede:** `pyproject.toml` — `[tool.ruff.lint]` ve `[tool.ruff.format]` bölümleri

### 12.2 mypy — Statik Tip Kontrolü

```bash
mypy app/  # Tip hatalarını bul (çalıştırmadan)
```

`strict = true` modu: tüm fonksiyonların dönüş tipleri ve parametreleri belirtilmeli, `Any` kullanımı kısıtlı, `Optional` yerine `X | None` zorunlu.

`pydantic-mypy` plugin'i aktif — Pydantic BaseModel field'larını mypy'ın anlayabileceği şekilde çözümler.

**Bu projede:** `pyproject.toml` — `[tool.mypy]` bölümü

### 12.3 `from __future__ import annotations` ve TYPE_CHECKING

Python 3.10+'dan önce `list[str]` gibi generic syntax hata verir. `from __future__ import annotations` tüm annotation'ları lazy string yapar — hem eski syntax uyumluluğu hem de döngüsel import sorunlarını çözer.

```python
# TYPE_CHECKING bloğu: sadece mypy çalışırken import edilir, runtime'da değil
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.services.user import UserService  # döngüsel importu kırar
```

**Kritik istisna:** Bazı framework'ler annotation'ları runtime'da `get_type_hints()` ile çözümler. Bu durumlarda TYPE_CHECKING bloğu kullanılırsa `NameError` fırlatılır:

| Framework                              | Neden runtime import zorunlu                           |
| -------------------------------------- | ------------------------------------------------------ |
| Pydantic `BaseModel` field'ları        | Schema oluşturma sırasında `get_type_hints()` çağrılır |
| SQLAlchemy `Mapped[...]` field'ları    | Mapper konfigürasyonunda annotation çözümlenir         |
| FastAPI endpoint / dependency imzaları | Bağımlılık grafiği `get_type_hints()` ile inşa edilir  |

**Bu projede:** `app/schemas/*.py`, `app/db/models/*.py`, `app/api/v1/endpoints/*.py` — bu dosyalarda TYPE_CHECKING kullanılmaz; `pyproject.toml`'da `TCH` kuralları per-file-ignore ile devre dışı bırakılmıştır.

### 12.4 pre-commit — Git Hook Otomasyonu

Her `git commit` öncesinde otomatik çalışan kalite kontrolleri.

```bash
pip install pre-commit
pre-commit install          # hook'ları .git/hooks/ altına yükle
pre-commit run --all-files  # tüm dosyalarda manuel çalıştır
```

`.pre-commit-config.yaml` tanımlı hook'lar:

- `trailing-whitespace`, `end-of-file-fixer`, `check-merge-conflict` — temel dosya kalitesi
- `detect-private-key` — gizli anahtar sızıntısı tespiti
- `ruff` (--fix) + `ruff-format` — her commit'te linting ve formatlama

**Bu projede:** `.pre-commit-config.yaml`

### 12.5 GitHub Actions — CI/CD

Her `push` ve `pull_request`'te (master, dev) otomatik çalışan üç paralel job:

**`.github/workflows/lint.yml` — Lint & Type Check:**

```
lint job      → pip install ruff → ruff check + ruff format --check
typecheck job → pip install -r requirements.txt -r requirements-dev.txt → mypy app/
```

**`.github/workflows/test.yml` — Tests:**

```
test job  → PostgreSQL 16 service container ayağa kalkar
          → pip install bağımlılıklar
          → openssl ile JWT key'leri üretilir
          → alembic upgrade head
          → pytest --cov=app (fakeredis ile, gerçek Redis gerekmez)
          → coverage.xml artifact olarak yüklenir (7 gün)
```

PR merge edilebilmesi için üç job'ın da (`lint`, `typecheck`, `test`) geçmesi zorunludur.

**Bu projede:** `.github/workflows/lint.yml`, `.github/workflows/test.yml`

### 12.6 structlog — Yapılandırılmış Loglama

JSON formatında log: her log satırı makine tarafından parse edilebilir.

```python
logger.info("user_created", user_id=str(user.id), email=user.email)
# {"event": "user_created", "user_id": "...", "email": "..."}
```

**Bu projede:** `app/core/logging.py`

---

## Seviye 13 — Altyapı Servisleri ve Gözlemlenebilirlik

### 13.1 Dosya Depolama — S3 / MinIO

S3 (Simple Storage Service), dosyaları nesne olarak depolayan bir AWS servisidir. MinIO, S3 API'siyle uyumlu açık kaynaklı bir alternatiftir — yerel geliştirme için kullanılır.

- **Bucket:** Dosyaların saklandığı kap (klasör benzeri)
- **Object key:** Dosyanın benzersiz yolu (örn. `uploads/user-123/avatar.png`)
- **Presigned URL:** Geçici erişim bağlantısı — dosyayı herkese açmadan paylaşmak için
- **MinIO Console:** http://localhost:9001 — tarayıcıdan bucket ve dosya yönetimi

```python
# Dosya yükleme
await s3_client.upload_fileobj(file, bucket_name, object_key)

# Dosya silme
await s3_client.delete_object(Bucket=bucket_name, Key=object_key)
```

**Bu projede:**

- `app/storage/backends.py` — MinIO/S3 backend soyutlaması
- `app/api/v1/endpoints/uploads.py` — dosya yükleme ve silme endpoint'leri
- `scripts/create_buckets.py` — uygulama başlangıcında bucket oluşturur
- `.env` — `STORAGE_BACKEND`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_NAME`

### 13.2 SQLAdmin — Admin Panel

SQLAlchemy modelleri üzerinde otomatik CRUD arayüzü oluşturan FastAPI uyumlu bir kütüphane.

- **Model View:** `ModelView` subclass'ı ile her model için yönetim ekranı
- **Authentication Backend:** Mevcut JWT sistemiyle entegre — ayrı hesap gerekmez
- **Session yönetimi:** `SessionMiddleware` + `itsdangerous` ile imzalı cookie

```python
class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.role, User.is_active]
    can_delete = True
```

**Bu projede:**

- `app/admin/views.py` — `UserAdmin`, `OAuthAccountAdmin` view'ları
- `app/admin/auth.py` — JWT doğrulamalı authentication backend
- `app/admin/seed.py` — `ADMIN_EMAIL`/`ADMIN_PASSWORD` ile ilk admin oluşturur
- Erişim: http://localhost:8000/admin (yalnızca `ADMIN` rolü)

### 13.3 Prometheus Metrikleri

Prometheus, zaman serisi metrik toplama sistemidir. `prometheus-fastapi-instrumentator` kütüphanesi FastAPI için otomatik HTTP metriklerini sağlar.

- **Counter:** Yalnızca artan sayaç (toplam istek sayısı)
- **Histogram:** Değer dağılımı (yanıt süresi yüzdelik dilimleri)
- **Gauge:** Anlık değer (aktif bağlantı sayısı)
- **Scraping:** Prometheus, `/metrics` endpoint'ini periyodik olarak çekerek veri toplar

Otomatik üretilen metrikler: `http_requests_total`, `http_request_duration_seconds`, `http_request_size_bytes` vb.

**Bu projede:**

- `app/core/metrics.py` — instrumentator kurulumu
- `GET /metrics` — Prometheus scrape endpoint'i

### 13.4 Sentry — Hata Takibi

Sentry, üretim ortamında oluşan hataları gerçek zamanlı olarak yakalar, gruplandırır ve raporlar.

- **DSN (Data Source Name):** Sentry projesine bağlantı adresi
- **Tracing:** Her HTTP isteğini uçtan uca izler (performance profiling)
- **PII Filtreleme:** Kişisel veri (cookie, auth header) otomatik temizlenir
- **Sample Rate:** `SENTRY_TRACES_SAMPLE_RATE=0.1` → trafiğin %10'u izlenir

```python
import sentry_sdk
sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
)
```

**Bu projede:**

- `app/main.py` — uygulama başlangıcında Sentry init (DSN boşsa atlanır)
- `.env` — `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`

### 13.5 Audit Logging — Denetim Kayıtları

Kimin ne zaman ne yaptığını izleyen kayıt sistemi. Güvenlik denetimi ve olay soruşturması için kritiktir.

- **Bağımsız session:** Audit kayıtları, işlem rollback'inden bağımsız `AsyncSessionFactory` ile yazılır — bir işlem başarısız olsa bile audit kaydı kaybolmaz
- **Opsiyonel bağımlılık:** `audit: AuditService | None = None` — testlerde geçirilmesi gerekmez

```
Kullanıcı login yapar
    ↓
AuthService.login() başarısız olursa
    ↓
DB transaction rollback olur
    ↓
AuditService.log(LOGIN_FAILED) bağımsız session ile yazar → kayıt korunur
```

**Bu projede:**

- `app/services/audit.py` — `AuditService` (bağımsız session factory kullanır)
- `app/services/base.py` — `AuditableMixin._audit_log()` tüm servislere miras
- `app/db/models/audit_log.py` — `AuditLog` modeli (action enum, ip_address, user_agent, JSONB extra)

---

## Önerilen Öğrenme Sırası

```
Hafta 1-2:   Python temelleri (Seviye 1)
Hafta 3:     Async programlama (Seviye 2)
Hafta 4:     HTTP ve REST (Seviye 3)
Hafta 5:     Pydantic + FastAPI (Seviye 4-5)
Hafta 6-7:   Veritabanı — SQL + SQLAlchemy (Seviye 6)
Hafta 8:     Güvenlik — JWT + OAuth2 + bcrypt + TOTP + API Key (Seviye 7)
Hafta 9:     Redis + ARQ + Bildirimler (Seviye 8)
Hafta 10:    Docker + Dosya Depolama S3/MinIO (Seviye 9, 13.1)
Hafta 11:    Test yazımı (Seviye 10)
Hafta 12:    Admin Panel + Prometheus + Sentry + Audit Log (Seviye 13.2-13.5)
Hafta 13+:   Mimari prensipleri okuyarak projeyi incele (Seviye 11-12)
```

---

## Bu Projeyi İncelerken Önerilen Dosya Sırası

1. `app/core/config.py` — Ne ayarlanır, neden? Production validator nasıl çalışır?
2. `app/db/models/user.py` — Veri nasıl modellenir? TOTP alanları nerede?
3. `app/db/repositories/base.py` — Generic `BaseRepository[T]` nasıl çalışır?
4. `app/db/repositories/user.py` — Domain-specific sorgular nasıl eklenir?
5. `app/services/base.py` — `AuditableMixin` nedir, neden tüm servisler miras alır?
6. `app/services/auth.py` — Login iş akışı nasıl çalışır? TOTP kontrolü nerede?
7. `app/api/v1/endpoints/auth.py` — HTTP katmanı ne kadar ince?
8. `app/api/dependencies/auth.py` — JWT ve API Key nasıl birlikte doğrulanır?
9. `app/core/security.py` — JWT RS256 nasıl oluşturulur ve doğrulanır?
10. `app/services/totp.py` — 2FA kurulumu ve Fernet şifreleme nasıl çalışır?
11. `app/services/api_key.py` — `sk_live_` prefix'li key'ler nasıl oluşturulur ve doğrulanır?
12. `app/services/notification.py` — Bildirim oluşturma ve WebSocket push akışı
13. `app/websockets/manager.py` — Oda tabanlı bağlantı yönetimi nasıl çalışır?
14. `app/services/audit.py` — Neden bağımsız session kullanılır?
15. `app/storage/backends.py` — S3/MinIO soyutlaması nasıl yapılmış?
16. `app/tasks/worker.py` — ARQ background task'ları nasıl tanımlanır?
17. `app/admin/views.py` — SQLAdmin view'ları nasıl kayıt edilir?
18. `tests/conftest.py` — Test fixture'ları ve izolasyon nasıl sağlanır?
19. `tests/integration/test_auth.py` — Uçtan uca akış nasıl test edilir?

---

## Faydalı Kaynaklar

| Konu           | Kaynak                                                                                        |
| -------------- | --------------------------------------------------------------------------------------------- |
| Python         | [docs.python.org/3/tutorial](https://docs.python.org/3/tutorial/)                             |
| Async Python   | [realpython.com/async-io-python](https://realpython.com/async-io-python/)                     |
| FastAPI        | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)                                         |
| SQLAlchemy 2.0 | [docs.sqlalchemy.org/en/20/](https://docs.sqlalchemy.org/en/20/)                              |
| Pydantic v2    | [docs.pydantic.dev](https://docs.pydantic.dev/)                                               |
| JWT            | [jwt.io/introduction](https://jwt.io/introduction/)                                           |
| TOTP / RFC6238 | [rfc-editor.org/rfc/rfc6238](https://www.rfc-editor.org/rfc/rfc6238)                          |
| Docker         | [docs.docker.com/get-started](https://docs.docker.com/get-started/)                           |
| MinIO          | [min.io/docs/minio/linux/index.html](https://min.io/docs/minio/linux/index.html)              |
| pytest         | [docs.pytest.org](https://docs.pytest.org/)                                                   |
| Ruff           | [docs.astral.sh/ruff](https://docs.astral.sh/ruff/)                                           |
| mypy           | [mypy.readthedocs.io](https://mypy.readthedocs.io/)                                           |
| pre-commit     | [pre-commit.com](https://pre-commit.com/)                                                     |
| SQLAdmin       | [aminalaee.dev/sqladmin](https://aminalaee.dev/sqladmin/)                                     |
| Prometheus     | [prometheus.io/docs/introduction/overview](https://prometheus.io/docs/introduction/overview/) |
| structlog      | [structlog.readthedocs.io](https://structlog.readthedocs.io/)                                 |
| 12-Factor App  | [12factor.net](https://12factor.net/)                                                         |
| OWASP Top 10   | [owasp.org/Top10](https://owasp.org/www-project-top-ten/)                                     |
