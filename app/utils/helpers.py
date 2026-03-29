"""Genel yardımcı fonksiyonlar."""

from __future__ import annotations

import re
import unicodedata
from typing import TypeVar

T = TypeVar("T")


def paginate(items: list[T], page: int, size: int) -> dict[str, object]:
    """Liste verilerini sayfalara böler."""
    total = len(items)
    start = (page - 1) * size
    end = start + size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
    }


def slugify(text: str) -> str:
    """Metni URL-uyumlu slug'a çevirir. Örn: 'Merhaba Dünya' → 'merhaba-dunya'"""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def mask_email(email: str) -> str:
    """E-postayı maskeler. Örn: 'user@example.com' → 'us**@example.com'"""
    local, domain = email.split("@", 1)
    masked = local[:2] + "*" * max(len(local) - 2, 2)
    return f"{masked}@{domain}"
