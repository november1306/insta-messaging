"""
Media Downloader Service for Instagram attachments.

Downloads media from Instagram CDN URLs and stores them locally.
Instagram media URLs expire after 7 days, so we download and cache immediately.
"""
import os
import logging
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)

# Maximum file size for media downloads (100 MB)
# Prevents excessive disk usage and potential abuse
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB in bytes


# MIME type to file extension mapping
MIME_TO_EXT = {
    # Images
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",

    # Videos
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
    "video/webm": ".webm",
    "video/3gpp": ".3gp",

    # Audio
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/aac": ".aac",
    "audio/amr": ".amr",
    "audio/wav": ".wav",

    # Documents
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/plain": ".txt",
}

# Default extensions by media type (fallback if MIME type is unknown)
DEFAULT_EXT_BY_TYPE = {
    "image": ".jpg",
    "video": ".mp4",
    "audio": ".mp3",
    "file": ".bin",
    "like_heart": "",  # No file for like hearts
}


@dataclass
class MediaFile:
    """
    Downloaded media file metadata.

    Attributes:
        local_path: Relative path to stored file (e.g., "media/page456/user123/mid_abc123_0.jpg")
        mime_type: Detected MIME type from HTTP response (e.g., "image/jpeg")
        extension: File extension including dot (e.g., ".jpg")
    """
    local_path: str
    mime_type: str
    extension: str


class MediaDownloader:
    """
    Service for downloading and storing Instagram media attachments.

    Downloads media from Instagram CDN URLs (which expire after 7 days) and
    stores them locally for permanent access. Supports images, videos, audio,
    and file attachments.
    """

    def __init__(self, base_dir: str = "media", timeout: float = 30.0):
        """
        Initialize MediaDownloader.

        Args:
            base_dir: Base directory for media storage (default: "media")
            timeout: HTTP request timeout in seconds (default: 30s)
        """
        self.base_dir = Path(base_dir)
        self.timeout = timeout

    async def download_media(
        self,
        instagram_url: str,
        message_id: str,
        attachment_index: int,
        media_type: str = "file"  # Fallback if MIME type unknown
    ) -> MediaFile:
        """
        Download media from Instagram URL and store locally.

        Args:
            instagram_url: Instagram CDN URL (expires in 7 days)
            message_id: Parent message ID (e.g., "mid_abc123")
            attachment_index: Attachment order (0, 1, 2...)
            media_type: Instagram media type ("image", "video", "audio", "file")

        Returns:
            MediaFile with local_path, mime_type, and extension

        Raises:
            httpx.HTTPError: If download fails
            ValueError: If file exceeds maximum size (100 MB)
            IOError: If file write fails
        """
        try:
            # Fetch media from Instagram URL
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Downloading media from Instagram: {instagram_url[:100]}...")
                response = await client.get(instagram_url, follow_redirects=True)
                response.raise_for_status()

                # Validate file size before processing
                content_length = len(response.content)
                if content_length > MAX_FILE_SIZE:
                    max_size_mb = MAX_FILE_SIZE / (1024 * 1024)
                    actual_size_mb = content_length / (1024 * 1024)
                    error_msg = (
                        f"File too large: {actual_size_mb:.1f} MB exceeds "
                        f"maximum allowed size of {max_size_mb:.0f} MB"
                    )
                    logger.error(f"❌ {error_msg}")
                    raise ValueError(error_msg)

                # Detect MIME type from Content-Type header
                content_type = response.headers.get("content-type", "application/octet-stream")
                # Strip charset if present (e.g., "image/jpeg; charset=utf-8" -> "image/jpeg")
                mime_type = content_type.split(";")[0].strip().lower()

                # Map MIME type to file extension
                extension = MIME_TO_EXT.get(mime_type)
                if not extension:
                    # Fallback to default extension for media type
                    extension = DEFAULT_EXT_BY_TYPE.get(media_type, ".bin")
                    logger.warning(
                        f"Unknown MIME type '{mime_type}' for media_type '{media_type}'. "
                        f"Using fallback extension: {extension}"
                    )

                # Generate local file path: media/attachments/{attachment_id}.{ext}
                # attachment_id format: {message_id}_{index} (e.g., mid_abc123_0)
                attachment_id = f"{message_id}_{attachment_index}"
                local_path = self._build_file_path(
                    attachment_id=attachment_id,
                    extension=extension
                )

                # Create directories if they don't exist
                local_path.parent.mkdir(parents=True, exist_ok=True)

                # Write media file to disk
                with open(local_path, "wb") as f:
                    f.write(response.content)

                # Get file size for logging
                file_size_kb = len(response.content) / 1024

                logger.info(
                    f"✅ Media downloaded successfully: {local_path} "
                    f"({file_size_kb:.1f} KB, {mime_type})"
                )

                # Return relative path (not absolute) for database storage
                relative_path = str(local_path.relative_to(self.base_dir.parent))

                return MediaFile(
                    local_path=relative_path.replace("\\", "/"),  # Normalize to forward slashes
                    mime_type=mime_type,
                    extension=extension
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error downloading media (status {e.response.status_code}): {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"❌ Network error downloading media: {e}")
            raise
        except IOError as e:
            logger.error(f"❌ File write error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error downloading media: {e}")
            raise

    def _build_file_path(
        self,
        attachment_id: str,
        extension: str
    ) -> Path:
        """
        Build local file path for media attachment.

        Path format: media/attachments/{attachment_id}{ext}
        Example: media/attachments/mid_abc123_0.jpg

        Args:
            attachment_id: Unique attachment identifier (message_id_index)
            extension: File extension including dot (e.g., ".jpg")

        Returns:
            Absolute Path object
        """
        filename = f"{attachment_id}{extension}"
        return self.base_dir / "attachments" / filename

    def get_media_url_for_frontend(self, media_url_local: Optional[str]) -> Optional[str]:
        """
        Convert local file path to frontend-accessible URL.

        Args:
            media_url_local: Local path like "media/page456/user123/mid_abc123_0.jpg"

        Returns:
            Frontend URL like "/media/page456/user123/mid_abc123_0.jpg" or None
        """
        if not media_url_local:
            return None

        # Ensure forward slashes and prepend "/"
        return "/" + media_url_local.replace("\\", "/")
