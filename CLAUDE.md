# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 이 저장소에서 대화 및 설명은 한글로 한다.

## 프로젝트 목적

입력 폴더의 이미지를 InsightFace로 분석해, **얼굴(또는 등록된 특정 인물)이 있는 이미지만 골라
촬영 연-월(`yyyy-mm`)별로 정리 저장**하는 CLI 도구. 언어 환경은 Python.

## 명령어

먼저 가상환경 활성화: `source .venv/bin/activate` (또는 명령 앞에 `.venv/bin/` 접두).

- 설치(개발 도구 포함, editable): `pip install -e ".[dev]"` — `pyproject.toml` 의존성 변경 후 필수.
- 인물 등록: `python -m child_photo_upload_job.main enroll <이름> <기준이미지폴더>` → `Image-processing/<이름>/<이름>.npy` 생성.
- 골라내기: `python -m child_photo_upload_job.main filter <입력폴더> <출력폴더> [--person <이름>]`
  - 콘솔 스크립트 `child-photo-upload-job <enroll|filter|upload> ...` 도 동일.
- 구글 포토 업로드: `python -m child_photo_upload_job.main upload <폴더> [--client-secret <json>] [--dry-run]`
  - `yyyy-mm` 하위폴더명을 앨범명으로 매핑. `--dry-run` 은 인증/네트워크 없이 예정 집계만.
- 전체 파이프라인: `python -m child_photo_upload_job.main process <입력> <출력> [--person <이름>] [--client-secret <json>] [--dry-run]`
  - filter(골라내기) 후 그 결과 폴더를 곧바로 구글 포토에 업로드한다. `--dry-run` 은 필터는 실행하되 업로드는 집계만.
- 테스트 전체: `pytest` / 단일: `pytest tests/test_main.py::test_person_matcher`
- 린트: `ruff check .` / 포맷: `ruff format .`

## 아키텍처

두 개의 **독립 서브패키지**로 구성된다. ① 얼굴 인식 `face_recognition/`(진입점 `RunFaceRecognition`),
② 구글 포토 업로드 `google_photos/`(진입점 `RunGooglePhotosUpload`). 둘은 서로 import 의존이 없다.
이 둘을 잇는 **상위 오케스트라 `orchestrator.py`(`PhotoPipeline`)** 만이 양쪽을 import 하는 최상위 계층이다.
CLI(`main.py`)가 네 서브커맨드를 위임한다: `enroll`/`filter` → 얼굴 인식, `upload` → 구글 포토,
`process` → `PhotoPipeline`(filter→upload 전체).

- **`orchestrator.py` — `PhotoPipeline`**: filter→upload 를 잇는 상위 오케스트라. 입력을 골라
  `output_dir/yyyy-mm/` 로 정리한 뒤 그 폴더를 구글 포토에 업로드한다. 두 러너를 **지연 생성**(dry-run·테스트
  주입 용이). 결과는 `PipelineResult(filter, upload)`.

- **`face_recognition/run_face_recognition.py` — `RunFaceRecognition`**: 얼굴 인식 시스템의 단일 진입점.
  비싼 `FaceDetector` 를 생성자에서 1회 만들어 보유·재사용하며 `enroll()`/`run()`(=filter) 을 위임한다.
  추후 상위 오케스트라는 이 한 클래스만 호출하면 된다.
- **`face_recognition/detector.py` — `FaceDetector`**: InsightFace `FaceAnalysis` 래퍼. 모델 로딩 비용이 크므로
  **인스턴스를 한 번 만들어 재사용**한다(루프 안에서 생성 금지). `detect()` 는 `min_score` 이상 얼굴 목록을
  반환하며 — **디코딩 실패는 `None`, 얼굴 없음은 빈 리스트**로 구분한다. `FaceAnalysis.get()` 이
  검출과 동시에 인식 임베딩(`normed_embedding`)도 채우므로 인물 매칭에 그대로 쓴다.
- **`face_recognition/identity.py` — `enroll_person()` / `PersonMatcher`**: '인식 트레이닝 모델'은 등록한 기준 얼굴들의
  정규화 임베딩 묶음(`Image-processing/<이름>/<이름>.npy`, `(N, 512)` 단일 배열)이다. enroll 은 각 기준 이미지의 **가장 큰 얼굴**을 대상으로 본다.
  매칭은 **코사인 유사도(정규화 임베딩의 내적) ≥ 임계값**(`DEFAULT_THRESHOLD=0.35`)으로 판정하며,
  얼굴 여러 개 중 하나라도 일치하면 통과.
- **`face_recognition/organize.py` — `photo_year_month()` / `unique_dest()`**: 저장 시 폴더(`yyyy-mm`)를 결정한다.
  날짜는 **EXIF 촬영일시(`DateTimeOriginal`) 우선, 없으면 파일 수정시각**으로 폴백. 파일명 충돌 시 `_1`, `_2` 접미사.
- **`face_recognition/pipeline.py` — `filter_folder()` / `FilterResult`**: 검출 오케스트레이션. 이미지별로
  검출 → (matcher 있으면)인물매칭 → 날짜폴더 저장. 결과는 전체/저장/얼굴없음/대상아님/실패 카운트.

