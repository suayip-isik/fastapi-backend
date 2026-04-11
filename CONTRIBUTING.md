# Contributing Guide

## Setup

```bash
git clone <repo>
cd fastapi-backend
cp .env.example .env     # Edit values
make keys                # Generate JWT RSA keys
make dev                 # Start Docker services
make migrate             # Apply DB migrations
```

## Development Workflow

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Make changes
3. Run tests: `make test`
4. Lint + type check: `make check`
5. Open a pull request to `dev`

## Adding a New Feature

Follow the layered architecture defined in `CLAUDE.md`:

1. **Model** → `app/db/models/` (extend `BaseModel`)
2. **Migration** → `make migration msg="add my_table"` then `make migrate`
3. **Repository** → `app/db/repositories/` (extend `BaseRepository[Model]`)
4. **Service** → `app/services/` (business logic only, inject repository)
5. **Schema** → `app/schemas/` (Pydantic request/response models)
6. **Endpoint** → `app/api/v1/endpoints/` (thin handlers, delegate to service)
7. **Surface seçimi** → Yeni endpoint yalnız bir canonical surface altında yaşamalı:
   - `client`
   - `admin`
   - `shared`
8. **Router** → Register in `app/api/v1/router.py`
9. **Docs** → README/CHANGELOG ve etkilenen diğer referans dokümanlar (`LEARNING_ROADMAP.md`, `.env.example` vb.) aynı PR'da güncellenmeli
10. **Tests** → `tests/integration/test_myfeature.py`

## Code Standards

- All code must pass `mypy app/` in strict mode
- All code must pass `ruff check app/`
- Test coverage must remain ≥ 80%
- No direct SQLAlchemy calls from services or endpoints — use repositories
- No business logic in endpoints — delegate to services
- Policy-first authorization: inline `surface` / permission kombinasyonları yazmak yerine ortak policy/dependency helper'ları kullan
- Global `AsyncSessionFactory` import'u service/policy katmanına sızdırma; request dışı DB erişimini provider/gateway arkasına al
- Admin-only erişim yalnız permission ile değil, `surface=admin` kuralıyla da korunmalı
- Security-sensitive failure'larda varsayılan davranış `deny`; side-effect servislerinde `log + degrade`
- Legacy route eklenmez; yalnız canonical `client/admin/shared` path'leri kullanılır

## Testing

```bash
make test          # Full suite with coverage
make test-fast     # Quick run, no coverage
make test-k k=test_login   # Run by name pattern
make test-file f=tests/integration/test_auth.py
```

Test fixtures are in `tests/conftest.py`:

- `client` — async httpx client with DB override
- `db_session` — fresh DB session per test
- `fake_redis` — fakeredis (no real Redis needed)
- `mock_enqueue` — ARQ tasks are mocked

Resmi codegen kaynakları:

- `/schema/client/openapi.json`
- `/schema/admin/openapi.json`

## Environment Variables

Copy `.env.example` to `.env`. All variables are documented there.
Never commit `.env` or `keys/` to version control.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add TOTP support
fix: resolve token expiry edge case
refactor: extract email validation to helper
test: add API key auth integration tests
docs: update CHANGELOG
```
