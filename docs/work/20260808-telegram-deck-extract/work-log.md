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
- 현재 결론 또는 상태: 영문 경로(c:\src\git\sgz_statiz)에서 재개 완료. TASK-01·02·04~08 완료 + TASK-10·11 오프라인 부분 완료, **전체 테스트 33건 성공**. 남은 작업은 전부 관리자 실행기 기동(사용자)이 선행 조건인 실기 계열: TASK-03 → 09 → 10(순회) → 11(scan) → 12 → 13.
- 다음 행동: 사용자가 tools\agent_shell_admin.bat를 관리자 권한으로 실행 → [재개 지점](#재개-지점)의 TASK-03 절차.

## 문서 연결

| 방향 | 관계 | 대상 문서 | 대상 항목 | 비고 |
|---|---|---|---|---|
| input | baseline | [PLAN-20260808-telegram-deck-extract: 구현 계획](./plan.md) | TASK-01~13 | 수행 대상 계획 |
| input | baseline | [DESIGN-20260808-telegram-deck-extract: 설계 v1](./design.md) | document | 구현 기준선 |

## 기준선과 현재 계획

기준선 v1(2026-08-08 승인). 계획 변경 없음. 진행 상태는 [plan.md 계획 트리](./plan.md#계획-트리)와 동기화됨.

## 현재 상태

- 진행 중인 작업: TASK-03 (blocked — 관리자 실행기 기동 대기), TASK-10·11 (오프라인 부분 완료, 실기 부분 대기)
- 마지막 완료 작업: TASK-08 + TASK-10·11 오프라인 부분 (2026-08-09)
- 작업 트리 상태: 구현 7/13 완료 + 2 부분 진행, blocked 1 — [plan.md](./plan.md#계획-트리)
- 차단 요인: 게임 클라이언트가 **관리자 권한**으로 실행 중 → UIPI가 비승격 도구의 PostMessage 입력을 차단. 관리자 실행기(tools/agent_shell.ps1 + agent_shell_admin.bat)는 ps1 ASCII 재작성 후 재시도 대기 상태(과거 2회 기동 실패 이력은 아래 발견 사항). 캡처(WGC)·오프라인 작업은 승격 불필요.

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

### 2026-08-09 — git 초기화·GitHub push (사용자 지시)

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

- 다음 작업: ① 관리자 실행기 기동(**사용자**: tools\agent_shell_admin.bat 우클릭 → 관리자 권한으로 실행, 기동 확인은 output\agent_shell\shell_status.txt 의 `elevated=True`) → ② TASK-03 좌표 실측(probe 스냅샷·클릭 검증, ui_telegram에 클릭 좌표·마커 4종 추가, 마커 NCC 실측) → ③ TASK-09 TelegramNavigator → ④ TASK-10 순회 루프(P-03) → ⑤ TASK-11 scan 연결 → ⑥ TASK-12 실기 검증(잔여 수확 포함) → ⑦ TASK-13.
- 먼저 확인할 사항: 이 문서 전체, [plan.md](./plan.md)의 TASK-03·09 정의, [발견 사항](#2026-08-08~09--task-03-착수와-차단)의 실행기 프로토콜(cmd_NNNN.txt → res_NNNN.log/done_NNNN.txt)
- 필요한 명령 또는 파일:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests   # 33건 green 기대
.\.venv\Scripts\python.exe -m deckscan.cli probe            # 창 진단(캡처는 승격 불필요)
# 클릭 검증(승격 필요 — 관리자 실행기 안에서): deckscan probe --click X Y
```
