"""얼굴 인식 시스템 서브패키지.

InsightFace 기반 검출/인식으로 얼굴(또는 등록된 인물)이 있는 이미지를 골라 날짜별로 정리한다.
공개 진입점은 ``RunFaceRecognition`` 오케스트레이터다.
"""

from .detector import FaceDetector, iter_images
from .identity import DEFAULT_THRESHOLD, PersonMatcher, enroll_person
from .organize import photo_year_month, unique_dest
from .pipeline import FilterResult, filter_folder
from .run_face_recognition import RunFaceRecognition

__all__ = [
    "RunFaceRecognition",
    "FaceDetector",
    "iter_images",
    "PersonMatcher",
    "enroll_person",
    "DEFAULT_THRESHOLD",
    "FilterResult",
    "filter_folder",
    "photo_year_month",
    "unique_dest",
]
