# Kapsamlı Kod Analizi

Kriterler: **Modülerlik · Ölçeklenebilirlik · Sürdürülebilirlik · Performans · DRY · SOLID · Clean Architecture**

---

## Özet Tablosu

| #   | Başlık                                         | Öncelik   | Kategori        | Dosya                  |
| --- | ---------------------------------------------- | --------- | --------------- | ---------------------- |
| 1   | Email body log'a yazılıyor                     | 🔴 KRİTİK | Güvenlik        | `email.py:28-33`       |
| 2   | WebSocket token URL'de                         | 🔴 KRİTİK | Güvenlik        | `ws/manager.py:80`     |
| 3   | JWT key diskten her seferinde okunuyor         | 🟠 YÜKSEK | Güvenlik + Perf | `config.py:77-82`      |
| 4   | ADMIN_PASSWORD production'da kontrol edilmiyor | 🟠 YÜKSEK | Güvenlik        | `config.py:116,144`    |
| 5   | OAuthAccount hiç kaydedilmiyor (Ghost Model)   | 🟡 ORTA   | Clean Arch      | `services/auth.py:283` |
| 6   | AuthService SRP ihlali (5 sorumluluk)          | 🟡 ORTA   | SOLID           | `services/auth.py`     |
| 7   | AuditService API layer'dan direkt çağrılıyor   | 🟡 ORTA   | Clean Arch      | `endpoints/uploads.py` |
| 8   | Pagination: 2 ayrı DB sorgusu                  | 🟡 ORTA   | Performans      | `services/user.py:35`  |
| 9   | ALLOWED_HOSTS = ["*"]                          | 🟡 ORTA   | Güvenlik        | `config.py:32`         |
| 10  | `_audit_log()` iki service'de tekrar           | 🟢 DÜŞÜK  | DRY             | `auth.py`, `user.py`   |
| 11  | Redis key'leri magic string                    | 🟢 DÜŞÜK  | DRY             | `services/auth.py`     |
| 12  | `get_with_oauth()` dead code                   | 🟢 DÜŞÜK  | Dead Code       | `repositories/user.py` |

---

## 🔴 KRİTİK — Güvenlik

### #1 — Email dev fallback: Token içeren HTML body log'a yazılıyor

**Dosya:** `app/core/email.py:28-33`

```python
logger.warning("smtp_not_configured_dev_fallback", to=to, subject=subject, body=html_body)
```

`body=html_body` parametresi doğrulama ve şifre sıfırlama URL'sini — dolayısıyla token'ı — içeriyor. Log aggregation sistemine (Loki, ELK, CloudWatch) erişimi olan herkes bu token'ı çalabilir.

**Fix:** `body` yerine yalnızca token'ı logla:

```python
import re
token_match = re.search(r'token=([A-Za-z0-9_-]+)', html_body)
logger.warning(
    "smtp_not_configured",
    to=to,
    subject=subject,
    dev_token=token_match.group(1) if token_match else "[no-token]",
)
```

---

### #2 — WebSocket token URL query param'ında

**Dosya:** `app/websockets/manager.py:80`

```python
token: str,  # Query param: ws://host/ws/room?token=xxx
```

URL'deki token şu yerlere yazılır: Nginx/Caddy/Apache access logları, tarayıcı geçmişi, CDN logları, `Referer` header'ı. JWT access token 30 dakika geçerli — bu süre içinde log erişimi olan herkes token'ı kullanabilir.

**Fix:** Bağlantı kurulduktan sonra ilk mesajla doğrula:

```python
await websocket.accept()
try:
    data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
    if data.get("type") != "auth":
        await websocket.close(code=4001, reason="Auth mesajı bekleniyor.")
        return
    payload = decode_token(data["token"])
except Exception:
    await websocket.close(code=4001, reason="Geçersiz token.")
    return
```

---

## 🟠 YÜKSEK — Güvenlik / Performans

### #3 — JWT key her token işleminde diskten okunuyor

**Dosya:** `app/core/config.py:77-82`

```python
@property
def JWT_PRIVATE_KEY(self) -> str:
    return self.JWT_PRIVATE_KEY_PATH.read_text()  # Her çağrıda disk I/O

@property
def JWT_PUBLIC_KEY(self) -> str:
    return self.JWT_PUBLIC_KEY_PATH.read_text()   # Her çağrıda disk I/O
```

