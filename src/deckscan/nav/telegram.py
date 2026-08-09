"""메인 → 동맹전보 교전 탭 내비게이션 (설계 DES-03, FR-01·NFR-02).

각 클릭은 직전 화면 마커를 재검증한 뒤 전송하고(오클릭 구조적 차단), 목표
화면 마커의 등장으로 성공을 판정한다. 좌표·마커는 ui_telegram(TASK-03 실기
실측), 판정 유틸은 navigator.ScreenJudge를 사용한다.

메인 화면 판별 주의: 더 보기 버튼(MARKER_MAIN)은 메뉴가 열린 상태에서도
보이므로, 메뉴 마커가 이미 떠 있으면 더 보기 클릭을 건너뛴다(재클릭 시
메뉴가 닫히는 토글 오동작 방지 — 2026-08-09 실기 확인).
"""

from __future__ import annotations

import logging

import numpy as np

from . import ui_telegram as ui
from .list_walker import ui_template
from .navigator import NavigationTimeout, ScreenJudge, WrongScreen

log = logging.getLogger(__name__)


class TelegramNavigator:
    step_timeout = 8.0   # 단계별 목표 마커 대기 상한(초)

    def __init__(self, judge: ScreenJudge, input_):
        self.judge = judge
        self.input = input_

    def _at(self, frame: np.ndarray, marker: tuple[str, tuple]) -> bool:
        name, rect = marker
        return self.judge.marker_score(frame, rect, ui_template(name)) \
            >= ui.MARKER_NCC_THRESHOLD

    def _wait(self, marker: tuple[str, tuple], what: str) -> None:
        name, rect = marker
        self.judge.wait_marker(rect, ui_template(name), ui.MARKER_NCC_THRESHOLD,
                               timeout=self.step_timeout, what=what)
        # 마커 등장 ≠ 입력 수용 가능 — 전환 연출 중 보낸 클릭은 무시된다
        # (2026-08-09 실기: 동맹 제목이 뜬 직후의 전보 클릭이 삼켜짐).
        self.judge.wait_stable()
        log.info("%s 도달", what)

    def _click_wait(self, cur: tuple[str, tuple], point: tuple[int, int],
                    target: tuple[str, tuple], what: str) -> None:
        """클릭 → 목표 마커 대기. 무반응이면 1회 재시도(설계 실패 흐름 표).

        재시도 전 화면을 재검증한다: 목표가 이미 떠 있으면 성공 처리(늦은 전환
        후 재클릭 시 토글 오동작 방지), 직전 화면도 아니면 재클릭하지 않는다.
        """
        self.input.click(*point)
        try:
            self._wait(target, what)
            return
        except NavigationTimeout:
            frame = self.judge.fresh()
            if self._at(frame, target):
                self.judge.wait_stable()
                return
            if not self._at(frame, cur):
                raise
            log.warning("%s: 클릭 무반응 — 1회 재시도", what)
        self.input.click(*point)
        self._wait(target, what)

    def _step(self, cur: tuple[str, tuple], point: tuple[int, int],
              target: tuple[str, tuple], what: str) -> None:
        frame = self.judge.fresh()
        if not self._at(frame, cur):
            raise WrongScreen(f"{what} 이동 중단: 직전 화면 재검증 실패")
        self._click_wait(cur, point, target, what)

    def goto_combat_tab(self) -> np.ndarray:
        """메인(또는 메뉴 열림) 상태에서 교전 탭까지 이동, 안정 프레임 반환."""
        frame = self.judge.wait_stable()
        if not self._at(frame, ui.MARKER_MENU):
            if not self._at(frame, ui.MARKER_MAIN):
                raise WrongScreen("메인 화면이 아님 — 메인에서 실행하세요 (A-01)")
            self._click_wait(ui.MARKER_MAIN, ui.CLICK_MORE,
                             ui.MARKER_MENU, "더 보기 메뉴")
        self._step(ui.MARKER_MENU, ui.CLICK_MENU_ALLIANCE,
                   ui.MARKER_ALLIANCE, "동맹 화면")
        self._step(ui.MARKER_ALLIANCE, ui.CLICK_ALLIANCE_TELEGRAM,
                   ui.MARKER_TELEGRAM, "동맹전보 화면")
        self._step(ui.MARKER_TELEGRAM, ui.CLICK_COMBAT_TAB,
                   ui.MARKER_COMBAT_TAB, "교전 탭")
        return self.judge.wait_stable()
