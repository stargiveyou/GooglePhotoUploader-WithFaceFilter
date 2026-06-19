"""대상 인물 등록(enroll)과 매칭.

InsightFace 인식 임베딩의 코사인 유사도로 특정 인물 여부를 판정한다.
'트레이닝 모델'은 등록한 기준 얼굴들의 임베딩 묶음(``Image-processing/<이름>/<이름>.npz``)으로,
나중에 filter 단계에서 불러와 적용한다.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from insightface.app.common import Face

from .detector import FaceDetector, iter_images

logger = logging.getLogger(__name__)

# buffalo_l(w600k_r50) 정규화 임베딩 기준 동일 인물 코사인 유사도 임계값.
# 값이 높을수록 엄격(오검출↓·미검출↑). 환경에 맞게 --match-threshold 로 조정.
DEFAULT_THRESHOLD = 0.35


def _largest_face(faces: list[Face]) -> Face:
    """가장 큰 얼굴(주 피사체로 가정)을 고른다."""
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def enroll_person(
    name: str,
    reference_dir: Path,
    detector: FaceDetector,
    model_dir: Path,
) -> tuple[Path, int]:
    """기준 이미지들에서 대상 인물의 임베딩을 모아 ``model_dir/<name>/<name>.npy`` 로 저장한다.

    각 기준 이미지에서는 가장 큰 얼굴 하나를 대상으로 본다.
    저장 경로와 사용된 이미지 수를 반환하며, 인물별 결과는 ``model_dir/<name>/`` 하위에 정리한다.
    """
    person_dir = model_dir / name
    person_dir.mkdir(parents=True, exist_ok=True)
    embeddings: list[np.ndarray] = []

    for img in iter_images(reference_dir, recursive=True):
        faces = detector.detect(img)
        if not faces:
            logger.warning("기준 이미지에서 얼굴 없음(건너뜀): %s", img.name)
            continue
        embeddings.append(_largest_face(faces).normed_embedding)
        logger.info("등록에 사용: %s", img.name)

    if not embeddings:
        raise ValueError(f"'{reference_dir}' 에서 등록할 얼굴을 찾지 못했습니다.")

    arr = np.vstack(embeddings).astype(np.float32)
    out = person_dir / f"{name}.npy"
    np.save(out, arr)
    return out, len(embeddings)


class PersonMatcher:
    """등록된 인물의 임베딩 묶음과 얼굴을 비교한다."""

    def __init__(self, name: str, embeddings: np.ndarray, threshold: float = DEFAULT_THRESHOLD):
        self.name = name
        self.embeddings = embeddings  # (N, 512), L2 정규화됨
        self.threshold = threshold

    @classmethod
    def load(
        cls, model_dir: Path, name: str, threshold: float = DEFAULT_THRESHOLD
    ) -> PersonMatcher:
        person_dir = model_dir / name
        npy_path = person_dir / f"{name}.npy"
        npz_path = person_dir / f"{name}.npz"
        if npy_path.exists():
            # 단일 배열 .npy (N, 512) — 정규화 임베딩 묶음
            embeddings = np.load(npy_path).astype(np.float32)
        elif npz_path.exists():
            # 하위호환: np.savez 로 저장된 'embeddings' 키
            embeddings = np.load(npz_path)["embeddings"].astype(np.float32)
        else:
            raise FileNotFoundError(
                f"등록된 인물 모델이 없습니다: {npy_path} (먼저 enroll 로 등록하세요)"
            )
        return cls(name, embeddings, threshold)

    def best_similarity(self, embedding: np.ndarray) -> float:
        """주어진 얼굴 임베딩과 등록 임베딩들 간 최대 코사인 유사도(둘 다 정규화)."""
        return float(np.max(self.embeddings @ embedding))

    def matches(self, faces: Iterable[Face]) -> bool:
        """얼굴들 중 하나라도 임계값 이상으로 일치하면 True."""
        return any(self.best_similarity(f.normed_embedding) >= self.threshold for f in faces)
