"""Helpers modülü unit testleri."""
from __future__ import annotations

import pytest
from app.utils.helpers import slugify, mask_email, paginate


def test_slugify_basic():
    assert slugify("Merhaba Dünya") == "merhaba-dunya"


def test_slugify_special_chars():
    assert slugify("Hello World!") == "hello-world"


def test_slugify_multiple_spaces():
    assert slugify("hello   world") == "hello-world"


def test_mask_email():
    assert mask_email("user@example.com") == "us**@example.com"


def test_mask_email_short_local():
    result = mask_email("ab@test.com")
    assert result.endswith("@test.com")


def test_paginate_first_page():
    items = list(range(50))
    result = paginate(items, page=1, size=10)
    assert result["items"] == list(range(10))
    assert result["total"] == 50
    assert result["pages"] == 5


def test_paginate_last_page():
    items = list(range(25))
    result = paginate(items, page=3, size=10)
    assert result["items"] == list(range(20, 25))
