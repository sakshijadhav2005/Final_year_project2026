"""VideoDB cloud media service adapter.

Encapsulates VideoDB connection, media ingestion, speech-to-text generation,
speaker diarization extraction, and optional scene indexing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger("videodb")


class VideoDBError(Exception):
    """Base exception for all VideoDB service and provider errors."""


class VideoDBConfigurationError(VideoDBError):
    """Raised when required VideoDB credentials or settings are missing."""


class VideoDBUploadError(VideoDBError):
    """Raised when uploading media to VideoDB fails."""


class VideoDBTranscriptionError(VideoDBError):
    """Raised when generating or retrieving a transcript from VideoDB fails."""


class VideoDBResponseError(VideoDBError):
    """Raised when VideoDB returns a malformed or invalid response payload."""


class VideoDBClient:
    """Client wrapper for interacting with the VideoDB Python SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        collection: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._collection = collection

    @property
    def api_key(self) -> str:
        return self._api_key or get_settings().videodb_api_key

    @property
    def collection_id(self) -> str:
        return self._collection or get_settings().videodb_collection

    def connect(self) -> Any:
        """Connects to the VideoDB service using the configured API key."""
        key = self.api_key
        if not key or not key.strip():
            raise VideoDBConfigurationError(
                "VideoDB API key is not configured. Set the VIDEODB_API_KEY environment variable."
            )

        try:
            import videodb
        except ImportError as exc:
            raise VideoDBError(
                "The 'videodb' package is not installed. Install it with: pip install videodb"
            ) from exc

        try:
            return videodb.connect(api_key=key)
        except Exception as exc:
            logger.error("videodb_connect_failed", error=str(exc))
            raise VideoDBError(f"Failed to connect to VideoDB: {exc}") from exc

    def get_collection(self, conn: Any = None) -> Any:
        """Resolves the configured VideoDB collection, falling back to default."""
        if conn is None:
            conn = self.connect()

        target_coll = self.collection_id
        if target_coll:
            try:
                return conn.get_collection(target_coll)
            except TypeError:
                try:
                    return conn.get_collection(collection_id=target_coll)
                except Exception as exc:
                    logger.warning("videodb_get_named_collection_failed", error=str(exc))
            except Exception as exc:
                logger.warning("videodb_get_named_collection_failed", error=str(exc))

        try:
            return conn.get_collection()
        except Exception as exc:
            logger.error("videodb_get_default_collection_failed", error=str(exc))
            raise VideoDBError(f"Failed to resolve VideoDB collection: {exc}") from exc

    def upload_media(self, file_path: str, collection: Any = None) -> Any:
        """Uploads a media file to the target VideoDB collection."""
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        coll = collection or self.get_collection()
        try:
            media = coll.upload(file_path=str(path_obj))
            logger.info("videodb_media_uploaded", media_id=getattr(media, "id", None))
            return media
        except Exception as exc:
            logger.error("videodb_upload_failed", path=file_path, error=str(exc))
            raise VideoDBUploadError(f"Failed to upload media to VideoDB: {exc}") from exc

    def generate_transcript(self, media: Any, language_code: str = "en") -> None:
        """Triggers asynchronous or synchronous speech-to-text generation on VideoDB."""
        if hasattr(media, "generate_transcript"):
            try:
                media.generate_transcript()
            except TypeError:
                try:
                    media.generate_transcript(language_code=language_code)
                except Exception as exc:
                    logger.error("videodb_generate_transcript_failed", error=str(exc))
                    raise VideoDBTranscriptionError(
                        f"VideoDB generate_transcript failed: {exc}"
                    ) from exc
            except Exception as exc:
                logger.error("videodb_generate_transcript_failed", error=str(exc))
                raise VideoDBTranscriptionError(
                    f"VideoDB generate_transcript failed: {exc}"
                ) from exc
        elif hasattr(media, "index_spoken_words"):
            try:
                media.index_spoken_words()
            except Exception as exc:
                logger.error("videodb_index_spoken_words_failed", error=str(exc))
                raise VideoDBTranscriptionError(
                    f"VideoDB index_spoken_words failed: {exc}"
                ) from exc

    def get_transcript(self, media: Any) -> tuple[str, Any]:
        """Fetches the generated transcript text and structured segment payload."""
        text = ""
        raw_payload: Any = None

        if hasattr(media, "get_transcript_text"):
            try:
                text = media.get_transcript_text() or ""
            except Exception as exc:
                logger.warning("videodb_get_transcript_text_failed", error=str(exc))

        if hasattr(media, "get_transcript"):
            try:
                raw_payload = media.get_transcript()
            except Exception as exc:
                logger.warning("videodb_get_transcript_payload_failed", error=str(exc))

        # Fallback to understand analyzer API if available
        if not text and hasattr(media, "understand"):
            try:
                understanding = media.understand(
                    analyzers=[{"type": "spoken_words", "name": "transcript"}]
                )
                if hasattr(understanding, "wait_until_complete"):
                    understanding.wait_until_complete()
                analyzer = (
                    understanding.get_analyzer("transcript")
                    if hasattr(understanding, "get_analyzer")
                    else None
                )
                for attr in ("text", "transcript", "content"):
                    val = getattr(analyzer, attr, None) if analyzer is not None else None
                    if isinstance(val, str) and val.strip():
                        text = val.strip()
                        break
            except Exception as exc:
                logger.warning("videodb_understand_failed", error=str(exc))

        return text, raw_payload

    def index_scenes(self, media: Any) -> list[dict[str, Any]]:
        """Indexes visual video scenes if supported by the media object."""
        scenes: list[dict[str, Any]] = []
        if hasattr(media, "index_scenes"):
            try:
                media.index_scenes()
            except Exception as exc:
                logger.debug("videodb_index_scenes_skipped", error=str(exc))

        if hasattr(media, "get_scenes"):
            try:
                raw_scenes = media.get_scenes()
                if isinstance(raw_scenes, list):
                    for item in raw_scenes:
                        if isinstance(item, dict):
                            scenes.append(item)
                        elif hasattr(item, "as_dict"):
                            scenes.append(item.as_dict())
                        elif hasattr(item, "__dict__"):
                            scenes.append(dict(item.__dict__))
            except Exception as exc:
                logger.debug("videodb_get_scenes_failed", error=str(exc))

        return scenes


def get_videodb_client(
    api_key: str | None = None,
    collection: str | None = None,
) -> VideoDBClient:
    """Factory helper to create a configured VideoDBClient."""
    return VideoDBClient(api_key=api_key, collection=collection)
