from pathlib import Path

from app.services.storage import LocalStorageService, S3CompatibleStorageService, get_storage


def test_local_storage_lifecycle(tmp_path: Path) -> None:
    storage = LocalStorageService(media_root=str(tmp_path))
    data = b"test audio content for eventai"
    dest_name = "test_audio.wav"

    saved_uri = storage.save_bytes(data, dest_name)
    assert Path(saved_uri).exists()
    assert Path(saved_uri).read_bytes() == data

    local_path = storage.get_local_path(saved_uri)
    assert local_path == saved_uri

    access_url = storage.get_access_url(saved_uri)
    assert "test_audio.wav" in access_url

    deleted = storage.delete(saved_uri)
    assert deleted is True
    assert not Path(saved_uri).exists()


def test_get_storage_default_is_local() -> None:
    storage = get_storage()
    assert isinstance(storage, LocalStorageService | S3CompatibleStorageService)

