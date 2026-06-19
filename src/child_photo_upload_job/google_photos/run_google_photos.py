"""구글 포토 업로드 시스템의 단일 진입점 오케스트레이터.

``RunGooglePhotosUpload`` 은 ``RunFaceRecognition`` 과 대칭되는 독립 시스템 진입점이다.
인증 세션·클라이언트·상태를 보유하고 폴더 업로드를 위임한다. 추후 상위 오케스트라는
이 한 클래스만 호출하면 구글 포토 업로드 전체를 쓸 수 있다.
"""

from __future__ import annotations

from pathlib import Path

from .auth import DEFAULT_TOKEN_PATH, get_session
from .client import GooglePhotosClient
from .state import DEFAULT_STATE_PATH, UploadState
from .uploader import UploadResult, upload_folder


class RunGooglePhotosUpload:
    """구글 포토 업로드 시스템 오케스트레이터.

    dry_run 시에는 인증/네트워크 없이 동작하도록, 클라이언트를 지연 생성한다.
    """

    def __init__(
        self,
        client_secret: Path | None = None,
        token_path: Path = DEFAULT_TOKEN_PATH,
        state_path: Path = DEFAULT_STATE_PATH,
    ) -> None:
        self.client_secret = client_secret
        self.token_path = token_path
        self.state = UploadState.load(state_path)
        self._client: GooglePhotosClient | None = None

    def _get_client(self) -> GooglePhotosClient:
        if self._client is None:
            if self.client_secret is None:
                raise ValueError("업로드에는 --client-secret 가 필요합니다(dry-run 제외).")
            session = get_session(self.client_secret, self.token_path)
            self._client = GooglePhotosClient(session)
        return self._client

    def run(
        self,
        folder: Path,
        by_album: bool = True,
        recursive: bool = True,
        dry_run: bool = False,
    ) -> UploadResult:
        """folder 의 미디어를 구글 포토에 업로드한다(dry_run 이면 집계만)."""
        # dry_run 은 클라이언트 없이도 동작(uploader 가 네트워크 호출 안 함)
        client = None if dry_run else self._get_client()
        return upload_folder(
            client=client,
            root=folder,
            state=self.state,
            by_album=by_album,
            recursive=recursive,
            dry_run=dry_run,
        )
