"""Google Photos Library API 저수준 REST 클라이언트.

업로드 전용(appendonly 스코프)으로 필요한 3개 동작만 감싼다: 바이트 업로드, 앨범 생성,
미디어 아이템 일괄 생성. 세션을 주입받아(테스트에서 가짜 세션 교체) HTTP를 수행한다.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

API_BASE = "https://photoslibrary.googleapis.com/v1"
UPLOAD_URL = f"{API_BASE}/uploads"
BATCH_CREATE_URL = f"{API_BASE}/mediaItems:batchCreate"
ALBUMS_URL = f"{API_BASE}/albums"

# batchCreate 는 한 번에 최대 50개
BATCH_LIMIT = 50
# 429 시 최소 대기(초)
RATE_LIMIT_DELAY = 30.0
MAX_RETRIES = 4


@dataclass
class ItemResult:
    """batchCreate 의 항목별 결과."""

    upload_token: str
    filename: str
    media_item_id: str | None  # 성공 시 채워짐
    ok: bool
    message: str = ""


class GooglePhotosError(RuntimeError):
    """구글 포토 API 호출 실패."""


class GooglePhotosClient:
    """appendonly 업로드에 필요한 최소 REST 래퍼."""

    def __init__(self, session, sleep=time.sleep):
        # session: requests.Session 호환(google AuthorizedSession). sleep 은 테스트 주입용.
        self._session = session
        self._sleep = sleep

    def _request(self, method: str, url: str, **kwargs):
        """429/5xx 에 지수 백오프 재시도하는 공통 요청."""
        for attempt in range(MAX_RETRIES):
            resp = self._session.request(method, url, **kwargs)
            if resp.status_code == 429:
                wait = RATE_LIMIT_DELAY * (attempt + 1)
                logger.warning("429 레이트 제한 — %.0f초 대기 후 재시도", wait)
                self._sleep(wait)
                continue
            if resp.status_code >= 500:
                wait = 2.0 * (attempt + 1)
                logger.warning("%d 서버 오류 — %.0f초 후 재시도", resp.status_code, wait)
                self._sleep(wait)
                continue
            return resp
        raise GooglePhotosError(f"재시도 초과: {method} {url}")

    def upload_bytes(self, path: Path, mime: str) -> str:
        """파일 바이트를 업로드하고 uploadToken(원문 텍스트)을 반환한다."""
        headers = {
            "Content-type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": mime,
            "X-Goog-Upload-Protocol": "raw",
            "X-Goog-Upload-File-Name": path.name,
        }
        data = path.read_bytes()
        resp = self._request("POST", UPLOAD_URL, headers=headers, data=data)
        if resp.status_code != 200 or not resp.text:
            raise GooglePhotosError(
                f"업로드 실패 {path.name}: {resp.status_code} {resp.text[:200]}"
            )
        return resp.text

    def create_album(self, title: str) -> str:
        """앨범을 생성하고 albumId 를 반환한다."""
        resp = self._request("POST", ALBUMS_URL, json={"album": {"title": title}})
        if resp.status_code != 200:
            raise GooglePhotosError(
                f"앨범 생성 실패 '{title}': {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()["id"]

    def batch_create(
        self, items: list[tuple[str, str]], album_id: str | None = None
    ) -> list[ItemResult]:
        """(uploadToken, filename) 목록으로 미디어 아이템을 일괄 생성한다(최대 50).

        200(전체성공)/207(부분성공) 모두 처리해 항목별 ItemResult 를 반환한다.
        """
        if len(items) > BATCH_LIMIT:
            raise ValueError(f"batch_create 는 최대 {BATCH_LIMIT}개 (받음: {len(items)})")
        new_media_items = [
            {"simpleMediaItem": {"fileName": fn, "uploadToken": tok}} for tok, fn in items
        ]
        body: dict = {"newMediaItems": new_media_items}
        if album_id:
            body["albumId"] = album_id

        resp = self._request("POST", BATCH_CREATE_URL, json=body)
        if resp.status_code not in (200, 207):
            raise GooglePhotosError(f"batchCreate 실패: {resp.status_code} {resp.text[:200]}")

        results: list[ItemResult] = []
        by_token = {tok: fn for tok, fn in items}
        for entry in resp.json().get("newMediaItemResults", []):
            tok = entry.get("uploadToken", "")
            status = entry.get("status", {})
            # status.code 0(또는 누락) = OK
            ok = status.get("code", 0) in (0, None)
            media = entry.get("mediaItem", {})
            results.append(
                ItemResult(
                    upload_token=tok,
                    filename=by_token.get(tok, ""),
                    media_item_id=media.get("id") if ok else None,
                    ok=ok and bool(media.get("id")),
                    message=status.get("message", ""),
                )
            )
        return results
