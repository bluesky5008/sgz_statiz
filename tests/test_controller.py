"""TASK-11 선행 테스트(오프라인 부분) — export CSV 계약·label 흐름·run 요약.

(FR-06, FR-07·AC-06 완결, 설계 §CSV 내보내기 계약. scan 전체는 실기 — TASK-12.)
"""

import tempfile
import unittest
from pathlib import Path

from deckscan.controller import label_pending, summarize_run
from deckscan.store.csv_export import export_csv
from deckscan.store.datastore import BattleRecord, DataStore, SlotRecord

BATTLES_HEADER = ["battle_key", "battle_time", "result", "attacker", "defender",
                  "attacker_alliance", "defender_alliance", "parse_status",
                  "capture_path"]
DECK_HEADER = ["battle_key", "battle_time", "result", "attacker", "defender",
               "side", "slot", "general", "level", "troops"]


def _seed(store: DataStore) -> BattleRecord:
    """확정 라벨 유저 2·동맹 2·장수 2와 전보 1건(슬롯 2)을 만든다."""
    ids = {}
    for ns, label in (("user", "토리의사생활"), ("user", "元이설탱스"),
                      ("alliance", "FIRST"), ("alliance", "잠룡"),
                      ("general", "가후"), ("general", "관우")):
        iid = store.create_identity(ns, None, f"assets/templates/{ns}/x.png")
        store.confirm_label(iid, label)
        ids[label] = iid
    rec = BattleRecord(
        battle_key="k1", battle_time="2026-08-08T22:58:47", result="승",
        attacker_id=ids["토리의사생활"], defender_id=ids["元이설탱스"],
        attacker_alliance_id=ids["FIRST"], defender_alliance_id=ids["잠룡"],
        capture_path="output/evidence/k1.png", parse_status="ok",
        slots=[SlotRecord("attack", 1, ids["가후"], 50, 8783),
               SlotRecord("defend", 1, ids["관우"], 50, 7676)])
    run = store.create_run()
    store.upsert_battle(run, rec)
    return rec


class CsvExportTest(unittest.TestCase):
    def test_contract(self):
        store = DataStore(":memory:")
        _seed(store)
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_csv(store, tmp)
            names = sorted(p.name for p in paths)
            self.assertEqual(len(paths), 2)
            self.assertTrue(names[0].startswith("battles_"), names)
            self.assertTrue(names[1].startswith("deck_long_"), names)
            for p in paths:
                self.assertEqual(p.read_bytes()[:3], b"\xef\xbb\xbf", p)  # BOM
            battles = paths[0].read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(battles[0].split(","), BATTLES_HEADER)
            self.assertEqual(len(battles), 2)
            self.assertIn("토리의사생활", battles[1])
            self.assertIn("잠룡", battles[1])
            deck = paths[1].read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(deck[0].split(","), DECK_HEADER)
            self.assertEqual(len(deck), 3)  # 헤더 + 슬롯 2
            self.assertIn("가후", deck[1])
            self.assertIn("관우", deck[2])
        store.close()


class LabelFlowTest(unittest.TestCase):
    def setUp(self):
        self.store = DataStore(":memory:")
        self.a = self.store.create_identity("user", "톨리?", "u1.png")
        self.b = self.store.create_identity("general", None, "g1.png")
        self.c = self.store.create_identity("general", "간우?", "g2.png")

    def tearDown(self):
        self.store.close()

    def _labels(self):
        return {r["identity_id"]: (r["label"], r["label_status"])
                for ns in ("user", "general")
                for r in self.store.iter_identities(ns)}

    def test_confirm_skip_and_remaining(self):
        inputs = iter(["토리의사생활", ""])          # 확정, 건너뜀 → 나머지 순회 종료
        done = label_pending(self.store, lambda prompt: next(inputs, "q"))
        self.assertEqual(done, 1)
        labels = self._labels()
        self.assertEqual(labels[self.a], ("토리의사생활", "confirmed"))
        self.assertEqual(labels[self.b][1], "pending")
        self.assertEqual(labels[self.c][1], "pending")

    def test_quit_immediately(self):
        done = label_pending(self.store, lambda prompt: "q")
        self.assertEqual(done, 0)
        self.assertEqual(len(self.store.pending_identities()), 3)

    def test_prompt_shows_suggestion_and_template(self):
        prompts = []

        def ask(prompt):
            prompts.append(prompt)
            return "q"

        label_pending(self.store, ask)
        self.assertIn("톨리?", prompts[0])   # OCR 제안 라벨 노출
        self.assertIn("u1.png", prompts[0])  # 크롭(템플릿) 경로 노출


class SummaryTest(unittest.TestCase):
    def test_summary_counts_and_pending(self):
        store = DataStore(":memory:")
        run = store.create_run()
        store.create_identity("general", "?", "g.png")
        store.create_identity("user", None, "u.png")
        store.finish_run(run, processed=5, saved=4, failed=1)
        text = summarize_run(store, run)
        for token in ("처리 5", "저장 4", "실패 1", "pending 2", "label"):
            self.assertIn(token, text)
        store.close()


if __name__ == "__main__":
    unittest.main()
