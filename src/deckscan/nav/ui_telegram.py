"""화면 좌표·마커 상수 — 이 작업의 유일한 캘리브레이션 지점 (설계 DES-02).

좌표계: 클라이언트 프레임 픽셀(2544×657 전제, NFR-04).
실측 근거: 참고 이미지 img/4~6.png(창 2546×689 = 클라이언트 2544×657 + 좌 1px·
제목 표시줄 31px). 창 픽셀 = round(표시 2000px 좌표 × 2546/2000),
클라이언트 = 창 - (1, 31).

펼친 패널 상수는 img/4.png의 행 배치를 기준선으로 삼고, 실제 패널의 세로
위치 차이는 앵커 y와 PANEL_ANCHOR_Y의 차만큼 상자 전체를 평행이동해
적용한다(가정 A-07 — 패널 내부 배치는 top 기준 상대 고정).

클릭 좌표와 화면 판정 마커는 TASK-03 실기 실측에서 이 모듈에 추가한다.
"""

_S = 2546 / 2000   # 표시 좌표 → 창 픽셀 배율
_OX, _OY = 1, 31   # 창 → 클라이언트 오프셋


def _box(x0: float, y0: float, x1: float, y1: float) -> tuple[int, int, int, int]:
    return (round(x0 * _S) - _OX, round(y0 * _S) - _OY,
            round(x1 * _S) - _OX, round(y1 * _S) - _OY)


# -- 펼친 패널 (기준선 img/4.png) ------------------------------------------------

PANEL_ANCHOR_Y = round(122 * _S) - _OY      # 행 헤더 텍스트 라인 top (클라이언트 y)
PANEL_REGION = _box(595, 112, 1420, 285)    # 대체 키 해시·전체 증거용 패널 영역

USER_ATT = _box(820, 122, 910, 140)         # 행 헤더: 공격 유저명 스트립
USER_DEF = _box(1080, 122, 1170, 140)       # 행 헤더: 수비 유저명 스트립
ALLI_ATT = _box(640, 122, 700, 140)         # 행 헤더: 공격 동맹명 스트립
ALLI_DEF = _box(1328, 122, 1386, 140)       # 행 헤더: 수비 동맹명 (미열람 배지 제외)
DATE_BOX = _box(915, 256, 1082, 274)        # 전투 일시 텍스트
SEAL_BOX = _box(950, 112, 1045, 195)        # 승/무/패 인장

_CARD_LEFTS = [630, 726, 822, 1103, 1199, 1295]   # 카드 좌 x — 공격 0~2, 수비 3~5
CARD_BOXES = [_box(cl, 145, cl + 96, 270) for cl in _CARD_LEFTS]
PORTRAIT_BOXES = [_box(cl + 18, 166, cl + 76, 214) for cl in _CARD_LEFTS]
NAME_BAR_BOXES = [_box(cl - 2, 233, cl + 80, 252) for cl in _CARD_LEFTS]
TROOPS_BOXES = [_box(cl - 8, 251, cl + 88, 269) for cl in _CARD_LEFTS]

# -- 전보 목록 (행 재탐지·펼침 판정, DES-04) ------------------------------------

ROW_ICON_BOX = _box(631, 124, 643, 138)      # 행 좌단 아이콘 (모든 전보 행 공통,
                                             #   배너에는 없음) — 템플릿 수확 원본
FRIENDLY_BOX = _box(598, 128, 614, 170)      # 펼침 패널 좌측 '아군' 세로 라벨 상단부
ROW_SCAN_PAD = 4                             # 탐지 시 x 스캔 여유 폭
# 행 아이콘 실측(img/3~6): 참 행 0.92~1.00, 오탐 상한 ≤0.50
ROW_NCC_THRESHOLD = 0.75
# 펼침 마커 실측(img/3~6): 참 0.957~1.000, 오탐 상한 ≤0.58
PANEL_NCC_THRESHOLD = 0.85

# 텍스트 스트립 NCC 임계 — 행 y 위치별 배경 그라데이션 차이로 같은 텍스트도
# 교차 이미지 점수가 초상(0.97+)보다 낮다(2026-08-09 img/4~6 교차 측정).
# 동맹명: 동일 0.90~0.94, 상이 ≤0.28. 유저명: 동일 0.825~0.942, 상이 ≤0.18.
# 초상은 identity.DEFAULT_THRESHOLD(0.90)를 그대로 쓴다. TASK-12에서 재보정.
ALLI_NCC_THRESHOLD = 0.80
USER_NCC_THRESHOLD = 0.80
