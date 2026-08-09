"""TASK-11 선행 테스트 — export CSV 계약·label 흐름·run 요약·scan 오케스트레이션.

(FR-06, FR-07·AC-06 완결, 설계 §CSV 내보내기 계약·§정상실패복구 흐름.
scan의 실기 종단 검증은 TASK-12.)
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from deckscan.controller import (choose_window, label_pending, run_scan,
                                 summarize_run)
from deckscan.store.csv_export import export_csv
from deckscan.store.datastore import BattleRecord, DataStore, SlotRecord
from deckscan.win.session import WindowInfo

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


class RunScanTest(unittest.TestCase):
    """run_scan 오케스트레이션 — 내비게이터는 스텁, 순회는 img/7 정지 화면."""

    def _walker_factory(self, store, tmp):
        from deckscan.nav.list_walker import ListWalker
        from deckscan.nav.navigator import ScreenJudge
        from deckscan.vision.deck_parser import DeckParser
        from tests.test_list_walker import FakeCapture, FakeInput

        window = np.asarray(Image.open(
            Path(__file__).resolve().parents[1] / "img" / "7.png").convert("RGB"))
        judge = ScreenJudge(FakeCapture(window), (2544, 657))
        parser = DeckParser(store, Path(tmp), evidence_dir=Path(tmp) / "ev")
        return lambda run_id: ListWalker(judge, FakeInput(), parser, store,
                                         run_id, captures_dir=Path(tmp) / "cap")

    def test_success_records_run_and_returns_zero(self):
        class NavOk:
            def goto_combat_tab(self):
                return None

        with tempfile.TemporaryDirectory() as tmp:
            store = DataStore(":memory:")
            code, text = run_scan(store, NavOk(),
                                  self._walker_factory(store, tmp))
            self.assertEqual(code, 0)
            self.assertIn("처리 2", text)
            run = store.get_run(1)
            self.assertEqual(run["status"], "done")
            self.assertEqual(run["processed"], 2)
            store.close()

    def test_navigation_failure_aborts_run_with_exit_2(self):
        from deckscan.nav.navigator import NavigationTimeout

        class NavFail:
            def goto_combat_tab(self):
                raise NavigationTimeout("테스트")

        with tempfile.TemporaryDirectory() as tmp:
            store = DataStore(":memory:")
            code, text = run_scan(store, NavFail(),
                                  self._walker_factory(store, tmp))
            self.assertEqual(code, 2)
            self.assertEqual(store.get_run(1)["status"], "aborted")
            self.assertEqual(store.battle_count(), 0)
            store.close()


def _win(hwnd: int) -> WindowInfo:
    return WindowInfo(hwnd=hwnd, title="삼국지-전략판", pid=1000 + hwnd,
                      rect=(10 * hwnd, 20, 2546, 689), client=(2544, 657),
                      elevated=True)


class ChooseWindowTest(unittest.TestCase):
    """TASK-14 선행 테스트 — 창 후보 선택(FR-08, DCR-002).

    입력 규약: 번호=선택(전면 표시 후 y/n 확인), q=중단. 후보 1개면 묻지 않는다.
    """

    def setUp(self):
        self.wins = [_win(1), _win(2)]
        self.raised: list[int] = []

    def _ask(self, answers: list[str]):
        it = iter(answers)
        prompts: list[str] = []

        def ask(prompt: str) -> str:
            prompts.append(prompt)
            return next(it)

        ask.prompts = prompts
        return ask

    def test_single_candidate_returned_without_prompt(self):
        def ask(prompt):
            raise AssertionError("후보 1개에서는 묻지 않아야 한다")
        self.assertIs(choose_window([self.wins[0]], ask, self.raised.append),
                      self.wins[0])
        self.assertEqual(self.raised, [])

    def test_select_confirm_returns_choice_and_brings_front(self):
        ask = self._ask(["2", "y"])
        got = choose_window(self.wins, ask, self.raised.append)
        self.assertIs(got, self.wins[1])
        self.assertEqual(self.raised, [2])          # 확인 전 전면 표시
        self.assertIn("0x1", ask.prompts[0])        # 후보 목록이 프롬프트에 나열
        self.assertIn("0x2", ask.prompts[0])

    def test_reject_confirmation_reprompts(self):
        ask = self._ask(["1", "n", "2", "y"])
        got = choose_window(self.wins, ask, self.raised.append)
        self.assertIs(got, self.wins[1])
        self.assertEqual(self.raised, [1, 2])

    def test_quit_returns_none(self):
        self.assertIsNone(choose_window(self.wins, self._ask(["q"]),
                                        self.raised.append))
        self.assertEqual(self.raised, [])

    def test_invalid_input_reprompts(self):
        ask = self._ask(["abc", "9", "2", "y"])
        got = choose_window(self.wins, ask, self.raised.append)
        self.assertIs(got, self.wins[1])
        self.assertEqual(self.raised, [2])

    def test_eof_means_noninteractive_abort(self):
        """stdin이 NUL 장치면 isatty()가 True를 돌려주는 Windows 특성(2026-08-09
        실기)으로 비대화형 가드가 뚫린다 — EOF는 트레이스백 없이 중단(None)."""
        def ask(prompt):
            raise EOFError
        self.assertIsNone(choose_window(self.wins, ask, self.raised.append))


if __name__ == "__main__":
    unittest.main()
