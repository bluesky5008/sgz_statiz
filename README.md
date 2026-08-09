# sgz_statiz — 동맹 전보(교전) 덱 정보 추출 도구 `deckscan`

삼국지 전략판 PC 클라이언트의 **동맹전보 → 교전 탭**을 자동으로 순회하며 각
전보의 덱 정보(유저·동맹·장수 6인·레벨·병력·일시·승패)를 화면 캡처와 이미지
인식으로 추출해 SQLite에 저장하고 CSV로 내보내는 로컬 CLI 도구입니다.
게임에 공개 표시되는 정보만 다루며 네트워크 전송은 없습니다.

> **상태: 구현 완료** (기준선 v5, 2026-08-09) — 인수 조건 AC-01~06 실기·단위
> 검증 성공, 오프라인 테스트 61건. 검증 기록:
> [work-log 검증 결과](docs/work/20260808-telegram-deck-extract/work-log.md#검증-결과-verification)

## 동작 방식

- **캡처·입력**: Windows Graphics Capture + PostMessage 클릭 — 창이 가려져도
  동작합니다. 클릭은 상수 모듈의 화이트리스트 좌표로만 전송하고 매 클릭 직전
  현재 화면 마커를 재검증합니다(오클릭 구조적 차단).
- **인식**: 유저명·장수 초상·동맹명은 **템플릿 NCC 매칭 기반 안정 ID**(OCR로
  한국어 소형 글꼴 이름을 신뢰성 있게 읽을 수 없음이 실증되어 채택), 레벨은
  숫자 글리프 템플릿, 병력·일시는 Windows 내장 OCR(winocr)을 사용합니다.
- **저장**: SQLite 원장(`output/deckscan.db`). `battle_key = sha1(일시 |
  공격자 | 수비자 | 장수 구성)` — **결정적 요소만** 사용해 재실행·재순회에도
  중복이 생기지 않습니다(멱등 upsert. 병력·레벨은 OCR 판독이라 키에서 제외하고
  값으로만 저장). **양측 3장수 완전 덱 전보만 저장**합니다(한쪽이라도 1~2장수면
  스킵 — NPC전·결원 덱 제외).
- **라벨 운영**: 처음 등장한 유저·장수는 `pending` ID로 저장되고, `label`
  명령으로 사람이 이름을 확정하면 이후·기존 레코드 조회에 반영됩니다.
- **안전장치**: 순회 중 목록 화면 이탈(열람 행 클릭 → 전투 상세 전환 등)을
  마커로 감지해 귀환으로 복구, 전환·확대 등 일과성 렌더는 이중 프레임 확증과
  무효 렌더 게이트로 저장에서 차단, 조작 후 커서는 목록 밖에 파킹합니다.

## 요구 환경

- Windows 11, Python ≥ 3.12
- 삼국지 전략판 PC 클라이언트, 창 모드 **클라이언트 2544×657** (다른 크기는
  실행 거부)
- 게임을 관리자 권한으로 실행 중이면 클릭 입력에 승격 도구가 필요합니다 —
  `tools\agent_shell_admin.bat`를 관리자 권한으로 실행(캡처만은 승격 불필요)

## 설치

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests   # 전체 테스트
```

## 사용법

```text
deckscan scan   [--hwnd N] [--max-items N] [--no-scroll] [--db PATH]
                # 메인 화면에서 실행 → 교전 탭까지 자동 이동 → 전보 순회·추출
                # 종료 코드: 0 정상 / 1 실행 불가(창·권한·해상도) / 2 순회 중단
deckscan probe  [--hwnd N] [--click X Y]   # 창 진단·스냅샷 (캘리브레이션용)
deckscan export [--db PATH] [--out DIR]    # CSV 내보내기 3종
deckscan label  [--db PATH]                # pending 식별자 라벨 확정(대화형)
```

- **클라이언트 창 선택**: `scan`·`probe`는 구동 시 창을 자동 탐지합니다.
  같은 제목의 클라이언트가 여러 개면 후보 목록에서 번호를 고르고, 선택한
  창이 전면에 표시되면 y/n으로 확인합니다. 자동화·스크립트 실행은 `--hwnd`로
  지정하세요(비대화형에서 다중 후보면 목록과 함께 거부).
- `scan` 실행 전 게임은 **메인 화면**(월드맵, 더 보기 메뉴 열림 허용)이어야
  합니다. 스캔 후 화면 복귀는 수동입니다.
- `export`는 `output/export/`에 UTF-8(BOM) CSV 3종을 생성합니다:
  `battles_<날짜>.csv`(전보 1행), `deck_long_<날짜>.csv`(장수 1행 — 피벗
  집계용), `generals_<날짜>.csv`(장수별 최신 전투 기준 레벨).

## 알려진 한계

- **열람(읽음) 처리된 전보는 재수집할 수 없습니다** — 열람 행은 클릭 시
  인라인 펼침 대신 전투 상세 화면으로 전환됩니다(자동 복구 후 건너뜀).
  DB를 유지하는 한 문제없으나, DB를 초기화하면 과거 전보는 유실됩니다.
- 병력 숫자는 실행 환경에 따라 OCR이 흔들릴 수 있습니다(키·중복에는 영향
  없음). 레코드의 `capture_path` 캡처로 사후 검증 가능합니다.
- 같은 초·같은 유저쌍·같은 장수 구성의 동시 다중 전투는 1건으로 합쳐집니다.
- 레벨 글리프 6·7은 미수확(실기 등장 시 partial + 증거 저장 후 등록).

## 프로젝트 구조

```text
src/deckscan/
├── cli.py  controller.py  watchdog.py
├── win/     # 창 탐색·권한·WGC 캡처·PostMessage 입력 (map_search에서 이식)
├── nav/     # ui_telegram.py(좌표·임계 상수 = 유일한 캘리브레이션 지점)
│            # list_walker.py(순회·펼침·복구)  telegram.py(화면 이동)
│            # navigator.py(판정 유틸)
├── vision/  # deck_parser.py(패널→레코드)  identity.py(템플릿 ID)
│            # digits.py(레벨 글리프)  ocr.py(병력·일시·인장)
└── store/   # datastore.py(SQLite 원장)  csv_export.py
assets/templates/   # 템플릿 자산 + 대장(README.md)
img/                # 참고 스크린샷(테스트 픽스처 원본)
docs/work/          # 요구사항·설계·ADR·구현 계획·작업 기록
```

## 문서

요구사항·설계·결정 기록(ADR)·구현 계획·작업 기록은
[docs/work/20260808-telegram-deck-extract/](docs/work/20260808-telegram-deck-extract/)에
있습니다. 시작점: [requirements.md](docs/work/20260808-telegram-deck-extract/requirements.md) →
[design.md](docs/work/20260808-telegram-deck-extract/design.md) →
[plan.md](docs/work/20260808-telegram-deck-extract/plan.md)
