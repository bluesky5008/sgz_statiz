"""deckscan CLI (설계 DES-10): scan | export | label | probe."""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from PIL import Image

from .win import session
from .win.capture import WgcCapture
from .win.input import PostMessageInput

PROBE_DIR = Path("output") / "probe"
DEFAULT_DB = str(Path("output") / "deckscan.db")
DEFAULT_EXPORT_DIR = str(Path("output") / "export")


def _resolve_session(hwnd_arg: int | None) -> session.WindowSession | None:
    """FR-08(DCR-002) 창 확정: --hwnd 생략 경로, 단일 자동, 다중 대화형 선택.

    비대화형 실행(stdin이 콘솔 아님)에서 다중 후보면 프롬프트 대기 없이
    후보 목록과 함께 거부한다 — 에이전트 실행기 보호.
    """
    if hwnd_arg is not None:
        return session.WindowSession(hwnd_arg)
    wins = session.find_client_windows()
    if not wins:
        print("대상 창 없음")
        return None
    if len(wins) > 1 and not sys.stdin.isatty():
        for w in wins:
            print(f"hwnd={w.hwnd:#x} pid={w.pid} rect={w.rect}")
        print("같은 제목의 창이 여러 개입니다 — 비대화형 실행은 --hwnd로 지정하세요")
        return None
    from .controller import choose_window
    from .win import win32
    chosen = choose_window(wins, input, win32.raise_to_top)
    if chosen is None:
        print("창 선택 중단")
        return None
    print(f"대상 창: hwnd={chosen.hwnd:#x} pid={chosen.pid} rect={chosen.rect}")
    return session.WindowSession(chosen.hwnd)


def _snap(cap: WgcCapture, tag: str) -> Path:
    frame = cap.grab_fresh()
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%H%M%S")
    path = PROBE_DIR / f"snap_{ts}_{tag}.png"
    Image.fromarray(frame).save(path)
    print(f"snapshot: {path}  frame={frame.shape[1]}x{frame.shape[0]}")
    return path


def cmd_probe(args: argparse.Namespace) -> int:
    for w in session.find_client_windows():
        print(f"hwnd={w.hwnd:#x} pid={w.pid} elevated={w.elevated} "
              f"rect={w.rect} client={w.client} title='{w.title}'")
    ws = _resolve_session(args.hwnd)
    if ws is None:
        return 1
    if args.click:
        ws.check_permission()   # 입력은 UIPI 제약 — 스냅샷만이면 승격 불필요
    info = ws.info()
    print(f"attached: hwnd={info.hwnd:#x} client={info.client}")
    with WgcCapture(info.hwnd, info.title) as cap:
        _snap(cap, "probe")
        if args.click:
            x, y = args.click
            inp = PostMessageInput(info.hwnd)
            inp.click(x, y)
            print(f"click: ({x},{y}) [클라이언트 좌표]")
            import time
            time.sleep(args.settle)
            _snap(cap, f"after_{x}x{y}")
    return 0


REQUIRED_CLIENT = (2544, 657)   # NFR-04 — 캘리브레이션 전제 해상도


def cmd_scan(args: argparse.Namespace) -> int:
    from .controller import run_scan
    from .nav.list_walker import ListWalker
    from .nav.navigator import ScreenJudge
    from .nav.telegram import TelegramNavigator
    from .store.datastore import DataStore
    from .vision.deck_parser import DeckParser

    ws = _resolve_session(args.hwnd)
    if ws is None:
        return 1
    try:
        ws.check_permission()
    except Exception as e:
        print(f"입력 권한 없음: {e}")
        return 1
    info = ws.info()
    if info.client != REQUIRED_CLIENT:
        print(f"클라이언트 크기 {info.client} ≠ {REQUIRED_CLIENT} — 실행 거부(NFR-04)")
        return 1

    root = Path.cwd()
    with DataStore(args.db) as store, \
            WgcCapture(info.hwnd, info.title) as cap:
        judge = ScreenJudge(cap, info.client)
        inp = PostMessageInput(info.hwnd)
        nav = TelegramNavigator(judge, inp)
        parser = DeckParser(store, root)

        def make_walker(run_id: int) -> ListWalker:
            return ListWalker(judge, inp, parser, store, run_id,
                              max_items=args.max_items,
                              scroll=not args.no_scroll)

        code, summary = run_scan(store, nav, make_walker)
    print(summary)
    return code


