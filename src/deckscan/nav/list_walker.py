"""전보 목록의 행 재탐지·펼침 판정·순회 루프 (설계 DES-04 v2, FR-02, DCR-001).

매 반복마다 현재 프레임에서 행 아이콘을 템플릿 매칭으로 재탐지한다 — 펼침으로
행 위치가 밀려도 추적 가능하고, 격전 보상 배너는 아이콘이 없어 자연 배제된다.
행별 펼침 상태를 판정해 이미 펼쳐진 행은 클릭 없이 파싱하고, 접힌 행(묶음)만
안전 지대(우측 화살표 열)를 클릭해 펼친다. 처리 중복은 패널 픽셀 서명(세션 내)
과 battle_key 멱등(저장 계층)이 이중으로 막는다.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from . import ui_telegram as ui
from .navigator import ScreenJudge, WrongScreen, same_image

log = logging.getLogger(__name__)

UI_DIR = Path(__file__).resolve().parents[3] / "assets" / "templates" / "ui"

FRIENDLY_SCAN_X0 = ui.FRIENDLY_BOX[0] - ui.ROW_SCAN_PAD

_cache: dict[str, np.ndarray] = {}


def ui_template(name: str) -> np.ndarray:
    """assets/templates/ui/의 템플릿을 적재한다(모듈 캐시). telegram.py와 공용."""
    if name not in _cache:
        _cache[name] = np.asarray(Image.open(UI_DIR / name).convert("RGB"))
    return _cache[name]


def _scan_column(frame: np.ndarray, box: tuple[int, int, int, int],
                 template: np.ndarray) -> np.ndarray:
    """box의 x 구간(±패드)에서 템플릿을 세로로 슬라이드한 y별 최고 점수."""
    x0, _, x1, _ = box
    col = frame[:, x0 - ui.ROW_SCAN_PAD:x1 + ui.ROW_SCAN_PAD]
    return cv2.matchTemplate(col, template, cv2.TM_CCOEFF_NORMED).max(axis=1)


def detect_row_ys(frame: np.ndarray) -> list[int]:
    """전보 행 아이콘 top의 클라이언트 y 목록(오름차순)을 반환한다."""
    scores = _scan_column(frame, ui.ROW_ICON_BOX, ui_template("row_icon.png"))
    ys: list[int] = []
    while True:
        y = int(scores.argmax())
        if scores[y] < ui.ROW_NCC_THRESHOLD:
            return sorted(ys)
        ys.append(y)
        scores[max(0, y - 6):y + 7] = -1.0   # 인접 피크 억제

def find_panel_anchor(frame: np.ndarray) -> int | None:
    """펼침 패널('아군' 라벨)을 찾아 패널 앵커 y를 반환한다. 미펼침이면 None."""
    scores = _scan_column(frame, ui.FRIENDLY_BOX, ui_template("panel_friendly.png"))
    y = int(scores.argmax())
    if scores[y] < ui.PANEL_NCC_THRESHOLD:
        return None
    return y - (ui.FRIENDLY_BOX[1] - ui.PANEL_ANCHOR_Y)


_ROW_TO_ANCHOR = ui.PANEL_ANCHOR_Y - 127   # 펼친 행 아이콘 top(기준선 127) → 앵커
_PANEL_H = ui.PANEL_REGION[3] - ui.PANEL_ANCHOR_Y


def row_anchor(icon_y: int) -> int:
    """펼친 행의 아이콘 top y → 패널 앵커 y."""
    return icon_y + _ROW_TO_ANCHOR


def row_expanded(frame: np.ndarray, icon_y: int) -> bool:
    """행 앵커 근방의 '아군' 세로 라벨 유무로 펼침 상태를 판정한다."""
    tpl = ui_template("panel_friendly.png")
    x0, _, x1, _ = ui.FRIENDLY_BOX
    top = row_anchor(icon_y) + (ui.FRIENDLY_BOX[1] - ui.PANEL_ANCHOR_Y)
    pad = ui.ROW_SCAN_PAD
    zone = frame[max(0, top - pad):top + tpl.shape[0] + pad,
                 max(0, x0 - pad):x1 + pad]
    if zone.shape[0] < tpl.shape[0] or zone.shape[1] < tpl.shape[1]:
        return False
    return float(cv2.matchTemplate(zone, tpl, cv2.TM_CCOEFF_NORMED).max()) \
        >= ui.PANEL_NCC_THRESHOLD


@dataclass
class WalkSummary:
    processed: int = 0
    saved: int = 0
    failed: int = 0
    partial: int = 0
    skipped: int = 0


class ListWalker:
    """교전 목록 순회 — 펼친 행 파싱, 접힌 행 펼침(1회 재시도), 스크롤·종착."""

    def __init__(self, judge: ScreenJudge, input_, parser, store, run_id: int,
                 *, max_items: int | None = None, scroll: bool = True,
                 captures_dir: Path | str = Path("output") / "captures"):
        self.judge = judge
        self.input = input_
        self.parser = parser
        self.store = store
        self.run_id = run_id
        self.max_items = max_items
        self.scroll = scroll
        self.captures_dir = Path(captures_dir)
        self.summary = WalkSummary()
        self._seen_panels: set[str] = set()
        self._expand_attempts: dict[str, int] = {}
        self._skipped: set[str] = set()
        # 묶음 펼침은 아코디언(2026-08-09 실기) — 새 묶음을 펼치면 이전 묶음이
        # 재접힘된다. 파싱을 마친 묶음의 재접힘 헤더 서명을 기억해 재클릭을
        # 막는다(재접힘 헤더는 픽셀 동일 실측 — img/accordion_s0·s2).
        self._done_rows: set[str] = set()
        self._pending_expand: str | None = None

    # -- 프레임 도우미 -------------------------------------------------------

    def _client(self, window_frame: np.ndarray) -> np.ndarray:
        ox, oy = self.judge.client_offset(window_frame)
        cw, ch = self.judge.client_size
        return window_frame[oy:oy + ch, ox:ox + cw]

    def _at_list(self, window: np.ndarray) -> bool:
        """전보 목록 화면 판정 — 화면 제목 마커(탭 무관)."""
        name, rect = ui.MARKER_TELEGRAM
        return self.judge.marker_score(window, rect, ui_template(name)) \
            >= ui.MARKER_NCC_THRESHOLD

    def _recover(self) -> None:
        """목록 화면 이탈 복구(결함 F — 2026-08-09 실기).

        열람된 단건 행 클릭은 인라인 펼침이 아니라 전투 상세 화면으로 전환된다.
        귀환으로 복귀하고 원인 행은 상세형으로 건너뜀 처리한다(재클릭 무의미).
        """
        if self._pending_expand is not None:
            self._skipped.add(self._pending_expand)
            self.summary.skipped += 1
            log.warning("행 클릭이 화면 전환 유발(상세형) — 건너뜀: %s",
                        self._pending_expand[:12])
            self._pending_expand = None
        for _ in range(2):
            self.input.click(*ui.CLICK_RETURN)
            self.input.move(*ui.MOUSE_PARK)
            self.input.pause()
            if self._at_list(self.judge.wait_stable()):
                log.info("전보 목록 복귀")
                return
        raise WrongScreen("전보 목록 이탈 — 귀환 복구 실패")

    @staticmethod
    def _crop(frame: np.ndarray, box, dy: int = 0) -> np.ndarray:
        x0, y0, x1, y1 = box
        return frame[y0 + dy:y1 + dy, x0:x1]

    def _row_sig(self, frame: np.ndarray, icon_y: int) -> str:
        strip = frame[icon_y:icon_y + 20, ui.ROW_ICON_BOX[0]:ui.ROW_CLICK_X]
        return hashlib.sha1(np.ascontiguousarray(strip).tobytes()).hexdigest()

    # -- 순회 ---------------------------------------------------------------

    def walk(self) -> WalkSummary:
        while True:
            window = self.judge.wait_stable()
            if not self._at_list(window):
                self._recover()
                continue
            frame = self._client(window)
            if self._pass(frame):
                continue                      # 화면이 변형됨 — 재탐지부터
            if self._done():
                return self.summary
            if not self.scroll:
                return self.summary
            before = self._crop(frame, ui.LIST_REGION)
            self.input.wheel(*ui.SCROLL_POINT, -ui.SCROLL_NOTCHES)
            self.input.move(*ui.MOUSE_PARK)   # 호버 확대 렌더 방지(결함 E)
            after_window = self.judge.wait_stable()
            if not self._at_list(after_window):
                self._recover()
                continue
            after = self._crop(self._client(after_window), ui.LIST_REGION)
            if same_image(before, after):
                return self.summary           # 종착 — 더 이상 스크롤되지 않음

    def _done(self) -> bool:
        return self.max_items is not None and \
            self.summary.processed >= self.max_items

    def _pass(self, frame: np.ndarray) -> bool:
        """가시 행 1패스. 화면을 변형시키는 조작(펼침 클릭)을 하면 True."""
        for icon_y in detect_row_ys(frame):
            if self._done():
                return False
            if icon_y < ui.LIST_REGION[1]:
                continue   # 상단 경계에 걸린 행 — 스크롤은 아래로만 가므로 이미 처리됨
            if row_expanded(frame, icon_y):
                a = row_anchor(icon_y)
                if a + _PANEL_H > frame.shape[0]:
                    return False              # 패널이 잘림 — 스크롤 후 처리
                self._parse_row(frame, a)
                continue
            sig = self._row_sig(frame, icon_y)
            if sig in self._skipped or sig in self._done_rows:
                continue
            attempts = self._expand_attempts.get(sig, 0)
            if attempts >= 2:                 # 1회 재시도까지 실패 — 건너뜀(NFR-01)
                self._skipped.add(sig)
                self.summary.skipped += 1
                log.warning("행 펼침 실패(재시도 포함) — 건너뜀: %s", sig[:12])
                continue
            self._expand_attempts[sig] = attempts + 1
            self._pending_expand = sig
            self.input.click(ui.ROW_CLICK_X, icon_y + ui.ROW_CLICK_DY)
            self.input.move(*ui.MOUSE_PARK)   # 호버 확대 렌더 방지(결함 E)
            self.input.pause()
            return True
        return False

    def _parse_row(self, frame: np.ndarray, anchor_y: int) -> None:
        dy = anchor_y - ui.PANEL_ANCHOR_Y
        panel = self._crop(frame, ui.PANEL_REGION, dy)
        sig = hashlib.sha1(np.ascontiguousarray(panel).tobytes()).hexdigest()
        if sig in self._seen_panels:
            return                            # 같은 렌더링 재방문(패스·스크롤 중복)
        # 이중 프레임 확증 — 전환·스크롤 연출 중의 일시 렌더를 파싱하면 필드
        # 오독으로 같은 전보가 다른 키로 중복 저장된다(2026-08-09 실기 실증:
        # 병력 9800→98 오독 중복). 다음 패스에서 재시도한다.
        fresh = self._client(self.judge.fresh())
        if not same_image(panel, self._crop(fresh, ui.PANEL_REGION, dy)):
            log.info("패널 렌더 미안정 — 이번 패스 건너뜀 (anchor %d)", anchor_y)
            return
        self._seen_panels.add(sig)
        rec = self.parser.parse(frame, anchor_y)
        if rec is None:
            # 무효 렌더(확대 등 일과성) — 저장하지 않는다. 같은 픽셀은 서명으로
            # 재파싱을 막고, 정상 재렌더는 새 서명이라 다음 패스에서 파싱된다.
            log.warning("무효 렌더 — 저장하지 않음 (anchor %d)", anchor_y)
            return
        if self._pending_expand is not None:
            # 직전 펼침 클릭이 새 패널로 소비됨 — 그 행의 재접힘 헤더는 완료 처리
            self._done_rows.add(self._pending_expand)
            self._pending_expand = None
        if rec.parse_status != "failed":
            att = sum(1 for s in rec.slots if s.side == "attack")
            dfd = sum(1 for s in rec.slots if s.side == "defend")
            if att < 3 or dfd < 3:
                # 양측 3장수 완전 덱만 유효(A-03 v2, DCR-004) — 결원·NPC 덱은
                # 저장하지 않는다. 전면 실패 기록(fallback 키)은 예외(NFR-01).
                log.info("불완전 덱(공 %d·수 %d) — 저장 안 함 (anchor %d)",
                         att, dfd, anchor_y)
                return
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        capture = self.captures_dir / f"{rec.battle_key}.png"
        Image.fromarray(np.ascontiguousarray(panel)).save(capture)
        rec.capture_path = str(capture)
        self.store.upsert_battle(self.run_id, rec)
        self.summary.processed += 1
        if rec.parse_status == "failed":
            self.summary.failed += 1
        else:
            self.summary.saved += 1
            if rec.parse_status == "partial":
                self.summary.partial += 1
        log.info("전보 저장: %s (%s)", rec.battle_key[:12], rec.parse_status)
