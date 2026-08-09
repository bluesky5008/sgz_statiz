"""TASK-07 선행 테스트 — 병력·일시·결과 판독 (ADR-002 결정 5, P-01 실증 재현)."""

import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from deckscan.nav import ui_telegram as ui
from deckscan.vision.ocr import OcrReader, ResultReader

IMG = Path(__file__).resolve().parents[1] / "img"
_S = 2546 / 2000
CARD_LEFTS = [630, 726, 822, 1103, 1199, 1295]
PANEL_DY = {"4.png": 0, "5.png": 37, "6.png": 72}
TROOPS = {
    "4.png": [8783, 9868, 9677, 6412, 8762, 7676],
    "5.png": [9486, 9958, 10433, 6796, 6791, 7163],
    "6.png": [10000, 10000, 10600, 8684, 8983, 9512],
}


def _crop(png: str, box_disp) -> np.ndarray:
    box = tuple(round(v * _S) for v in box_disp)
    return np.asarray(Image.open(IMG / png).convert("RGB").crop(box))


def troop_strip(png: str, card: int) -> np.ndarray:
    dy = PANEL_DY[png]
    cl = CARD_LEFTS[card]
    return _crop(png, (cl - 8, 251 + dy, cl + 88, 269 + dy))


def date_strip(png: str) -> np.ndarray:
    dy = PANEL_DY[png]
    return _crop(png, (915, 256 + dy, 1082, 274 + dy))


def seal_crop(png: str) -> np.ndarray:
    dy = PANEL_DY[png]
    return _crop(png, (955, 142 + dy, 1040, 210 + dy))  # 글리프 전용(위치 텍스트 제외)


class OcrReaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ocr = OcrReader()

    def test_troops_all_fixtures(self):
        failures = []
        for png, expected in TROOPS.items():
            for card, exp in enumerate(expected):
                got = self.ocr.read_number(troop_strip(png, card))
                if got != exp:
                    failures.append(f"{png} card{card}: exp {exp} got {got}")
        self.assertEqual(failures, [])

    def test_datetime_all_fixtures(self):
        for png in PANEL_DY:
            self.assertEqual(self.ocr.read_datetime(date_strip(png)),
                             "2026-08-08T22:58:47", png)


def panel_crop(png: str, box: tuple[int, int, int, int]) -> np.ndarray:
    """PANEL_REGION 크기 저장 캡처(img/panel_*.png)에서 필드 상자를 자른다."""
    px, py = ui.PANEL_REGION[0], ui.PANEL_REGION[1]
    img = np.asarray(Image.open(IMG / png).convert("RGB"))
    return img[box[1] - py:box[3] - py, box[0] - px:box[2] - px]


class RenderVariantTest(unittest.TestCase):
    """2026-08-09 실기 scan run2 오독 렌더 회귀 픽스처 (TASK-12 결함 D).

    같은 전보의 재렌더에서 숫자 '0'의 상하 획이 어두워지면 이진화에서 좌우
    호만 남아 OCR이 '0'을 '()'로 읽거나(10600→106, 10000→0) 인식을 거부했고
    (→None), 일시는 시:분 콜론이 소실됐다("0134:42"→불일치). 오독 값이 그대로
    battle_key에 들어가 같은 전보가 다른 키로 중복 저장됐다(FR-05 위반).
    """

    @classmethod
    def setUpClass(cls):
        cls.ocr = OcrReader()

    def test_broken_zero_troops_read_correctly(self):
        cases = [("panel_081141.png", ui.TROOPS_BOXES[0], 10600),
                 ("panel_081141.png", ui.TROOPS_BOXES[2], 10000),
                 ("panel_e1423b.png", ui.TROOPS_BOXES[5], 10000)]
        failures = []
        for png, box, exp in cases:
            got = self.ocr.read_number(panel_crop(png, box))
            if got != exp:
                failures.append(f"{png} {box}: exp {exp} got {got}")
        self.assertEqual(failures, [])

    def test_datetime_missing_colon_read_correctly(self):
        self.assertEqual(self.ocr.read_datetime(
            panel_crop("panel_fa584b.png", ui.DATE_BOX)),
            "2026-08-09T01:34:42")


class ResultReaderTest(unittest.TestCase):
    def test_win_seal_all_fixtures(self):
        rr = ResultReader()
        for png in PANEL_DY:
            self.assertEqual(rr.read(seal_crop(png)), "승", png)


if __name__ == "__main__":
    unittest.main()
