"""필터링 오케스트레이션: 검출 → (선택)인물매칭 → 날짜별 정리 저장."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from .detector import FaceDetector, iter_images
from .identity import PersonMatcher
from .organize import photo_year_month, unique_dest

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """필터링 실행 결과 요약."""

    total: int = 0      # 검사한 이미지 수
    saved: int = 0      # 저장한 수
    no_face: int = 0    # 얼굴이 없어 건너뛴 수
    no_match: int = 0   # 얼굴은 있으나 대상 인물이 아니라 건너뛴 수
    failed: int = 0     # 디코딩/처리 실패 수


def filter_folder(
    input_dir: Path,
    output_dir: Path,
    detector: FaceDetector,
    matcher: PersonMatcher | None = None,
    recursive: bool = False,
    move: bool = False,
    by_date: bool = True,
) -> FilterResult:
    """input_dir 의 이미지를 검사해 조건을 만족하는 것만 output_dir 로 복사(또는 이동)한다.

    - matcher 가 주어지면 해당 인물이 포함된 이미지만 저장(없으면 얼굴 유무만 판정).
    - by_date=True 면 ``output_dir/yyyy-mm/`` 으로 촬영 연-월별 정리, False 면 평평하게 저장.
    - recursive 는 input_dir 하위 폴더까지 탐색할지 여부.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    result = FilterResult()

    for image_path in iter_images(input_dir, recursive):
        result.total += 1
        faces = detector.detect(image_path)

        if faces is None:
            result.failed += 1
            continue
        if not faces:
            result.no_face += 1
            logger.info("얼굴 없음(건너뜀): %s", image_path.name)
            continue
        if matcher is not None and not matcher.matches(faces):
            result.no_match += 1
            logger.info("대상 인물 아님(건너뜀): %s", image_path.name)
            continue

        dest_dir = output_dir / photo_year_month(image_path) if by_date else output_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = unique_dest(dest_dir, image_path.name)
        if move:
            shutil.move(str(image_path), str(dest))
        else:
            shutil.copy2(image_path, dest)
        result.saved += 1
        logger.info("저장: %s -> %s", image_path.name, dest.relative_to(output_dir))

    return result
