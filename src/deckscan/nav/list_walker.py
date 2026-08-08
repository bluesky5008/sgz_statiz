"""전보 목록의 행 재탐지·펼침 패널 앵커 탐지 (설계 DES-04, FR-02).

매 반복마다 현재 프레임에서 행 아이콘을 템플릿 매칭으로 재탐지한다 — 펼침으로
행 위치가 밀려도 추적 가능하고, 격전 보상 배너는 아이콘이 없어 자연 배제된다.
순회 루프(클릭·스크롤·종착 판정)는 TASK-09 내비게이터와 실기 환경이 갖춰진 뒤
이 모듈에 추가한다(TASK-10 실기 부분).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from . import ui_telegram as ui

UI_DIR = Path(__file__).resolve().parents[3] / "assets" / "templates" / "ui"

FRIENDLY_SCAN_X0 = ui.FRIENDLY_BOX[0] - ui.ROW_SCAN_PAD

_cache: dict[str, np.ndarray] = {}


def _template(name: str) -> np.ndarray:
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
    scores = _scan_column(frame, ui.ROW_ICON_BOX, _template("row_icon.png"))
    ys: list[int] = []
    while True:
        y = int(scores.argmax())
        if scores[y] < ui.ROW_NCC_THRESHOLD:
            return sorted(ys)
        ys.append(y)
        scores[max(0, y - 6):y + 7] = -1.0   # 인접 피크 억제

def find_panel_anchor(frame: np.ndarray) -> int | None:
    """펼침 패널('아군' 라벨)을 찾아 패널 앵커 y를 반환한다. 미펼침이면 None."""
    scores = _scan_column(frame, ui.FRIENDLY_BOX, _template("panel_friendly.png"))
    y = int(scores.argmax())
    if scores[y] < ui.PANEL_NCC_THRESHOLD:
        return None
    return y - (ui.FRIENDLY_BOX[1] - ui.PANEL_ANCHOR_Y)
