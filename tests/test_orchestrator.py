"""상위 오케스트라 PhotoPipeline 단위 테스트 (모델/네트워크 없이 가짜 러너 주입)."""

from pathlib import Path

from child_photo_upload_job.face_recognition import FilterResult
from child_photo_upload_job.google_photos import UploadResult
from child_photo_upload_job.orchestrator import PhotoPipeline, PipelineResult


class FakeFace:
    def __init__(self):
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return FilterResult(total=10, saved=7, no_face=2, no_match=1, failed=0)


class FakeUploader:
    def __init__(self):
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return UploadResult(total=7, uploaded=7, skipped=0, failed=0, per_album={"2023-04": 7})


def test_pipeline_chains_filter_then_upload(tmp_path: Path):
    pipe = PhotoPipeline()
    face, uploader = FakeFace(), FakeUploader()
    # 지연 생성 캐시에 가짜 주입 → 실제 모델/인증 안 만듦
    pipe._face = face
    pipe._uploader = uploader

    out = tmp_path / "out"
    result = pipe.run(
        input_dir=tmp_path / "in",
        output_dir=out,
        person="doyun",
        by_album=True,
        dry_run=True,
    )

    assert isinstance(result, PipelineResult)
    # 필터 결과가 그대로 전달됨
    assert result.filter.saved == 7
    assert result.upload.uploaded == 7
    # 필터는 입력 폴더로, 업로드는 출력 폴더(filter 결과)로 호출됨
    assert face.calls[0]["input_dir"] == tmp_path / "in"
    assert face.calls[0]["person"] == "doyun"
    assert uploader.calls[0]["folder"] == out
    assert uploader.calls[0]["dry_run"] is True
