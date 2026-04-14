# Getting Started

Bu belge, repoyu fork/kopya aldıktan sonra projeyi lokal ortamda güvenli ve tekrarlanabilir şekilde ayağa kaldırmak için izlenecek canonical adımdır.

## 1. Ön Gereksinimler

- Docker Desktop veya Docker Engine + Compose plugin
- OpenSSL
- Git

İsteğe bağlı ama önerilen:

- `make`
- `jq`

## 2. Repoyu klonla

```bash
git clone <repo-url>
cd fastapi-backend
```

Fork üzerinden çalışıyorsanız:

```bash
git remote add upstream <original-repo-url>
git fetch upstream
```

## 3. Ortam dosyasını hazırla

```bash
make env
```

Bu komut `.env.example` dosyasını `.env` olarak kopyalar. İlk kurulum için aşağıdaki değerleri kontrol edin:

- `APP_ENV=development`
- `SEED_SYSTEM_ROLES_ON_STARTUP=true`
- `SEED_DEFAULT_SUPERADMIN=true`
- `SEED_DEFAULT_APP_USER=true`
- `DOCS_ACCESS_MODE=public`
- `METRICS_ACCESS_MODE=public`
- `HEALTH_DETAIL_ACCESS_MODE=public`

## 4. JWT key çiftini üret

```bash
make keys
```

Üretilen dosyalar:

- `keys/private.pem`
- `keys/public.pem`

Bu dosyalar commit edilmemelidir.

## 5. Servisleri başlat

```bash
make dev
```

Ardından migration uygula:

```bash
make migrate
```

## 6. Canonical role setini doğrula

Varsayılan geliştirme akışında `SEED_SYSTEM_ROLES_ON_STARTUP=true` olduğu için roller startup sırasında senkronize edilir. Manuel çalıştırmak isterseniz:

```bash
make seed-roles
```

## 7. Varsayılan kullanıcıları oluştur

Lokal geliştirmede `.env` içindeki seed flag’leri açıksa startup sırasında çalışırlar. Manuel olarak da tetikleyebilirsiniz:

```bash
make seed
```

Bu komut:

- varsayılan `panel_admin` kullanıcısını
- varsayılan `app_user` kullanıcısını

idempotent biçimde oluşturur.

## 8. Uygulamayı doğrula

Lokal geliştirme için beklenen adresler:

- API: `http://localhost:8000`
- Admin panel: `http://localhost:8000/admin`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Client schema docs: `http://localhost:8000/schema/client/docs`
- Admin schema docs: `http://localhost:8000/schema/admin/docs`
- Metrics: `http://localhost:8000/metrics`
- MinIO Console: `http://localhost:9001`

Sağlık kontrolleri:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

## 9. İlk admin hesabını yönet

Mevcut kullanıcıyı admin yapmak:

```bash
make make-admin email=admin@example.com
```

Yeni admin oluşturmak:

```bash
make make-admin create=1 email=admin@example.com password='StrongAdminPass123!'
```

Bu komutlar production bootstrap için de kullanılabilir.

## 10. Sık kullanılan komutlar

```bash
make logs
make test-fast
make lint
make typecheck
make dbshell
```

## 11. Sorun giderme

`keys/private.pem` bulunamadı:

- `make keys` çalıştırın.

Container’lar ayakta ama API cevap vermiyor:

- `make logs`
- `docker compose ps`
- `make migrate`

Varsayılan kullanıcı oluşmadı:

- `.env` içinde `SEED_DEFAULT_SUPERADMIN` veya `SEED_DEFAULT_APP_USER` değerlerini kontrol edin.
- Gerekirse `make seed` çalıştırın.

Rol/permission yüzeyi beklenen gibi değil:

- `make seed-roles` çalıştırın.

## 12. Sonraki belgeler

- Konfigürasyon referansı: [configuration.md](./configuration.md)
- Production kurulum rehberi: [production.md](./production.md)
- Operasyon runbook: [operations.md](./operations.md)
- Katkı rehberi: [contributing.md](./contributing.md)
