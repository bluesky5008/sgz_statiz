"""TASK-10 선행 테스트(픽스처 부분) — 행 헤더 탐지·펼침 패널 앵커 (FR-02, DES-04).

순회(클릭·스크롤) 자체는 실기 검증(TASK-12)이며, 여기서는 img/3~6.png로
행 재탐지와 펼침 마커→패널 앵커 변환을 검증한다. 격전 보상 배너는 행
아이콘이 없어 자연 배제되어야 한다(3·4.png 배너 구간 client y 456~523).
"""

import tempfile
import unittest
from pathlib import Path

from deckscan.nav import list_walker as lw
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


if __name__ == "__main__":
    unittest.main()
