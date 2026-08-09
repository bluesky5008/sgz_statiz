"""TASK-04 선행 테스트 — DataStore·battle_key (FR-04·FR-05, AC-03·AC-05 오프라인 부분)."""

import tempfile
import unittest
from pathlib import Path

from deckscan.store.datastore import (
    BattleRecord,
    DataStore,
    SlotRecord,
    make_battle_key,
    make_fallback_key,
)


def _slots():
    return [
        SlotRecord("attack", 1, general_id=11, level=50, troops=8783),
        SlotRecord("attack", 2, general_id=12, level=50, troops=9868),
        SlotRecord("attack", 3, general_id=13, level=50, troops=9677),
        SlotRecord("defend", 1, general_id=21, level=50, troops=6412),
        SlotRecord("defend", 2, general_id=22, level=49, troops=8762),
        SlotRecord("defend", 3, general_id=23, level=50, troops=7676),
    ]


def _battle(key: str) -> BattleRecord:
    return BattleRecord(
        battle_key=key, battle_time="2026-08-08T22:58:47", result="승",
        attacker_id=1, defender_id=2,
        attacker_alliance_id=91, defender_alliance_id=92,
        capture_path="evidence/x.png", parse_status="ok", slots=_slots())


class DbPathTest(unittest.TestCase):
    def test_creates_missing_parent_dirs(self):
        """기본 경로 output/deckscan.db처럼 부모 디렉터리가 없어도 열려야 한다."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "output" / "deckscan.db"
            with DataStore(str(path)) as store:
                self.assertEqual(store.battle_count(), 0)
            self.assertTrue(path.is_file())


class BattleKeyTest(unittest.TestCase):
    def test_reproducible(self):
        a = make_battle_key("2026-08-08T22:58:47", 1, 2, _slots())
        b = make_battle_key("2026-08-08T22:58:47", 1, 2, _slots())
        self.assertEqual(a, b)

    def test_content_sensitive_to_generals(self):
        base = make_battle_key("2026-08-08T22:58:47", 1, 2, _slots())
        changed = _slots()
        changed[0].general_id = 99
        self.assertNotEqual(base, make_battle_key("2026-08-08T22:58:47", 1, 2, changed))

    def test_key_ignores_troops_and_level_variance(self):
        """DCR-003: 병력·레벨은 OCR 판독이라 실행 컨텍스트에 따라 값이 흔들려
        (2026-08-09 run2 실증: 같은 캡처가 10000/10/10011) 키에 넣으면 같은
        전보가 다른 키로 중복 저장된다. 키는 결정적 요소(일시·유저·장수
        구성)만 사용한다."""
        base = make_battle_key("2026-08-08T22:58:47", 1, 2, _slots())
        varied = _slots()
        varied[0].troops = 10
        varied[1].troops = None
        varied[2].level = None
        varied[3].level = 48
        self.assertEqual(base, make_battle_key("2026-08-08T22:58:47", 1, 2, varied))

    def test_slot_order_insensitive(self):
        slots = _slots()
        self.assertEqual(make_battle_key("t", 1, 2, slots),
                         make_battle_key("t", 1, 2, list(reversed(slots))))

    def test_fallback_key_stable(self):
        self.assertEqual(make_fallback_key(b"png-bytes"), make_fallback_key(b"png-bytes"))
        self.assertNotEqual(make_fallback_key(b"a"), make_fallback_key(b"b"))


class DataStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = DataStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_general_latest_levels(self):
        """DCR-003: 장수별 최신 전투 기준 레벨 조회 (레벨 성장 반영)."""
        run = self.store.create_run()
        gid = self.store.create_identity("general", "가후", "t.png")
        old = BattleRecord("k-old", "2026-08-08T10:00:00", "승", 1, 2, None,
                           None, None, "ok",
                           [SlotRecord("attack", 1, gid, 49, 9000)])
        new = BattleRecord("k-new", "2026-08-09T10:00:00", "승", 1, 2, None,
                           None, None, "ok",
                           [SlotRecord("attack", 1, gid, 50, 9100)])
        self.store.upsert_battle(run, old)
        self.store.upsert_battle(run, new)
        rows = list(self.store.general_latest_levels())
        self.assertEqual([(r["general_id"], r["general"], r["level"],
                           r["last_battle_time"]) for r in rows],
                         [(gid, "가후", 50, "2026-08-09T10:00:00")])

    def test_upsert_idempotent(self):
        run = self.store.create_run()
        key = make_battle_key("t", 1, 2, _slots())
        self.store.upsert_battle(run, _battle(key))
        self.store.upsert_battle(run, _battle(key))
        self.assertEqual(self.store.battle_count(), 1)
        self.assertEqual(self.store.slot_count(), 6)

    def test_identity_lifecycle(self):
        iid = self.store.create_identity("user", "元이설탱스?", "tpl/u1.png")
        pend = self.store.pending_identities()
        self.assertEqual([r["identity_id"] for r in pend], [iid])
        self.store.confirm_label(iid, "元이설탱스")
        self.assertEqual(self.store.pending_identities(), [])
        rows = list(self.store.iter_identities("user"))
        self.assertEqual(rows[0]["label"], "元이설탱스")
        self.assertEqual(rows[0]["label_status"], "confirmed")
        self.assertEqual(self.store.templates_of(iid), ["tpl/u1.png"])

    def test_deck_rows_joins_labels(self):
        """AC-05: (전보, 진영, 슬롯) 단위로 유저명·장수명·레벨 조회."""
        run = self.store.create_run()
        u1 = self.store.create_identity("user", "공격자", "tpl/u1.png")
        u2 = self.store.create_identity("user", "수비자", "tpl/u2.png")
        g = self.store.create_identity("general", "가후", "tpl/g1.png")
        slots = [SlotRecord("attack", 1, general_id=g, level=50, troops=100)]
        rec = BattleRecord(
            battle_key=make_battle_key("t", u1, u2, slots),
            battle_time="t", result="승", attacker_id=u1, defender_id=u2,
            attacker_alliance_id=None, defender_alliance_id=None,
            capture_path=None, parse_status="ok", slots=slots)
        self.store.upsert_battle(run, rec)
        rows = list(self.store.deck_rows())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["attacker"], "공격자")
        self.assertEqual(row["defender"], "수비자")
        self.assertEqual(row["general"], "가후")
        self.assertEqual(row["level"], 50)
        self.assertEqual(row["side"], "attack")

    def test_run_summary(self):
        run = self.store.create_run()
        self.store.finish_run(run, "done", processed=5, saved=4, failed=1)
        row = self.store.get_run(run)
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["saved"], 4)


if __name__ == "__main__":
    unittest.main()
