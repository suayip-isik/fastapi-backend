"""Helpers modülü unit testleri."""

from __future__ import annotations

from app.utils.helpers import mask_email, paginate, slugify


def test_slugify_basic():
    """test_slugify_basic senaryosunu test eder."""
    assert slugify("Merhaba Dünya") == "merhaba-dunya"


def test_slugify_special_chars():
    """test_slugify_special_chars senaryosunu test eder."""
    assert slugify("Hello World!") == "hello-world"


def test_slugify_multiple_spaces():
    """test_slugify_multiple_spaces senaryosunu test eder."""
    assert slugify("hello   world") == "hello-world"


def test_mask_email():
    """test_mask_email senaryosunu test eder."""
    assert mask_email("user@example.com") == "us**@example.com"


def test_mask_email_short_local():
    """test_mask_email_short_local senaryosunu test eder."""
    result = mask_email("ab@test.com")
    assert result.endswith("@test.com")


def test_paginate_first_page():
    """test_paginate_first_page senaryosunu test eder."""
    items = list(range(50))
    result = paginate(items, page=1, size=10)
    assert result["items"] == list(range(10))
    assert result["total"] == 50
    assert result["pages"] == 5


def test_paginate_last_page():
    """test_paginate_last_page senaryosunu test eder."""
    items = list(range(25))
    result = paginate(items, page=3, size=10)
    assert result["items"] == list(range(20, 25))
