# Contributing Guide

Bu repo, backend geliştirmeyi kolaylaştırmak için API-first ve permission-first bir yapı izler. Yeni katkı yapacak geliştiriciler için temel akış aşağıdadır.

## Geliştirme akışı

1. Branch açın.
2. `.env.example` üzerinden lokal ortamı hazırlayın.
3. `make dev`, `make migrate` ile sistemi ayağa kaldırın.
4. Değişiklik öncesi ilgili testleri bulun veya ekleyin.
5. `make lint`, `make typecheck`, `make test-fast` çalıştırın.

## Permission / RBAC değişiklikleri

Yeni permission eklerken:

- `resource.action.scope` standardını kullanın
- role kontrolü yerine permission kontrolü yazın
- route access ile action access’i ayırın
- backend’i nihai otorite olarak bırakın

Tipik akış:

1. `app/core/permissions.py` içine yeni permission ekle
2. Gerekli sistem rol setlerini güncelle
3. Dependency/policy katmanını kullan
4. Endpoint/service testlerini ekle
5. Gerekirse `make seed-roles` ile canonical sync çalıştır

## Migration kuralları

- Şema değişikliği varsa Alembic migration yazın
- Localde migration’ı uygulayıp rollback yolunu düşünün
- Generic, her şeyi yapan tek update endpoint’lerinden kaçının

## Test beklentisi

En azından ilgili katmanda test ekleyin:

- unit
- integration
- gerekiyorsa e2e

Çalıştır:

```bash
make lint
make typecheck
make test-fast
```

## Dokümantasyon beklentisi

Davranış değiştiriyorsanız şu yüzeyleri güncelleyin:

- `README.md`
- ilgili `docs/*.md`
- `.env.example`

Özellikle production davranışı, seed akışı veya operational endpoint policy değişirse dokümantasyon zorunlu olarak güncellenmelidir.
