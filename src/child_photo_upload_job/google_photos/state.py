"""업로드 상태 영속화 — 재실행 시 앨범 재사용과 중복 업로드 방지.

구글 포토는 동일 바이트를 자동 dedupe 하지만, 불필요한 재업로드와 중복 앨범 생성을 막기 위해
앱이 만든 앨범(title→id)과 이미 업로드한 파일(file_key→mediaItemId)을 로컬 JSON에 기록한다.
또한 appendonly 스코프로는 앨범 목록 조회 신뢰도가 낮아, 이 상태 파일이 앨범 재사용의 근거가 된다.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_STATE_PATH = Path.home() / ".config" / "child-photo-upload-job" / "upload_state.json"


def file_key(path: Path) -> str:
    """파일을 식별하는 키. 경로+크기+수정시각 조합으로 내용 변경/이동을 구분한다."""
    st = path.stat()
    return f"{path.name}:{st.st_size}:{int(st.st_mtime)}"


class UploadState:
    """앨범 매핑과 업로드 내역을 보관하는 상태 객체."""

    def __init__(self, path: Path = DEFAULT_STATE_PATH):
        self.path = path
        self.albums: dict[str, str] = {}
        self.uploaded: dict[str, str] = {}

    @classmethod
    def load(cls, path: Path = DEFAULT_STATE_PATH) -> UploadState:
        state = cls(path)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            state.albums = dict(data.get("albums", {}))
            state.uploaded = dict(data.get("uploaded", {}))
        return state

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"albums": self.albums, "uploaded": self.uploaded}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 앨범 -------------------------------------------------------------
    def album_id(self, title: str) -> str | None:
        return self.albums.get(title)

    def set_album(self, title: str, album_id: str) -> None:
        self.albums[title] = album_id

    # 업로드 -----------------------------------------------------------
    def is_uploaded(self, path: Path) -> bool:
        return file_key(path) in self.uploaded

    def mark_uploaded(self, path: Path, media_item_id: str) -> None:
        self.uploaded[file_key(path)] = media_item_id
