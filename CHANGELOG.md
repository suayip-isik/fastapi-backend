# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Runtime access policy dokümantasyonu ve testleri:
  - `DOCS_ACCESS_MODE`
  - `METRICS_ACCESS_MODE`
  - `HEALTH_DETAIL_ACCESS_MODE`
  - `INTERNAL_ACCESS_TOKEN`
- Yeni bootstrap ve operasyon komutları:
  - `make seed-roles`
  - `make make-admin`
- Başlangıç, konfigürasyon, production ve operasyon belgeleri:
  - `docs/getting-started.md`
  - `docs/configuration.md`
  - `docs/production.md`
  - `docs/operations.md`
  - `docs/contributing.md`
- `surface` tabanlı actor ayrımı (`client`, `admin`)
- Canonical API surface modeli:
  - `/api/v1/client/*`
  - `/api/v1/admin/*`
  - `/api/v1/shared/*`
- Consumer-specific OpenAPI kaynakları:
  - `/schema/client/openapi.json`
  - `/schema/admin/openapi.json`
- Admin panel erişimi için admin-surface permission doğrulaması
- Admin kullanıcı oluşturma ve davet akışı:
  - `POST /api/v1/admin/users`
  - `POST /api/v1/admin/users/{user_id}/resend-invite`
- Yeni permission: `users.create.admin`
- Yeni worker görevi: `send_admin_invite_email`
- Admin daveti için yeni audit action'lar:
  - `admin_user_created`
  - `admin_invite_resent`
- Admin invite permission/audit backfill migration'ı
- Surface ve legacy removal regression testleri
- Merkezi authorization policy helper'ları
- Permission provider/cache/query ayrımı
- Session provider abstraction (`AsyncSessionFactory` doğrudan servis katmanına sızmıyor)

### Changed

- Production runtime surfaces artık policy kontrollüdür:
  - `/docs`
  - `/redoc`
  - `/schema/*`
  - `/metrics`
  - `/health`
  - `/health/ready`
- Trusted host enforcement aktif hale getirildi
- Admin session cookie ayarları explicit config alanlarına taşındı
- Startup seed davranışı flag kontrollü hale getirildi
- Default user/admin seed'leri production startup'ında önerilmeyen davranış olarak ayrıldı
- Nginx auth rate-limit path'leri canonical route yapısına göre düzeltildi
- Production compose örneği tek-host kullanım için netleştirildi
- README ve tüm ana markdown belgeleri yeni kullanıcı onboarding akışına göre yeniden düzenlendi
- `role_permissions.permission` artık canonical RBAC sözlüğünü PostgreSQL enum + app guard ile zorunlu kılar
- Web ve mobil istemciler artık tek `client` surface üzerinden çalışır
- Sistem roller `panel_admin` ve `app_user` olarak yenilendi; `moderator` sistem rolü kaldırıldı
- `POST /api/v1/client/auth/register` ile açılan tüm `surface=client` kullanıcılar varsayılan olarak `app_user` rolü alır
- Varsayılan seed kullanıcıları artık `superadmin@example.com` (`panel_admin`) ve `suayip@example.com` (`app_user`) olarak oluşturulur
- Yeni operasyonel reset komutu ile kullanıcı, rol ve bağlı veriler hard delete edilip canonical seed baştan kurulabilir
- Admin panel ve admin API erişimi yalnız `surface=admin` kullanıcılar için geçerlidir
- SQLAdmin auth artık `surface=admin` + admin-surface permission seti gerektirir; `admin:access` compatibility fallback'i kaldırıldı
- Client kullanıcı oluşturma artık yalnız self-register akışıyla yapılır: `/api/v1/client/auth/register`
- Admin kullanıcı oluşturma yalnız admin surface altında yapılır ve şifre doğrudan atanmaz
- Admin davet e-postası mevcut `reset-password` ekranını yeniden kullanır
- Davet edilen admin kullanıcı ilk şifresini kurduğunda `is_verified=true` olur
- Shared upload “delete any file” yetkisi artık `surface=admin` + `uploads.delete.any` gerektirir
- Admin auth, permission çözümleme ve audit servisleri daha düşük coupling ile injectable provider/gateway sınırlarına taşındı
- Email/worker/websocket exception boundary'leri daraltıldı
- Dokümantasyon canonical surface modeliyle eşitlendi

### Removed

- Legacy route ailesi:
  - `/api/v1/auth/*`
  - `/api/v1/users/*`
  - root-level alias admin/shared endpoint'leri
- Legacy schema alias'ları:
  - `/schema/user/*`
  - `/schema/mobile/*`
- Legacy deprecation middleware
- `admin:access` compatibility fallback'i

## [1.0.0] - 2026-03-01

### Added

- Initial release
- Email/password authentication with bcrypt + RS256 JWT
- User management with role-based access control
- File uploads via S3/MinIO with validation
- WebSocket room-based messaging
- ARQ background task queue (email, file processing)
- Redis-backed rate limiting (slowapi)
- SQLAdmin panel
- Structured JSON logging (structlog)
- Audit logging for all auth and user actions
- Repository pattern with generic BaseRepository
- Layered architecture: API → Service → Repository
- Docker Compose development environment
- pytest integration tests with 80% coverage threshold
- GitHub Actions lint + type check CI
