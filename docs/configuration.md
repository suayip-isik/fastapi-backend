# Configuration Reference

Bu belge, uygulamanın önemli environment variable’larını ve beklenen çalışma modlarını açıklar.

## Çalışma Modları

- `development`: geliştirici deneyimi öncelikli; docs/metrics açık olabilir, seed akışları default açık tutulabilir.
- `staging`: production’a yakın davranış test edilir; prod policy’leri kademeli denenebilir.
- `production`: runtime access policy, secure cookies ve host validation zorunlu hale gelir.

## Temel Uygulama Ayarları

| Değişken       | Açıklama                               | Development             | Production                  |
| -------------- | -------------------------------------- | ----------------------- | --------------------------- |
| `APP_ENV`      | Çalışma modu                           | `development`           | `production`                |
| `APP_DEBUG`    | Debug/log ayrıntısı                    | `true` olabilir         | `false` zorunlu             |
| `APP_URL`      | API public base URL                    | `http://localhost:8000` | `https://api.example.com`   |
| `FRONTEND_URL` | Frontend public URL                    | localhost olabilir      | HTTPS gerçek domain zorunlu |
| `SECRET_KEY`   | Session + symmetric crypto root secret | rastgele                | güçlü ve uzun zorunlu       |

## Host ve CORS

| Değişken        | Açıklama                                                    |
| --------------- | ----------------------------------------------------------- |
| `ALLOWED_HOSTS` | Trusted host listesi. Production’da `["*"]` yasak.          |
| `CORS_ORIGINS`  | Tarayıcı origin whitelist’i. Production’da boş bırakılamaz. |

Örnek:

```env
ALLOWED_HOSTS=["api.example.com"]
CORS_ORIGINS=["https://app.example.com"]
```

## Auth Cookie ve Admin Session Ayarları

Uygulama iki ayrı cookie yüzeyi kullanır:

- API auth cookie’leri (`access_token`, `refresh_token`)
- SQLAdmin session cookie’si

İlgili ayarlar:

| Değişken                        | Açıklama                       |
| ------------------------------- | ------------------------------ |
| `COOKIE_DOMAIN`                 | Auth cookie domain             |
| `COOKIE_SECURE`                 | Auth cookie secure flag        |
| `COOKIE_SAMESITE`               | Auth cookie same-site policy   |
| `ADMIN_SESSION_COOKIE_NAME`     | Admin panel session cookie adı |
| `ADMIN_SESSION_COOKIE_SECURE`   | Admin session secure flag      |
| `ADMIN_SESSION_COOKIE_SAMESITE` | Admin session same-site policy |
| `ADMIN_SESSION_MAX_AGE`         | Admin session TTL (saniye)     |

Production’da:

- `COOKIE_SECURE=true`
- `ADMIN_SESSION_COOKIE_SECURE=true`

olmalıdır.

## Runtime Access Policy

Bu ayarlar production’da operational yüzeyleri korur.

| Değişken                    | Değerler                         | Açıklama                                        |
| --------------------------- | -------------------------------- | ----------------------------------------------- |
| `DOCS_ACCESS_MODE`          | `public`, `internal`, `disabled` | `/docs`, `/redoc`, `/openapi.json`, `/schema/*` |
| `METRICS_ACCESS_MODE`       | `public`, `internal`, `disabled` | `/metrics`                                      |
| `HEALTH_DETAIL_ACCESS_MODE` | `public`, `internal`, `disabled` | `/health`, `/health/ready`                      |
| `INTERNAL_ACCESS_TOKEN`     | string                           | `internal` mode kullanılıyorsa zorunlu          |

Davranış:

- `public`: endpoint herkese açık
- `internal`: endpoint `X-Internal-Access-Token` header’ı veya `?access_token=` query param ile açılır
- `disabled`: endpoint 404 döner

Notlar:

- `health/live` her zaman public kalır
- Runtime access policy sadece production’da enforce edilir; development/staging’de geliştirici deneyimi korunur

## Startup Seed Ayarları

| Değişken                       | Açıklama                           | Öneri                      |
| ------------------------------ | ---------------------------------- | -------------------------- |
| `SEED_SYSTEM_ROLES_ON_STARTUP` | Canonical role/permission sync     | dev: `true`, prod: `false` |
| `SEED_DEFAULT_SUPERADMIN`      | Varsayılan admin kullanıcı oluştur | dev: `true`, prod: `false` |
| `SEED_DEFAULT_APP_USER`        | Varsayılan app user oluştur        | dev: `true`, prod: `false` |

Seed flag’leri kapalıyken ilgili password alanlarının dolu olması zorunlu değildir.

## Seed User Alanları

| Değişken                     | Açıklama                   |
| ---------------------------- | -------------------------- |
| `SUPERADMIN_USERNAME`        | Varsayılan admin username  |
| `SUPERADMIN_EMAIL`           | Varsayılan admin email     |
| `SUPERADMIN_PASSWORD`        | Admin seed password        |
| `DEFAULT_APP_USER_USERNAME`  | Varsayılan client username |
| `DEFAULT_APP_USER_EMAIL`     | Varsayılan client email    |
| `DEFAULT_APP_USER_PASSWORD`  | Client seed password       |
| `DEFAULT_APP_USER_FULL_NAME` | Client full name           |

Production önerisi:

- Bu alanları doldurabilirsiniz, fakat seed flag’lerini kapalı tutun.
- İlk bootstrap için explicit `make make-admin` veya `make seed` kullanın.

## Production Minimum Örnek

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
```
