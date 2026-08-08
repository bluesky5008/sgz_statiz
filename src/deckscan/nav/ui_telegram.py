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

USER_ATT = _box(820, 122, 910, 140)         # 행 헤더: 좌측(아군) 유저명 스트립
USER_DEF = _box(1080, 122, 1170, 140)       # 행 헤더: 우측(적군) 유저명 스트립
ALLI_ATT = _box(640, 122, 700, 140)         # 행 헤더: 좌측 동맹명 스트립
ALLI_DEF = _box(1328, 122, 1386, 140)       # 행 헤더: 우측 동맹명 (미열람 배지 제외)
# 패널 좌측 세로 라벨 하단('공격'/'수비') — 좌우 역할 판정(DES-05 v2, DCR-001).
# 실측: 정답 라벨 0.90~1.00, 오답 0.66~0.77 → 비교 판정(높은 쪽), 최소 0.5.
SIDE_LABEL_BOX = _box(596, 240, 616, 290)
SIDE_MIN_SCORE = 0.5
DATE_BOX = _box(915, 256, 1082, 274)        # 전투 일시 텍스트
SEAL_BOX = _box(955, 142, 1040, 210)        # 승/무/패 인장 — 글리프 전용 영역
                                            #   (행 헤더의 위치 텍스트 제외, 2026-08-09 실기 실측)

_CARD_LEFTS = [630, 726, 822, 1103, 1199, 1295]   # 카드 좌 x — 공격 0~2, 수비 3~5
CARD_BOXES = [_box(cl, 145, cl + 96, 270) for cl in _CARD_LEFTS]
PORTRAIT_BOXES = [_box(cl + 18, 166, cl + 76, 214) for cl in _CARD_LEFTS]
NAME_BAR_BOXES = [_box(cl - 2, 233, cl + 80, 252) for cl in _CARD_LEFTS]
TROOPS_BOXES = [_box(cl - 8, 251, cl + 88, 269) for cl in _CARD_LEFTS]

# -- 화면 이동 (DES-02·DES-03) --------------------------------------------------

# 클릭 좌표(클라이언트 픽셀). 2026-08-09 실기 클릭 검증(output/agent_shell res_0002~0005:
# 각 클릭 후 스냅샷으로 목표 화면 도달 확인).
CLICK_MORE = (1432, 631)                # 메인 하단 바 '더 보기'
CLICK_MENU_ALLIANCE = (1124, 535)       # 더 보기 메뉴의 '동맹'
CLICK_ALLIANCE_TELEGRAM = (2488, 407)   # 동맹 화면 우측 '전보'
CLICK_COMBAT_TAB = (1020, 94)           # 동맹전보 '교전' 탭

# 화면 판정 마커 — (assets/templates/ui/ 파일명, 기대 위치 상자).
# 2026-08-09 실기 스냅샷 5장 교차 NCC: 자기 화면 1.000, 타 화면 최대 0.673
# (동맹↔동맹전보 제목 접두 중첩·비활성 탭이 최대 오탐원 — 상자 확장으로 분리).
# 주의: MARKER_MAIN(더 보기 버튼)은 메뉴 열림 상태에서도 보인다 — 메인 화면
# 판별은 MARKER_MENU 부재를 함께 확인할 것.
MARKER_MAIN = ("main_more.png", _box(1104, 510, 1148, 530))
MARKER_MENU = ("menu_alliance.png", _box(845, 434, 922, 456))
MARKER_ALLIANCE = ("alliance_title.png", _box(10, 33, 100, 55))
MARKER_TELEGRAM = ("telegram_title.png", _box(10, 33, 105, 55))
MARKER_COMBAT_TAB = ("combat_tab_on.png", _box(760, 80, 850, 116))
MARKER_NCC_THRESHOLD = 0.8
MARKER_SCAN_PAD = 6                     # 기대 위치 주변 슬라이딩 여유(px)

# -- 전보 목록 (행 재탐지·펼침 판정, DES-04) ------------------------------------

ROW_ICON_BOX = _box(631, 124, 643, 138)      # 행 좌단 아이콘 (모든 전보 행 공통,
                                             #   배너에는 없음) — 템플릿 수확 원본
FRIENDLY_BOX = _box(598, 128, 614, 170)      # 펼침 패널 좌측 '아군' 세로 라벨 상단부
ROW_SCAN_PAD = 4                             # 탐지 시 x 스캔 여유 폭
LIST_REGION = _box(595, 118, 1420, 540)      # 전보 목록 영역(휠 스크롤·종착 판정 대상)
SCROLL_POINT = (1281, 400)                   # 휠 이벤트 전송 지점(목록 중앙, 링크 없는 열)
SCROLL_NOTCHES = 6                           # 1회 스크롤 노치 수(실기 보정 대상, TASK-12)
# 접힌 행 펼침 클릭 지점 — 우측 화살표(∨) 열. 헤더 중앙의 위치 링크·유저명·
# 동맹명은 클릭 금지(오클릭 시 월드맵 이동 — 2026-08-09 실기 사고, DCR-001).
ROW_CLICK_X = round(1392 * _S) - _OX
ROW_CLICK_DY = 7                             # 행 아이콘 top → 행 중앙 y 오프셋
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
