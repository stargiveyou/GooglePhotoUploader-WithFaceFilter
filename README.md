# child-photo-upload-job

입력 폴더의 이미지를 [InsightFace](https://github.com/deepinsight/insightface)로 분석해,
**얼굴(또는 등록한 특정 인물)이 있는 이미지만 골라 촬영 연-월(`yyyy-mm`)별로 정리 저장**하는 도구입니다.

## 설치

```bash
# (서버/헤드리스 환경) opencv-python 에 필요한 시스템 라이브러리
sudo apt-get install -y libgl1 libglib2.0-0 libxcb1 libxext6 libsm6

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

> 최초 실행 시 InsightFace 모델(buffalo_l, 약 280MB)이 `~/.insightface` 로 자동 다운로드됩니다.

## 사용법

### 1) 특정 인물 등록 (선택)

대상 인물의 기준 사진 폴더로 인식 모델(임베딩)을 만들어 `models/` 에 저장합니다.

```bash
child-photo-upload-job enroll 우리아이 ./기준사진
# -> models/우리아이.npz 생성
```

> 기준 사진은 **얼굴이 또렷한 일반 촬영 사진** 여러 장을 권장합니다(정렬된 작은 크롭은 검출 안 됨).
> 한 장에 얼굴이 여럿이면 **가장 큰 얼굴**을 대상으로 등록합니다.

### 2) 골라내기 (날짜별 정리)

```bash
# 등록한 인물만 골라 yyyy-mm 폴더로 정리
child-photo-upload-job filter ./입력폴더 ./출력폴더 --person 우리아이

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

날짜는 **EXIF 촬영일시 우선, 없으면 파일 수정시각**을 사용합니다.

### 주요 옵션 (filter)

| 옵션 | 설명 |
|------|------|
| `--person <이름>` | 등록된 해당 인물만 골라냄 (생략 시 얼굴 유무만 판정) |
| `--match-threshold <float>` | 인물 일치 코사인 임계값 (기본 0.35, 높을수록 엄격) |
| `-r, --recursive` | 하위 폴더까지 탐색 |
| `--move` | 복사 대신 이동 |
| `--flat` | 날짜별 정리 없이 평평하게 저장 |
| `--min-score <float>` | 얼굴 최소 검출 점수 (기본 0.5) |
| `--gpu` | GPU(CUDA) 사용 |
| `-v, --verbose` | 이미지별 처리 로그 |

## 개발

```bash
pytest                          # 테스트
ruff check . && ruff format .   # 린트 & 포맷
```
