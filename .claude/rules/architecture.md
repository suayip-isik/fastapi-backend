---
paths:
  - "app/api/**/*.py"
  - "app/services/**/*.py"
  - "app/db/**/*.py"
---

# Katman Kuralları

## API Katmanı (app/api/)

- Endpoint fonksiyonları iş mantığı içermez — tüm iş service'e delege edilir
- `Depends()` sadece endpoint parametrelerinde kullanılır, service constructorlarında değil
- HTTP durum kodları ve response model dönüşümü endpoint'te kalır

## Service Katmanı (app/services/)

- Repository haricinde SQLAlchemy doğrudan çağrılmaz
- Servis bağımlılıkları constructor injection ile alınır (`__init__` parametresi), FastAPI `Depends()` değil
- Audit log kaydı `AuditableMixin._audit_log()` üzerinden yapılır

## Repository Katmanı (app/db/repositories/)

- SQLAlchemy sorguları yalnızca repository'de yazılır — service veya endpoint'te çağrılmaz
- Generic CRUD için `BaseRepository[T]` extend edilir
- Sayfalama için `get_page()` kullanılır (window function, tek sorguda items + total döner)
