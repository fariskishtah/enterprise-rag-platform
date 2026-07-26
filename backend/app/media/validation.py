from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

from app.core.errors import UploadValidationError

ALLOWED_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".m4a",
    ".mp3",
    ".wav",
}

MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


def validate_media_filename(filename: str) -> tuple[str, str]:
    safe_name = Path(filename).name
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_MEDIA_EXTENSIONS:
        raise UploadValidationError(
            code="unsupported_media_type",
            message="Supported media types are MP4, MOV, MKV, WEBM, M4A, MP3, and WAV.",
            status_code=415,
        )
    return extension, MEDIA_TYPES[extension]


def is_youtube_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return hostname in {"youtube.com", "youtu.be", "m.youtube.com"}


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UploadValidationError(
            code="unsupported_url_scheme",
            message="Only public HTTP and HTTPS media URLs are supported.",
        )
    if parsed.username or parsed.password:
        raise UploadValidationError(
            code="url_credentials_rejected",
            message="Media URLs containing credentials are not allowed.",
        )
    hostname = parsed.hostname
    if not hostname:
        raise UploadValidationError(
            code="invalid_media_url",
            message="The media URL must include a valid public hostname.",
        )
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise UploadValidationError(
            code="media_host_unreachable",
            message="The media hostname could not be resolved.",
        ) from exc
    for address in addresses:
        value = ipaddress.ip_address(address)
        if any(
            (
                value.is_private,
                value.is_loopback,
                value.is_link_local,
                value.is_multicast,
                value.is_reserved,
                value.is_unspecified,
            )
        ):
            raise UploadValidationError(
                code="private_media_url",
                message="Private, local, reserved, and link-local media URLs are blocked.",
            )
    return url
