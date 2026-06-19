# GooglePhotoUploader-WithFaceFilter

입력 폴더의 이미지를 [InsightFace](https://github.com/deepinsight/insightface)로 분석해
**얼굴(또는 등록한 특정 인물)이 있는 이미지만 골라 촬영 연-월(`yyyy-mm`)별로 정리**하고,
정리된 결과를 **구글 포토에 앨범별로 업로드**하는 CLI 도구입니다.

> 파이썬 패키지/콘솔 명령 이름은 `child-photo-upload-job` 입니다.

## 기능 개요

- **얼굴/인물 필터링** — 등록한 인물만 골라내거나, 얼굴이 있는 사진만 골라냄
- **날짜별 정리** — EXIF 촬영일시(없으면 파일 수정시각) 기준 `yyyy-mm` 폴더로 분류
- **HEIC/HEIF 지원** — 아이폰 사진(HEIC)도 디코딩
- **구글 포토 업로드** — `yyyy-mm` 폴더명을 앨범명으로 매핑해 업로드(재실행 시 중복 방지)

내부는 서로 독립된 두 서브패키지(`face_recognition/`, `google_photos/`)와, 둘을 잇는
상위 오케스트라(`orchestrator.py` — `PhotoPipeline`)로 구성됩니다.

## 설치

Python 3.11 이상이 필요합니다.

### Linux / macOS

```bash
# (리눅스 서버/헤드리스 환경만) opencv-python 에 필요한 시스템 라이브러리
sudo apt-get install -y libgl1 libglib2.0-0 libxcb1 libxext6 libsm6

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Windows

PowerShell 기준입니다. (위의 `apt-get` 시스템 라이브러리 단계는 **리눅스 전용**이라 Windows에서는 불필요합니다.)

```powershell
# 1) Python 3.11+ 설치 (https://www.python.org/downloads/ — 설치 시 "Add Python to PATH" 체크)

# 2) 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\Activate.ps1
#  ↑ 실행 정책 오류 시(한 번만):
#    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#  cmd.exe 를 쓴다면: .venv\Scripts\activate.bat

# 3) 설치
pip install -e ".[dev]"
```

> - 최초 실행 시 InsightFace 모델(`buffalo_l`, 약 280MB)이 `~/.insightface`
>   (Windows: `C:\Users\<사용자>\.insightface`)로 자동 다운로드됩니다(네트워크 필요).
> - Windows/macOS 에서는 `opencv-python`·`pillow-heif` 휠이 그대로 설치되어 HEIC 포함 정상 동작합니다.
> - 명령은 콘솔 스크립트 `child-photo-upload-job ...` 또는
>   `python -m child_photo_upload_job.main ...` 둘 다 동일합니다.
> - 아래 예시의 줄바꿈 `\`(역슬래시)는 **bash 기준**입니다. PowerShell 에서는 백틱(`` ` ``)을 쓰거나
>   한 줄로 이어서 입력하세요.

## 사용법

### 1) 특정 인물 등록 (선택)

대상 인물의 기준 사진 폴더로 인식 임베딩을 만들어 `Image-processing/<이름>/<이름>.npy` 에 저장합니다.

```bash
child-photo-upload-job enroll doyun ./기준사진
# -> Image-processing/doyun/doyun.npy 생성
```

> - 기준 사진은 **얼굴이 또렷한 일반 촬영 사진** 여러 장을 권장합니다(정렬된 작은 크롭은 검출 안 됨).
> - 한 장에 얼굴이 여럿이면 **가장 큰 얼굴**을 대상으로 등록합니다.
> - 인물 이름은 파일시스템 유니코드(NFC/NFD) 문제를 피하려면 **영문 권장**(예: `doyun`).

### 2) 골라내기 (날짜별 정리)

```bash
# 등록한 인물만 골라 yyyy-mm 폴더로 정리
child-photo-upload-job filter ./입력폴더 ./출력폴더 --person doyun

# 인물 구분 없이 '얼굴이 있는' 모든 이미지
child-photo-upload-job filter ./입력폴더 ./출력폴더
```

출력 예시:

```
출력폴더/
├── 2024-08/
│   └── group.jpg
└── 2025-03/
    └── ...
```

### 3) 구글 포토 업로드

정리된 폴더(보통 `filter` 결과)를 구글 포토에 올립니다. `yyyy-mm` 하위폴더명이 앨범명이 됩니다.

```bash
# 네트워크/인증 없이 무엇이 올라갈지 미리보기
child-photo-upload-job upload ./출력폴더 --dry-run

# 실제 업로드(최초 1회 브라우저 동의)
child-photo-upload-job upload ./출력폴더 --client-secret ./client_secret.json
```

