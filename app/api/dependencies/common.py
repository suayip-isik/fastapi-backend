"""
Yaygın kullanılan API dependency fonksiyonları.

Bu modül pagination, sorting ve filtreleme gibi yaygın kullanılan
dependency fonksiyonlarını içerir.
"""

from typing import Literal

from fastapi import Query


def get_pagination(
    skip: int = Query(0, ge=0, description="Atlanacak kayıt sayısı"),
    limit: int = Query(10, ge=1, le=100, description="Döndürülecek kayıt sayısı"),
) -> tuple[int, int]:
    """Sayfalama parametrelerini döner.

    Query parameter'lardan skip ve limit değerlerini alıp validation yapar.
    Maksimum limit 100 ile sınırlıdır.

    Args:
        skip: Atlanacak kayıt sayısı (offset). Varsayılan 0, minimum 0
        limit: Döndürülecek kayıt sayısı. Varsayılan 10, min 1, max 100

    Returns:
        (skip, limit) tuple olarak sayfalama parametreleri

    Example:
        >>> # GET /users?skip=20&limit=50
        >>> skip, limit = get_pagination(skip=20, limit=50)
        >>> # (20, 50)

    Note:
        - Limit maksimum 100 (DoS koruması)
        - Repository.list() metodu ile kullanılır
        - Veritabanı OFFSET ve LIMIT sorguları için kullanılır
    """
    return skip, limit


def get_sorting(
    sort_by: str = Query("created_at", description="Sıralama yapılacak alan"),
    order: Literal["asc", "desc"] = Query("desc", description="Sıralama yönü"),
) -> tuple[str, str]:
    """Sıralama parametrelerini döner.

    Query parameter'lardan sıralama alanı ve yönünü alır. Varsayılan olarak
    oluşturulma tarihine göre azalan sırada (desc) sıralar.

    Args:
        sort_by: Sıralama yapılacak alan adı. Varsayılan "created_at"
        order: Sıralama yönü ("asc" veya "desc"). Varsayılan "desc"

    Returns:
        (sort_by, order) tuple olarak sıralama parametreleri

    Example:
        >>> # GET /users?sort_by=email&order=asc
        >>> field, direction = get_sorting(sort_by="email", order="asc")
        >>> # ("email", "asc")

    Note:
        - order parametresi sadece "asc" veya "desc" değerlerini kabul eder
        - Güvenlik için sort_by değerinin repository katmanında whitelist ile kontrol edilmesi önerilir
        - Repository.list() metodunda order_by parametresi için kullanılır

    Raises:
        FastAPI otomatik olarak ValidationError fırlatır (422) eğer:
        - order değeri "asc" veya "desc" değilse
    """
    return sort_by, order


def get_search(
    q: str | None = Query(None, min_length=1, max_length=100, description="Arama terimi"),
) -> str | None:
    """Arama parametresini döner.

    Query parameter'dan arama terimini alır. Minimum 1, maksimum 100 karakter
    ile sınırlıdır. Boş string kontrolü yapar.

    Args:
        q: Arama terimi. Varsayılan None, min 1 karakter, max 100 karakter

    Returns:
        Arama terimi veya None

    Example:
        >>> # GET /users?q=john
        >>> search_term = get_search(q="john")
        >>> # "john"
        >>>
        >>> # GET /users
        >>> search_term = get_search()
        >>> # None

    Note:
        - Maksimum 100 karakter (SQL injection ve performans koruması)
        - Repository katmanında ILIKE veya full-text search ile kullanılır
        - None değeri filtreleme olmadığı anlamına gelir

    Raises:
        FastAPI otomatik olarak ValidationError fırlatır (422) eğer:
        - q değeri 1 karakterden kısa veya 100 karakterden uzunsa
    """
    return q.strip() if q else None