`settings` nesnesi `@lru_cache` ile önbelleklenmiş ancak `@property` her erişimde yeniden çalışır. `security.py`'deki `create_access_token()`, `create_refresh_token()` ve `decode_token()` — her token işleminde dosya okuma yapıyor.

**Fix:** `@cached_property` kullan:

```python
from functools import cached_property

@cached_property
def JWT_PRIVATE_KEY(self) -> str:
    return self.JWT_PRIVATE_KEY_PATH.read_text()

@cached_property
def JWT_PUBLIC_KEY(self) -> str:
    return self.JWT_PUBLIC_KEY_PATH.read_text()
```

> Not: `@cached_property` ile `model_config = SettingsConfigDict(...)` birlikte çalışmıyorsa `model_validator(mode="after")` içinde `object.__setattr__` ile set et.

---

### #4 — ADMIN_PASSWORD production'da kontrol edilmiyor

**Dosya:** `app/core/config.py:116, 144-151`

```python
ADMIN_PASSWORD: str = "changeme"  # ← default değer

@model_validator(mode="after")
def validate_production_settings(self) -> "Settings":
    if self.APP_ENV == "production":
        assert self.SECRET_KEY != "change-this-..."  # ✓ kontrol var
        assert not self.APP_DEBUG                    # ✓ kontrol var
        # ✗ ADMIN_PASSWORD kontrolü YOK
        # ✗ ALLOWED_HOSTS kontrolü YOK
```

**Fix:**

```python
if self.APP_ENV == "production":
    assert self.SECRET_KEY != "change-this-to-a-random-secret-key-in-production"
    assert not self.APP_DEBUG
    assert self.ADMIN_PASSWORD != "changeme", "Production'da ADMIN_PASSWORD değiştirilmeli!"
    assert self.ALLOWED_HOSTS != ["*"], "Production'da ALLOWED_HOSTS açık bırakılamaz!"
```

---

## 🟡 ORTA — Clean Architecture / SOLID / Güvenlik

### #5 — OAuthAccount tablosu hiç doldurulmuyor (Ghost Model)

**Dosya:** `app/services/auth.py:283-305`

`OAuthAccount` modeli, migration'ı ve `OAuthAccountAdmin` view'ı mevcut — ama `_upsert_oauth_user()` OAuthAccount kaydı **hiç oluşturmuyor**. `access_token`, `provider`, `provider_user_id` parametreleri sessizce atılıyor:

```python
async def _upsert_oauth_user(self, *, provider, provider_user_id, email,
                              full_name, avatar_url, access_token) -> TokenResponse:
    user = await self._repo.get_active_by_email(email)
    if not user:
        user = await self._repo.create(email=email.lower(), ...)
    # ↑ OAuthAccount.create() YAPILMIYOR
    tokens = create_token_pair(str(user.id))
    return TokenResponse(**tokens)
```

**Güvenlik sonucu:** Aynı email adresiyle Google + GitHub üzerinden kayıt yapılabilir, ikisi aynı User'a bağlanır — provider doğrulaması yok. Google hesabı ele geçirilirse GitHub'dan da aynı hesaba giriş açılır.

**Fix:**

1. `app/db/repositories/oauth_account.py` → `OAuthAccountRepository` oluştur
2. `_upsert_oauth_user()` içinde `(provider, provider_user_id)` ile upsert yap
3. `get_with_oauth()` metodunu `UserRepository`'den kaldır veya burada kullan

---

### #6 — AuthService SRP İhlali (306 satır, 5 sorumluluk)

**Dosya:** `app/services/auth.py`

Tek sınıfta beş farklı sorumluluk:

| Sorumluluk          | Metodlar                                                                   |
| ------------------- | -------------------------------------------------------------------------- |
| Email/password auth | `login`, `register`                                                        |
| Token yönetimi      | `refresh`, `logout`                                                        |
| Google OAuth        | `get_google_auth_url`, `google_callback`                                   |
| GitHub OAuth        | `get_github_auth_url`, `github_callback`                                   |
| Hesap yönetimi      | `verify_email`, `resend_verification`, `forgot_password`, `reset_password` |

**Önerilen bölünme:**

