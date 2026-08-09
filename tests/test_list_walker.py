"""TASK-10 선행 테스트 — 행 탐지·펼침 앵커·펼침 판정·순회 루프 (FR-02, DES-04 v2).

실기 순회(스크롤 실측·묶음 행 펼침·P-03)는 TASK-12에서 검증하고, 여기서는
img/3~7.png로 행 재탐지, 펼침 마커→패널 앵커 변환, 행별 펼침 상태 판정,
walk() 루프(파싱·멱등·종착)를 검증한다. 격전 보상 배너는 행 아이콘이 없어
자연 배제되어야 한다(3·4.png 배너 구간 client y 456~523).
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from deckscan.nav import list_walker as lw
from deckscan.nav import ui_telegram as ui
from deckscan.nav.navigator import ScreenJudge
from deckscan.store.datastore import DataStore
from deckscan.vision.deck_parser import DeckParser
from tests.test_deck_parser import TROOPS, LEVELS, anchor, client_frame

# 실측 기대값(클라이언트 y, 2026-08-09 img/3~6 스캔): 행 아이콘 top 목록.
# 펼친 행 헤더와 접힌 행은 아이콘 세로 위치가 수 px 다르다(펼침 시 헤더 재스타일).
EXPECTED_ROWS = {
    "3.png": [127, 341, 386, 529, 575],
    "4.png": [127, 341, 386, 529, 575],
    "5.png": [134, 173, 386, 529, 575],
    "6.png": [134, 180, 218, 529, 575],
}


class RowDetectTest(unittest.TestCase):
    def test_row_ys_all_fixtures(self):
        for png, expected in EXPECTED_ROWS.items():
            got = lw.detect_row_ys(client_frame(png))
            self.assertEqual(got, expected, png)

    def test_banner_zone_has_no_rows(self):
        for y in lw.detect_row_ys(client_frame("4.png")):
            self.assertFalse(456 <= y <= 523, f"배너 구간 오탐: {y}")


class PanelAnchorTest(unittest.TestCase):
    def test_anchor_close_to_content_anchor(self):
        for png in ("3.png", "4.png", "5.png", "6.png"):
            got = lw.find_panel_anchor(client_frame(png))
            ref = anchor(png if png != "3.png" else "4.png")
            self.assertIsNotNone(got, png)
            self.assertLessEqual(abs(got - ref), 1, png)

    def test_no_panel_returns_none(self):
        frame = client_frame("4.png").copy()
        x0, y0 = lw.FRIENDLY_SCAN_X0, 0
        frame[:, x0:x0 + 40] = 0  # 마커 열을 지우면 미탐지여야 한다
        self.assertIsNone(lw.find_panel_anchor(frame))

    def test_detected_anchor_parses_correctly(self):
        """탐지 앵커(내용 앵커와 ±1px)로도 파싱이 정확해야 한다 — 5·6.png."""
        with tempfile.TemporaryDirectory() as tmp:
            store = DataStore(":memory:")
            parser = DeckParser(store, Path(tmp), evidence_dir=Path(tmp) / "ev")
            for png in ("5.png", "6.png"):
                frame = client_frame(png)
                rec = parser.parse(frame, lw.find_panel_anchor(frame))
                self.assertEqual(rec.parse_status, "ok", png)
                self.assertEqual([s.troops for s in rec.slots], TROOPS[png], png)
                self.assertEqual([s.level for s in rec.slots], LEVELS[png], png)
            store.close()


class RowExpandedTest(unittest.TestCase):
    def test_expanded_state_per_row(self):
        f4 = client_frame("4.png")
        rows4 = lw.detect_row_ys(f4)
        self.assertEqual([lw.row_expanded(f4, y) for y in rows4],
                         [True, False, False, False, False])
        f7 = client_frame("7.png")
        rows7 = lw.detect_row_ys(f7)
        self.assertEqual([lw.row_expanded(f7, y) for y in rows7[:2]],
                         [True, True])  # 다중 동시 펼침(A-02 v2)

    def test_row_anchor_matches_content_anchor(self):
        self.assertEqual(lw.row_anchor(127), anchor("4.png"))


class FakeCapture:
    """항상 같은 창 프레임 — 스크롤해도 불변(종착 상태 재현)."""

    def __init__(self, window_frame: np.ndarray):
        self.frame = window_frame

    def grab_fresh(self) -> np.ndarray:
        return self.frame


class FlickerCapture:
    """두 프레임을 번갈아 반환 — 전환 연출 중의 일시 렌더 재현."""

    def __init__(self, a: np.ndarray, b: np.ndarray):
        self.frames = [a, b]
        self.i = 0

    def grab_fresh(self) -> np.ndarray:
        self.i += 1
        return self.frames[self.i % 2]


class FakeInput:
    def __init__(self):
        self.clicks: list[tuple[int, int]] = []
        self.wheels: list[tuple[int, int, int]] = []
        self.moves: list[tuple[int, int]] = []

    def click(self, x, y):
        self.clicks.append((x, y))

    def wheel(self, x, y, notches):
        self.wheels.append((x, y, notches))

    def move(self, x, y):
        self.moves.append((x, y))


class StalledCapture:
    """완전 정지 화면 재현 — grab_fresh는 CaptureStalled, grab은 마지막 프레임."""

    def __init__(self, frame: np.ndarray, hwnd: int | None = None):
        self.frame = frame
        if hwnd is not None:
            self.hwnd = hwnd

    def grab_fresh(self, timeout: float = 2.0) -> np.ndarray:
        from deckscan.win.capture import CaptureStalled
        raise CaptureStalled("정지")

    def grab(self) -> np.ndarray:
        return self.frame


class StaticScreenStallTest(unittest.TestCase):
    """TASK-12 결함 C(2026-08-09 실기): WGC는 화면 변화가 없으면 프레임을 보내지
    않아 완전 정지 화면(목록 종착)이 CaptureStalled로 오판돼 run이 aborted됐다.
    창이 살아 있으면 정적 화면=안정으로 수용하고, 창이 사라졌으면 설계 실패
    흐름대로 다시 던져야 한다(죽은 화면 오판 방지 정책 유지)."""

    window = np.zeros((689, 2546, 3), dtype=np.uint8)

    def test_wait_stable_accepts_static_screen(self):
        judge = ScreenJudge(StalledCapture(self.window), (2544, 657))
        self.assertIs(judge.wait_stable(), self.window)

    def test_dead_window_still_raises(self):
        from deckscan.win.capture import CaptureStalled
        judge = ScreenJudge(StalledCapture(self.window, hwnd=0), (2544, 657))
        with self.assertRaises(CaptureStalled):
            judge.fresh()


class WalkTest(unittest.TestCase):
    def test_walk_parses_visible_expanded_rows_idempotently(self):
        """img/7 정지 화면 walk: 펼친 행 2개 파싱(3행은 패널 잘림 — 스크롤 몫),
        스크롤 후 화면 불변 → 종착. 재실행에도 레코드 수 불변(AC-03 오프라인)."""
        window = np.asarray(Image.open(
            Path(__file__).resolve().parents[1] / "img" / "7.png").convert("RGB"))
        with tempfile.TemporaryDirectory() as tmp:
            store = DataStore(":memory:")
            parser = DeckParser(store, Path(tmp), evidence_dir=Path(tmp) / "ev")
            judge = ScreenJudge(FakeCapture(window), (2544, 657))
            fi = FakeInput()
            run = store.create_run()
            walker = lw.ListWalker(judge, fi, parser, store, run,
                                   captures_dir=Path(tmp) / "cap")
            s = walker.walk()
            self.assertEqual(s.processed, 2)
            self.assertEqual(store.battle_count(), 2)
            self.assertEqual(len(fi.wheels), 1)       # 스크롤 1회 → 불변 → 종착
            self.assertEqual(fi.clicks, [])           # 접힌 행 없음 — 클릭 불필요
            # 스크롤 후 커서를 목록 밖에 파킹한다 — 호버가 패널을 확대 렌더로
            # 바꿔 쓰레기 파싱을 만든다(2026-08-09 실기 결함 E, panel_4ffae5).
            self.assertEqual(fi.moves, [ui.MOUSE_PARK])
            for b in store.iter_battles():
                self.assertTrue(Path(b["capture_path"]).is_file())  # NFR-03

            walker2 = lw.ListWalker(judge, fi, parser, store, run,
                                    captures_dir=Path(tmp) / "cap")
            walker2.walk()
            self.assertEqual(store.battle_count(), 2)  # 멱등
            store.close()

    def test_top_boundary_row_skipped(self):
        """목록 상단 경계 가드(TASK-12 결함 B): 아이콘이 목록 위 y인 행은
        파싱하지 않는다. 스크롤은 아래로만 가므로 그 행은 이미 처리된 행이다."""
        window = np.asarray(Image.open(
            Path(__file__).resolve().parents[1] / "img" / "7.png").convert("RGB"))
        rolled = np.roll(window, -30, axis=0)   # 1행 아이콘 127→97 < 목록 top
        with tempfile.TemporaryDirectory() as tmp:
            store = DataStore(":memory:")
            parser = DeckParser(store, Path(tmp), evidence_dir=Path(tmp) / "ev")
            judge = ScreenJudge(FakeCapture(rolled), (2544, 657))
            run = store.create_run()
            walker = lw.ListWalker(judge, FakeInput(), parser, store, run,
                                   captures_dir=Path(tmp) / "cap")
            s = walker.walk()
            self.assertEqual(s.processed, 1)     # 경계 행 제외, 2행만
            store.close()

    def test_invalid_render_is_not_saved(self):
        """무효 렌더(파서가 None 반환)는 저장하지 않고 재파싱도 반복하지 않는다."""
        window = np.asarray(Image.open(
            Path(__file__).resolve().parents[1] / "img" / "7.png").convert("RGB"))

        class NoneParser:
            calls = 0

            def parse(self, frame, anchor):
                type(self).calls += 1
                return None

        with tempfile.TemporaryDirectory() as tmp:
            store = DataStore(":memory:")
            judge = ScreenJudge(FakeCapture(window), (2544, 657))
            run = store.create_run()
            walker = lw.ListWalker(judge, FakeInput(), NoneParser(), store, run,
                                   captures_dir=Path(tmp) / "cap")
            s = walker.walk()
            self.assertEqual(s.processed, 0)
            self.assertEqual(store.battle_count(), 0)
            self.assertEqual(NoneParser.calls, 2)   # 펼친 행 2개 × 1회(픽셀 서명 기억)
            store.close()

    def test_transient_panel_is_not_parsed(self):
        """일시 렌더 방어(2026-08-09 실기 중복 재현): 패널 픽셀이 프레임마다
        흔들리는 행(1행)은 확증 실패로 저장하지 않고, 안정된 행(2행)만 저장."""
        a = np.asarray(Image.open(
            Path(__file__).resolve().parents[1] / "img" / "7.png").convert("RGB"))
        b = a.copy()
        rows = lw.detect_row_ys(a[31:688, 1:2545])
        y0 = 31 + lw.row_anchor(rows[0]) + 60          # 1행 패널 내부(창 좌표)
        b[y0:y0 + 60, 1200:1260] = np.clip(
            b[y0:y0 + 60, 1200:1260].astype(int) + 60, 0, 255).astype(np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            store = DataStore(":memory:")
            parser = DeckParser(store, Path(tmp), evidence_dir=Path(tmp) / "ev")
            judge = ScreenJudge(FlickerCapture(a, b), (2544, 657))
            run = store.create_run()
            walker = lw.ListWalker(judge, FakeInput(), parser, store, run,
                                   captures_dir=Path(tmp) / "cap")
            s = walker.walk()
            self.assertEqual(s.processed, 1)           # 2행만
            self.assertEqual(store.battle_count(), 1)
            store.close()


if __name__ == "__main__":
    unittest.main()
