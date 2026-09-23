import hashlib
import io
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.core.config import get_settings
from app.services.storage import (
    LocalDiskStorage,
    S3CompatibleStorage,
    StorageError,
    get_storage,
    reset_storage,
)
from app.services.uploads import (
    sanitize_filename,
    validate_upload,
    validate_upload_metadata,
)
from starlette.datastructures import UploadFile as StarletteUploadFile


def _create_upload_file(data: bytes, filename: str, content_type: str) -> StarletteUploadFile:
    file_obj = io.BytesIO(data)
    return StarletteUploadFile(
        file=file_obj,
        filename=filename,
        size=len(data),
        headers={"content-type": content_type},
    )


# 1. Filename sanitization & path traversal protection
def test_sanitize_filename_prevents_path_traversal() -> None:
    assert sanitize_filename("../../etc/passwd.mp4") == "passwd.mp4"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.wav") == "cmd.wav"
    assert sanitize_filename("../../../../secret.mp3") == "secret.mp3"
    assert sanitize_filename("normal_audio.wav") == "normal_audio.wav"
    assert sanitize_filename("spaced name & symbols #1.mp4") == "spaced_name_symbols_1.mp4"
    assert sanitize_filename("") == "upload.bin"
    assert sanitize_filename("...") == "media_upload"


# 2. Upload metadata validation: extensions, double extensions, MIME
def test_validate_upload_metadata_valid() -> None:
    for ext in [".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm", ".txt", ".md"]:
        clean = validate_upload_metadata(f"recording{ext}", "audio/wav")
        assert clean.endswith(ext)


def test_validate_upload_metadata_unsupported_extension() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        validate_upload_metadata("malicious.exe", "application/x-msdownload")

    with pytest.raises(ValueError, match="not allowed"):
        validate_upload_metadata("script.sh", "text/x-sh")


def test_validate_upload_metadata_double_extension() -> None:
    with pytest.raises(ValueError, match="Double extension"):
        validate_upload_metadata("audio.exe.mp3", "audio/mp3")

    with pytest.raises(ValueError, match="Double extension"):
        validate_upload_metadata("talk.js.wav", "audio/wav")


def test_validate_upload_metadata_invalid_mime() -> None:
    with pytest.raises(ValueError, match="MIME type"):
        validate_upload_metadata("valid_name.wav", "application/x-executable")


# 3. File size and empty file validation
def test_validate_upload_empty_file() -> None:
    with pytest.raises(ValueError, match="Empty file"):
        validate_upload("empty.wav", "audio/wav", 0)


def test_validate_upload_file_size_exceeded() -> None:
    settings = get_settings()
    excess_bytes = (settings.effective_max_upload_mb + 10) * 1024 * 1024
    with pytest.raises(ValueError, match="exceeds"):
        validate_upload("huge.mp4", "video/mp4", excess_bytes)


# 4. StorageAdapter key generation
def test_generate_key_deterministic_and_safe() -> None:
    storage = LocalDiskStorage()
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    e_id = uuid.uuid4()

    key_without_event = storage.generate_key(u_id, r_id, "../../unsafe.mp4")
    assert key_without_event == f"media/{u_id}/{r_id}/unsafe.mp4"

    key_with_event = storage.generate_key(u_id, r_id, "safe.wav", event_id=e_id)
    assert key_with_event == f"media/{u_id}/{e_id}/{r_id}/safe.wav"


# 5. LocalDiskStorage lifecycle (save_bytes, save_file, exists, delete)
def test_local_storage_lifecycle(tmp_path: Path) -> None:
    storage = LocalDiskStorage(media_root=str(tmp_path))
    content = b"Local audio bytes for testing"
    dest = "test/nested/recording.wav"

    uri = storage.save_bytes(content, dest)
    assert Path(uri).exists()
    assert storage.exists(uri) is True
    assert storage.exists("nonexistent.wav") is False

    # Save file copy
    source_file = tmp_path / "source.wav"
    source_file.write_bytes(b"copied source content")
    copied_uri = storage.save_file(str(source_file), "copied/recording.wav")
    assert storage.exists(copied_uri) is True

    # Delete
    assert storage.delete(uri) is True
    assert storage.exists(uri) is False


# 6. LocalDiskStorage streaming upload with SHA-256 calculation
@pytest.mark.asyncio
async def test_local_streaming_upload_sha256(tmp_path: Path) -> None:
    storage = LocalDiskStorage(media_root=str(tmp_path))
    content = b"Streaming audio chunk data 12345" * 100
    expected_sha256 = hashlib.sha256(content).hexdigest()

    upload_file = _create_upload_file(content, "stream_test.mp3", "audio/mpeg")
    result = await storage.stream_upload(
        file=upload_file,
        destination_key="streams/stream_test.mp3",
        max_bytes=10 * 1024 * 1024,
        chunk_size=1024,
        content_type="audio/mpeg",
    )

    assert result.storage_backend == "local"
    assert result.size_bytes == len(content)
    assert result.sha256 == expected_sha256
    assert Path(result.local_path).exists()
    assert Path(result.local_path).read_bytes() == content


