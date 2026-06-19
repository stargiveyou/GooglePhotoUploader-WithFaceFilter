"""InsightFace 얼굴 검출 래퍼와 이미지 탐색 유틸."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
import pillow_heif
from insightface.app import FaceAnalysis
from insightface.app.common import Face
from PIL import Image

logger = logging.getLogger(__name__)

# pillow-heif 를 PIL 에 등록해 HEIC/HEIF 를 Image.open 으로 열 수 있게 한다.
# (EXIF 읽는 organize.py 의 Image.open 도 함께 HEIC 를 지원하게 됨)
pillow_heif.register_heif_opener()

# OpenCV(cv2.imdecode)로 디코딩 가능한 확장자
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
# cv2 가 못 읽어 pillow-heif(PIL)로 디코딩하는 확장자
HEIF_EXTENSIONS = {".heic", ".heif"}
# filter/enroll 이 탐색 대상으로 삼는 전체 확장자
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | HEIF_EXTENSIONS


class FaceDetector:
    """InsightFace ``FaceAnalysis`` 래퍼.

    모델 로딩 비용이 크므로 인스턴스를 한 번 만들어 여러 이미지에 재사용한다.
    최초 실행 시 모델(기본 buffalo_l)이 ``~/.insightface`` 로 자동 다운로드된다.
    검출과 함께 인식 임베딩(``normed_embedding``)도 채워지므로 인물 매칭에 그대로 쓸 수 있다.
    """

    def __init__(
        self,
        model_name: str = "buffalo_l",
        use_gpu: bool = False,
        det_size: tuple[int, int] = (640, 640),
        min_score: float = 0.5,
    ) -> None:
        self.min_score = min_score
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if use_gpu
            else ["CPUExecutionProvider"]
        )
        self.app = FaceAnalysis(name=model_name, providers=providers)
        self.app.prepare(ctx_id=0 if use_gpu else -1, det_size=det_size)

    def detect(self, image_path: Path) -> list[Face] | None:
        """이미지에서 ``min_score`` 이상으로 검출된 얼굴 목록을 반환한다.

        디코딩에 실패하면 None(=실패), 얼굴이 없으면 빈 리스트를 반환한다.
        HEIC/HEIF 는 cv2 가 읽지 못하므로 pillow-heif(PIL)로 디코딩하고,
        나머지는 한글/유니코드 경로에 안전한 ``np.fromfile`` + ``cv2.imdecode`` 로 읽는다.
        InsightFace 는 BGR 배열을 기대하므로 PIL(RGB) 결과는 BGR 로 변환한다.
        """
        if image_path.suffix.lower() in HEIF_EXTENSIONS:
            img = self._decode_heif(image_path)
        else:
            img = self._decode_cv2(image_path)
        if img is None:
            return None

        faces = self.app.get(img)
        return [f for f in faces if float(f.det_score) >= self.min_score]

    @staticmethod
    def _decode_cv2(image_path: Path) -> np.ndarray | None:
        try:
            raw = np.fromfile(str(image_path), dtype=np.uint8)
            img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        except OSError as exc:
            logger.warning("읽기 실패 %s: %s", image_path, exc)
            return None
        if img is None:
            logger.warning("디코딩 실패 %s", image_path)
        return img

    @staticmethod
    def _decode_heif(image_path: Path) -> np.ndarray | None:
        try:
            with Image.open(image_path) as im:
                rgb = np.asarray(im.convert("RGB"))
        except (OSError, ValueError) as exc:
            logger.warning("HEIC 디코딩 실패 %s: %s", image_path, exc)
            return None
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def iter_images(input_dir: Path, recursive: bool) -> list[Path]:
    """input_dir 내 이미지 파일 경로 목록(정렬됨)을 반환한다."""
    walker = input_dir.rglob("*") if recursive else input_dir.glob("*")
    return sorted(p for p in walker if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
