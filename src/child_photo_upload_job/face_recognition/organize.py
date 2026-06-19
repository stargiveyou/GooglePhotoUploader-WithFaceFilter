"""골라낸 이미지를 촬영 연-월(yyyy-mm) 폴더로 정리하는 유틸."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

_EXIF_IFD = 0x8769  # Exif SubIFD 포인터 태그
_DATETIME_ORIGINAL = 36867  # 촬영 일시
_DATETIME_DIGITIZED = 36868  # 디지털화 일시
_DATETIME = 306  # 기본 IFD 의 수정 일시


def photo_year_month(path: Path) -> str:
    """촬영 연-월 'yyyy-mm' 문자열. EXIF 촬영일시 우선, 없으면 파일 수정시각."""
    dt = _exif_datetime(path) or datetime.fromtimestamp(path.stat().st_mtime)
    return dt.strftime("%Y-%m")


def _exif_datetime(path: Path) -> datetime | None:
    """EXIF에서 촬영 일시를 읽는다. 없거나 파싱 실패 시 None."""
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            value = None
            ifd = exif.get_ifd(_EXIF_IFD)
            if ifd:
                value = ifd.get(_DATETIME_ORIGINAL) or ifd.get(_DATETIME_DIGITIZED)
            if not value:
                value = exif.get(_DATETIME)
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        logger.debug("EXIF 읽기 실패 %s: %s", path, exc)
        return None

    if not value:
        return None
    try:
        # EXIF 표준 형식: 'YYYY:MM:DD HH:MM:SS'
        return datetime.strptime(str(value).strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        logger.debug("EXIF 일시 형식 인식 불가 %s: %r", path, value)
        return None


def unique_dest(dest_dir: Path, filename: str) -> Path:
    """dest_dir 안에서 겹치지 않는 경로를 만든다. 충돌 시 '_1', '_2' … 를 붙인다."""
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    i = 1
    while (cand := dest_dir / f"{stem}_{i}{suffix}").exists():
        i += 1
    return cand
