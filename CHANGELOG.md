# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `surface` tabanlı actor ayrımı (`client`, `admin`)
- Canonical API surface modeli:
  - `/api/v1/client/*`
  - `/api/v1/admin/*`
  - `/api/v1/shared/*`
- Consumer-specific OpenAPI kaynakları:
  - `/schema/client/openapi.json`
  - `/schema/admin/openapi.json`
- Admin panel erişimi için `admin:panel_access`
- Admin kullanıcı oluşturma ve davet akışı:
  - `POST /api/v1/admin/users`
  - `POST /api/v1/admin/users/{user_id}/resend-invite`
- Yeni permission: `users:create_admin`
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

- Web ve mobil istemciler artık tek `client` surface üzerinden çalışır
- Sistem roller `panel_admin` ve `app_user` olarak yenilendi; `moderator` sistem rolü kaldırıldı
- `POST /api/v1/client/auth/register` ile açılan tüm `surface=client` kullanıcılar varsayılan olarak `app_user` rolü alır
- Varsayılan seed kullanıcıları artık `superadmin@example.com` (`panel_admin`) ve `suayip@example.com` (`app_user`) olarak oluşturulur
- Yeni operasyonel reset komutu ile kullanıcı, rol ve bağlı veriler hard delete edilip canonical seed baştan kurulabilir
- Admin panel ve admin API erişimi yalnız `surface=admin` kullanıcılar için geçerlidir
- SQLAdmin auth artık `admin:panel_access` gerektirir; `admin:access` compatibility fallback'i kaldırıldı
- Client kullanıcı oluşturma artık yalnız self-register akışıyla yapılır: `/api/v1/client/auth/register`
- Admin kullanıcı oluşturma yalnız admin surface altında yapılır ve şifre doğrudan atanmaz
- Admin davet e-postası mevcut `reset-password` ekranını yeniden kullanır
- Davet edilen admin kullanıcı ilk şifresini kurduğunda `is_verified=true` olur
- Shared upload “delete any file” yetkisi artık `surface=admin` + `admin:panel_access` gerektirir
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
- User management with roles (ADMIN, USER, MODERATOR)
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
