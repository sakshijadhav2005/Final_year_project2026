from __future__ import annotations

import abc
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    from fastapi import UploadFile

logger = structlog.get_logger("storage")


class StorageError(Exception):
    """Raised when a storage operation fails."""
    pass


@dataclass
class StorageUploadResult:
    storage_uri: str
    storage_backend: str
    size_bytes: int
    sha256: str
    key: str
    local_path: str


class StorageAdapter(abc.ABC):
    """Abstract storage interface for event recordings across cloud and local providers."""

    name: str = "storage_adapter"

    @abc.abstractmethod
    def save_bytes(self, data: bytes, destination_name: str) -> str:
        """Saves bytes and returns storage URI/path."""
        pass

    @abc.abstractmethod
    def save_file(
        self, source_path: str, destination_name: str, content_type: str | None = None
    ) -> str:
        """Saves a local file into storage and returns storage URI."""
        pass

    @abc.abstractmethod
    async def stream_upload(
        self,
        file: UploadFile,
        destination_key: str,
        max_bytes: int,
        chunk_size: int = 5 * 1024 * 1024,
        content_type: str | None = None,
    ) -> StorageUploadResult:
        """Streams upload incrementally, computes SHA-256 and validates size."""
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

    @abc.abstractmethod
    def exists(self, storage_uri: str) -> bool:
        """Checks if the stored file exists."""
        pass

    def generate_key(
        self,
        user_id: UUID | str,
        recording_id: UUID | str,
        filename: str,
        event_id: UUID | str | None = None,
    ) -> str:
        """Generates a collision-safe, deterministic, sanitized storage key."""
        from app.services.uploads import sanitize_filename

        settings = get_settings()
        prefix = (getattr(settings, "media_storage_prefix", "media") or "media").strip("/")
        safe_name = sanitize_filename(filename)
        u_str = str(user_id)
        r_str = str(recording_id)
        if event_id:
            e_str = str(event_id)
            return f"{prefix}/{u_str}/{e_str}/{r_str}/{safe_name}"
        return f"{prefix}/{u_str}/{r_str}/{safe_name}"


# Backwards-compatible alias
StorageService = StorageAdapter


class LocalDiskStorage(StorageAdapter):
    """Stores media files on the local filesystem."""

    name: str = "local"

    def __init__(self, media_root: str | None = None) -> None:
        settings = get_settings()
        self.media_root = Path(media_root or settings.resolved_media_root)
        self.media_root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, data: bytes, destination_name: str) -> str:
        dest = self.media_root / destination_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def save_file(
        self, source_path: str, destination_name: str, content_type: str | None = None
    ) -> str:
        import shutil

        dest = self.media_root / destination_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)
        return str(dest)

    async def stream_upload(
        self,
        file: UploadFile,
        destination_key: str,
        max_bytes: int,
        chunk_size: int = 5 * 1024 * 1024,
        content_type: str | None = None,
    ) -> StorageUploadResult:
        dest_path = self.media_root / destination_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total_bytes = 0

        try:
            with open(dest_path, "wb") as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise ValueError(
                            f"File exceeds maximum allowed size of {max_bytes // (1024 * 1024)} MB"
                        )
                    hasher.update(chunk)
                    f.write(chunk)

            if total_bytes == 0:
                dest_path.unlink(missing_ok=True)
                raise ValueError("Empty file upload is not allowed")

            return StorageUploadResult(
                storage_uri=str(dest_path),
                storage_backend="local",
                size_bytes=total_bytes,
                sha256=hasher.hexdigest(),
                key=destination_key,
                local_path=str(dest_path),
            )
        except Exception:
            dest_path.unlink(missing_ok=True)
            raise

    def get_local_path(self, storage_uri: str) -> str:
        if not Path(storage_uri).is_absolute():
            return str(self.media_root / storage_uri)
        return storage_uri

    def get_access_url(self, storage_uri: str, expires_in: int = 3600) -> str:
        return f"/api/v1/media/{Path(storage_uri).name}"

    def delete(self, storage_uri: str) -> bool:
        try:
            path = Path(storage_uri)
            if not path.is_absolute():
                path = self.media_root / storage_uri
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
                return True
        except Exception as exc:
            logger.warning("local_storage_delete_failed", path=storage_uri, error=str(exc))
        return False

    def exists(self, storage_uri: str) -> bool:
        if storage_uri.startswith("s3://"):
            return False
        path = Path(storage_uri)
        if not path.is_absolute():
            path = self.media_root / storage_uri
        return path.exists() and path.is_file()