> 구글 포토 OAuth 준비는 아래 [구글 포토 업로드 준비](#구글-포토-업로드-준비) 참고.
> 같은 폴더를 다시 올려도 상태 파일로 **이미 올린 파일은 건너뜁니다**(중복/중복앨범 방지).

### 4) 전체 파이프라인 (filter → upload 한 번에)

```bash
child-photo-upload-job process ./입력폴더 ./출력폴더 \
  --person doyun --client-secret ./client_secret.json

# 필터는 실행하되 업로드는 미리보기만
child-photo-upload-job process ./입력폴더 ./출력폴더 --person doyun --dry-run
```

### 주요 옵션

**filter / process (검출·정리)**

| 옵션 | 설명 |
|------|------|
| `--person <이름>` | 등록된 해당 인물만 골라냄 (생략 시 얼굴 유무만 판정) |
| `--match-threshold <float>` | 인물 일치 코사인 임계값 (기본 0.35, 높을수록 엄격) |
| `-r, --recursive` | 입력 하위 폴더까지 탐색 |
| `--move` | 복사 대신 이동 |
| `--flat` | 날짜별 정리 없이 평평하게 저장 |
| `--min-score <float>` | 얼굴 최소 검출 점수 (기본 0.5) |
| `--gpu` | GPU(CUDA) 사용 (`onnxruntime-gpu`·CUDA 별도 필요) |
| `-v, --verbose` | 이미지별 처리 로그 |

**upload / process (구글 포토)**

| 옵션 | 설명 |
|------|------|
| `--client-secret <json>` | 구글 OAuth 데스크톱 클라이언트 시크릿 (실제 업로드에 필요) |
| `--dry-run` | 업로드 없이 예정 집계만 출력(인증 불필요) |
| `--no-album` | 앨범 없이 라이브러리에 업로드 |
| `--token <path>` | 토큰 캐시 경로 (기본 `~/.config/child-photo-upload-job/token.json`) |
| `--state <path>` | 업로드 상태 파일 경로 (기본 `~/.config/.../upload_state.json`) |

## 구글 포토 업로드 준비

업로드에는 본인 구글 계정의 **OAuth 데스크톱 클라이언트**가 한 번 필요합니다.

1. [Google Cloud Console](https://console.cloud.google.com) 에서 프로젝트 생성/선택
2. **Photos Library API** 사용 설정(Enable)
3. **OAuth 동의 화면**: External, 본인 계정을 Test user 로 추가, 스코프 `photoslibrary.appendonly`
4. **사용자 인증 정보 → OAuth 클라이언트 ID → 애플리케이션 유형: 데스크톱 앱** → `client_secret.json` 다운로드
5. `--client-secret ./client_secret.json` 로 전달 — 최초 실행 시 브라우저 동의 1회,
   이후 `token.json` 이 자동 재사용됩니다.

> 2025-04 이후 구글 포토 API는 **앱이 올린 미디어만** 다루며, 업로드/앨범 생성은 `appendonly`
> 스코프로 동작합니다. `batchCreate` 는 앨범당 50개/배치 제한이 있어 내부에서 자동 분할합니다.

> ⚠️ `client_secret.json`·`token.json`·`upload_state.json`·`Image-processing/` 는 민감 정보라
> `.gitignore` 로 커밋에서 제외됩니다.

## 구조

```
src/child_photo_upload_job/
├── main.py                # CLI (enroll / filter / upload / process)
├── face_recognition/      # 얼굴 인식 (독립) — RunFaceRecognition
│   ├── detector.py        #   InsightFace 검출 + HEIC 디코딩
│   ├── identity.py        #   인물 등록(.npy)·매칭
│   ├── organize.py        #   yyyy-mm 폴더 결정(EXIF/수정시각)
│   └── pipeline.py        #   검출→매칭→저장
├── google_photos/         # 구글 포토 업로드 (독립) — RunGooglePhotosUpload
│   ├── auth.py            #   OAuth(appendonly)
│   ├── client.py          #   REST(upload/album/batchCreate)
│   ├── media.py state.py  #   미디어 탐색 / 업로드 상태(resume)
│   └── uploader.py        #   앨범 그룹화·50개 청크 업로드
└── orchestrator.py        # 상위 오케스트라 — PhotoPipeline (filter→upload)
```

## 개발

```bash
pytest                          # 테스트
ruff check . && ruff format .   # 린트 & 포맷
```
