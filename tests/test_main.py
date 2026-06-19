from pathlib import Path
from types import SimpleNamespace

import numpy as np

from child_photo_upload_job import __version__
from child_photo_upload_job.face_recognition.detector import iter_images
from child_photo_upload_job.face_recognition.identity import PersonMatcher
from child_photo_upload_job.face_recognition.organize import photo_year_month, unique_dest


def _face(vec):
    v = np.asarray(vec, dtype=np.float32)
    return SimpleNamespace(normed_embedding=v / np.linalg.norm(v))


def test_version():
    assert __version__ == "0.1.0"


def test_face_recognition_public_api():
    # 서브패키지 공개 진입점이 import 되는지 (오케스트레이터 생성은 모델 로딩이 필요해 제외)
    from child_photo_upload_job.face_recognition import RunFaceRecognition

    assert hasattr(RunFaceRecognition, "enroll")
    assert hasattr(RunFaceRecognition, "run")


def test_iter_images_filters_and_sorts(tmp_path: Path):
    (tmp_path / "b.JPG").write_bytes(b"")
    (tmp_path / "a.png").write_bytes(b"")
    (tmp_path / "note.txt").write_bytes(b"")  # 이미지 아님 → 제외
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.jpeg").write_bytes(b"")

    flat = iter_images(tmp_path, recursive=False)
    assert [p.name for p in flat] == ["a.png", "b.JPG"]  # 정렬, txt 제외, 하위폴더 제외

    deep = iter_images(tmp_path, recursive=True)
    assert "c.jpeg" in [p.name for p in deep]


def test_person_matcher():
    ref = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    matcher = PersonMatcher("target", ref, threshold=0.5)

    assert matcher.matches([_face([1, 0, 0])])           # 동일 → 일치
    assert not matcher.matches([_face([0, 1, 0])])        # 직교 → 불일치
    assert matcher.matches([_face([0, 1, 0]), _face([1, 0, 0])])  # 하나라도 일치하면 True


def test_unique_dest(tmp_path: Path):
    (tmp_path / "a.jpg").write_bytes(b"")
    assert unique_dest(tmp_path, "a.jpg").name == "a_1.jpg"  # 충돌 → 접미사
    assert unique_dest(tmp_path, "b.jpg").name == "b.jpg"    # 비충돌 → 그대로


def test_photo_year_month_mtime_fallback(tmp_path: Path):
    import os
    from datetime import datetime

    p = tmp_path / "x.jpg"
    p.write_bytes(b"")
    ts = datetime(2025, 3, 14, 9, 0, 0).timestamp()
    os.utime(p, (ts, ts))
    # EXIF 없는 빈 파일 → 파일 수정시각으로 폴백
    assert photo_year_month(p) == "2025-03"
