# Operations Runbook

Bu belge günlük operasyonlar ve incident anlarında hızlı uygulanacak komutları içerir.

## Health kontrolü

Public liveness:

```bash
curl https://api.example.com/health/live
```

Internal readiness:

```bash
curl -H "X-Internal-Access-Token: $INTERNAL_ACCESS_TOKEN" \
  https://api.example.com/health/ready
```

## Log inceleme

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f nginx
```

## Migration yönetimi

```bash
make migrate
make rollback
```

Production:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head
```

## Canonical role sync

Permission enum veya sistem rol seti değiştiyse:

```bash
make seed-roles
```

Production:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
  python -c "import asyncio; from app.admin.seed import seed_system_roles; asyncio.run(seed_system_roles())"
```

## Admin bootstrap / recovery

Yeni admin oluştur:

```bash
make make-admin create=1 email=admin@example.com password='StrongAdminPass123!'
```

Mevcut kullanıcıyı admin yap:

```bash
make make-admin email=admin@example.com
```

## Destructive reset

Lokal geliştirme için:

```bash
make reset-seed
```

Bu komut kullanıcı/rol verisini hard-delete eder. Production’da çalıştırılmamalıdır.

## Backup önerisi

PostgreSQL dump:

```bash
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-appdb}" > backup.sql
```

Geri yükleme:

```bash
cat backup.sql | docker compose exec -T db psql -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-appdb}"
```

Önerilen operasyon politikası:

- günlük DB backup
- düzenli restore testi
- object storage versioning
- log retention politikası

## Incident checklist

1. `health/live` yanıt veriyor mu kontrol et.
2. `api`, `worker`, `db`, `redis`, `nginx` loglarını ayır.
3. Son migration/deploy değişikliğini kontrol et.
4. Gerekirse `health/ready` ile dependency seviyesinde problemi ayrıştır.
5. Permission veya sistem rol problemi varsa `seed_system_roles` sync çalıştır.
