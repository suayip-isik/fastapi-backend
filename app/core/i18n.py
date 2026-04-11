"""
Internationalization (i18n) — çok dil desteği.
Accept-Language header'a göre Türkçe/İngilizce mesajlar döner.
"""

from __future__ import annotations

import contextlib
import json
from contextvars import ContextVar
from pathlib import Path

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"en", "tr"})
DEFAULT_LANGUAGE = "en"

# Request başına dil bilgisi tutan context variable
language_var: ContextVar[str] = ContextVar("language", default=DEFAULT_LANGUAGE)

# Startup'ta bir kez yüklenen çeviri dict'leri
_translations: dict[str, dict[str, str]] = {}


def _load_translations() -> None:
    i18n_dir = Path(__file__).parent.parent.parent / "i18n"
    for lang in SUPPORTED_LANGUAGES:
        path = i18n_dir / f"{lang}.json"
        if path.exists():
            with path.open(encoding="utf-8") as f:
                _translations[lang] = json.load(f)
        else:
            _translations[lang] = {}


_load_translations()


def t(key: str, lang: str | None = None, **kwargs: object) -> str:
    """Verilen key için çevrilmiş mesajı döndürür.

    Args:
        key: Çeviri anahtarı (ör. "error.auth.failed")
        lang: Dil kodu; None ise context var'dan okunur.
        **kwargs: Format değişkenleri (ör. count=5 → "{count}" yerine "5" gelir)

    Returns:
        Çevrilmiş string; key bulunamazsa key'in kendisi döner (safe fallback).
    """
    resolved = lang or language_var.get()
    catalog = _translations.get(resolved, {})
    message = catalog.get(key) or _translations.get(DEFAULT_LANGUAGE, {}).get(key) or key
    if kwargs:
        with contextlib.suppress(KeyError, ValueError):
            message = message.format_map(dict(kwargs))
    return message
