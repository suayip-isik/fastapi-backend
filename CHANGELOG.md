# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `POST /api/v1/users/{user_id}/activate` — deaktif kullanıcıyı yeniden aktif eder (Admin only)
- `PATCH /api/v1/users/{user_id}/role` — kullanıcı rolünü değiştirir; body: `{"role": "user"|"moderator"|"admin"}` (Admin only)
- `AuditAction.USER_ACTIVATED` enum değeri ve ilgili Alembic migration (`e1f7a2c94b06`)
- Self-action koruması: admin kendi hesabı üzerinde activate/deactivate/role-change yapamaz (HTTP 403)
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
- **OAuth CSRF protection** — state parameter (cryptographically random, Redis-backed TTL=600s) added to Google and GitHub OAuth flows; callbacks validate and consume state before processing
- **`send_welcome_email` task** — fully implemented with SMTP delivery via `send_email()`; previously a stub
- **`cleanup_expired_tokens` cron job** — scans Redis key prefixes (`blacklist:*`, `email_verify:*`, `password_reset:*`, `oauth_state:*`) and deletes orphaned keys (TTL=-1); runs nightly at midnight via ARQ cron
- **mypy pre-commit hook** — `mirrors-mypy v1.11.2` with strict mode added to `.pre-commit-config.yaml`
- **Test: `tests/unit/test_middleware.py`** — RequestIDMiddleware, TimingMiddleware, SecurityHeadersMiddleware coverage (9 tests)
- **Test: `tests/unit/test_repository_base.py`** — `BaseRepository.get_page()` window function pagination scenarios (7 tests)
- **Test: `tests/unit/test_health.py`** — `check_redis`, `check_storage` unit tests + degraded/503 endpoint scenarios (7 tests)
- **Test: `tests/integration/test_audit_log.py`** — `AuditableMixin._audit_log` call assertions for REGISTER, LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT, TOKEN_REFRESHED actions (7 tests)
- **Test: `tests/integration/test_admin.py`** — admin panel access control (unauthenticated redirect, login page, wrong credentials, mocked authenticated access) (5 tests)
- `OAUTH_STATE_KEY` constant in `app/services/_keys.py`

### Changed

- `DELETE /api/v1/users/{user_id}` artık self-action korumasına sahip (admin kendi hesabını deaktif edemez)
- `LoginRequest` now accepts optional `totp_code` field
- `get_current_user` dependency now accepts `X-API-Key` header in addition to Bearer token
- `/health` endpoint now checks real DB, Redis, and Storage connectivity
- `OAuthService.get_google_auth_url()` and `get_github_auth_url()` are now `async` (state generation requires Redis write)
- `OAuthService.google_callback()` and `github_callback()` now require `state: str` parameter for CSRF validation
- `google_login` and `github_login` endpoints now `await` the auth URL methods
- `google_callback` and `github_callback` endpoints now accept `state: str` query parameter
- `validate_production_settings()` now rejects weak `ADMIN_PASSWORD` values (`changeme`, `admin`, `password`, `123456`, empty) in production
- `tests/integration/test_oauth.py` updated: callback tests now include `state` query param and pre-seed `oauth_state:{state}` in FakeRedis; redirect tests verify `state=` in Location header; invalid state tests added (expect HTTP 401)
- `pyproject.toml`: added `TCH002`/`TCH003` to `tests/**/*.py` per-file-ignores (fixture type hints don't need `TYPE_CHECKING` guards)

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
