from __future__ import annotations

import abc
import os
from pathlib import Path
from typing import BinaryIO

import structlog

from app.core.config import get_settings

logger = structlog.get_logger("storage")


class StorageService(abc.ABC):
    """Abstract storage interface for event recordings."""

    @abc.abstractmethod
    def save_bytes(self, data: bytes, destination_name: str) -> str:
        """Saves bytes and returns storage URI/path."""
        pass

    @abc.abstractmethod
    def get_local_path(self, storage_uri: str) -> str:
        """Returns a readable local file path (downloading if necessary)."""
        pass

    @abc.abstractmethod
    def get_access_url(self, storage_uri: str, expires_in: int = 3600) -> str:
        """Returns a URL to access/stream the media."""
        pass

    @abc.abstractmethod
    def delete(self, storage_uri: str) -> bool:
        """Deletes the stored file."""
        pass


class LocalStorageService(StorageService):
    """Stores files on the local filesystem / persistent volume."""

    def __init__(self, media_root: str | None = None) -> None:
        settings = get_settings()
        self.media_root = Path(media_root or settings.media_root)
        self.media_root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, data: bytes, destination_name: str) -> str:
        dest = self.media_root / destination_name
        dest.write_bytes(data)
        return str(dest)

    def get_local_path(self, storage_uri: str) -> str:
        return storage_uri

    def get_access_url(self, storage_uri: str, expires_in: int = 3600) -> str:
        # Local file path or relative URL
        return f"/api/v1/media/{Path(storage_uri).name}"

    def delete(self, storage_uri: str) -> bool:
        try:
            path = Path(storage_uri)
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
                return True
        except Exception as exc:
            logger.warning("local_storage_delete_failed", path=storage_uri, error=str(exc))
        return False


class S3CompatibleStorageService(StorageService):
    """Stores files in S3-compatible cloud object storage (Cloudflare R2, AWS S3, MinIO)."""

    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region_name: str = "auto",
        public_domain: str = "",
    ) -> None:
        import boto3
        from botocore.config import Config

        self.bucket_name = bucket_name
        self.public_domain = public_domain.rstrip("/")
        self.local_cache = Path(get_settings().media_root)
        self.local_cache.mkdir(parents=True, exist_ok=True)

        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )

    def save_bytes(self, data: bytes, destination_name: str) -> str:
        # Keep local copy for fast processing without re-downloading
        local_dest = self.local_cache / destination_name
        local_dest.write_bytes(data)

        # Upload to cloud bucket
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=destination_name,
                Body=data,
            )
            logger.info("cloud_upload_success", bucket=self.bucket_name, key=destination_name)
        except Exception as exc:
            logger.error("cloud_upload_failed", bucket=self.bucket_name, key=destination_name, error=str(exc))
            # Even if cloud upload fails, local copy is saved
            return str(local_dest)

        return f"s3://{self.bucket_name}/{destination_name}"

    def get_local_path(self, storage_uri: str) -> str:
        if not storage_uri.startswith("s3://"):
            return storage_uri

        # Extract key from s3://bucket/key
        key = storage_uri.split(f"s3://{self.bucket_name}/")[-1]
        local_dest = self.local_cache / key
        if local_dest.exists() and local_dest.stat().st_size > 0:
            return str(local_dest)

        # Download from cloud if not present in cache
        try:
            self.s3.download_file(self.bucket_name, key, str(local_dest))
            return str(local_dest)
        except Exception as exc:
            logger.error("cloud_download_failed", key=key, error=str(exc))
            return str(local_dest)

    def get_access_url(self, storage_uri: str, expires_in: int = 3600) -> str:
        if self.public_domain and storage_uri.startswith("s3://"):
            key = storage_uri.split(f"s3://{self.bucket_name}/")[-1]
            return f"{self.public_domain}/{key}"

        if storage_uri.startswith("s3://"):
            key = storage_uri.split(f"s3://{self.bucket_name}/")[-1]
            try:
                return self.s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in,
                )
            except Exception as exc:
                logger.warning("presigned_url_failed", error=str(exc))

        return storage_uri

    def delete(self, storage_uri: str) -> bool:
        key = storage_uri.split(f"s3://{self.bucket_name}/")[-1] if storage_uri.startswith("s3://") else storage_uri
        # Delete local cached copy
        try:
            local_dest = self.local_cache / key
            if local_dest.exists():
                local_dest.unlink(missing_ok=True)
        except Exception:
            pass

        # Delete from cloud
        if storage_uri.startswith("s3://"):
            try:
                self.s3.delete_object(Bucket=self.bucket_name, Key=key)
                return True
            except Exception as exc:
                logger.error("cloud_delete_failed", key=key, error=str(exc))
                return False
        return True


_storage_singleton: StorageService | None = None


def get_storage() -> StorageService:
    """Returns the configured storage service instance (Cloudflare R2, S3, or Local)."""
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton

    settings = get_settings()

    # Cloudflare R2
    if settings.storage_backend == "r2" and settings.r2_account_id and settings.r2_access_key_id:
        endpoint = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
        try:
            _storage_singleton = S3CompatibleStorageService(
                endpoint_url=endpoint,
                access_key_id=settings.r2_access_key_id,
                secret_access_key=settings.r2_secret_access_key,
                bucket_name=settings.r2_bucket_name,
                region_name="auto",
                public_domain=settings.r2_public_domain,
            )
            logger.info("storage_initialized", backend="cloudflare_r2", bucket=settings.r2_bucket_name)
            return _storage_singleton
        except Exception as exc:
            logger.error("r2_init_failed_falling_back_to_local", error=str(exc))

    # Generic S3 (AWS S3 or MinIO)
    elif settings.storage_backend == "s3" and settings.s3_access_key_id:
        try:
            _storage_singleton = S3CompatibleStorageService(
                endpoint_url=settings.s3_endpoint_url,
                access_key_id=settings.s3_access_key_id,
                secret_access_key=settings.s3_secret_access_key,
                bucket_name=settings.s3_bucket_name,
                region_name=settings.s3_region or "auto",
            )
            logger.info("storage_initialized", backend="s3_compatible", bucket=settings.s3_bucket_name)
            return _storage_singleton
        except Exception as exc:
            logger.error("s3_init_failed_falling_back_to_local", error=str(exc))

    # Default: Local storage
    _storage_singleton = LocalStorageService(settings.media_root)
    return _storage_singleton
