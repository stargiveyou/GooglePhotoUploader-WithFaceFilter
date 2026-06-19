"""google_photos 서브패키지 단위 테스트 (실제 OAuth/네트워크 없이 가짜 client 주입)."""

from pathlib import Path

from child_photo_upload_job.google_photos.client import ItemResult
from child_photo_upload_job.google_photos.media import guess_mime, iter_media
from child_photo_upload_job.google_photos.state import UploadState
from child_photo_upload_job.google_photos.uploader import upload_folder


# --- media ---------------------------------------------------------------
def test_iter_media_filters_and_sorts(tmp_path: Path):
    (tmp_path / "b.HEIC").write_bytes(b"x")
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "clip.mp4").write_bytes(b"x")
    (tmp_path / "note.txt").write_bytes(b"x")  # 비대상
    found = [p.name for p in iter_media(tmp_path, recursive=False)]
    assert found == ["a.jpg", "b.HEIC", "clip.mp4"]  # 정렬, txt 제외, heic/mp4 포함


def test_guess_mime():
    assert guess_mime(Path("x.heic")) == "image/heic"
    assert guess_mime(Path("x.jpg")) == "image/jpeg"
    assert guess_mime(Path("x.mov")) == "video/quicktime"


# --- state ---------------------------------------------------------------
def test_state_roundtrip(tmp_path: Path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"data")
    sp = tmp_path / "state.json"
    st = UploadState.load(sp)
    assert not st.is_uploaded(f)
    st.set_album("2023-04", "ALBUM1")
    st.mark_uploaded(f, "MEDIA1")
    st.save()

    st2 = UploadState.load(sp)
    assert st2.album_id("2023-04") == "ALBUM1"
    assert st2.is_uploaded(f)


# --- uploader (가짜 client) ----------------------------------------------
class FakeClient:
    """GooglePhotosClient 인터페이스 모방. 호출 기록과 실패 주입 지원."""

    def __init__(self, fail_filenames=()):
        self.fail_filenames = set(fail_filenames)
        self.uploaded = []          # upload_bytes 호출된 파일명
        self.created_albums = []    # create_album 호출된 title
        self.batch_sizes = []       # batch_create 청크 크기들
        self._album_seq = 0

    def upload_bytes(self, path: Path, mime: str) -> str:
        self.uploaded.append(path.name)
        return f"token:{path.name}"

    def create_album(self, title: str) -> str:
        self.created_albums.append(title)
        self._album_seq += 1
        return f"album:{self._album_seq}"

    def batch_create(self, items, album_id=None):
        self.batch_sizes.append(len(items))
        out = []
        for tok, fn in items:
            ok = fn not in self.fail_filenames
            out.append(
                ItemResult(
                    upload_token=tok,
                    filename=fn,
                    media_item_id=f"media:{fn}" if ok else None,
                    ok=ok,
                    message="" if ok else "fail",
                )
            )
        return out


def _make_album_folder(root: Path, album: str, n: int, prefix="img"):
    d = root / album
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (d / f"{prefix}_{i:03d}.jpg").write_bytes(b"x")


def test_dry_run_groups_without_network(tmp_path: Path):
    _make_album_folder(tmp_path, "2023-04", 3)
    _make_album_folder(tmp_path, "2022-07", 2)
    client = FakeClient()
    state = UploadState(tmp_path / "s.json")

    res = upload_folder(client, tmp_path, state, by_album=True, dry_run=True)

    assert res.total == 5
    assert res.uploaded == 5  # 예정 집계
    assert res.per_album == {"2023-04": 3, "2022-07": 2}
    assert client.uploaded == []        # 네트워크 0회
    assert client.created_albums == []


def test_chunking_into_50(tmp_path: Path):
    _make_album_folder(tmp_path, "2023-04", 55)
    client = FakeClient()
    state = UploadState(tmp_path / "s.json")

    res = upload_folder(client, tmp_path, state, by_album=True)

    assert res.total == 55
    assert res.uploaded == 55
    assert res.failed == 0
    assert client.batch_sizes == [50, 5]          # 50개씩 청크
    assert client.created_albums == ["2023-04"]   # 앨범 1회 생성
    assert res.per_album == {"2023-04": 55}


def test_skip_already_uploaded_and_album_reuse(tmp_path: Path):
    _make_album_folder(tmp_path, "2023-04", 2)
    sp = tmp_path / "s.json"
    client = FakeClient()

    # 1차 실행
    state = UploadState.load(sp)
    res1 = upload_folder(client, tmp_path, state, by_album=True)
    assert res1.uploaded == 2 and res1.skipped == 0

    # 2차 실행: 상태파일로 전부 skip, 앨범 재생성 안 함
    client2 = FakeClient()
    state2 = UploadState.load(sp)
    res2 = upload_folder(client2, tmp_path, state2, by_album=True)
    assert res2.skipped == 2 and res2.uploaded == 0
    assert client2.uploaded == []
    assert client2.created_albums == []  # 기존 albumId 재사용


def test_partial_failure_counted(tmp_path: Path):
    _make_album_folder(tmp_path, "2023-04", 3)
    client = FakeClient(fail_filenames=["img_001.jpg"])
    state = UploadState(tmp_path / "s.json")

    res = upload_folder(client, tmp_path, state, by_album=True)

    assert res.total == 3
    assert res.uploaded == 2
    assert res.failed == 1
