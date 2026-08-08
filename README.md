# sgz_statiz — 동맹 전보(교전) 덱 정보 추출 도구 `deckscan`

삼국지 전략판 PC 클라이언트의 **동맹전보 → 교전 탭**을 자동으로 순회하며 각
전보의 덱 정보(유저·동맹·장수 6인·레벨·병력·일시·승패)를 화면 캡처와 이미지
인식으로 추출해 SQLite에 저장하고 CSV로 내보내는 로컬 CLI 도구입니다.
게임에 공개 표시되는 정보만 다루며 네트워크 전송은 없습니다.

> **상태: 구현 진행 중** — 오프라인(픽스처 기반) 계층은 완성·검증되었고,
> 실기 자동화 계층(화면 이동·목록 순회·scan 명령)은 구현 중입니다.
> 진행 현황: [docs/work/20260808-telegram-deck-extract/plan.md](docs/work/20260808-telegram-deck-extract/plan.md)

## 동작 방식

- **캡처·입력**: Windows Graphics Capture + PostMessage 클릭 — 창이 가려져도
  동작합니다. 클릭은 상수 모듈의 화이트리스트 좌표로만 전송하고 매 클릭 직전
  현재 화면 마커를 재검증합니다(오클릭 구조적 차단).
- **인식**: 유저명·장수 초상·동맹명은 **템플릿 NCC 매칭 기반 안정 ID**(OCR로
  한국어 소형 글꼴 이름을 신뢰성 있게 읽을 수 없음이 실증되어 채택), 레벨은
  숫자 글리프 템플릿, 병력·일시는 Windows 내장 OCR(winocr)을 사용합니다.
- **저장**: SQLite 원장(`output/deckscan.db`). 전보 내용 해시 `battle_key`로
  재실행·재순회에도 중복이 생기지 않습니다(멱등 upsert).
- **라벨 운영**: 처음 등장한 유저·장수는 `pending` ID로 저장되고, `label`
  명령으로 사람이 이름을 확정하면 이후·기존 레코드 조회에 반영됩니다.

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
deckscan probe  [--hwnd N] [--click X Y]   # 창 진단·스냅샷 (캘리브레이션용)
deckscan export [--db PATH] [--out DIR]    # CSV 내보내기 2종
deckscan label  [--db PATH]                # pending 식별자 라벨 확정
deckscan scan   ...                        # (구현 예정) 전보 순회·추출 실행
```

`export`는 `output/export/`에 UTF-8(BOM) CSV 2종을 생성합니다:
`battles_<날짜>.csv`(전보 1행), `deck_long_<날짜>.csv`(장수 1행 — 피벗 집계용).

## 프로젝트 구조

```text
src/deckscan/
├── cli.py  controller.py  watchdog.py
├── win/     # 창 탐색·권한·WGC 캡처·PostMessage 입력 (map_search에서 이식)
├── nav/     # ui_telegram.py(좌표·임계 상수 = 유일한 캘리브레이션 지점)
│            # list_walker.py(행 재탐지·펼침 앵커)  navigator.py(판정 유틸)
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