# Backwards-compatible alias
LocalStorageService = LocalDiskStorage


class S3CompatibleStorage(StorageAdapter):
    """Stores files in S3-compatible cloud object storage (Cloudflare R2, AWS S3, MinIO)
    with local disk fallback."""

    def __init__(
        self,
        endpoint_url: str | None,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region_name: str = "auto",
        public_domain: str = "",
        backend_name: str = "s3",
        fallback_enabled: bool = True,
    ) -> None:
        import boto3
        from botocore.config import Config

        self.bucket_name = bucket_name
        self.public_domain = public_domain.rstrip("/")
        self.backend_name = backend_name
        self.name = backend_name
        self.fallback_enabled = fallback_enabled
        self.local_cache = Path(get_settings().resolved_media_root)
        self.local_cache.mkdir(parents=True, exist_ok=True)

        # Standard AWS S3 requires endpoint_url=None
        normalized_endpoint = (
            endpoint_url.strip() if endpoint_url and endpoint_url.strip() else None
        )

        self.s3 = boto3.client(
            "s3",
            endpoint_url=normalized_endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )

    def _extract_key(self, storage_uri: str) -> str:
        if storage_uri.startswith(f"s3://{self.bucket_name}/"):
            return storage_uri.split(f"s3://{self.bucket_name}/")[-1]
        if storage_uri.startswith("s3://"):
            # strip s3://<bucket>/
            parts = storage_uri[5:].split("/", 1)
            return parts[1] if len(parts) > 1 else parts[0]
        return storage_uri

    def save_bytes(self, data: bytes, destination_name: str) -> str:
        local_dest = self.local_cache / destination_name
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        local_dest.write_bytes(data)

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=destination_name,
                Body=data,
            )
            logger.info(
                "cloud_upload_success",
                backend=self.backend_name,
                bucket=self.bucket_name,
                key=destination_name,
            )
            return f"s3://{self.bucket_name}/{destination_name}"
        except Exception as exc:
            logger.error(
                "cloud_upload_failed",
                backend=self.backend_name,
                bucket=self.bucket_name,
                key=destination_name,
                error=str(exc),
            )
            if self.fallback_enabled:
                logger.warning(
                    "storage_fallback_activated",
                    key=destination_name,
                    local_path=str(local_dest),
                )
                return str(local_dest)
            local_dest.unlink(missing_ok=True)
            raise StorageError(f"Cloud storage upload failed: {exc}") from exc

    def save_file(
        self, source_path: str, destination_name: str, content_type: str | None = None
    ) -> str:
        import shutil

        local_dest = self.local_cache / destination_name
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        if str(source_path) != str(local_dest):
            shutil.copy2(source_path, local_dest)

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self.s3.upload_file(
                Filename=str(local_dest),
                Bucket=self.bucket_name,
                Key=destination_name,
                ExtraArgs=extra_args if extra_args else None,
            )
            logger.info(
                "cloud_upload_success",
                backend=self.backend_name,
                bucket=self.bucket_name,
                key=destination_name,
            )
            return f"s3://{self.bucket_name}/{destination_name}"
        except Exception as exc:
            logger.error(
                "cloud_upload_failed",
                backend=self.backend_name,
                bucket=self.bucket_name,
                key=destination_name,
                error=str(exc),
            )
            if self.fallback_enabled:
                logger.warning(
                    "storage_fallback_activated",
                    key=destination_name,
                    local_path=str(local_dest),
                )
                return str(local_dest)
            local_dest.unlink(missing_ok=True)
            raise StorageError(f"Cloud upload failed: {exc}") from exc

    async def stream_upload(
        self,
        file: UploadFile,
        destination_key: str,
        max_bytes: int,
        chunk_size: int = 5 * 1024 * 1024,
        content_type: str | None = None,
    ) -> StorageUploadResult:
        local_dest = self.local_cache / destination_key
        local_dest.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total_bytes = 0

        try:
            with open(local_dest, "wb") as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise ValueError(
                            f"File exceeds maximum allowed size of {max_bytes // (1024 * 1024)} MB"
                        )
                    hasher.update(chunk)
                    f.write(chunk)

            if total_bytes == 0:
                local_dest.unlink(missing_ok=True)
                raise ValueError("Empty file upload is not allowed")

            sha256_hex = hasher.hexdigest()
        except Exception:
            local_dest.unlink(missing_ok=True)
            raise

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self.s3.upload_file(
                Filename=str(local_dest),
                Bucket=self.bucket_name,
                Key=destination_key,
                ExtraArgs=extra_args if extra_args else None,
            )
            logger.info(
                "cloud_upload_success",
                backend=self.backend_name,
                bucket=self.bucket_name,
                key=destination_key,
                size_bytes=total_bytes,
            )
            return StorageUploadResult(
                storage_uri=f"s3://{self.bucket_name}/{destination_key}",
                storage_backend=self.backend_name,
                size_bytes=total_bytes,
                sha256=sha256_hex,
                key=destination_key,
                local_path=str(local_dest),
            )
        except Exception as exc:
            logger.error(
                "cloud_upload_failed",
                backend=self.backend_name,
                bucket=self.bucket_name,
                key=destination_key,
                error=str(exc),
            )
            if self.fallback_enabled:
                logger.warning(
                    "storage_fallback_activated",
                    key=destination_key,
                    local_path=str(local_dest),
                )
                return StorageUploadResult(
                    storage_uri=str(local_dest),
                    storage_backend="local_fallback",
                    size_bytes=total_bytes,
                    sha256=sha256_hex,
                    key=destination_key,
                    local_path=str(local_dest),
                )
            local_dest.unlink(missing_ok=True)
            raise StorageError(
                f"Cloud upload to {self.backend_name} failed and local fallback is disabled: {exc}"
            ) from exc

    def get_local_path(self, storage_uri: str) -> str:
        if not storage_uri.startswith("s3://"):
            return storage_uri

        key = self._extract_key(storage_uri)
        local_dest = self.local_cache / key
        if local_dest.exists() and local_dest.stat().st_size > 0:
            return str(local_dest)

        local_dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.s3.download_file(self.bucket_name, key, str(local_dest))
            return str(local_dest)
        except Exception as exc:
            logger.error(
                "cloud_download_failed",
                backend=self.backend_name,
                key=key,
                error=str(exc),
            )
            return str(local_dest)

    def get_access_url(self, storage_uri: str, expires_in: int = 3600) -> str:
        key = self._extract_key(storage_uri)
        if self.public_domain and storage_uri.startswith("s3://"):
            return f"{self.public_domain}/{key}"

        if storage_uri.startswith("s3://"):
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
        key = self._extract_key(storage_uri)
        try:
            local_dest = self.local_cache / key
            if local_dest.exists():
                local_dest.unlink(missing_ok=True)
        except Exception:
            pass

        if storage_uri.startswith("s3://"):
            try:
                self.s3.delete_object(Bucket=self.bucket_name, Key=key)
                return True
            except Exception as exc:
                logger.error(
                    "cloud_delete_failed",
                    backend=self.backend_name,
                    key=key,
                    error=str(exc),
                )
                return False
        return True

    def exists(self, storage_uri: str) -> bool:
        if storage_uri.startswith("s3://"):
            key = self._extract_key(storage_uri)
            try:
                self.s3.head_object(Bucket=self.bucket_name, Key=key)
                return True
            except Exception:
                return False

        path = Path(storage_uri)
        if not path.is_absolute():
            path = self.local_cache / storage_uri
        return path.exists() and path.is_file()