def cmd_export(args: argparse.Namespace) -> int:
    from .store.csv_export import export_csv
    from .store.datastore import DataStore

    with DataStore(args.db) as store:
        for path in export_csv(store, args.out):
            print(f"export: {path}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    import sqlite3

    from .stats.aggregate import collect
    from .stats.csv_out import export_stats_csv
    from .stats.report import render_report

    if not Path(args.db).is_file():
        print(f"DB 없음: {args.db}")
        return 1
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)   # NFR-01 읽기 전용
    try:
        try:
            stats = collect(conn, alliance=args.alliance)
        except ValueError as e:
            print(e)
            return 1
    finally:
        conn.close()
    if not stats["battle_count"]:
        print("전보 데이터가 없습니다 — scan을 먼저 실행하세요")
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    import datetime as dt
    report = out / f"report_{dt.datetime.now():%Y%m%d}.html"
    report.write_text(render_report(stats), encoding="utf-8")
    print(f"report: {report}")
    for p in export_stats_csv(stats, out):
        print(f"csv: {p}")
    return 0


def cmd_label(args: argparse.Namespace) -> int:
    import os

    from .controller import label_pending
    from .store.datastore import DataStore

    with DataStore(args.db) as store:
        n = label_pending(store, lambda prompt: input(prompt),
                          opener=os.startfile)
        print(f"라벨 확정 {n}건")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="deckscan",
                                description="동맹 전보(교전) 덱 정보 추출 도구")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("scan", help="교전 전보 순회·추출 실행")
    ps.add_argument("--hwnd", type=lambda s: int(s, 0), default=None)
    ps.add_argument("--max-items", type=int, default=None,
                    help="처리할 전보 수 상한 (기본: 전체)")
    ps.add_argument("--no-scroll", action="store_true",
                    help="화면에 보이는 행만 처리(스크롤 생략)")
    ps.add_argument("--db", default=DEFAULT_DB)
    ps.set_defaults(func=cmd_scan)

    pp = sub.add_parser("probe", help="창 진단·스냅샷 (캘리브레이션용)")
    pp.add_argument("--hwnd", type=lambda s: int(s, 0), default=None)
    pp.add_argument("--click", type=int, nargs=2, metavar=("X", "Y"),
                    help="캘리브레이션용 클릭(클라이언트 좌표) 후 재스냅샷")
    pp.add_argument("--settle", type=float, default=1.5,
                    help="클릭 후 스냅샷까지 대기 초")
    pp.set_defaults(func=cmd_probe)

    pe = sub.add_parser("export", help="CSV 내보내기 (battles·deck_long)")
    pe.add_argument("--db", default=DEFAULT_DB)
    pe.add_argument("--out", default=DEFAULT_EXPORT_DIR)
    pe.set_defaults(func=cmd_export)

    pl = sub.add_parser("label", help="pending 식별자 라벨 확정")
    pl.add_argument("--db", default=DEFAULT_DB)
    pl.set_defaults(func=cmd_label)

    pt = sub.add_parser("stats", help="교전 통계 HTML 리포트·CSV 생성")
    pt.add_argument("--db", default=DEFAULT_DB)
    pt.add_argument("--out", default=str(Path("output") / "stats"))
    pt.add_argument("--alliance", default=None,
                    help="아군 동맹 라벨 또는 ID (기본: 최빈 동맹 자동 추정)")
    pt.set_defaults(func=cmd_stats)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
