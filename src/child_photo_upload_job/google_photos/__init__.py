"""구글 포토 업로드 시스템 서브패키지 (얼굴 인식과 독립).

정리된 로컬 폴더(예: filter 결과의 ``yyyy-mm`` 하위폴더)를 구글 포토에 업로드하며,
하위폴더명을 앨범명으로 매핑한다. 공개 진입점은 ``RunGooglePhotosUpload`` 오케스트레이터다.
"""

from .client import GooglePhotosClient, ItemResult
from .run_google_photos import RunGooglePhotosUpload
from .state import UploadState
from .uploader import UploadResult, upload_folder

__all__ = [
    "RunGooglePhotosUpload",
    "UploadResult",
    "upload_folder",
    "UploadState",
    "GooglePhotosClient",
    "ItemResult",
]
