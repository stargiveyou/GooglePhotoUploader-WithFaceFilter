"""CLI 진입점.

서브커맨드:
  enroll  : 대상 인물의 기준 이미지로 인식 모델(임베딩)을 등록한다.
  filter  : 입력 폴더에서 (선택한 인물의) 얼굴이 있는 이미지만 날짜별로 골라 저장한다.
  upload  : 정리된 폴더를 구글 포토에 업로드한다(yyyy-mm 하위폴더 → 앨범).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from child_photo_upload_job.face_recognition import DEFAULT_THRESHOLD, RunFaceRecognition

DEFAULT_MODEL_DIR = Path("Image-processing")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="child-photo-upload-job",
        description="InsightFace로 얼굴(또는 특정 인물)이 있는 이미지만 날짜별로 골라냅니다.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # 공통 검출 옵션
    def add_detector_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument("--gpu", action="store_true", help="GPU(CUDA) 사용")
        p.add_argument("--model", default="buffalo_l", help="InsightFace 모델 (기본: buffalo_l)")
        p.add_argument(
            "--min-score", type=float, default=0.5, help="얼굴 최소 검출 점수 (기본: 0.5)"
        )
        p.add_argument("-v", "--verbose", action="store_true", help="이미지별 로그 출력")

    # enroll
    pe = sub.add_parser("enroll", help="대상 인물 등록(임베딩 저장)")
    pe.add_argument("name", help="인물 이름(모델 파일명으로 사용)")
    pe.add_argument("reference_dir", type=Path, help="대상 인물의 기준 이미지 폴더")
    pe.add_argument(
        "--model-dir",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help="모델 저장 상위 폴더, 인물 이름별로 정리됨 (기본: Image-processing)",
    )
    add_detector_opts(pe)

    # filter
    pf = sub.add_parser("filter", help="얼굴/인물 이미지 골라내기")
    pf.add_argument("input_dir", type=Path, help="검사할 입력 폴더")
    pf.add_argument("output_dir", type=Path, help="결과 저장 폴더")
    pf.add_argument(
        "--person",
        nargs="+",
        help="등록된 인물(들)만 골라냄. 여러 명이면 OR 매칭(생략 시 얼굴 유무만 판정)",
    )
    pf.add_argument(
        "--model-dir",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help="모델 상위 폴더, 인물 이름별로 정리됨 (기본: Image-processing)",
    )
    pf.add_argument(
        "--match-threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"인물 일치 코사인 임계값 (기본: {DEFAULT_THRESHOLD})",
    )
    pf.add_argument("-r", "--recursive", action="store_true", help="하위 폴더까지 탐색")
    pf.add_argument("--move", action="store_true", help="복사 대신 이동")
    pf.add_argument("--flat", action="store_true", help="날짜별 정리 없이 평평하게 저장")
    add_detector_opts(pf)

    # upload
    pu = sub.add_parser("upload", help="정리된 폴더를 구글 포토에 업로드")
    pu.add_argument("folder", type=Path, help="업로드할 폴더(보통 filter 결과)")
    pu.add_argument(
        "--client-secret",
        type=Path,
        help="구글 OAuth 데스크톱 클라이언트 시크릿 JSON 경로(최초 동의에 필요)",
    )
    pu.add_argument("--token", type=Path, default=None, help="토큰 캐시 경로(기본: ~/.config/...)")
    pu.add_argument(
        "--state", type=Path, default=None, help="업로드 상태 파일 경로(기본: ~/.config/...)"
    )
    pu.add_argument("--no-album", action="store_true", help="앨범 없이 라이브러리에 업로드")
    pu.add_argument(
        "--no-recursive", action="store_true", help="하위 폴더 탐색 안 함(기본: 재귀 탐색)"
    )
    pu.add_argument(
        "--dry-run", action="store_true", help="업로드 없이 예정 집계만 출력(인증 불필요)"
    )
    pu.add_argument("-v", "--verbose", action="store_true", help="상세 로그 출력")

    # process (filter → upload 전체 파이프라인)
    pp = sub.add_parser("process", help="골라내기 후 구글 포토 업로드까지 한 번에")
    pp.add_argument("input_dir", type=Path, help="검사할 입력 폴더")
    pp.add_argument("output_dir", type=Path, help="정리 저장 폴더(업로드 대상)")
    pp.add_argument("--person", help="이 이름으로 등록된 인물만 골라냄(생략 시 얼굴 유무만 판정)")
    pp.add_argument(
        "--model-dir",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help="모델 상위 폴더 (기본: Image-processing)",
    )
    pp.add_argument(
        "--match-threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"인물 일치 코사인 임계값 (기본: {DEFAULT_THRESHOLD})",
    )
    pp.add_argument("-r", "--recursive", action="store_true", help="입력 하위 폴더까지 탐색")
    pp.add_argument("--move", action="store_true", help="복사 대신 이동")
    pp.add_argument("--flat", action="store_true", help="날짜별 정리 없이 평평하게 저장")
    pp.add_argument(
        "--client-secret", type=Path, help="구글 OAuth 데스크톱 클라이언트 시크릿 JSON 경로"
    )
    pp.add_argument("--token", type=Path, default=None, help="토큰 캐시 경로(기본: ~/.config/...)")
    pp.add_argument(
        "--state", type=Path, default=None, help="업로드 상태 파일 경로(기본: ~/.config/...)"
    )
    pp.add_argument("--no-album", action="store_true", help="앨범 없이 라이브러리에 업로드")
    pp.add_argument(
        "--dry-run", action="store_true", help="필터는 실행하되 업로드는 집계만(인증 불필요)"
    )
    add_detector_opts(pp)
    return parser


def _make_runner(args: argparse.Namespace) -> RunFaceRecognition:
    return RunFaceRecognition(
        model_name=args.model,
        use_gpu=args.gpu,
        min_score=args.min_score,
        model_dir=args.model_dir,
    )


def _cmd_enroll(args: argparse.Namespace) -> int:
    if not args.reference_dir.is_dir():
        print(f"기준 이미지 폴더가 없습니다: {args.reference_dir}", file=sys.stderr)
        return 1
    out, used = _make_runner(args).enroll(args.name, args.reference_dir)
    print(f"등록 완료: '{args.name}' (이미지 {used}장) -> {out}")
    return 0


def _cmd_filter(args: argparse.Namespace) -> int:
    if not args.input_dir.is_dir():
        print(f"입력 폴더가 없습니다: {args.input_dir}", file=sys.stderr)
        return 1

    runner = _make_runner(args)
    try:
        result = runner.run(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            person=args.person,
            match_threshold=args.match_threshold,
            recursive=args.recursive,
            move=args.move,
            by_date=not args.flat,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        f"완료: 전체 {result.total}장 / 저장 {result.saved}장 / "
        f"얼굴없음 {result.no_face}장 / 대상아님 {result.no_match}장 / 실패 {result.failed}장"
    )
    return 0


def _cmd_upload(args: argparse.Namespace) -> int:
    if not args.folder.is_dir():
        print(f"업로드할 폴더가 없습니다: {args.folder}", file=sys.stderr)
        return 1
    if not args.dry_run and not args.client_secret:
        print("업로드에는 --client-secret 가 필요합니다(또는 --dry-run).", file=sys.stderr)
        return 1

    # 지연 import: 구글 포토 의존성은 upload 에서만 필요
    from child_photo_upload_job.google_photos import RunGooglePhotosUpload
    from child_photo_upload_job.google_photos.auth import DEFAULT_TOKEN_PATH
    from child_photo_upload_job.google_photos.state import DEFAULT_STATE_PATH

    runner = RunGooglePhotosUpload(
        client_secret=args.client_secret,
        token_path=args.token or DEFAULT_TOKEN_PATH,
        state_path=args.state or DEFAULT_STATE_PATH,
    )
    try:
        result = runner.run(
            folder=args.folder,
            by_album=not args.no_album,
            recursive=not args.no_recursive,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    verb = "업로드예정" if args.dry_run else "업로드"
    print(
        f"완료: 전체 {result.total}개 / {verb} {result.uploaded}개 / "
        f"건너뜀 {result.skipped}개 / 실패 {result.failed}개"
    )
    for album, n in sorted(result.per_album.items()):
        print(f"  앨범 {album}: {n}개")
    return 0


def _cmd_process(args: argparse.Namespace) -> int:
    if not args.input_dir.is_dir():
        print(f"입력 폴더가 없습니다: {args.input_dir}", file=sys.stderr)
        return 1
    if not args.dry_run and not args.client_secret:
        print("업로드에는 --client-secret 가 필요합니다(또는 --dry-run).", file=sys.stderr)
        return 1

    # 지연 import: 구글 포토 의존성은 process/upload 에서만 필요
    from child_photo_upload_job.google_photos.auth import DEFAULT_TOKEN_PATH
    from child_photo_upload_job.google_photos.state import DEFAULT_STATE_PATH
    from child_photo_upload_job.orchestrator import PhotoPipeline

    pipeline = PhotoPipeline(
        model_name=args.model,
        use_gpu=args.gpu,
        min_score=args.min_score,
        model_dir=args.model_dir,
        client_secret=args.client_secret,
        token_path=args.token or DEFAULT_TOKEN_PATH,
        state_path=args.state or DEFAULT_STATE_PATH,
    )
    try:
        result = pipeline.run(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            person=args.person,
            match_threshold=args.match_threshold,
            recursive=args.recursive,
            move=args.move,
            by_date=not args.flat,
            by_album=not args.no_album,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    f, u = result.filter, result.upload
    print(
        f"[필터] 전체 {f.total}장 / 저장 {f.saved}장 / "
        f"얼굴없음 {f.no_face}장 / 대상아님 {f.no_match}장 / 실패 {f.failed}장"
    )
    verb = "업로드예정" if args.dry_run else "업로드"
    print(
        f"[업로드] 전체 {u.total}개 / {verb} {u.uploaded}개 / "
        f"건너뜀 {u.skipped}개 / 실패 {u.failed}개"
    )
    for album, n in sorted(u.per_album.items()):
        print(f"  앨범 {album}: {n}개")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s"
    )
    if args.command == "enroll":
        return _cmd_enroll(args)
    if args.command == "upload":
        return _cmd_upload(args)
    if args.command == "process":
        return _cmd_process(args)
    return _cmd_filter(args)


if __name__ == "__main__":
    raise SystemExit(main())
