# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- TOTP / 2FA support (`POST /api/v1/auth/totp/setup|verify|disable`)
- API Key authentication (`X-API-Key` header, `POST/GET/DELETE /api/v1/api-keys`)
- In-app notification system (`/api/v1/notifications`)
- Prometheus metrics endpoint (`/metrics`)
- Sentry error tracking integration
- Real health check endpoints with DB/Redis/Storage probes (`/health`, `/health/live`, `/health/ready`)
- `Makefile` with common dev commands
- GitHub Actions test CI workflow
- Dev Container support (`.devcontainer/`)
- Production Docker Compose override (`docker-compose.prod.yml`)
- Nginx reverse proxy configuration (`docker/nginx.conf`)
- HSTS, Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy security headers

### Changed
- `LoginRequest` now accepts optional `totp_code` field
- `get_current_user` dependency now accepts `X-API-Key` header in addition to Bearer token
- `/health` endpoint now checks real DB, Redis, and Storage connectivity

## [1.0.0] - 2026-03-01

### Added
- Initial release
- Email/password authentication with bcrypt + RS256 JWT
- Google and GitHub OAuth2 integration
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
