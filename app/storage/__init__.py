"""Dosya depolama abstraction katmanı."""
from app.storage.backends import storage, StorageBackend, S3StorageBackend

__all__ = ["storage", "StorageBackend", "S3StorageBackend"]
