"""구글 OAuth 인증 — 데스크톱 앱 흐름으로 토큰을 얻어 인증된 세션을 만든다.

최초 1회는 client_secret.json 으로 브라우저 동의를 받고(InstalledAppFlow),
이후에는 캐시된 token.json 을 로드/갱신해 재사용한다.
업로드 전용이므로 appendonly 스코프만 요청한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/photoslibrary.appendonly"]
DEFAULT_TOKEN_PATH = Path.home() / ".config" / "child-photo-upload-job" / "token.json"


def load_credentials(client_secret: Path, token_path: Path = DEFAULT_TOKEN_PATH) -> Credentials:
    """캐시 토큰을 로드(없으면 동의 흐름)하고 필요 시 갱신해 Credentials 를 반환한다."""
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        logger.info("토큰 갱신 중")
        creds.refresh(Request())
    else:
        if not client_secret.exists():
            raise FileNotFoundError(
                f"OAuth client_secret 파일이 없습니다: {client_secret}\n"
                "구글 클라우드 콘솔에서 '데스크톱 앱' OAuth 클라이언트를 만들어 다운로드하세요."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
        creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def get_session(client_secret: Path, token_path: Path = DEFAULT_TOKEN_PATH) -> AuthorizedSession:
    """인증된 요청 세션(토큰 자동 갱신 포함)을 반환한다."""
    return AuthorizedSession(load_credentials(client_secret, token_path))