### `google_photos/` (구글 포토 업로드, 얼굴 인식과 독립)
- **`run_google_photos.py` — `RunGooglePhotosUpload`**: 단일 진입점. 인증 세션·클라이언트·상태를 보유하고
  폴더 업로드를 위임한다. `dry_run` 은 인증/네트워크 없이 동작하도록 클라이언트를 **지연 생성**한다.
- **`auth.py`**: 데스크톱 OAuth(`InstalledAppFlow`)로 최초 동의 → `token.json` 캐시·갱신. 스코프는
  업로드 전용 **`photoslibrary.appendonly` 하나**(2025-04 이후 readonly/sharing 등은 제거됨).
- **`client.py` — `GooglePhotosClient`**: 저수준 REST(세션 주입). `upload_bytes`(→uploadToken),
  `create_album`, `batch_create`(**최대 50개/배치**, 200/207 처리). 429/5xx 지수 백오프 재시도.
- **`media.py`**: `iter_media()`/`guess_mime()` — face_recognition 미의존 자체 구현(동영상 확장자도 포함).
- **`state.py` — `UploadState`**: `~/.config/child-photo-upload-job/upload_state.json` 에 앨범명→albumId,
  업로드 파일→mediaItemId 기록. 재실행 시 **앨범 재사용·중복 업로드 방지**(idempotent/resume)의 근거.
- **`uploader.py` — `upload_folder()` / `UploadResult`**: `yyyy-mm` 하위폴더명을 앨범으로 그룹화 →
  바이트 업로드 → 50개 청크 `batchCreate`. 결과는 전체/업로드/건너뜀/실패 + 앨범별 분포.

## 환경 / 주의점

- **InsightFace 가 `opencv-python`(non-headless)을 강제 의존**한다. 이 서버에는 GUI 라이브러리가 없어
  import 가 깨지므로 **시스템 패키지가 필요**하다(이미 설치됨):
  `sudo apt-get install -y libgl1 libglib2.0-0 libxcb1 libxext6 libsm6`.
  `opencv-python-headless` 로 우회하려 하지 말 것 — insightface 가 다시 `opencv-python` 을 끌어와 충돌한다.
- 추론 백엔드는 `onnxruntime`(CPU). `--gpu` 사용 시 `onnxruntime-gpu` 와 CUDA가 별도로 필요.
- 최초 실행 시 모델(기본 `buffalo_l`, ~280MB)이 `~/.insightface` 로 자동 다운로드된다(네트워크 필요).
- **정렬된 얼굴 크롭(예: 112×112)은 검출되지 않는다**(검출기는 여백 있는 일반 사진에서 동작). 정상 동작이며
  일반 촬영 사진은 0.85+ 점수로 안정적으로 검출된다. enroll 기준 이미지도 정렬 크롭이 아닌 일반 사진을 쓸 것.
- 한글/유니코드 경로 디코딩은 `np.fromfile` + `cv2.imdecode` 패턴을 유지(=`cv2.imread` 금지).
- **HEIC/HEIF 는 cv2 가 못 읽어 `pillow-heif`(PIL)로 디코딩**한다. `detector.py` 가 import 시 `register_heif_opener()` 를
  호출하므로 `organize.py` 의 EXIF 읽기(`Image.open`)도 HEIC 를 함께 지원한다. PIL 은 RGB 라 InsightFace 용으로 BGR 변환 필요.
  탐색 대상 확장자는 `SUPPORTED_EXTENSIONS`(= `IMAGE_EXTENSIONS` ∪ `HEIF_EXTENSIONS`).
- 런타임 의존성은 bare `pip install` 이 아니라 `pyproject.toml` 의 `dependencies` 에 추가하고 editable 재설치.
- `Image-processing/` 는 등록된 인물 임베딩 저장 상위 폴더로, `Image-processing/<이름>/<이름>.npy` 처럼 인물 이름별로 정리된다(과거 `.npz` 도 로드 호환). 한글 이름은 파일시스템에 따라 NFC/NFD 불일치로 매칭이 깨질 수 있으니 영문 이름(예: `doyun`) 사용을 권장. 아직 git 저장소가 아니다.
- **구글 포토 업로드 OAuth**: 구글 클라우드 콘솔에서 ①프로젝트 생성 ②**Photos Library API** Enable
  ③OAuth 동의 화면(External, 본인을 Test user 로) ④**데스크톱 앱** OAuth 클라이언트 → `client_secret.json`
  다운로드. `upload --client-secret <경로>` 최초 실행 시 브라우저 동의 1회, 이후 `token.json` 자동 재사용.
  `--dry-run` 은 자격증명 없이 동작. `client_secret.json`/`token.json`/`upload_state.json` 은 커밋 금지(민감).
- 구글 포토 API 제약: `batchCreate` 는 **앨범당 50개/배치**, **사용자별 직렬**(429 시 30초+ 대기). API는 이제
  앱이 올린 미디어만 다루며, 동일 바이트는 구글이 자동 dedupe(상태파일이 재업로드·중복앨범 방지).
