"""TASK-08 선행 테스트 — DeckParser 통합 (FR-03·AC-02, AC-04·NFR-01·FR-05 부분).

픽스처는 창 스크린샷(img/4~6.png, 2546×689)을 클라이언트 프레임(2544×657)으로
잘라 사용한다. 패널 앵커는 4.png 배치를 기준선으로 행 위치 차이(dy)만 보정한다.
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from deckscan.nav import ui_telegram as ui
from deckscan.store.datastore import DataStore
from deckscan.vision.deck_parser import DeckParser

IMG = Path(__file__).resolve().parents[1] / "img"
_S = 2546 / 2000
PANEL_DY = {"4.png": 0, "5.png": 37, "6.png": 72}       # 교차 검증 픽스처(아군=공격)
ANCHOR_DY = {**PANEL_DY, "7.png": 0}                    # 앵커 계산용(7 = 아군=수비)

TROOPS = {
    "4.png": [8783, 9868, 9677, 6412, 8762, 7676],
    "5.png": [9486, 9958, 10433, 6796, 6791, 7163],
    "6.png": [10000, 10000, 10600, 8684, 8983, 9512],
}
LEVELS = {
    "4.png": [50, 50, 50, 50, 49, 50],
    "5.png": [50] * 6,
    "6.png": [50] * 6,
}
# AC-02 기준값. 수비 슬롯 2의 '성채'는 판독 후보(TBD) — 실기 확대 화면에서 확정.
AC02_ATTACK = ["가후", "곽가", "양기"]
AC02_DEFEND = ["법정", "성채", "관우"]


def client_frame(png: str) -> np.ndarray:
    im = Image.open(IMG / png).convert("RGB").crop((1, 31, 2545, 688))
    return np.asarray(im)


def anchor(png: str) -> int:
    return ui.PANEL_ANCHOR_Y + round(ANCHOR_DY[png] * _S)


def _user_strip(png: str, right: bool) -> "np.ndarray":
    box = ui.USER_DEF if right else ui.USER_ATT
    x0, y0, x1, y1 = box
    return client_frame(png)[y0:y1, x0:x1]


class DeckParserTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = DataStore(":memory:")
        self.parser = DeckParser(self.store, self.root,
                                 evidence_dir=self.root / "ev")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_ac02_img4_record_and_label_lookup(self):
        """AC-02: img/4.png → 유저·장수·레벨 추출, 라벨 확정 후 조회 반영."""
        rec = self.parser.parse(client_frame("4.png"), anchor("4.png"))
        self.assertEqual(rec.parse_status, "ok")
        self.assertEqual(rec.battle_time, "2026-08-08T22:58:47")
        self.assertEqual(rec.result, "승")
        self.assertEqual(len(rec.slots), 6)
        self.assertEqual([s.troops for s in rec.slots], TROOPS["4.png"])
        self.assertEqual([s.level for s in rec.slots], LEVELS["4.png"])
        self.assertEqual([s.side for s in rec.slots],
                         ["attack"] * 3 + ["defend"] * 3)
        self.assertIsNotNone(rec.attacker_id)
        self.assertNotEqual(rec.attacker_id, rec.defender_id)
        self.assertIsNotNone(rec.attacker_alliance_id)
        self.assertNotEqual(rec.attacker_alliance_id, rec.defender_alliance_id)

        # FR-07 라벨 확정 → AC-05 구조로 이름 조회 (AC-06 부분)
        self.store.confirm_label(rec.attacker_id, "토리의사생활")
        self.store.confirm_label(rec.defender_id, "元이설탱스")
        for slot, name in zip(rec.slots, AC02_ATTACK + AC02_DEFEND):
            self.store.confirm_label(slot.general_id, name)
        run = self.store.create_run()
        self.store.upsert_battle(run, rec)
        rows = list(self.store.deck_rows())
        self.assertEqual([r["general"] for r in rows], AC02_ATTACK + AC02_DEFEND)
        self.assertEqual({r["attacker"] for r in rows}, {"토리의사생활"})
        self.assertEqual({r["defender"] for r in rows}, {"元이설탱스"})

    def test_cross_image_identity_and_key_reproducibility(self):
        """같은 장수·유저는 교차 이미지에서 같은 ID, 재파싱은 같은 battle_key(FR-05)."""
        recs = {png: self.parser.parse(client_frame(png), anchor(png))
                for png in PANEL_DY}
        for png, rec in recs.items():
            self.assertEqual(rec.parse_status, "ok", png)
            self.assertEqual([s.troops for s in rec.slots], TROOPS[png], png)
            self.assertEqual([s.level for s in rec.slots], LEVELS[png], png)
        r4, r5, r6 = recs["4.png"], recs["5.png"], recs["6.png"]
        for i in range(3):  # 공격 덱(가후·곽가·양기)은 3장 모두 동일
            self.assertEqual(r4.slots[i].general_id, r5.slots[i].general_id, i)
            self.assertEqual(r4.slots[i].general_id, r6.slots[i].general_id, i)
        defend_ids = [r.slots[i].general_id for r in recs.values()
                      for i in range(3, 6)]
        self.assertEqual(len(set(defend_ids)), 9)  # 수비 장수 9종은 전부 상이
        self.assertEqual(len({r.attacker_id for r in recs.values()}), 1)
        self.assertEqual(len({r.defender_id for r in recs.values()}), 1)
        self.assertEqual(len({r.attacker_alliance_id for r in recs.values()}), 1)
        self.assertEqual(len({r.defender_alliance_id for r in recs.values()}), 1)
        self.assertEqual(len({r.battle_key for r in recs.values()}), 3)

        # 새 파서(저장소에서 템플릿 재적재)로 재파싱해도 같은 키가 재현된다
        parser2 = DeckParser(self.store, self.root,
                             evidence_dir=self.root / "ev")
        rec4b = parser2.parse(client_frame("4.png"), anchor("4.png"))
        self.assertEqual(rec4b.battle_key, r4.battle_key)
        run = self.store.create_run()
        self.store.upsert_battle(run, r4)
        self.store.upsert_battle(run, rec4b)
        self.assertEqual(self.store.battle_count(), 1)

    def test_corrupt_date_gives_partial_with_evidence(self):
        """AC-04·NFR-01 부분: 일시 훼손 → partial, 증거 저장, 나머지는 정상."""
        frame = client_frame("4.png").copy()
        x0, y0, x1, y1 = ui.DATE_BOX
        frame[y0:y1, x0:x1] = 0
        rec = self.parser.parse(frame, anchor("4.png"))
        self.assertEqual(rec.parse_status, "partial")
        self.assertIsNone(rec.battle_time)
        self.assertEqual([s.troops for s in rec.slots], TROOPS["4.png"])
        self.assertFalse(rec.battle_key.startswith("img-"))  # 내용 키 유지
        evidence = list((self.root / "ev").glob("*battle_time*.png"))
        self.assertEqual(len(evidence), 1)

    def test_empty_slot_skipped(self):
        """A-03: 빈 카드 칸(레벨·병력 모두 없음)은 슬롯 저장에서 제외한다."""
        frame = client_frame("4.png").copy()
        x0, y0, x1, y1 = ui.CARD_BOXES[5]
        frame[y0:y1, x0:x1] = 0
        rec = self.parser.parse(frame, anchor("4.png"))
        self.assertEqual([(s.side, s.slot) for s in rec.slots],
                         [("attack", 1), ("attack", 2), ("attack", 3),
                          ("defend", 1), ("defend", 2)])

    def test_defend_left_panel_flips_sides(self):
        """DES-05 v2(DCR-001): 아군=수비 전보(img/7)는 좌우 역할이 반전된다.

        img/7 1행 — 좌(아군/수비): NPC 부대 100·100·빈 칸, 우(적군/공격):
        3400·3300·3400, 결과 '패'. 좌측이 수비로 매핑되어야 한다.
        """
        rec = self.parser.parse(client_frame("7.png"), anchor("7.png"))
        self.assertEqual(rec.result, "패")
        self.assertEqual([s.troops for s in rec.slots if s.side == "attack"],
                         [3400, 3300, 3400])
        self.assertEqual([s.troops for s in rec.slots if s.side == "defend"],
                         [100, 100])
        # 유저 매핑도 반전: 공격 유저는 우측 스트립의 식별자여야 한다
        rid, _, new = self.parser.users.resolve(_user_strip("7.png", right=True))
        self.assertEqual(rec.attacker_id, rid)
        self.assertFalse(new)  # 이미 등록된 ID와 매칭(신규 아님)

    def test_invalid_render_returns_none(self):
        """무효 렌더 게이트(TASK-12 결함 E): 확대(호버) 렌더는 레코드가 아니다.

        2026-08-09 실기 run2: 헤더는 정위치인데 내용이 확대된 렌더가 이중 프레임
        확증을 통과해 일시·병력 전 필드 실패의 쓰레기 partial로 저장됐다
        (img/panel_4ffae5.png). 일시 없음 + 슬롯 존재 + 병력 전원 실패 조합은
        전보 훼손(AC-04 대상)이 아니라 렌더 이상이므로 저장하지 않는다.
        """
        frame = np.zeros((657, 2544, 3), dtype=np.uint8)
        panel = np.asarray(Image.open(IMG / "panel_4ffae5.png").convert("RGB"))
        x0, y0, x1, y1 = ui.PANEL_REGION
        frame[y0:y1, x0:x1] = panel
        self.assertIsNone(self.parser.parse(frame, ui.PANEL_ANCHOR_Y))

    def test_component_exception_gives_failed_fallback_key(self):
        """NFR-01: 구성요소 예외에도 파서는 레코드를 반환하고 대체 키로 저장 가능."""
        class Boom:
            def __getattr__(self, name):
                def _raise(*a, **k):
                    raise RuntimeError("boom")
                return _raise

        for attr in ("users", "generals", "alliances", "digits", "ocr",
                     "results"):
            setattr(self.parser, attr, Boom())
        rec = self.parser.parse(client_frame("4.png"), anchor("4.png"))
        self.assertEqual(rec.parse_status, "failed")
        self.assertTrue(rec.battle_key.startswith("img-"))
        self.assertEqual(rec.slots, [])
        run = self.store.create_run()
        self.store.upsert_battle(run, rec)
        self.store.upsert_battle(run, rec)
        self.assertEqual(self.store.battle_count(), 1)


if __name__ == "__main__":
    unittest.main()
