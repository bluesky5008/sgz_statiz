"""TASK-09 선행 테스트 — 마커 판별 + TelegramNavigator 단계 로직 (FR-01, NFR-02).

img/1~4가 메뉴 열림·동맹·동맹전보(전체 탭)·교전 탭 활성을 커버한다. 실측
기대값(2026-08-09): 자기 화면 1.000, 타 화면 최대 0.692. 메뉴 닫힌 메인
화면은 저장소 픽스처가 없어 '더 보기 클릭' 분기는 실기 검증으로 확인한다.
"""

import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from deckscan.nav import ui_telegram as ui
from deckscan.nav.list_walker import ui_template
from deckscan.nav.navigator import ScreenJudge, WrongScreen
from deckscan.nav.telegram import TelegramNavigator

IMG = Path(__file__).resolve().parents[1] / "img"
FRAMES = {n: np.asarray(Image.open(IMG / f"{n}.png").convert("RGB"))
          for n in (1, 2, 3, 4)}
MARKERS = {"MAIN": ui.MARKER_MAIN, "MENU": ui.MARKER_MENU,
           "ALLI": ui.MARKER_ALLIANCE, "TG": ui.MARKER_TELEGRAM,
           "TAB": ui.MARKER_COMBAT_TAB}
# 마커별 (임계 이상이어야 하는 픽스처 번호들) — 그 외에는 임계 미만이어야 한다.
EXPECT_ON = {"MAIN": {1}, "MENU": {1}, "ALLI": {2}, "TG": {3, 4}, "TAB": {4}}


class FakeGame:
    """클릭 → 화면 전이 상태 기계. grab_fresh는 현재 화면 픽스처를 반환한다."""

    TRANSITIONS = {ui.CLICK_MENU_ALLIANCE: {1: 2},
                   ui.CLICK_ALLIANCE_TELEGRAM: {2: 3},
                   ui.CLICK_COMBAT_TAB: {3: 4}}

    def __init__(self, state: int):
        self.state = state
        self.clicks: list[tuple[int, int]] = []

    def grab_fresh(self) -> np.ndarray:
        return FRAMES[self.state]

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))
        nxt = self.TRANSITIONS.get((x, y), {}).get(self.state)
        if nxt:
            self.state = nxt


def _nav(state: int) -> tuple[TelegramNavigator, FakeGame]:
    game = FakeGame(state)
    return TelegramNavigator(ScreenJudge(game, (2544, 657)), game), game


class MarkerDiscriminationTest(unittest.TestCase):
    def test_each_marker_fires_only_on_its_screen(self):
        judge = ScreenJudge(capture=None, client_size=(2544, 657))
        for mname, (fname, rect) in MARKERS.items():
            tpl = ui_template(fname)
            for n, frame in FRAMES.items():
                score = judge.marker_score(frame, rect, tpl)
                if n in EXPECT_ON[mname]:
                    self.assertGreaterEqual(score, ui.MARKER_NCC_THRESHOLD,
                                            f"{mname} on img/{n}")
                else:
                    self.assertLess(score, ui.MARKER_NCC_THRESHOLD,
                                    f"{mname} on img/{n}")


class NavigatorFlowTest(unittest.TestCase):
    def test_full_flow_from_open_menu(self):
        nav, game = _nav(1)
        nav.goto_combat_tab()
        self.assertEqual(game.state, 4)
        self.assertEqual(game.clicks, [ui.CLICK_MENU_ALLIANCE,
                                       ui.CLICK_ALLIANCE_TELEGRAM,
                                       ui.CLICK_COMBAT_TAB])

    def test_wrong_screen_aborts_without_click(self):
        nav, game = _nav(2)  # 동맹 화면에서 시작 — 메인/메뉴가 아니므로 중단
        with self.assertRaises(WrongScreen):
            nav.goto_combat_tab()
        self.assertEqual(game.clicks, [])

    def test_swallowed_click_is_retried_once(self):
        """실기 재현(2026-08-09): 목록 갱신 중 교전 탭 클릭이 무시됨 — 1회 재시도."""
        game = FakeGame(1)
        swallow = {ui.CLICK_COMBAT_TAB}
        orig_click = game.click

        def flaky_click(x, y):
            if (x, y) in swallow:
                swallow.discard((x, y))
                game.clicks.append((x, y))   # 클릭은 보냈지만 게임이 무시
                return
            orig_click(x, y)

        game.click = flaky_click
        nav = TelegramNavigator(ScreenJudge(game, (2544, 657)), game)
        nav.step_timeout = 0.3               # 테스트용 짧은 대기
        nav.goto_combat_tab()
        self.assertEqual(game.state, 4)
        self.assertEqual(game.clicks.count(ui.CLICK_COMBAT_TAB), 2)


if __name__ == "__main__":
    unittest.main()
