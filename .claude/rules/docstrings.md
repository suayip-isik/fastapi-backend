---
paths:
  - "app/**/*.py"
  - "tests/**/*.py"
  - "alembic/**/*.py"
---

# Docstring Kuralları

Tek kriter: OpenAPI spec'e katkı sağlıyor mu, yoksa kodun söylediklerini tekrar mı ediyor?

## Zorunlu

- Route/endpoint fonksiyonları: her endpoint'te docstring yaz — FastAPI bunu Swagger UI'da description olarak gösterir
- Pydantic model sınıfları: class docstring yaz; her alan için `Field(description=...)` kullan
- Service metodları: kural, yetki kontrolü veya birden fazla adım içeriyorsa docstring yaz
- Custom exception sınıfları: ne zaman fırlatıldığını tek cümlede açıkla
- Paylaşılan utility fonksiyonları: parametreler veya dönüş değeri tip imzasından anlaşılmıyorsa belge

## Yasak

- Fonksiyon adının zaten söylediği her şeyi tekrar etme
- Basit CRUD repository metodlarına docstring yazma
- `__init__` metodlarına docstring yazma
- Dependency fonksiyonlarına docstring yazma — tip imzası yeterli

## Temel İlke

Kodu tekrar eden her docstring teknik borçtur — silinmelidir.
