# FastAPI Production Backend

Production odaklı, API-first bir FastAPI backend boilerplate'i. Proje; JWT tabanlı auth, TOTP/2FA, RBAC/permission modeli, admin panel, API key, bildirimler, upload, background jobs ve operasyonel production guard'ları ile gelir.

Bu repo ile ilk kez karşılaşıyorsanız iki ana yol vardır:

- Uygulamayı localde ayağa kaldırıp geliştirmeye başlamak
- Uygulamayı production'a güvenli şekilde yayınlamak

Bu iki akış için canonical giriş belgeleri aşağıdadır.

## Nereden Başlamalıyım?

- Lokal geliştirme kurulumu: [docs/getting-started.md](./docs/getting-started.md)
- Tüm environment değişkenleri: [docs/configuration.md](./docs/configuration.md)
- Production deployment: [docs/production.md](./docs/production.md)
- Operasyon ve bakım: [docs/operations.md](./docs/operations.md)
- Katkı akışı: [docs/contributing.md](./docs/contributing.md)

## Hızlı Başlangıç

Lokal geliştirme için minimum akış:

```bash
git clone <repo-url>
cd fastapi-backend

make env
make keys
make dev
make migrate
make seed-roles
make seed
```

Ardından şu adresleri açabilirsiniz:

- API: `http://localhost:8000`
- Admin panel: `http://localhost:8000/admin`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Client docs: `http://localhost:8000/schema/client/docs`
- Admin docs: `http://localhost:8000/schema/admin/docs`

İlk admin hesabını explicit oluşturmak isterseniz:

```bash
make make-admin create=1 email=admin@example.com password='StrongAdminPass123!'
```

## Production Notları

Production davranışı local geliştirmeden farklıdır:

- `health/live` public probe olarak açık kalır
- `/health`, `/health/ready`, `/docs`, `/redoc`, `/schema/*`, `/metrics` runtime access policy ile korunur
- default seed kullanıcıları production startup'ında önerilmez
- ilk admin hesabı explicit bootstrap ile oluşturulmalıdır
- `docker-compose.prod.yml` tek-host örneğidir; gerçek HA/orchestrator çözümü değildir

Canonical production rehberi:

- [docs/production.md](./docs/production.md)

## Temel Özellikler

- JWT RS256 access/refresh token akışı
- TOTP / 2FA
- API key authentication
- Permission-first RBAC
- SQLAdmin admin paneli
- Redis-backed rate limiting
- S3/MinIO upload
- WebSocket tabanlı bildirim/gerçek zamanlı akışlar
- ARQ background worker
- Structured JSON logging
- Prometheus metrics
- Health probes ve production runtime access policy

## Proje Yapısı

Ana dizinler:

- `app/`: uygulama kodu
- `tests/`: unit, integration ve e2e testleri
- `alembic/`: migration dosyaları
- `docker/`: Dockerfile ve nginx config
- `scripts/`: operasyonel scriptler
- `docs/`: kullanıcı ve operasyon dokümantasyonu

Önemli uygulama modülleri:

- `app/main.py`: app factory, middleware, runtime surfaces
- `app/core/config.py`: tüm env tabanlı ayarlar
- `app/core/access.py`: docs/metrics/health access policy
- `app/api/v1/router.py`: canonical surface router kompozisyonu
- `app/admin/seed.py`: role ve seed akışları

## Canonical Surface Modeli

Tüm endpoint'ler üç surface altında yaşar:

- `client`
- `admin`
- `shared`

Örnekler:

- `/api/v1/client/auth/login`
- `/api/v1/admin/users`
- `/api/v1/shared/me`

Legacy route ailesi yeniden kullanılmamalıdır.

## Geliştirme Komutları

En sık kullanılan komutlar:

```bash
make dev
make stop
make logs
make migrate
make seed-roles
make seed
make make-admin email=admin@example.com
make test-fast
make lint
make typecheck
```

Detaylar için:

- [docs/getting-started.md](./docs/getting-started.md)
- [docs/contributing.md](./docs/contributing.md)

## Production Runtime Access Policy

Production'da şu env alanları operasyonel yüzeyleri kontrol eder:

- `DOCS_ACCESS_MODE`
- `METRICS_ACCESS_MODE`
- `HEALTH_DETAIL_ACCESS_MODE`
- `INTERNAL_ACCESS_TOKEN`

Desteklenen modlar:

- `public`
- `internal`
- `disabled`

Örnek internal docs erişimi:

```text
https://api.example.com/docs?access_token=<INTERNAL_ACCESS_TOKEN>
```

Örnek internal metrics erişimi:

```bash
curl -H "X-Internal-Access-Token: $INTERNAL_ACCESS_TOKEN" \
  https://api.example.com/metrics
```

## Bootstrap ve Seed Modeli

Yeni production-safe model:

- `SEED_SYSTEM_ROLES_ON_STARTUP`
- `SEED_DEFAULT_SUPERADMIN`
- `SEED_DEFAULT_APP_USER`

Önerilen kullanım:

- development: seed flag'leri açık olabilir
- production: default user seed kapalı olmalı
- first admin: `make make-admin` veya `scripts/make_admin.py`

## İlk Kez Gelenler İçin Önerilen Okuma Sırası

1. [docs/getting-started.md](./docs/getting-started.md)
2. [docs/configuration.md](./docs/configuration.md)
3. [docs/production.md](./docs/production.md)
4. [docs/operations.md](./docs/operations.md)
5. [docs/contributing.md](./docs/contributing.md)

## Troubleshooting

Kısa özet:

- `keys/private.pem` yoksa: `make keys`
- roller eksikse: `make seed-roles`
- varsayılan kullanıcı oluşmadıysa: `.env` seed flag'lerini kontrol edip `make seed`
- production'da `/docs` açılmıyorsa: bu beklenen davranış olabilir; `DOCS_ACCESS_MODE` ve `INTERNAL_ACCESS_TOKEN` kontrol edin

Detaylı runbook:

- [docs/operations.md](./docs/operations.md)

## Katkı

Katkı yapmadan önce:

- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [docs/contributing.md](./docs/contributing.md)
- [AGENTS.md](./AGENTS.md)

okuyun.
