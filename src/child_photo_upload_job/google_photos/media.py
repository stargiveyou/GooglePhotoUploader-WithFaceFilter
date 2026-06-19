"""업로드 대상 미디어 파일 탐색과 MIME 추정.

google_photos 서브패키지의 독립성을 위해 face_recognition 의 탐색 유틸에 의존하지 않고
자체 구현한다(구글 포토는 이미지뿐 아니라 동영상도 받으므로 확장자 집합도 별도).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

# 구글 포토가 받는 이미지/동영상 확장자
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif", ".gif",
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# mimetypes 가 모르는 확장자 보정
_EXTRA_MIME = {
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".webp": "image/webp",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
    ".mkv": "video/x-matroska",
}


def iter_media(folder: Path, recursive: bool = True) -> list[Path]:
    """folder 내 업로드 대상 미디어 경로 목록(정렬됨)을 반환한다."""
    walker = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        p for p in walker if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def guess_mime(path: Path) -> str:
    """파일의 MIME 타입을 추정한다. 모르면 application/octet-stream."""
    ext = path.suffix.lower()
    if ext in _EXTRA_MIME:
        return _EXTRA_MIME[ext]
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"