# Backwards-compatible alias
S3CompatibleStorageService = S3CompatibleStorage

_storage_singleton: StorageAdapter | None = None


def reset_storage() -> None:
    """Resets the storage singleton instance (useful for unit tests)."""
    global _storage_singleton
    _storage_singleton = None


def get_storage() -> StorageAdapter:
    """Returns the configured storage adapter (Cloudflare R2, AWS S3, MinIO, or Local disk)."""
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton

    settings = get_settings()
    backend = (settings.storage_backend or "local").lower().strip()

    # Cloudflare R2
    if backend == "r2":
        access_key = settings.r2_access_key_id or settings.s3_access_key_id
        secret_key = settings.r2_secret_access_key or settings.s3_secret_access_key
        bucket = settings.r2_bucket_name or settings.resolved_s3_bucket

        if not access_key or not secret_key:
            logger.warning(
                "r2_credentials_missing_falling_back_to_local",
                backend="r2",
                reason="R2_ACCESS_KEY_ID or R2_SECRET_ACCESS_KEY not configured",
            )
            _storage_singleton = LocalDiskStorage(settings.resolved_media_root)
            return _storage_singleton

        endpoint = (
            settings.s3_endpoint_url
            if settings.s3_endpoint_url
            else f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
            if settings.r2_account_id
            else ""
        )

        try:
            _storage_singleton = S3CompatibleStorage(
                endpoint_url=endpoint,
                access_key_id=access_key,
                secret_access_key=secret_key,
                bucket_name=bucket,
                region_name="auto",
                public_domain=settings.r2_public_domain,
                backend_name="r2",
                fallback_enabled=settings.storage_fallback_to_local,
            )
            logger.info("storage_initialized", backend="cloudflare_r2", bucket=bucket)
            return _storage_singleton
        except Exception as exc:
            logger.error("r2_init_failed_falling_back_to_local", error=str(exc))
            _storage_singleton = LocalDiskStorage(settings.resolved_media_root)
            return _storage_singleton

    # AWS S3 or MinIO
    if backend in ("s3", "minio"):
        access_key = settings.s3_access_key_id
        secret_key = settings.s3_secret_access_key
        bucket = settings.resolved_s3_bucket

        if not access_key or not secret_key:
            logger.warning(
                "s3_credentials_missing_falling_back_to_local",
                backend=backend,
                reason="S3_ACCESS_KEY_ID or S3_SECRET_ACCESS_KEY not configured",
            )
            _storage_singleton = LocalDiskStorage(settings.resolved_media_root)
            return _storage_singleton

        try:
            _storage_singleton = S3CompatibleStorage(
                endpoint_url=settings.s3_endpoint_url,
                access_key_id=access_key,
                secret_access_key=secret_key,
                bucket_name=bucket,
                region_name=settings.s3_region or "auto",
                backend_name=backend,
                fallback_enabled=settings.storage_fallback_to_local,
            )
            logger.info("storage_initialized", backend=backend, bucket=bucket)
            return _storage_singleton
        except Exception as exc:
            logger.error(f"{backend}_init_failed_falling_back_to_local", error=str(exc))
            _storage_singleton = LocalDiskStorage(settings.resolved_media_root)
            return _storage_singleton

    # Default: Local Disk Storage
    _storage_singleton = LocalDiskStorage(settings.resolved_media_root)
    return _storage_singleton
