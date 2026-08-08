"""TASK-07 선행 테스트 — 병력·일시·결과 판독 (ADR-002 결정 5, P-01 실증 재현)."""

import unittest
from pathlib import Path

import numpy as np
from PIL import Image

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
    return _crop(png, (950, 112 + dy, 1045, 195 + dy))


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


class ResultReaderTest(unittest.TestCase):
    def test_win_seal_all_fixtures(self):
        rr = ResultReader()
        for png in PANEL_DY:
            self.assertEqual(rr.read(seal_crop(png)), "승", png)


if __name__ == "__main__":
    unittest.main()
