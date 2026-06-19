"""얼굴 인식 시스템의 단일 진입점 오케스트레이터.

``RunFaceRecognition`` 은 비싼 ``FaceDetector`` 를 한 번 생성해 보유·재사용하면서
인물 등록(enroll)과 골라내기(filter)를 위임한다. 추후 추가될 상위 오케스트라(구글 포토
시스템과 합치는 계층)는 이 한 클래스만 호출하면 얼굴 인식 시스템 전체를 쓸 수 있다.
"""

from __future__ import annotations

from pathlib import Path

from .detector import FaceDetector
from .identity import DEFAULT_THRESHOLD, PersonMatcher, enroll_person
from .pipeline import FilterResult, filter_folder

DEFAULT_MODEL_DIR = Path("Image-processing")


class RunFaceRecognition:
    """얼굴 인식 시스템 오케스트레이터.

    검출기(모델 로딩 비용이 큼)를 생성자에서 1회 만들어 ``enroll``/``run`` 간에 재사용한다.
    """

    def __init__(
        self,
        model_name: str = "buffalo_l",
        use_gpu: bool = False,
        min_score: float = 0.5,
        model_dir: Path = DEFAULT_MODEL_DIR,
    ) -> None:
        self.model_dir = model_dir
        self._detector = FaceDetector(
            model_name=model_name, use_gpu=use_gpu, min_score=min_score
        )

    @property
    def detector(self) -> FaceDetector:
        """보유 중인 재사용 검출기."""
        return self._detector

    def enroll(self, name: str, reference_dir: Path) -> tuple[Path, int]:
        """기준 이미지로 인물 임베딩을 등록한다. (저장 경로, 사용 이미지 수) 반환."""
        return enroll_person(name, reference_dir, self._detector, self.model_dir)

    def run(
        self,
        input_dir: Path,
        output_dir: Path,
        person: str | None = None,
        match_threshold: float = DEFAULT_THRESHOLD,
        recursive: bool = False,
        move: bool = False,
        by_date: bool = True,
    ) -> FilterResult:
        """입력 폴더에서 (선택 인물의) 얼굴이 있는 이미지만 골라 날짜별로 저장한다.

        ``person`` 이 주어지면 등록된 인물 모델을 불러와 그 인물만 골라낸다.
        """
        matcher = (
            PersonMatcher.load(self.model_dir, person, match_threshold) if person else None
        )
        return filter_folder(
            input_dir=input_dir,
            output_dir=output_dir,
            detector=self._detector,
            matcher=matcher,
            recursive=recursive,
            move=move,
            by_date=by_date,
        )
