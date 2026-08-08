"""TASK-05 선행 테스트 — IdentityMatcher (FR-07, AC-06 부분, ADR-002)."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from deckscan.store.datastore import DataStore
from deckscan.vision.identity import IdentityMatcher

IMG = Path(__file__).resolve().parents[1] / "img"
_S = 2546 / 2000  # 참고 이미지 표시 좌표 -> 원본 배율 (스파이크 실측 재사용)


def _crop(png: str, box_disp: tuple[int, int, int, int]) -> np.ndarray:
    box = tuple(round(v * _S) for v in box_disp)
    return np.asarray(Image.open(IMG / png).convert("RGB").crop(box))


def _att_user(png: str, dy: int) -> np.ndarray:
    return _crop(png, (820, 122 + dy, 910, 140 + dy))


def _def_user(png: str, dy: int) -> np.ndarray:
    return _crop(png, (1080, 122 + dy, 1170, 140 + dy))


class IdentityMatcherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = DataStore(":memory:")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _matcher(self):
        return IdentityMatcher(self.store, self.root, "user")

    def test_first_seen_registers_pending(self):
        m = self._matcher()
        iid, score, new = m.resolve(_att_user("4.png", 0), suggest_label="토리?")
        self.assertTrue(new)
        pend = self.store.pending_identities()
        self.assertEqual([r["identity_id"] for r in pend], [iid])
        tpl = self.store.templates_of(iid)
        self.assertEqual(len(tpl), 1)
        self.assertTrue((self.root / tpl[0]).is_file())

    def test_same_crop_resolves_same_id(self):
        m = self._matcher()
        iid, _, _ = m.resolve(_att_user("4.png", 0))
        m2 = self._matcher()  # 새 인스턴스 — 저장소에서 재적재
        iid2, score, new = m2.resolve(_att_user("4.png", 0))
        self.assertEqual(iid, iid2)
        self.assertFalse(new)
        self.assertGreaterEqual(score, m2.threshold)

    def test_other_screenshot_same_user_matches(self):
        """다른 스크린샷(5.png, 행 위치 상이)의 같은 유저는 같은 ID여야 한다."""
        m = self._matcher()
        iid, _, _ = m.resolve(_att_user("4.png", 0))
        iid2, _, new = m.resolve(_att_user("5.png", 37))
        self.assertEqual(iid, iid2)
        self.assertFalse(new)

    def test_different_user_gets_new_id(self):
        m = self._matcher()
        iid_att, _, _ = m.resolve(_att_user("4.png", 0))
        iid_def, _, new = m.resolve(_def_user("4.png", 0))
        self.assertTrue(new)
        self.assertNotEqual(iid_att, iid_def)


if __name__ == "__main__":
    unittest.main()
