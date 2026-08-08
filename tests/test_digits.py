"""TASK-06 선행 테스트 — 레벨 숫자 판독 (FR-03 부분, ADR-002 결정 4)."""

import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from deckscan.vision.digits import DigitReader

IMG = Path(__file__).resolve().parents[1] / "img"
_S = 2546 / 2000
CARD_LEFTS = [630, 726, 822, 1103, 1199, 1295]
PANEL_DY = {"4.png": 0, "5.png": 37, "6.png": 72}
EXPECTED = {
    "4.png": ["50", "50", "50", "50", "49", "50"],
    "5.png": ["50", "50", "50", "50", "50", "50"],
    "6.png": ["50", "50", "50", "50", "50", "50"],
}


def name_bar(png: str, card: int) -> np.ndarray:
    dy = PANEL_DY[png]
    cl = CARD_LEFTS[card]
    box = tuple(round(v * _S) for v in (cl - 2, 233 + dy, cl + 80, 252 + dy))
    return np.asarray(Image.open(IMG / png).convert("RGB").crop(box))


class LevelReadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = DigitReader()

    def test_all_fixture_levels(self):
        """18개 이름 바에서 레벨을 전부 정확히 읽는다 (분리 '0'은 복구 패스)."""
        failures = []
        for png, expected in EXPECTED.items():
            for card, exp in enumerate(expected):
                strip = name_bar(png, card)
                got = self.reader.read(strip)
                if got != exp:
                    got = self.reader.read(strip, repair=True)
                if got != exp:
                    failures.append(f"{png} card{card}: exp {exp} got {got!r}")
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
