"""상위 오케스트라 — 얼굴 인식과 구글 포토 업로드를 잇는 전체 파이프라인.

`PhotoPipeline` 은 독립 시스템인 `RunFaceRecognition`(filter)과 `RunGooglePhotosUpload`(upload)를
조합한다. 입력 폴더를 골라내 `output_dir/yyyy-mm/` 로 정리한 뒤, 그 폴더를 구글 포토에 업로드한다.

두 시스템은 서로 의존하지 않으며, 이 모듈만 양쪽을 import 하는 최상위 계층이다.
러너는 **지연 생성**해 dry-run(인증·모델 불필요 경로)이나 테스트에서 주입할 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .face_recognition import DEFAULT_THRESHOLD, FilterResult, RunFaceRecognition
from .google_photos import RunGooglePhotosUpload, UploadResult
from .google_photos.auth import DEFAULT_TOKEN_PATH
from .google_photos.state import DEFAULT_STATE_PATH

DEFAULT_MODEL_DIR = Path("Image-processing")


@dataclass
class PipelineResult:
    """전체 파이프라인 실행 결과(필터 + 업로드)."""

    filter: FilterResult
    upload: UploadResult


class PhotoPipeline:
    """filter → upload 를 잇는 상위 오케스트라."""

    def __init__(
        self,
        model_name: str = "buffalo_l",
        use_gpu: bool = False,
        min_score: float = 0.5,
        model_dir: Path = DEFAULT_MODEL_DIR,
        client_secret: Path | None = None,
        token_path: Path = DEFAULT_TOKEN_PATH,
        state_path: Path = DEFAULT_STATE_PATH,
    ) -> None:
        self._model_name = model_name
        self._use_gpu = use_gpu
        self._min_score = min_score
        self._model_dir = model_dir
        self._client_secret = client_secret
        self._token_path = token_path
        self._state_path = state_path
        # 지연 생성/주입 가능
        self._face: RunFaceRecognition | None = None
        self._uploader: RunGooglePhotosUpload | None = None

    def _get_face(self) -> RunFaceRecognition:
        if self._face is None:
            self._face = RunFaceRecognition(
                model_name=self._model_name,
                use_gpu=self._use_gpu,
                min_score=self._min_score,
                model_dir=self._model_dir,
            )
        return self._face

    def _get_uploader(self) -> RunGooglePhotosUpload:
        if self._uploader is None:
            self._uploader = RunGooglePhotosUpload(
                client_secret=self._client_secret,
                token_path=self._token_path,
                state_path=self._state_path,
            )
        return self._uploader

    def run(
        self,
        input_dir: Path,
        output_dir: Path,
        person: str | list[str] | None = None,
        match_threshold: float = DEFAULT_THRESHOLD,
        recursive: bool = False,
        move: bool = False,
        by_date: bool = True,
        by_album: bool = True,
        dry_run: bool = False,
    ) -> PipelineResult:
        """입력 폴더를 골라내 정리한 뒤 구글 포토에 업로드한다.

        1) filter: input_dir → output_dir/yyyy-mm/ (선택 인물만)
        2) upload: output_dir 를 yyyy-mm 하위폴더명 = 앨범명으로 업로드(dry_run 이면 집계만).
        """
        filter_result = self._get_face().run(
            input_dir=input_dir,
            output_dir=output_dir,
            person=person,
            match_threshold=match_threshold,
            recursive=recursive,
            move=move,
            by_date=by_date,
        )
        upload_result = self._get_uploader().run(
            folder=output_dir,
            by_album=by_album,
            recursive=True,
            dry_run=dry_run,
        )
        return PipelineResult(filter=filter_result, upload=upload_result)
