"""TASK-S1·S2 선행 테스트 — 교전 통계 집계 (REQ-20260809-battle-stats FR-01~04).

픽스처 전투 7건(승/무/패, 아군=공격/수비, 일시 없음, 아군 불명)으로 관점
정규화(A-01)·조합 통계(A-02)·최신 덱·픽률·전적의 기대값을 검증한다.

픽스처 구성(아군 동맹 FIRST — 최빈 6/7):
  t1 08-01 FIRST u_me 공격{g1(49),g2,g3} vs 잠룡 u_a 수비{g4,g5,g6} — 승
  t2 08-02 동일(g1=50) — 무
  t3 08-03 잠룡 u_a 공격{g4,g5,g6} vs FIRST u_me 수비{g1,g2,g3} — 승(아군 수비)
  t4 08-04 FIRST u_me 공격{g1,g2,g7} vs 잠룡 u_b 수비{g4,g5,g6} — 패
  t5 (일시 없음) FIRST u_me 공격{g1,g2,g3} vs ENEMY2 u_b 수비{g4,g5,g6} — 승
  t6 08-05 FIRST u_me 공격{g1,g2,g7} vs ENEMY2 u_b 수비{g4,g5,g6} — 승
  t7 08-06 잠룡 u_a 공격{g4,g5,g6} vs ENEMY2 u_b 수비{g1,g2,g3} — 무(아군 불명)
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckscan.stats.aggregate import collect
from deckscan.store.datastore import BattleRecord, DataStore, SlotRecord


def _slots(att, dfd, levels=None):
    levels = levels or {}
    out = []
    for i, gid in enumerate(att):
        out.append(SlotRecord("attack", i + 1, gid, levels.get(gid, 50), 9000))
    for i, gid in enumerate(dfd):
        out.append(SlotRecord("defend", i + 1, gid, levels.get(gid, 50), 9000))
    return out


def build_fixture(path: str) -> dict:
    """픽스처 DB를 만들고 식별자 ID 맵을 반환한다."""
    store = DataStore(path)
    ids = {}
    for key, ns, label, confirmed in (
            ("FIRST", "alliance", "FIRST", True),
            ("JAM", "alliance", "잠룡", True),
            ("EN2", "alliance", "적동맹2", True),
            ("u_me", "user", "우리유저", True),
            ("u_a", "user", "상대A", True),
            ("u_b", "user", "상대B제안", False),
            ("g1", "general", "가후", True), ("g2", "general", "곽가", True),
            ("g3", "general", "양기", True), ("g4", "general", "법정", True),
            ("g5", "general", "성채", False), ("g6", "general", "관우", True),
            ("g7", "general", "장비", True)):
        iid = store.create_identity(ns, label, f"assets/templates/{ns}/x.png")
        if confirmed:
            store.confirm_label(iid, label)
        ids[key] = iid
    run = store.create_run()
    OUR, ENE = [ids[k] for k in ("g1", "g2", "g3")], [ids[k] for k in ("g4", "g5", "g6")]
    ALT = [ids["g1"], ids["g2"], ids["g7"]]
    battles = [
        ("k1", "2026-08-01T12:00:00", "승", "u_me", "u_a", "FIRST", "JAM",
         OUR, ENE, {ids["g1"]: 49}),
        ("k2", "2026-08-02T12:00:00", "무", "u_me", "u_a", "FIRST", "JAM",
         OUR, ENE, None),
        ("k3", "2026-08-03T12:00:00", "승", "u_a", "u_me", "JAM", "FIRST",
         ENE, OUR, None),
        ("k4", "2026-08-04T12:00:00", "패", "u_me", "u_b", "FIRST", "JAM",
         ALT, ENE, None),
        ("k5", None, "승", "u_me", "u_b", "FIRST", "EN2", OUR, ENE, None),
        ("k6", "2026-08-05T12:00:00", "승", "u_me", "u_b", "FIRST", "EN2",
         ALT, ENE, None),
        ("k7", "2026-08-06T12:00:00", "무", "u_a", "u_b", "JAM", "EN2",
         ENE, OUR, None),
    ]
    for key, t, res, au, du, aa, da, att, dfd, lv in battles:
        store.upsert_battle(run, BattleRecord(
            battle_key=key, battle_time=t, result=res,
            attacker_id=ids[au], defender_id=ids[du],
            attacker_alliance_id=ids[aa], defender_alliance_id=ids[da],
            capture_path=None, parse_status="ok", slots=_slots(att, dfd, lv)))
    store.close()
    return ids


class StatsAggregateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        db = str(Path(cls.tmp.name) / "s.db")
        cls.ids = build_fixture(db)
        cls.conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cls.stats = collect(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.tmp.cleanup()

    def test_friendly_alliance_auto_and_override(self):
        f = self.stats["friendly"]
        self.assertEqual(f["alliance_id"], self.ids["FIRST"])   # 최빈 6/7
        self.assertFalse(f["overridden"])
        s2 = collect(self.conn, alliance="잠룡")
        self.assertEqual(s2["friendly"]["alliance_id"], self.ids["JAM"])
        self.assertTrue(s2["friendly"]["overridden"])

    def test_excluded_counts(self):
        self.assertEqual(self.stats["excluded"],
                         {"no_time": 1, "no_side": 1})   # t5, t7 (NFR-03)

    def test_latest_decks_and_history(self):
        by_user = {d["user_id"]: d for d in self.stats["latest_decks"]}
        me = by_user[self.ids["u_me"]]
        self.assertEqual(me["last_battle_time"], "2026-08-05T12:00:00")
        self.assertEqual(sorted(me["deck"]),
                         sorted([self.ids["g1"], self.ids["g2"], self.ids["g7"]]))
        self.assertEqual([t for t, _ in me["history"]],
                         ["2026-08-01T12:00:00", "2026-08-04T12:00:00"])
        ub = by_user[self.ids["u_b"]]
        self.assertEqual(ub["last_battle_time"], "2026-08-06T12:00:00")
        self.assertEqual(sorted(ub["deck"]),
                         sorted([self.ids["g1"], self.ids["g2"], self.ids["g3"]]))

    def test_pick_rates(self):
        by_gen = {p["general_id"]: p for p in self.stats["pick_rates"]}
        g1 = by_gen[self.ids["g1"]]
        self.assertEqual((g1["total"], g1["attack"], g1["defend"]), (7, 5, 2))
        self.assertAlmostEqual(g1["share"], 7 / 42)
        self.assertEqual(by_gen[self.ids["g7"]]["total"], 2)
        self.assertEqual(by_gen[self.ids["g4"]]["total"], 7)

    def test_combo_stats_perspective_normalized(self):
        by_combo = {c["generals"]: c for c in self.stats["combos"]}
        our = by_combo[tuple(sorted([self.ids["g1"], self.ids["g2"], self.ids["g3"]]))]
        self.assertEqual((our["win"], our["draw"], our["lose"], our["n"]),
                         (3, 1, 0, 4))     # t1승·t2무·t3승(수비)·t5승
        alt = by_combo[tuple(sorted([self.ids["g1"], self.ids["g2"], self.ids["g7"]]))]
        self.assertEqual((alt["win"], alt["draw"], alt["lose"], alt["n"]),
                         (1, 0, 1, 2))     # t4패·t6승
        ene = by_combo[tuple(sorted([self.ids["g4"], self.ids["g5"], self.ids["g6"]]))]
        self.assertEqual((ene["win"], ene["draw"], ene["lose"], ene["n"]),
                         (1, 1, 4, 6))     # 아군의 반대측 관점

    def test_user_records(self):
        by_user = {r["user_id"]: r for r in self.stats["records"]}
        ua = by_user[self.ids["u_a"]]
        self.assertEqual((ua["win"], ua["draw"], ua["lose"]), (2, 1, 0))
        self.assertEqual(ua["last_battle_time"], "2026-08-03T12:00:00")
        ub = by_user[self.ids["u_b"]]
        self.assertEqual((ub["win"], ub["draw"], ub["lose"]), (2, 0, 1))
        self.assertEqual(ub["last_battle_time"], "2026-08-05T12:00:00")

    def test_display_names(self):
        names = self.stats["names"]
        self.assertEqual(names[self.ids["u_a"]], "상대A")
        self.assertEqual(names[self.ids["u_b"]],
                         f"#{self.ids['u_b']}(상대B제안)")   # FR-06 미확정 표기
        self.assertEqual(names[self.ids["g5"]], f"#{self.ids['g5']}(성채)")

    def test_latest_levels_reflected(self):
        by_user = {d["user_id"]: d for d in self.stats["latest_decks"]}
        me = by_user[self.ids["u_me"]]
        self.assertEqual(me["levels"][self.ids["g1"]], 50)   # 49→50 성장 반영


if __name__ == "__main__":
    unittest.main()
