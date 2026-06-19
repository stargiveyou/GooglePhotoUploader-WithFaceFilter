"""업로드 오케스트레이션: 폴더 → 앨범 그룹화 → 바이트 업로드 → 50개 청크 batchCreate.

상태 파일로 앨범을 재사용하고 이미 업로드한 파일은 건너뛴다(idempotent/resume).
dry_run 이면 네트워크 호출 없이 업로드 예정 집계만 낸다.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .client import BATCH_LIMIT, GooglePhotosClient
from .media import guess_mime, iter_media
from .state import UploadState

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """업로드 실행 결과 요약."""

    total: int = 0       # 발견한 미디어 수
    uploaded: int = 0    # 이번에 업로드/등록 성공
    skipped: int = 0     # 상태파일 기준 이미 업로드되어 건너뜀
    failed: int = 0      # 업로드/등록 실패
    per_album: dict[str, int] = field(default_factory=dict)  # 앨범별 이번 업로드 수


def _album_key(path: Path, root: Path, by_album: bool) -> str | None:
    """파일이 속할 앨범명. by_album 이면 root 기준 직속 상위 폴더명, 아니면 None(라이브러리)."""
    if not by_album:
        return None
    rel = path.relative_to(root)
    # root 직속 파일은 앨범 없음, 하위폴더 안 파일은 그 첫 폴더명을 앨범으로
    return rel.parts[0] if len(rel.parts) > 1 else None


def _ensure_album(client: GooglePhotosClient, state: UploadState, title: str) -> str:
    album_id = state.album_id(title)
    if album_id:
        return album_id
    album_id = client.create_album(title)
    state.set_album(title, album_id)
    state.save()
    logger.info("앨범 생성: %s", title)
    return album_id


def _chunks(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def upload_folder(
    client: GooglePhotosClient,
    root: Path,
    state: UploadState,
    by_album: bool = True,
    recursive: bool = True,
    dry_run: bool = False,
) -> UploadResult:
    """root 폴더의 미디어를 (앨범별로) 구글 포토에 업로드한다."""
    result = UploadResult()
    files = iter_media(root, recursive)
    result.total = len(files)

    # 앨범명(None=라이브러리)별로 그룹화하되, 이미 업로드된 파일은 제외
    groups: dict[str | None, list[Path]] = defaultdict(list)
    for path in files:
        if state.is_uploaded(path):
            result.skipped += 1
            continue
        groups[_album_key(path, root, by_album)].append(path)

    for album_title, paths in groups.items():
        if not paths:
            continue
        if dry_run:
            label = album_title or "(라이브러리)"
            result.per_album[label] = result.per_album.get(label, 0) + len(paths)
            result.uploaded += len(paths)  # 예정 수로 집계
            continue

        album_id = _ensure_album(client, state, album_title) if album_title else None

        # 1) 바이트 업로드 → (token, filename, path) 수집 (실패는 failed)
        pending: list[tuple[str, str, Path]] = []
        for path in paths:
            try:
                token = client.upload_bytes(path, guess_mime(path))
                pending.append((token, path.name, path))
            except Exception as exc:  # noqa: BLE001 — 개별 파일 실패는 건너뛰고 계속
                logger.warning("바이트 업로드 실패 %s: %s", path.name, exc)
                result.failed += 1

        # 2) 50개씩 batchCreate → 성공분 상태 기록
        for chunk in _chunks(pending, BATCH_LIMIT):
            items = [(tok, fn) for tok, fn, _ in chunk]
            path_by_token = {tok: p for tok, _, p in chunk}
            try:
                item_results = client.batch_create(items, album_id=album_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("batchCreate 실패(청크 %d개): %s", len(items), exc)
                result.failed += len(items)
                continue
            for ir in item_results:
                if ir.ok and ir.media_item_id:
                    state.mark_uploaded(path_by_token[ir.upload_token], ir.media_item_id)
                    result.uploaded += 1
                    label = album_title or "(라이브러리)"
                    result.per_album[label] = result.per_album.get(label, 0) + 1
                else:
                    result.failed += 1
            state.save()

    return result
