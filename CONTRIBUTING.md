# Contributing Guide

Bu belge, repoya katkı yaparken izlenecek kısa ve canonical akıştır. Daha detaylı contributor rehberi için [docs/contributing.md](./docs/contributing.md) dosyasına bakın.

## Kurulum

```bash
git clone <repo-url>
cd fastapi-backend

make env
make keys
make dev
make migrate
make seed-roles
```

Varsayılan geliştirme kullanıcılarını oluşturmak isterseniz:

```bash
make seed
```

## Geliştirme Akışı

1. Branch açın.
2. İlgili kodu değiştirin.
3. Gerekli testleri ekleyin veya güncelleyin.
4. Aşağıdaki kontrolleri çalıştırın:

```bash
make lint
make typecheck
make test-fast
```

5. Etkilenen dokümantasyonu aynı PR içinde güncelleyin.

## Mimari Kurallar

- Endpoint içinde business logic yazmayın.
- Service katmanında doğrudan FastAPI `Depends()` kullanmayın.
- Service veya endpoint içinde doğrudan dağınık SQLAlchemy erişimi yapmayın; repository/gateway katmanını kullanın.
- Authorization için permission-first helper/policy yapısını kullanın.
- Yeni route'lar sadece canonical surface modeli altında olmalı:
  - `client`
  - `admin`
  - `shared`

## RBAC / Permission Kuralları

- Permission adları `resource.action.scope` standardında olmalı.
- Role adına göre inline kontrol yazmayın.
- Admin-only erişim hem permission hem `surface=admin` ile korunmalı.
- Yeni permission veya role seti eklerseniz:
  - `app/core/permissions.py`
  - ilgili seed/role setleri
  - testler
  - dokümantasyon

Rol/permisson değişikliğinden sonra canonical sync:

```bash
make seed-roles
```

## Yeni Özellik Eklerken

Tipik sıra:

1. Model
2. Migration
3. Repository
4. Service
5. Schema
6. Endpoint
7. Router kaydı
8. Tests
9. Docs

## Dokümantasyon Zorunluluğu

Şu yüzeylerden herhangi biri değişirse markdown dokümanları da güncellenmelidir:

- setup akışı
- env alanları
- runtime access policy
- seed/bootstrap akışı
- prod deploy davranışı
- developer workflow

Kontrol edilmesi gereken temel dosyalar:

- `README.md`
- `docs/*.md`
- `CHANGELOG.md`
- gerekiyorsa `CLAUDE.md` ve `AGENTS.md`

## Commit Mesajları

Conventional Commits kullanın:

```text
feat: add runtime access policy docs
fix: correct nginx auth route pattern
docs: update onboarding guides
test: add runtime surface access coverage
```
