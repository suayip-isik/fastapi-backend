"""Dosya depolama abstraction katmanı."""

from app.storage.backends import S3StorageBackend, StorageBackend

__all__ = ["StorageBackend", "S3StorageBackend"]