- `app/services/auth.py` → email/password login + logout + refresh (ince)
- `app/services/oauth.py` → Google + GitHub callback + `_upsert_oauth_user`
- `app/services/account.py` → email verify + password reset + resend

---

### #7 — AuditService API Layer'dan Doğrudan Çağrılıyor

**Dosya:** `app/api/v1/endpoints/uploads.py:36-40, 62-65`

```python
await AuditService().log(...)  # ← endpoint içinde service instantiation
```

`auth.py` ve `users.py` endpoint'leri `AuditService`'i `Depends()` ile inject ediyor; `uploads.py` kendi başına oluşturuyor. Tutarsızlık ve Clean Architecture ihlali.

**Fix:** `uploads.py`'e `AuditServiceDep` bağımlılığı ekle:

```python
async def upload_file(
    request: Request,
    current_user: CurrentUserDep,
    audit: AuditServiceDep,      # ← ekle
    file: UploadFile = File(...),
):
    ...
    await audit.log(AuditAction.FILE_UPLOADED, ...)
```

---

### #8 — Pagination'da 2 Ayrı DB Sorgusu

**Dosya:** `app/services/user.py:35-39`

```python
users = await self._repo.get_all(offset=offset, limit=size)  # Query 1
total = await self._repo.count()                              # Query 2
```

Her sayfalama isteğinde 2 round-trip. Yük altında latency'yi ikiye katlıyor.

**Fix:** `BaseRepository`'e window function destekli metod ekle:

```python
# repositories/base.py
async def get_page(self, *, offset: int, limit: int) -> tuple[list[ModelType], int]:
    stmt = (
        select(self.model, func.count().over().label("total"))
        .offset(offset)
        .limit(limit)
    )
    rows = (await self._session.execute(stmt)).all()
    items = [row[0] for row in rows]
    total = rows[0][1] if rows else 0
    return items, total
```

---

### #9 — ALLOWED_HOSTS = ["*"]

**Dosya:** `app/core/config.py:32`

Tüm Host header değerlerini kabul ediyor. Production'da şifre sıfırlama linkleri kötü amaçlı domain ile oluşturulabilir (Host header injection).

**Fix:** `#4`'teki production validator'a dahil et.

---

## 🟢 DÜŞÜK — DRY / Dead Code

### #10 — `_audit_log()` İki Service'de Tekrarlanıyor

**Dosyalar:** `app/services/auth.py:40-42`, `app/services/user.py:25-27`

Birebir aynı 3 satır her iki service'e de kopyalanmış:

```python
async def _audit_log(self, action: AuditAction, **kwargs) -> None:
    if self._audit:
        await self._audit.log(action, **kwargs)
```

**Fix:** Mixin veya standalone fonksiyon:

```python
# app/services/_mixins.py
class AuditableMixin:
    _audit: AuditService | None = None

    async def _audit_log(self, action: AuditAction, **kwargs) -> None:
        if self._audit:
            await self._audit.log(action, **kwargs)
```

---

### #11 — Redis Key'leri Magic String

**Dosya:** `app/services/auth.py`

Aynı prefix 2-3 farklı metodda inline yazılıyor. Bir typo sessiz bir bug olur:

```python
# register() ve resend_verification() ve verify_email() içinde:
f"email_verify:{token}"    # 3 ayrı yerde
f"password_reset:{token}"  # 2 ayrı yerde
f"blacklist:{jti}"         # 3 ayrı yerde
```

**Fix:** Modül seviyesi sabitler:

```python
_KEY_EMAIL_VERIFY = "email_verify:{}"
_KEY_PASSWORD_RESET = "password_reset:{}"
_KEY_BLACKLIST = "blacklist:{}"

# Kullanım:
await redis.setex(_KEY_EMAIL_VERIFY.format(token), _EMAIL_VERIFY_TTL, str(user.id))
```

---

### #12 — `get_with_oauth()` Dead Code

**Dosya:** `app/db/repositories/user.py:27-34`

OAuthAccount kayıtları hiç oluşturulmadığı için (`#5`) bu metod anlamsız sonuç döndürüyor ve proje genelinde hiçbir yerden çağrılmıyor.

**Fix:** `#5` çözülene kadar sil. `#5` çözüldüğünde `OAuthAccountRepository`'de daha uygun bir yere taşı.