# 7. LocalDiskStorage streaming upload: empty file and size limit
@pytest.mark.asyncio
async def test_local_streaming_upload_empty_rejected(tmp_path: Path) -> None:
    storage = LocalDiskStorage(media_root=str(tmp_path))
    upload_file = _create_upload_file(b"", "empty.wav", "audio/wav")

    with pytest.raises(ValueError, match="Empty file"):
        await storage.stream_upload(
            file=upload_file,
            destination_key="empty/test.wav",
            max_bytes=1024 * 1024,
            chunk_size=1024,
        )


@pytest.mark.asyncio
async def test_local_streaming_upload_size_limit_rejected(tmp_path: Path) -> None:
    storage = LocalDiskStorage(media_root=str(tmp_path))
    content = b"x" * 5000
    upload_file = _create_upload_file(content, "oversize.wav", "audio/wav")

    with pytest.raises(ValueError, match="exceeds maximum"):
        await storage.stream_upload(
            file=upload_file,
            destination_key="oversize/test.wav",
            max_bytes=2000,  # 2KB limit
            chunk_size=1024,
        )


# 8. S3CompatibleStorage using mocked boto3
def test_s3_compatible_storage_mocked_boto3(tmp_path: Path) -> None:
    with patch("boto3.client") as mock_boto_client:
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        storage = S3CompatibleStorage(
            endpoint_url="https://fake-account-id.r2.cloudflarestorage.com",
            access_key_id="fake_access_key",
            secret_access_key="fake_secret_key",
            bucket_name="test-bucket",
            backend_name="r2",
        )
        storage.local_cache = tmp_path

        # Test save_bytes
        data = b"S3 object payload"
        uri = storage.save_bytes(data, "cloud/file.mp4")
        assert uri == "s3://test-bucket/cloud/file.mp4"
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket", Key="cloud/file.mp4", Body=data
        )

        # Test exists
        mock_s3.head_object.return_value = {"ContentLength": len(data)}
        assert storage.exists("s3://test-bucket/cloud/file.mp4") is True
        mock_s3.head_object.assert_called_once_with(
            Bucket="test-bucket", Key="cloud/file.mp4"
        )

        # Test delete
        assert storage.delete("s3://test-bucket/cloud/file.mp4") is True
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="cloud/file.mp4"
        )


# 9. S3-compatible cloud failure -> local fallback
@pytest.mark.asyncio
async def test_s3_upload_cloud_failure_falls_back_to_local(tmp_path: Path) -> None:
    with patch("boto3.client") as mock_boto_client:
        mock_s3 = MagicMock()
        # Simulate cloud upload failure (e.g. Connection error or 403 Forbidden)
        mock_s3.upload_file.side_effect = Exception("AWS S3 Connection Timeout")
        mock_boto_client.return_value = mock_s3

        storage = S3CompatibleStorage(
            endpoint_url=None,  # AWS S3 standard
            access_key_id="fake_key",
            secret_access_key="fake_secret",
            bucket_name="my-event-bucket",
            backend_name="s3",
            fallback_enabled=True,
        )
        storage.local_cache = tmp_path

        content = b"Important event audio that must not be lost"
        upload_file = _create_upload_file(content, "event.wav", "audio/wav")

        result = await storage.stream_upload(
            file=upload_file,
            destination_key="recordings/event.wav",
            max_bytes=10 * 1024 * 1024,
            chunk_size=1024,
            content_type="audio/wav",
        )

        # Confirm fallback occurred
        assert result.storage_backend == "local_fallback"
        assert result.storage_uri.startswith(str(tmp_path))
        assert Path(result.local_path).exists()
        assert Path(result.local_path).read_bytes() == content


# 10. S3-compatible cloud failure raises StorageError when fallback disabled
@pytest.mark.asyncio
async def test_s3_upload_cloud_failure_raises_when_fallback_disabled(tmp_path: Path) -> None:
    with patch("boto3.client") as mock_boto_client:
        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = Exception("Cloud unreachable")
        mock_boto_client.return_value = mock_s3

        storage = S3CompatibleStorage(
            endpoint_url="http://localhost:9000",  # MinIO
            access_key_id="minioadmin",
            secret_access_key="minioadmin",
            bucket_name="minio-bucket",
            backend_name="minio",
            fallback_enabled=False,
        )
        storage.local_cache = tmp_path

        upload_file = _create_upload_file(b"Audio payload", "minio.wav", "audio/wav")

        with pytest.raises(StorageError, match="Cloud upload to minio failed"):
            await storage.stream_upload(
                file=upload_file,
                destination_key="minio/test.wav",
                max_bytes=1024 * 1024,
                chunk_size=1024,
            )


# 11. get_storage() fallback when credentials missing
def test_get_storage_fallback_on_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_storage()
    monkeypatch.setenv("STORAGE_BACKEND", "r2")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "")

    # Invalidate lru_cache for settings
    from app.core.config import get_settings
    get_settings.cache_clear()

    storage = get_storage()
    assert isinstance(storage, LocalDiskStorage)
    assert storage.name == "local"

    reset_storage()
    get_settings.cache_clear()
