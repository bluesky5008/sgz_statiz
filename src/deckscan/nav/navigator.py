"""화면 판정·대기 유틸과 좌표 변환 (설계 DES-03의 공통 판정 계층).

출처: map_search C:\\src\\git\\map_search\\src\\mapscan\\nav\\navigator.py 의
판정 유틸(wait_stable, 마커 NCC, _same_image, frame_client_offset)을 이식
(2026-08-08). 월드맵 전용 로직(그리드·점프·팬)은 가져오지 않았다.

좌표계 규약(원본과 동일): 입력은 클라이언트 좌표, 캡처 프레임은 창 전체
(제목 표시줄 포함). 변환은 frame_client_offset()으로 한다.
"""

from __future__ import annotations

import logging
import time

import cv2
import numpy as np

log = logging.getLogger(__name__)

_DIFF_PER_PIXEL = 12     # 픽셀이 "변했다"고 보는 채널 합 차이
_STABLE_FRACTION = 0.05  # 변한 픽셀 비율이 이 미만이면 정지 프레임
_SAME_PIXEL_DIFF = 30
_SAME_MAX_FRACTION = 0.01


class StabilizeTimeout(RuntimeError):
    """화면이 제한 시간 안에 안정되지 않았다."""


class WrongScreen(RuntimeError):
    """기대한 화면이 아니어서 클릭·조작을 중단했다(오클릭 방지)."""


class NavigationTimeout(RuntimeError):
    """클릭 후 목표 화면 마커가 제한 시간 안에 나타나지 않았다."""


def frame_client_offset(frame_shape: tuple[int, ...],
                        client_size: tuple[int, int]) -> tuple[int, int]:
    """캡처 프레임 안에서 클라이언트 (0,0)의 위치 (원본 실측 검증 로직)."""
    fh, fw = frame_shape[:2]
    cw, ch = client_size
    border = (fw - cw) // 2
    return border, fh - ch - border


def changed_fraction(a: np.ndarray, b: np.ndarray) -> float:
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).sum(axis=2)
    return float((diff > _DIFF_PER_PIXEL).mean())


def same_image(a: np.ndarray, b: np.ndarray) -> bool:
    """같은 내용이 렌더링되었는지 엄격 비교(스크롤 종착 판정 등)."""
    if a.shape != b.shape:
        return False
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).sum(axis=2)
    return float((diff > _SAME_PIXEL_DIFF).mean()) <= _SAME_MAX_FRACTION


class ScreenJudge:
    """프레임 크롭·마커 점수·안정화 대기. capture는 grab_fresh()를 제공해야 한다."""

    def __init__(self, capture, client_size: tuple[int, int]):
        self.capture = capture
        self.client_size = client_size

    def client_offset(self, frame: np.ndarray) -> tuple[int, int]:
        return frame_client_offset(frame.shape, self.client_size)

    def crop_client(self, frame: np.ndarray,
                    rect: tuple[int, int, int, int]) -> np.ndarray:
        ox, oy = self.client_offset(frame)
        x0, y0, x1, y1 = rect
        return frame[y0 + oy:y1 + oy, x0 + ox:x1 + ox]

    def marker_score(self, frame: np.ndarray, rect: tuple[int, int, int, int],
                     template: np.ndarray) -> float:
        crop = self.crop_client(frame, rect)
        if crop.shape[:2] != template.shape[:2]:
            return 0.0
        return float(cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)[0, 0])

    def wait_stable(self, timeout: float = 6.0, min_still: int = 2,
                    fraction: float = _STABLE_FRACTION) -> np.ndarray:
        """연속 프레임 변화율이 임계 미만인 상태가 min_still회 이어질 때까지 대기."""
        deadline = time.monotonic() + timeout
        prev = self.capture.grab_fresh()
        still = 0
        while time.monotonic() < deadline:
            cur = self.capture.grab_fresh()
            still = still + 1 if changed_fraction(prev, cur) < fraction else 0
            prev = cur
            if still >= min_still:
                return cur
        raise StabilizeTimeout(f"{timeout}s 내 화면 미안정 (임계 {fraction})")

    def wait_marker(self, rect: tuple[int, int, int, int], template: np.ndarray,
                    threshold: float, present: bool = True,
                    timeout: float = 5.0, what: str = "마커") -> np.ndarray:
        """마커의 등장(present=True)/소멸을 폴링 대기하고 마지막 프레임을 반환."""
        deadline = time.monotonic() + timeout
        frame = self.capture.grab_fresh()
        while time.monotonic() < deadline:
            if (self.marker_score(frame, rect, template) >= threshold) == present:
                return frame
            time.sleep(0.1)
            frame = self.capture.grab_fresh()
        raise NavigationTimeout(f"{what} {'등장' if present else '소멸'} 대기 시간 초과 ({timeout}s)")
