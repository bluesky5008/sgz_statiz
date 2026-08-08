# WORK-20260808-telegram-deck-extract: deckscan 구현 작업 기록

> 문서 유형: `work-log`
> 작업 ID: `20260808-telegram-deck-extract`
> 상태: `in-progress`
> 기준선: `v1`
> 작성일: 2026-08-08
> 최종 갱신: 2026-08-09
> 관련 문서: [PLAN: 구현 계획](./plan.md), [REQ: 요구사항 v1](./requirements.md), [DESIGN: 설계 v1](./design.md)

## 요약

- 목적: [구현 계획](./plan.md)의 TASK 수행 기록과 재개 지점 유지.
- 현재 결론 또는 상태: **TASK-01~09 + 10·11 전체 구현 완료**(기준선 v2, DCR-001), 오프라인 테스트 **44건 성공**. 실기 scan 동작 실증(전체 목록 순회·저장·멱등·요약). TASK-12 진행 중 — 세션 마감 시점에 AC-03용 2회 연속 scan(cmd_0018)이 관리자 실행기에서 실행 중이며 결과는 res_0018.log·DB에 남는다. 실기 결함 2건 조사 대기(아래 재개 지점).
- 다음 행동: [재개 지점](#재개-지점) — cmd_0018 결과 확인부터.

## 문서 연결

| 방향 | 관계 | 대상 문서 | 대상 항목 | 비고 |
|---|---|---|---|---|
| input | baseline | [PLAN-20260808-telegram-deck-extract: 구현 계획](./plan.md) | TASK-01~13 | 수행 대상 계획 |
| input | baseline | [DESIGN-20260808-telegram-deck-extract: 설계 v1](./design.md) | document | 구현 기준선 |

## 기준선과 현재 계획

기준선 v1(2026-08-08 승인). 계획 변경 없음. 진행 상태는 [plan.md 계획 트리](./plan.md#계획-트리)와 동기화됨.

## 현재 상태

- 진행 중인 작업: TASK-12 (실기 통합 검증 — AC-03 2회 scan이 cmd_0018로 실행 중, 결함 2건 조사 대기)
- 마지막 완료 작업: TASK-10·11 완결(순회 루프·scan 연결, 2026-08-09)
- 작업 트리 상태: 구현 11/13 완료 — [plan.md](./plan.md#계획-트리)
- 차단 요인: 없음. 관리자 실행기 가동 중(pid 30648, 유휴 300분 후 자동 종료 — 죽었으면 사용자가 tools\agent_shell_admin.bat 재실행). 다음 명령 순번: cmd_0019.

## 수행 기록

### 2026-08-08 — 착수, TASK-01, TASK-02

- 수행 내용: 사용자 구현 착수 승인. 프로젝트 뼈대(pyproject.toml, src/deckscan, .venv, 스모크 테스트). map_search 플랫폼 계층 5개 파일(win32/input/capture/session/watchdog) 무수정 복사+출처 주석. 판정 유틸(navigator.py: wait_stable·마커 NCC·same_image·frame_client_offset) 이식. probe CLI(창 진단·스냅샷·캘리브레이션 클릭) 작성.
- 변경 파일: pyproject.toml, .gitignore, src/deckscan/(__init__, cli, watchdog, win/*, nav/navigator), tests/test_smoke.py, tools/agent_shell.ps1(+bat)
- 실행한 검증: `pip install -e .` + 스모크 테스트 OK. probe 실기: 창 hwnd=0x2097c, **클라이언트 2544×657 = 캘리브레이션 일치 확인**, WGC 캡처 정상(승격 불필요), 메인 화면 스냅샷 output/probe/에 확보.

### 2026-08-08 — TASK-04 DataStore (TDD)

- 수행 내용: 실패 테스트 8건 선작성(Red 확인) → 스키마·멱등 upsert·battle_key·대체 키·identity 수명주기·deck_rows 조인 구현(Green).
- 변경 파일: src/deckscan/store/datastore.py, tests/test_datastore.py
- 결과: 8/8 성공.

### 2026-08-08 — TASK-05 IdentityMatcher (TDD)

- 수행 내용: img/4·5.png 유저명 스트립 픽스처 테스트 4건 작성 → NCC 슬라이딩 매칭+pending 등록 구현.
- TDD 편차: 테스트를 먼저 작성했으나 **Red 실행을 생략**하고 구현 후 바로 Green 확인 — 절차 편차로 기록.
- 결과: 4/4 성공. **교차 스크린샷(행 위치 상이) 동일 유저 매칭·상이 유저 구분 실증** — ADR-002의 핵심 가정 검증됨.
- 변경 파일: src/deckscan/vision/identity.py, tests/test_identity.py

### 2026-08-09 — TASK-06 레벨 글리프 (TDD)

- 발견: 덱 카드 이름 바의 **레벨 숫자는 흰색**(장수명은 주황) — map_search DigitReader의 크림 마스크(S<90, V≥170)가 그대로 유효하며 마스크가 레벨 숫자만 자연 분리한다. 금색 마스크 가정은 기각.
- 수행 내용: digits.py 이식(DEFAULT_DIR만 digits_level로 변경). img/4~6에서 글리프 수확(0·4·5·9 + 변형) → assets/templates/digits_level/.
- 결과: 픽스처 18건 레벨 정확 판독(분리된 '0'은 repair 패스로 복구 — 원본의 알려진 실패 모드와 동일).
- 잔여: 글리프 **1·2·3·6·7·8 미수확** — 픽스처에 레벨 49·50만 존재. 실기에서 다른 레벨 등장 시 '?' → partial + 증거 저장 → 수확 등록(TASK-12).
- 변경 파일: src/deckscan/vision/digits.py, tests/test_digits.py, assets/templates/digits_level/*

### 2026-08-09 — TASK-07 OcrReader (TDD)

- 수행 내용: Red(병력 4건·일시 실패) → 원인 2건 실측 수정: ① 이진화에 잡음 성분 제거(면적 필터)+12px 흰 여백 패딩 필요(Windows OCR이 테두리 파편·여백 부족 시 인식 거부), ② 일시 텍스트 위치 정정(표시 y 256~274 — 인장 아래).
- 결과: 병력 18/18, 일시 3/3, 승 인장 3/3 성공. 승 인장 템플릿 수확(assets/templates/result/win.png).
- 잔여: **무·패 인장 템플릿 미수확** — 실기에서 무/패 전보를 펼쳐 수확 필요(TASK-12).
- 변경 파일: src/deckscan/vision/ocr.py, tests/test_ocr.py, assets/templates/result/win.png

### 2026-08-08~09 — TASK-03 착수와 차단

- 수행 내용: probe로 실기 창 확인(위 TASK-02 기록). 메인 화면 스냅샷 확보. 클릭 단계에서 차단.
- 발견 사항(재개 시 필수 숙지):
  1. **게임이 관리자 권한 실행** → 비승격 도구의 클릭이 UIPI에 차단됨. **캡처(WGC)는 승격 불필요**.
  2. Claude의 자체 승격 프로세스 기동은 권한 정책 차단 → 사용자가 직접 관리자 실행기를 기동해야 함.
  3. 관리자 실행기 기동 실패 2회: 1차 — 한글 경로 명령 타이핑 문제 추정. 2차(.bat 우클릭) — **tools/agent_shell.ps1이 비BOM UTF-8 + 한글 리터럴이라 PS 5.1이 오해석했을 가능성** → ps1을 ASCII 전용($PSScriptRoot 기반 경로)으로 재작성 완료. **수정 후 재시도는 아직 안 됨.**
  4. 실행기 프로토콜: output/agent_shell/에 cmd_0001.txt(PowerShell 스크립트) 작성 → 실행기가 res_0001.log(출력)+done_0001.txt(종료코드) 생성. 순번 증가. `quit` 로 종료. 상태는 shell_status.txt.
- 참고 좌표(메인 화면 스냅샷 실측 전 추정치, 표시 2000px 좌표계 ×1.273→프레임, 클라이언트=프레임-(1,31)): 더 보기 클릭 ≈ 클라이언트 (1435, 631). TASK-03에서 실측 확정할 것.

### 2026-08-09 — 세션 정리

- 사용자 결정: 한글 폴더명(동맹전보_통계정리)을 영문으로 변경하고 새 세션에서 재개. 한글 경로가 관리자 실행기 문제의 근본 원인 후보이므로 합리적 조치.
- 전체 테스트 최종 확인: **17건 전부 성공** (smoke 1 + datastore 8 + identity 4 + digits 1 + ocr 3).

### 2026-08-09 — 세션 재개 (영문 경로 c:\src\git\sgz_statiz)

- venv 재생성 완료: Python 3.13.1, `pip install -e .` 성공 (numpy 2.5.1, opencv 5.0.0.93, pillow 12.3.0, windows-capture 2.0.0, winocr 0.0.15).
- 전체 테스트 재확인: **17건 전부 성공** — 폴더 이동에 따른 회귀 없음.
- 관리자 실행기 미기동(output/agent_shell/ 없음) → TASK-03은 사용자 기동 대기, 병행 오프라인 작업 TASK-08 착수.

### 2026-08-09 — TASK-08 DeckParser (TDD)

- 사전 실측(img/4~6 교차 측정, 스크래치): 초상 크롭 `(카드좌+18, 166, 카드좌+76, 214)`(표시 좌표) — 같은 장수 NCC 0.974~0.990, 다른 장수 ≤0.469. 동맹명은 **행 헤더 라인**(유저명과 같은 y)에 위치: 공격 (640,122,700,140), 수비 (1328,122,1386,140) — 수비 쪽은 우측 미열람 빨간 배지(행 상태 요소)를 제외하도록 조정.
- 수행 내용: AC-02 인수 테스트 5건 선작성(Red: 모듈 부재 확인) → `nav/ui_telegram.py`(패널 상수 절, 클라이언트 프레임 좌표계) + `vision/deck_parser.py`(DES-05) 구현.
- Red→Green 과정의 실측 발견: 유저명 스트립은 행 y 위치별 배경 그라데이션 차이로 같은 유저도 교차 이미지 NCC가 0.825까지 떨어짐(수비 유저 4↔5 = 0.854 < 기본 임계 0.90 → ID 분열로 테스트 1건 실패). 분리도 실측(같은 유저 min 0.825, 다른 유저 max 0.178, 심나온 접힌 행 표본 포함) 후 **유저·동맹 네임스페이스 임계 0.80** 채택(`ui_telegram.USER_NCC_THRESHOLD`·`ALLI_NCC_THRESHOLD`). 초상은 기본 0.90 유지. match_score 저장으로 사후 감사 가능(RISK-04 완화 그대로), TASK-12에서 재보정.
- 구현 세부: ① 빈 카드 칸(A-03)은 레벨 텍스트 없음+병력 판독 실패 조합으로 판정해 증거 없이 제외(실기 확정은 TASK-12), ② 정보가 전혀 없는 슬롯은 저장하지 않음, ③ 대체 키(`img-` 접두)는 일시·유저 ID·슬롯이 모두 빈 경우에만 사용(설계 그대로), ④ 실패 필드 증거는 `<패널해시12>_<필드>.png` — 무·패 인장 미수확 시 `result` 증거가 수확 원본이 됨, ⑤ 템플릿 디렉터리는 네임스페이스 단수형(`user/general/alliance` — 설계 예시의 복수형 명칭과 다른 내부 세부).
- 결과: 신규 테스트 5건 성공 — AC-02 전체 레코드+라벨 조회, 교차 이미지 ID 안정성(공격 덱 3장 동일·수비 9종 상이)+새 파서 재파싱 battle_key 재현(FR-05 오프라인), 일시 훼손 partial+증거(AC-04·NFR-01 부분), 빈 슬롯 제외(A-03), 구성요소 예외 시 failed+대체 키 멱등. **전체 22건 성공.**
- 변경 파일: src/deckscan/nav/ui_telegram.py(신규), src/deckscan/vision/deck_parser.py(신규), tests/test_deck_parser.py(신규)

### 2026-08-09 — TASK-10 오프라인 부분: 행 재탐지·펼침 앵커 (TDD)

- 사전 실측(img/3~6, 스크래치): 행 좌단 아이콘(표시 631,124,643,138)이 모든 전보 행에 존재하고 격전 배너에는 없음 — 행 재탐지 앵커로 채택. 참 행 NCC 0.92~1.00 vs 오탐 상한 ≤0.50 → 임계 0.75. 펼침 패널 '아군' 세로 라벨(표시 598,128,614,170): 참 0.957~1.000 vs 오탐 ≤0.58 → 임계 0.85. 발견: 펼친 행 헤더와 접힌 행은 아이콘 세로 위치가 수 px 다름(펼침 시 헤더 재스타일). img/3.png(전체 탭)도 동일 구조 확인.
- 수행 내용: 픽스처 테스트 5건 선작성(Red: 모듈 부재) → 템플릿 2종 수확(assets/templates/ui/row_icon.png·panel_friendly.png) → `nav/list_walker.py`의 `detect_row_ys`·`find_panel_anchor` 구현(Green). 순회 루프(클릭·스크롤·종착)는 TASK-09·실기 이후로 남김.
- Red→Green 과정의 결함 발견·수정: 탐지 앵커는 반올림 누적으로 내용 앵커와 ±1px 어긋날 수 있는데, 1px 이동만으로 병력 "10433"이 OCR에서 "104"+"33"으로 분리 인식됨(자간 넓음, 5.png 실측) → `OcrReader.read_number`에 **숫자 사이 공백·구두점 접합** 수정(근본 원인 수정 — 실기에서도 발생할 위험). 탐지 앵커로 5·6.png 파싱 정확성 테스트로 회귀 방지.
- 자산 대장 작성: assets/templates/README.md (digits_level·result·ui·식별 네임스페이스, 잔여 수확 항목 명시). row_icon이 동맹 문장일 가능성은 TASK-12 확인 항목으로 기록.
- 결과: 신규 테스트 5건 성공(행 y 탐지 4픽스처·배너 배제·앵커 정합 ±1px·마커 부재 시 None·탐지 앵커 파싱 정확성). **전체 27건 성공.**
- 변경 파일: src/deckscan/nav/list_walker.py(신규), src/deckscan/nav/ui_telegram.py(목록 탐지 상수 추가), src/deckscan/vision/ocr.py(read_number 접합 수정), tests/test_list_walker.py(신규), assets/templates/ui/*(신규 2종), assets/templates/README.md(신규)

### 2026-08-09 — 관리자 실행기 기동 실패 근본 원인 확정·수정

- 사용자 3차 기동 시도 실패 출력(`'?쇰줈'`·`'oProfile'`·`'뚮맖]'` 명령 인식 불가)으로 원인 확정: **agent_shell_admin.bat 자체**가 ① 비BOM UTF-8 한글(rem·echo 줄)을 cmd.exe가 CP949로 오해석 + ② LF 전용 줄바꿈(cmd는 CRLF 요구, LF 전용은 줄 병합·분할 오동작 — `'oProfile'` 분리가 그 증거). 오류가 PowerShell 기동 전 cmd 단계에서 났으므로, 지난 세션의 "ps1 인코딩" 가설은 부분 원인이었고 bat가 주 원인.
- 수정: bat를 순수 ASCII + CRLF로 재작성(비ASCII 0바이트 확인). ps1은 ASCII 상태 유지 확인(비ASCII 0바이트). powershell 줄을 echo로 치환한 무해 사본으로 cmd 파싱 정상 검증.
- 다음: 사용자 재시도 대기 — 우클릭 → 관리자 권한으로 실행, 기동 확인은 output\agent_shell\shell_status.txt 의 `elevated=True`.

### 2026-08-09 — TASK-03 좌표 실측·마커·인장 (실기, 관리자 실행기 경유)

- 관리자 실행기 3차 시도 **성공**(bat ASCII+CRLF 재작성 후): shell_status `elevated=True`, pid 30648. 프로토콜(cmd_NNNN.txt → res/done) 정상 동작, cmd_0001~0008 수행.
- 창 확인: hwnd=0x2097c, 클라이언트 2544×657(캘리브레이션 일치), WGC 프레임은 창 크기 2546×689(참고 이미지와 동일 기하).
- **클릭 좌표 4종 실측 검증(각 클릭 후 스냅샷으로 도달 확인, 복구 경로에서 2회째 재검증)**: 더 보기 (1432,631) → 동맹 (1124,535) → 전보 (2488,407) → 교전 탭 (1020,94) — 모두 클라이언트 좌표, `ui_telegram.CLICK_*` 등록. 참고 이미지와 실기 배치 일치(가정 A-06 성립).
- **마커 5종 수확·교차 검증**(실기 스냅샷 5장 NCC 행렬): 자기 화면 1.000 / 타 화면 최대 0.673 → 임계 0.8. 함정 2건 해결: ① '동맹' 제목이 '동맹전보'의 접두 — 제목 우측 여백을 상자에 포함해 분리(0.669), ② 교전 탭 활성이 텍스트 상자로는 비활성과 0.954 — 주황 브래킷 포함 탭 전체 상자로 재수확(오탐 ≤0.369).
- **인장 재보정·수확**: 기존 SEAL_BOX가 행 헤더의 전투별 위치 텍스트("울타리(1020,643)")를 포함 → 글리프 전용 (955,142,1040,210)으로 재보정, win.png 재수확 + **무 인장(draw.png) 실기 수확**(교전 탭 2행 무승부 전보). 판별 실측(같은 인장 0.989~1.0, 다른 인장 ≤0.561) → RESULT_THRESHOLD 0.6→0.75. 잔여: 패 인장.
- 실기 프레임에서 오프라인 구현 검증: `detect_row_ys` [127,338,549], `find_panel_anchor` 124 — 모두 정상.
- 목록 상수 추가: LIST_REGION, SCROLL_POINT.
- **위험 발견(사고 1건·복구 완료)**: 행 헤더 **중앙에 위치 링크**("울타리(1020,643)")가 있어 헤더 중앙 클릭(클라이언트 1272,136)이 전보 화면을 닫고 월드맵 해당 좌표로 이동, **행군·주둔 버튼 팝업**이 열림. 검증된 경로(동맹→전보→교전)로 복구. 교훈: 행 클릭 x는 링크·유저명·동맹명 영역을 피해야 함 — 안전 클릭 지대 확정은 TASK-10에서 수행.
- **설계 가정 편차 발견(A-02, DCR 후보)**: 실기 교전 탭은 **모든(미열람) 행이 펼쳐진 상태**로 표시 — 참고 이미지의 아코디언(한 행만 펼침)과 다름. 또한 아군이 수비인 전보는 패널 좌우 역할이 반전됨(좌=수비, 세로 라벨 공격/수비가 방향 표시 — 파서의 좌측=공격 가정에 영향). ListWalker 순회 전략과 DeckParser 측면 매핑에 영향 → **TASK-10 착수 시점에 DCR 여부 판정**(wf-design 반환 준비). 파서 측면 매핑은 세로 라벨 판독으로 해결 가능(구현 세부 후보).
- 전체 테스트 **33건 성공** 유지.
- 변경 파일: src/deckscan/nav/ui_telegram.py(CLICK_*·MARKER_*·SEAL_BOX·LIST_REGION), src/deckscan/vision/ocr.py(RESULT_THRESHOLD), tests/test_ocr.py(인장 상자), assets/templates/ui/*(마커 5종), assets/templates/result/(win 재수확·draw 신규), assets/templates/README.md

### 2026-08-09 — TASK-09 TelegramNavigator (TDD + 실기)

- 선행 테스트 3건 작성(Red: 모듈 부재) → `nav/telegram.py` 구현(Green): 마커 판별(픽스처 img/1~4 — 메뉴·동맹·전보·교전 탭 커버, 실기 수확 템플릿이 전날 픽스처와 정확 위치 NCC 1.000 = 교차 세션 픽셀 동일 실증), 전체 흐름 상태 기계 테스트(가짜 게임), WrongScreen 중단 테스트. `list_walker._template` → 공개 `ui_template`로 개명(공용화).
- 실기 결함 2건 발견·수정(각각 실기 재현 → 원인 수정 → 재검증):
  1. **마커 등장 ≠ 입력 수용**: 동맹 화면 제목이 전환 연출 중 먼저 떠서 즉시 보낸 전보 클릭이 무시됨 → `_wait`에 `wait_stable` 추가(상태 기반 대기, NFR-02). 자동 재현 불가(실기 타이밍) — 사유 기록, 실기 재실행으로 후행 검증.
  2. **목록 갱신 중 클릭 무반응**: 새 전보 도착으로 목록 리렌더 중 교전 탭 클릭이 삼켜짐 → 설계 실패 흐름 표의 "1회 재시도"를 `_click_wait`로 구현(재시도 전 목표 마커 재확인 — 늦은 전환 후 재클릭 토글 방지, 직전 화면 이탈 시 재클릭 금지). **이 건은 가짜 게임으로 오프라인 재현 가능 → 재현 테스트 선작성(Red)** 후 구현.
- **실기 1회 내비게이션 성공**(res_0015, 완료 조건 충족): 메뉴 열림 분기 → 동맹 → 동맹전보 → 교전 탭, 로그에 재시도 WARNING 1회 포함(재시도 로직이 실전 작동). 증거: output/probe/nav_evidence_combat_tab.png.
- 부수 사고·복구(TASK-03 절의 위험 발견과 동일 건): 행 헤더 중앙의 위치 링크 오클릭으로 월드맵 이동 발생했었음 — 내비게이터 화이트리스트 클릭은 팝업 잔존 상태에서도 안전하게 통과함을 실기 확인.
- 변경 파일: src/deckscan/nav/telegram.py(신규), src/deckscan/nav/list_walker.py(ui_template 공개), tests/test_telegram_nav.py(신규 4건)

### 2026-08-09 — TASK-12 잔여 선행 수확: 패 인장 + 글리프 1·2·3·8 (실기 스냅샷)

- 실기 스냅샷에 잔여 수확 재료가 등장해 선행 수확: **패 인장**(nav_evidence 2행 → result/lose.png, 판독 "패", 승 0.483·무 0.379와 분리 — **승·무·패 3종 완비**), **레벨 글리프 1·2·3·8**(전체 탭 스냅샷 레벨 31·32·33, 교전 탭 48·49) + 오독 1건('33'의 첫 글리프가 8로) → 변형 3_2.png 추가로 해소. 잔여 글리프: **6·7만 미수확**.
- 발견(알려진 한계로 기록): NPC 부대 카드("1 군사"·"1 기병")는 부대명도 흰색이라 크림 마스크에 잡혀 레벨 판독이 '1???'로 실패 — 교전 탭 PvP 범위 밖(전체·약탈 탭 전보)이며, 등장해도 partial+증거로 안전 처리됨(NFR-01).
- 검증: PvP 스트립 24장(실기 2프레임 × 12) 전부 정확 판독, 기존 픽스처 회귀 없음 — **전체 테스트 37건 성공**.
- 변경 파일: assets/templates/result/lose.png(신규), assets/templates/digits_level/1·2·3·8·3_2.png(신규)

### 2026-08-09 — DCR-001 승인, 기준선 v2 발행

- TASK-03·09의 실기 발견(A-02 편차·좌우 역할 반전·위치 링크 사고)을 [DCR-001](./changes/DCR-001-list-traversal.md)로 정리해 사용자 승인(2026-08-09). 변경 3건: ① A-02 v2(단건 펼침·묶음 접힘·다중 펼침), ② DES-04 v2(펼침 판정 순회+안전 클릭 지대), ③ DES-05 v2(세로 라벨 측면 판정). 데이터 모델·CSV·AC 불변.
- REQ·DESIGN 기준선 v2 갱신, plan 기준선 절 반영. TASK-10 재개 가능.

### 2026-08-09 — TASK-10 완결부·TASK-11 scan 연결 (TDD + 실기, 기준선 v2)

- **측면 라벨 판정(DES-05 v2)**: side_attack/side_defend 템플릿 수확(실측: 정답 0.90~1.00, 오답 0.66~0.77 → 비교 판정+최소 0.5). 아군=수비 픽스처 img/7.png(실기 스냅샷) 추가, Red(반전 실패 확인)→Green. 판정 불능 시 공격 기본값+partial 표면화.
- **ListWalker 순회 루프(DES-04 v2)**: `row_expanded`(행별 펼침 판정)·`row_anchor`·`ListWalker.walk()`(펼친 행 파싱, 접힌 행 안전 지대 클릭 1회 재시도 후 건너뜀, 패널 잘림 스크롤 유예, 휠 스크롤+`same_image` 종착, 패널 픽셀 서명 중복 방지, battle_key 멱등, capture_path 저장 NFR-03). walk 오프라인 테스트: img/7 정지 화면 2행 파싱·멱등·종착.
- **scan 오케스트레이션(TASK-11 완결)**: `controller.run_scan`(run 기록·예외 경계 — 내비 실패 시 aborted+종료 2, 저장 레코드 유지), CLI `scan` 명령(창·권한·해상도 2544×657 검증 → 종료 1). Red→Green 2건.
- **1차 실기 scan**: exit 0, 처리 5·저장 5. 결함 발견 — 전환·스크롤 연출 중 일시 렌더 파싱으로 병력 9800→98 오독, 같은 전보가 다른 키로 중복 저장(match_score 1.0 vs 0.95~0.98로 두 파싱의 픽셀 상이 실증). → **이중 프레임 확증** 수정(파싱 전 연속 두 프레임의 패널 픽셀 동일 확인, FlickerCapture로 오프라인 재현 테스트 선작성 Red→Green).
- **2차 실기 scan(전체 목록)**: exit 0, 처리 20·고유 전보 13(ok 9·partial 4)·실패 0. partial의 레벨 실패 크롭에서 **글리프 변형 4종 수확**(4_2·4_3·9_2·1_2 — 행 y 위치별 렌더 변형) → 해당 크롭 전부 정독. NPC 부대 카드 레벨 실패는 알려진 한계 유지.
- 진행 중 관찰(조사 예정): ① 접힌 묶음 행의 펼침 클릭(우측 화살표 열)이 실제로는 펼치지 못함 — 전 묶음 행 skip됨(안전 클릭 지대 재실측 필요), ② 목록 경계에 걸린 패널로 추정되는 쓰레기 파싱 1건(side_label 포함 광범위 실패) — 상단 경계 가드 검토.
- 전체 오프라인 테스트 **44건 성공**.
- 변경 파일: src/deckscan/nav/list_walker.py(row_expanded·ListWalker), src/deckscan/nav/ui_telegram.py(SIDE_LABEL·ROW_CLICK·SCROLL 상수), src/deckscan/vision/deck_parser.py(측면 판정), src/deckscan/controller.py(run_scan), src/deckscan/cli.py(scan), tests/*(신규 6건), img/7.png, assets/templates/ui/side_*.png, assets/templates/digits_level/변형 4종

### 2026-08-09 — 포트폴리오 생성·plan 서식 정규화 (사용자 지시)

- [PF-sgz-statiz 포트폴리오](../PF-sgz-statiz/portfolio.md) 생성 — wf-tree 범위 승인 관문 통과(사용자 승인 2026-08-09). 작업 1(본 작업) 등재 + 작업 2(교전 통계 분석·시각화) 후보 등재.
- plan.md를 현행 wf-doc·wf-tree 규칙으로 서식 정규화(의미 불변): ① `## 계획 트리` 절을 `## 작업 목록` 바로 앞으로 이동(템플릿 위치), ② 13개 TASK에 `상위: 없음` 필드 추가(분해 관계 명시), ③ Mermaid를 현행 표기로 재생성(승인 게이트 이중 테두리 `[[★…]]` 분리, in-progress `active`·`blocked` classDef), ④ 문서 연결에 포트폴리오 행 추가, ⑤ ASCII 트리 부분 진행 표기 `◐`→`[▶]` 통일.

- README.md 작성(프로젝트 소개·동작 방식·설치·사용법·구조·문서 링크 — TASK-13에서 최종화 예정), .gitattributes 추가(`*.bat eol=crlf` — 위 실행기 결함 재발 방지, `*.png binary`).
- `git init -b main` → 루트 커밋 580630d(73개 파일: 코드·테스트·문서·자산·img 픽스처·tools. .venv/output은 .gitignore로 제외) → https://github.com/bluesky5008/sgz_statiz 에 push, `origin/main` 추적 설정. 원격 해시 일치·작업 트리 클린 확인.

### 2026-08-09 — TASK-11 오프라인 부분: export·label·요약 (TDD)

- 수행 내용: 선행 테스트 5건 작성(Red: 모듈 부재) → `store/csv_export.py`(UTF-8 BOM, battles_·deck_long_ 2종 — map_search 규약 이식, 분할 저장은 규모상 제외), `controller.py`(`label_pending` — 빈값=건너뜀·q=중단·확정 수 반환, `summarize_run` — FR-06 요약+pending 안내), `datastore.battle_rows()`(전보 1행 라벨 조인), CLI `export`·`label` 명령 연결(Green). deck_long 컬럼은 설계 열거 그대로(동맹·parse_status는 battles CSV가 담당).
- 스모크에서 결함 발견·수정(TDD 재현 테스트 선행): DB 부모 디렉터리 부재 시 sqlite 열기 실패(기본 경로 `output/deckscan.db` 최초 실행이 해당) → 재현 테스트 `DbPathTest` 추가(Red 확인) 후 `DataStore.__init__`에 부모 디렉터리 생성 추가(Green).
- 결과: 신규 테스트 6건 성공(CSV 계약·label 확정/건너뜀/중단/프롬프트 내용·요약 집계·DB 경로). CLI `export` 실기 스모크 exit 0. **전체 33건 성공.**
- 잔여(TASK-11): `scan` 명령 오케스트레이션 — TASK-09·10 실기 부분 이후.
- 변경 파일: src/deckscan/store/csv_export.py(신규), src/deckscan/controller.py(신규), src/deckscan/store/datastore.py(battle_rows·경로 수정), src/deckscan/cli.py(export·label), tests/test_controller.py(신규), tests/test_datastore.py(DbPathTest)

## 설계와 달라진 점

- 없음(기준선 준수). 구현 세부 확정 2건: ① 레벨 숫자 마스크는 원본 크림 마스크 재사용(금색 가정 기각 — 내부 세부사항), ② OCR 이진화 전처리에 성분 필터+패딩 추가(내부 세부사항).

## 미완료 항목

- TASK-03(blocked — 관리자 실행기 대기), TASK-09, TASK-10(실기 부분), TASK-11~13
- 실기 수확 잔여: 레벨 글리프 1·2·3·6·7·8, 무·패 인장
- TASK-12 확인 항목: row_icon 템플릿의 동맹 문장 여부, 유저·동맹 NCC 임계 0.80 재보정, 빈 카드 칸 판정 실기 확인

## 재개 지점

- 다음 작업 (TASK-12 계속):
  1. **cmd_0018 최종 결과 분석** (세션 마감 직전 완료됨): 1차 scan **내비게이션 단계 aborted**(exit 2, 0건 — 귀환×2가 메인에 도달하지 못한 듯, res_0018.log의 run#1 트레이스 확인), 2차 scan **순회 중 예외로 aborted**(exit 2 — 처리 24건·저장 24건까지 진행 후 중단, **결함 C**: res_0018.log의 run#2 트레이스에서 원인 확인 — StabilizeTimeout(스크롤 연출 미안정) 또는 파서 예외 후보). 저장 레코드는 설계대로 유지됨. AC-03 판정은 결함 수정 후 재실행 카운트 비교로 수행.
  2. **결함 A — 접힌 묶음 행 펼침 클릭 무효**: ROW_CLICK_X(우측 화살표 열, 클라이언트 x=1771) 클릭이 묶음 행을 펼치지 못해 전부 skip됨. 실기 probe로 유효 클릭 지대 실측(후보: 헤더의 텍스트 없는 빈 구간, 표시 x≈1025~1075 → 클라이언트 ≈1303. **주의: 중앙 위치 링크(표시 945~1055 부근 단건 행)·유저명·동맹명 클릭 금지** — 오클릭 시 월드맵 이동). 묶음 행 전용이므로 [N회 승] 텍스트(중앙)와 수비 유저명 사이 빈 구간이 후보.
  3. **결함 B — 목록 경계 패널 가드**: 스크롤로 목록 상단·경계에 걸친 패널이 파싱돼 광범위 실패 레코드 1건 발생(side_label 포함 전 필드) — `_pass`에 앵커 하한 가드(`anchor < LIST_REGION[1]` skip) 추가 + 재현 테스트.
  4. 수정 후 DB 초기화(output/deckscan.db·captures·evidence 삭제) → **연속 2회 scan**으로 AC-01·03·04 판정 → verification.md 작성(VER-01~06, 증거: res 로그·DB 카운트·captures).
  5. TASK-13: README 최종화·completion.md·추적성 갱신.
- 먼저 확인할 사항: 이 문서의 2026-08-09 기록 전체(특히 TASK-10 완결부·DCR-001), [plan.md](./plan.md), [DCR-001](./changes/DCR-001-list-traversal.md)
- 환경: 관리자 실행기(유휴 300분 자동 종료 — shell_status.txt 확인, 죽었으면 사용자가 tools\agent_shell_admin.bat 관리자 실행). 다음 명령 순번 cmd_0019. 게임 클라이언트 상시 사용 허가(2026-08-09 사용자).
- 필요한 명령 또는 파일:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests   # 44건 green 기대
Get-Content output\agent_shell\res_0018.log | Select-Object -Last 20   # 2회 scan 결과
# 실행기 프로토콜: output\agent_shell\cmd_0019.txt 작성 → res_0019.log/done_0019.txt 대기
# scan 시작 전제: 메인 화면(귀환 ×2로 복귀 가능, 클라이언트 (2499,24) 클릭)
```

### 다음 세션 시작 프롬프트 (사용자용)

> sgz_statiz 프로젝트(deckscan)의 진행 중 작업을 재개하자.
> `docs/work/20260808-telegram-deck-extract/work-log.md`의 재개 지점과 `plan.md`를 읽고 wf-implement 워크플로우로 TASK-12부터 계속 진행해줘.
> 순서: 지난 세션에 걸어둔 2회 scan(cmd_0018) 결과 확인 → 결함 A(묶음 행 펼침 클릭 실측)·결함 B(목록 경계 가드) 수정 → AC-01~06 실기 검증·verification.md → TASK-13 완료 보고.
> 게임 클라이언트는 켜져 있고 언제든 사용해도 된다. 관리자 실행기가 죽어 있으면 내가 다시 실행하겠다.
