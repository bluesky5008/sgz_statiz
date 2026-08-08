# DESIGN-20260808-telegram-deck-extract: 동맹 전보(교전) 덱 정보 추출 SW 설계

> 문서 유형: `design`
> 작업 ID: `20260808-telegram-deck-extract`
> 상태: `approved`
> 기준선: `v2` (승인일 2026-08-09 — [DCR-001](./changes/DCR-001-list-traversal.md))
> 작성일: 2026-08-08
> 최종 갱신: 2026-08-09
> 관련 문서: [REQ-20260808-telegram-deck-extract: 요구사항](./requirements.md), [ADR-001: 저장 형식](./decisions/ADR-001-storage-format.md), [ADR-002: 인식 전략](./decisions/ADR-002-recognition-strategy.md)

## 요약

- 목적: [요구사항](./requirements.md)을 만족하는 자동 추출 도구의 구조·계약·동작을 정의한다.
- 현재 결론 또는 상태: 기준선 v1 승인 완료(2026-08-08, 사용자). map_search 플랫폼 계층 재사용 + 화면별 신규 모듈(내비게이션 상수, 목록 순회, 덱 파서, 식별 매처)로 구성. 저장은 SQLite+CSV([ADR-001](./decisions/ADR-001-storage-format.md)), 인식은 템플릿 ID+OCR 보조([ADR-002](./decisions/ADR-002-recognition-strategy.md)).
- 다음 행동: wf-implement 계획 수립.

## 문서 연결

| 방향 | 관계 | 대상 문서 | 대상 항목 | 비고 |
|---|---|---|---|---|
| input | baseline | [REQ-20260808-telegram-deck-extract: 요구사항](./requirements.md) | document | 이 설계가 구체화하는 요구사항 |
| input | decision | [ADR-001: 저장 형식](./decisions/ADR-001-storage-format.md) | ADR-001 | 데이터 설계의 근거 |
| input | decision | [ADR-002: 인식 전략](./decisions/ADR-002-recognition-strategy.md) | ADR-002 | 인식 컴포넌트 설계의 근거 |
| input | related | [map_search 저장소](file:///C:/src/git/map_search) | document | 재사용 원천. 외부 저장소라 역방향 링크 불가(단방향 사유) |
| output | handoff | [PLAN-20260808-telegram-deck-extract: 구현 계획](./plan.md) | TASK-01~13 | 이 설계를 번역한 구현 계획 |

## 설계 목표와 제약

- 목표: 수동 개입 없는 1회 실행으로 교전 전보를 순회·추출·저장하고, 실패를 증거와 함께 표면화한다.
- 제약:
  - 클라이언트 창 크기는 map_search 캘리브레이션과 동일한 클라이언트 2544×657을 전제한다(참고 이미지 창 2546×689 = 클라이언트 2544×657 + 테두리·제목 표시줄, 일치 확인됨). 불일치 시 실행을 거부한다.
  - 게임 화면을 바꾸는 클릭은 상수 모듈에 정의된 좌표 화이트리스트로 한정한다.
  - 백그라운드(가려진 창) 동작을 위해 map_search와 동일하게 PostMessage 입력 + Windows Graphics Capture를 사용한다.

## 시스템 경계와 구조

시스템은 로컬 PC에서 실행되는 단일 CLI 프로세스다. 외부 연동은 (1) 게임 클라이언트 창(캡처·입력), (2) 로컬 SQLite 파일, (3) 템플릿 자산 디렉터리뿐이다. 네트워크 통신은 없다.

```text
CLI(scan|export|label|probe)
  └─ Controller ──────────────── runs 요약, 예외 경계
       ├─ 플랫폼 계층(DES-01)     창 탐색·권한·캡처·입력·워치독  ← map_search 복사
       ├─ TelegramNavigator(DES-03)  화면 이동·판정  ← 로직 이식 + ui_telegram 상수(DES-02)
       ├─ ListWalker(DES-04)         행 탐지·펼치기·스크롤
       ├─ DeckParser(DES-05)         패널 크롭 → BattleRecord
       │    ├─ IdentityMatcher(DES-06)   유저·장수·(동맹) 템플릿 ID
       │    ├─ DigitGlyphReader(DES-07)  레벨 숫자
       │    └─ OcrReader(DES-08)         병력·일시·라벨 제안
       └─ DataStore + CsvExport(DES-09)  SQLite 저장·내보내기
```

프로젝트 구조(신규 저장소, 패키지명 `deckscan`):

```text
동맹전보_통계정리/
├── pyproject.toml            # Python ≥3.12, pillow numpy opencv-python windows-capture winocr
├── src/deckscan/
│   ├── cli.py  controller.py  watchdog.py
│   ├── win/    # win32.py capture.py input.py session.py  ← map_search 무수정 복사(출처 주석)
│   ├── nav/    # navigator.py(판정 유틸 이식)  ui_telegram.py(신규 좌표 상수)
│   ├── vision/ # deck_parser.py  identity.py  digits.py(이식)  ocr.py
│   └── store/  # datastore.py(스키마 교체)  csv_export.py(이식)
├── assets/templates/         # ui/ digits_gold/ users/ portraits/ alliances/ + README.md(자산 대장)
├── img/                      # 참고 이미지(기존)
├── output/                   # deckscan.db, evidence/, export/  (커밋 제외)
└── docs/work/20260808-telegram-deck-extract/
```

## 컴포넌트와 책임

- DES-01 **플랫폼 계층**: [map_search win/](file:///C:/src/git/map_search/src/mapscan/win) 4개 모듈과 watchdog을 무수정 복사. 창 탐색(`삼국지-전략판`), UIPI 권한 검사, WGC 캡처(`grab_fresh`, `CaptureStalled`), PostMessage 클릭·휠, 검은 화면·크기 변경 감지. 각 파일 머리에 원본 경로·복사일 주석을 남긴다.
- DES-02 **ui_telegram 좌표 상수 모듈**: 이 작업의 유일한 캘리브레이션 지점. 클릭 좌표(더 보기, 메뉴의 동맹, 동맹 화면의 전보, 교전 탭), 화면 판정 마커 사각형(동맹 화면 제목, 동맹전보 제목, 교전 탭 활성), 목록 영역, 펼친 패널 내 상대 크롭(카드 6칸의 초상·이름 바·병력 행, 유저명 스트립, 일시·결과 영역)을 상수로 정의한다. 값은 구현 초기에 참고 이미지와 실기 스냅샷으로 실측한다(TASK로 인계).
- DES-03 **TelegramNavigator**: 화면 전환의 실행과 판정. map_search에서 `wait_stable`(프레임 안정화), 마커 NCC 점수, `_click_verified`(클릭 직전 현재 화면 재검증), `_wait_marker`(등장·소멸 폴링), `_same_image`, 프레임↔클라이언트 좌표 변환을 이식한다. 단계: 메인 화면 확인 → 더 보기 → 동맹 → 전보 → 교전 탭. 각 단계는 목표 마커 등장으로 성공을 판정하고 타임아웃 시 `NavigationTimeout`을 던진다.
- DES-04 **ListWalker** (v2, [DCR-001](./changes/DCR-001-list-traversal.md)): 전보 목록 순회. 매 반복마다 현재 프레임에서 행 헤더 y좌표들을 템플릿 매칭으로 재탐지한다(펼침으로 행 위치가 밀려도 추적 가능). 전보가 아닌 행(격전 보상 배너)은 행 헤더 패턴 불일치로 자연 배제된다. **행별 펼침 상태를 판정**(행 앵커 근방의 '아군' 세로 라벨)해 이미 펼쳐진 행은 클릭 없이 바로 파싱하고, 접힌 행(묶음 등)만 클릭해 펼친다(A-02 v2). 행 클릭은 헤더 중앙의 위치 링크·유저명·동맹명을 피한 **안전 x 지대**로 한정한다(오클릭 시 월드맵 이동 — 실기 사고 실증). 화면 내 행 소진 시 목록 영역에서 `wheel` 스크롤 후 `_same_image`로 종착(더 이상 스크롤 안 됨)을 판정한다. 처리 여부는 저장 계층의 `battle_key` 멱등에 위임하므로 스크롤 중복은 무해하다.
- DES-05 **DeckParser** (v2, [DCR-001](./changes/DCR-001-list-traversal.md)): 펼친 패널 이미지를 받아 `BattleRecord`(유저 2, 동맹 2, 일시, 결과, 슬롯 6 × (장수 ID, 레벨, 병력))를 생성. **패널 좌우 세로 라벨('공격'/'수비')을 템플릿 판정해 좌측 3칸의 공격·수비 역할을 결정한다**(아군=수비 전보는 좌우 역할 반전 — 실기 실증. BattleRecord의 attacker/defender 의미는 불변). 필드별 실패를 모아 `ok | partial | failed`를 판정하고, 실패 필드 크롭을 증거로 저장한다.
- DES-06 **IdentityMatcher**: [ADR-002](./decisions/ADR-002-recognition-strategy.md)의 식별기. 네임스페이스(users/portraits/alliances)별 템플릿 라이브러리에 NCC 매칭, 임계 이상 최고점 채택. 미등록이면 신규 ID 발행 + 크롭을 템플릿으로 저장 + OCR 제안 라벨과 함께 `pending` 등록. 동일 라벨에 복수 템플릿 허용(초상 변형 흡수).
- DES-07 **DigitGlyphReader**: [map_search DigitReader](file:///C:/src/git/map_search/src/mapscan/vision/digits.py) 이식. 이름 바 좌측 레벨 숫자(금색 폰트 0~9) 판독. 글리프는 구현 단계에서 수확 도구로 등록한다.
- DES-08 **OcrReader**: winocr(Windows.Media.Ocr, ko) 어댑터. 병력 수, 전투 일시, 승·무·패 결과 판독과 신규 등록용 라벨 제안. P-01에서 숫자·날짜 정확성 실증. 엔진 교체는 이 어댑터 구현 교체로 한정한다. 결과 판독은 `승/무/패` 인장 영역의 템플릿 매칭을 우선 후보로 하되(3종 폐쇄 집합), 어느 쪽이든 이 컴포넌트가 캡슐화한다.
- DES-09 **DataStore + CsvExport**: 아래 데이터 설계 참조. [map_search datastore.py](file:///C:/src/git/map_search/src/mapscan/store/datastore.py) 골격(WAL, 멱등 upsert, run 기록)과 [csv_export.py](file:///C:/src/git/map_search/src/mapscan/store/csv_export.py)(UTF-8 BOM) 이식.
- DES-10 **Controller/CLI**: `scan`(추출 실행), `export`(CSV), `label`(pending 라벨 등록 대화), `probe`(창 탐색·스냅샷·마커 점수 진단). 실행 요약(FR-06)과 예외 경계(아래 실패 흐름) 담당.

## 데이터와 인터페이스

### SQLite 스키마 (원본 저장소, [ADR-001](./decisions/ADR-001-storage-format.md))

```sql
meta(key TEXT PRIMARY KEY, value TEXT);                -- schema_version 등

runs(run_id INTEGER PRIMARY KEY AUTOINCREMENT,
     started_at TEXT, finished_at TEXT,
     status TEXT DEFAULT 'running',                    -- running|done|aborted
     processed INTEGER, saved INTEGER, failed INTEGER);

identities(identity_id INTEGER PRIMARY KEY AUTOINCREMENT,
     namespace TEXT,                                   -- user|general|alliance
     label TEXT,                                       -- 확정 라벨(미확정 시 OCR 제안)
     label_status TEXT DEFAULT 'pending',              -- pending|confirmed
     first_seen TEXT);
identity_templates(identity_id INTEGER REFERENCES identities,
     template_path TEXT,                               -- assets/templates/<ns>/... 상대 경로
     PRIMARY KEY (identity_id, template_path));

battles(battle_key TEXT PRIMARY KEY,                   -- 정규화 내용 sha1 (아래)
     run_id INTEGER, battle_time TEXT, result TEXT,    -- 승|무|패 (아군 기준)
     attacker_id INTEGER, defender_id INTEGER,         -- identities(user)
     attacker_alliance_id INTEGER, defender_alliance_id INTEGER,
     capture_path TEXT, parse_status TEXT,             -- ok|partial|failed
     captured_at TEXT);

deck_slots(battle_key TEXT REFERENCES battles,
     side TEXT CHECK(side IN ('attack','defend')),
     slot INTEGER CHECK(slot BETWEEN 1 AND 3),
     general_id INTEGER,                               -- identities(general), 미인식 NULL
     level INTEGER, troops INTEGER,
     match_score REAL, crop_path TEXT,
     PRIMARY KEY (battle_key, side, slot));
```

- `battle_key = sha1(battle_time | attacker_id | defender_id | 정렬된 슬롯 튜플)`. 식별 ID가 영속 레지스트리에서 오므로 재실행에도 같은 키가 재현되어 `INSERT OR REPLACE`로 멱등이다(FR-05, AC-03). 일시·유저·덱이 완전히 동일한 두 전보는 1건으로 합쳐진다(알려진 한계, 위험 참조).
- 파싱 실패로 키 재료가 비면 패널 크롭의 픽셀 해시로 대체 키를 만들어 `failed` 레코드도 멱등 저장한다.

### CSV 내보내기 계약

`export` 명령이 `output/export/`에 UTF-8 BOM CSV 2종을 생성한다: `battles_<날짜>.csv`(전보 1행), `deck_long_<날짜>.csv`(장수 1행 — battle_key, 일시, 결과, 공격·수비 유저 라벨, side, slot, 장수 라벨, 레벨, 병력; 피벗 집계용 long 형식).

### CLI 계약

```text
deckscan scan  [--hwnd N] [--max-items N] [--no-scroll] [--db PATH]
deckscan export [--db PATH] [--out DIR]
deckscan label  [--db PATH]          # pending 순회: 크롭 표시 → 라벨 입력 → confirmed
deckscan probe  [--hwnd N]           # 창 나열, 스냅샷 저장, 마커 점수 출력
```

`scan` 종료 코드: 0 정상(부분 실패 포함, 요약에 표시) / 1 실행 불가(창·권한·해상도) / 2 내비게이션 실패 중단.

### 템플릿 자산 대장

`assets/templates/README.md`에 파일 ↔ 의미 ↔ 원본(캡처 경로·크롭 사각형) ↔ 등록일을 표로 유지한다(map_search 규약). `users/·portraits/·alliances/` 하위는 `label` 명령이 자동 추가한다.

## 정상·실패·복구 흐름

### 정상 흐름

1. 초기화: 창 탐색(제목 또는 `--hwnd`) → UIPI 권한 검사 → WGC 캡처 시작 → 클라이언트 크기 = 2544×657 검증 → run 생성.
2. 내비게이션(FR-01): 메인 화면 마커 확인 → `더 보기` 클릭 → 메뉴 마커 대기 → `동맹` 클릭 → 동맹 화면 마커 → `전보` 클릭 → 동맹전보 마커 → `교전` 탭 클릭 → 탭 활성 마커. 각 클릭은 직전 화면 재검증(`_click_verified` 패턴) 후 전송.
3. 순회(FR-02, FR-03): ListWalker 루프 — 행 재탐지 → 클릭 → 펼침 마커 + `wait_stable` → `grab_fresh` → DeckParser → `INSERT OR REPLACE` → 다음 행. 소진 시 스크롤, `_same_image`로 종착 판정.
4. 종료(FR-06): run 마감(processed/saved/failed), 콘솔 요약. pending 신규 식별 수를 함께 보고하고 `label` 실행을 안내한다. 게임 화면 복귀는 하지 않는다(범위 밖).

### 실패와 복구

| 상황 | 감지 | 대응 |
|---|---|---|
| 창 없음·다중 창·권한 부족·해상도 불일치 | 초기화 검사 | 안내 후 종료 코드 1 (아무 조작 없음) |
| 화면 전환 타임아웃 | 마커 미등장·`StabilizeTimeout` | 현재 프레임 증거 저장, run `aborted`, 종료 코드 2. 저장된 레코드는 유지 |
| 클릭 무반응(행 펼침 실패) | 펼침 마커 미등장 | 1회 재시도 후 해당 행 건너뜀 + 증거 저장 (NFR-01) |
| 필드 인식 실패 | 매칭 임계 미달·판독 실패 | `partial/failed` 저장 + 필드 크롭 증거, 계속 진행 (NFR-01) |
| 캡처 정지·검은 화면·창 크기 변경 | `CaptureStalled`·Watchdog | run `aborted`, 즉시 중단 (죽은 화면 오判 방지) |
| 실행 중 새 전보 도착으로 목록 밀림 | — (직접 감지 없음) | `battle_key` 멱등으로 중복 무해. 누락 가능성은 재실행으로 보완 |

## 보안과 품질 속성

- **조작 안전**: 클릭은 ui_telegram 상수의 화이트리스트 좌표로만 전송하고, 매 클릭 직전 현재 화면 마커를 재검증한다. 잘못된 화면에서의 비가역 버튼(행군·점령 등) 오클릭을 구조적으로 차단한다(map_search 실기 사고 대응 이식).
- **개인정보**: 취급 데이터는 게임 화면에 공개된 정보(닉네임·덱)뿐이며 로컬 파일에만 저장, 네트워크 전송 없음.
- **성능**: 전보당 목표 2~4초(펼침 안정화 대기가 지배). 100건 ≈ 5~7분. 구속 조건 아님.
- **관측성**: 콘솔 로그(단계·행 단위), `output/evidence/` 실패 크롭, runs 테이블 요약.

## 마이그레이션과 롤백

- 신규 프로젝트로 기존 데이터 없음. `meta.schema_version`으로 향후 스키마 변경에 대비한다.
- 롤백: DB 파일·output 삭제로 초기 상태 복원. 게임 측 상태는 전보 열람(읽음 표시) 외에 변경되지 않으며 이는 되돌리지 않는다(수용).

## 검증 전략

| 대상 | 방법 |
|---|---|
| AC-02 (파싱 정확성) | [img/4~6.png](../../../img/4.png) 및 실기 캡처 픽스처 기반 단위 테스트. DeckParser가 기대 레코드를 산출하는지 TDD로 작성(테스트 방법 상세는 wf-implement 소유) |
| AC-01 (내비게이션) | 실기 검증 — 메인 화면에서 `scan` 실행, 로그·스냅샷 증거 |
| AC-03 (멱등) | 실기 연속 2회 실행 후 `SELECT count(*)` 비교 + battle_key 단위 테스트 |
| AC-04 (부분 실패 계속) | 훼손 크롭 주입 단위 테스트 + 실기 요약 확인 |
| AC-05 (조회 구조) | 저장 후 집계 SQL 예시 실행 테스트 |
| AC-06 (pending 등록) | 미등록 식별 → pending 저장 → `label` 확정 → 재조회 반영 단위 테스트 |

### 설계 단계 프로토타입

- **P-01 (완료)**: OCR 정확성 검증 → 가설 기각, 결과는 [ADR-002](./decisions/ADR-002-recognition-strategy.md#프로토타입-p-01-결과-증거)에 기록. 스파이크 코드는 폐기.
- **P-02 (구현 초기 TASK로 인계)**: ui_telegram 좌표 실측 — map_search의 snap/ui_survey 도구 이식으로 실기 화면에서 상수 확정. 참고 이미지와 실기 배치 일치가 가정(A-06)이며 불일치 시 상수만 재측정.
- **P-03 (구현 초기 TASK로 인계)**: 아코디언 펼침 상태에서 행 재탐지 순회의 안정성 실기 확인. 실패 시 순회 전략 변경은 DCR로 처리.

## 대안과 결정

- 저장 형식: [ADR-001](./decisions/ADR-001-storage-format.md) — SQLite + CSV 내보내기.
- 인식 전략: [ADR-002](./decisions/ADR-002-recognition-strategy.md) — 템플릿 ID + OCR 보조.
- **코드 재사용 방식(설계 수준 결정)**: map_search를 패키지 의존으로 참조하는 대안 대신 **파일 복사 + 출처 주석**을 채택한다. 이유: map_search는 배포 패키지가 아니고 화면별 커스터마이즈가 필요하며, 두 저장소의 독립 진화가 자연스럽다. 단점(상류 버그 수정 미전파)은 파일 머리 출처 주석으로 추적 가능하게 한다.
- **기술 스택**: map_search와 동일(Python ≥3.12, pillow/numpy/opencv-python/windows-capture) + winocr. 별도 venv. 새 ADR 없이 [map_search ADR-001](file:///C:/src/git/map_search/docs/work/20260801-worldmap-land-scan/decisions/ADR-001-tech-stack.md)을 승계한다.

## 가정과 미해결 질문

- 가정 A-06: 참고 이미지의 UI 배치가 실기 화면과 일치한다(같은 클라이언트·창 크기에서 캡처됨). P-02에서 실측으로 확인한다.
- 가정 A-07: 펼침 패널의 내부 배치(카드 6칸 위치)는 패널 top 기준 상대 좌표로 고정이다(참고 이미지 3장에서 일관 확인).
- 미해결 질문 없음 — [요구사항 Q-01~Q-03](./requirements.md#가정과-미해결-질문)은 2026-08-08 승인 관문에서 결정됨(스크롤 포함 전체·모두 저장·수동 1회 실행). 본 설계 초안의 전제와 동일하다.

## 위험

- RISK-04: NCC 임계 설정 부적절 시 오매칭(다른 유저를 같은 ID로) 또는 과잉 pending. 완화: 임계 실측 캘리브레이션, match_score 저장으로 사후 감사 가능, 증거 크롭 보관.
- RISK-05: 동일 (일시·유저·덱) 전보가 1건으로 합쳐짐. 완화: 알려진 한계로 문서화. 필요 시 목록 위치를 키에 추가하는 DCR.
- RISK-06: `[N회 승/무]` 묶음 행이 1개 덱만 노출 → 묶음 내 개별 전보는 취득 불가(가정 A-04). 사용자 승인 관문에서 명시 확인.
- 요구사항의 [RISK-01~03](./requirements.md#위험)은 ADR-002(01), battle_key 멱등(02), 초기화 해상도 검증(03)으로 대응한다.

## 추적성

| 요구사항 | 설계 | 인수 조건 | 검증(계획) |
|---|---|---|---|
| [FR-01](./requirements.md#기능-요구사항) | DES-02, DES-03 | [AC-01](./requirements.md#인수-조건) | 실기 |
| [FR-02](./requirements.md#기능-요구사항) | DES-04 | [AC-01, AC-03](./requirements.md#인수-조건) | 실기·단위 |
| [FR-03](./requirements.md#기능-요구사항) | DES-05~08 | [AC-02](./requirements.md#인수-조건) | 픽스처 단위 |
| [FR-04](./requirements.md#기능-요구사항) | DES-09, [ADR-001](./decisions/ADR-001-storage-format.md) | [AC-03, AC-05](./requirements.md#인수-조건) | 단위·실기 |
| [FR-05](./requirements.md#기능-요구사항) | battle_key 설계 | [AC-03](./requirements.md#인수-조건) | 단위·실기 |
| [FR-06](./requirements.md#기능-요구사항) | DES-10 | [AC-04](./requirements.md#인수-조건) | 실기 |
| [FR-07](./requirements.md#기능-요구사항) | DES-06, DES-10(label) | [AC-06](./requirements.md#인수-조건) | 단위 |
| [NFR-01](./requirements.md#비기능-요구사항) | 실패 흐름 표 | [AC-04](./requirements.md#인수-조건) | 단위·실기 |
| [NFR-02](./requirements.md#비기능-요구사항) | DES-03 (`wait_stable`·마커) | [AC-01](./requirements.md#인수-조건) | 실기 |
| [NFR-03](./requirements.md#비기능-요구사항) | capture_path·crop_path·evidence | [AC-02](./requirements.md#인수-조건) | 단위 |
| [NFR-04](./requirements.md#비기능-요구사항) | 초기화 해상도 검증 | — | 실기 |

## 승인 기록

- 승인 대상: 본 설계 v1, [요구사항 v1](./requirements.md), [ADR-001](./decisions/ADR-001-storage-format.md), [ADR-002](./decisions/ADR-002-recognition-strategy.md)
- 결과: **승인** / 결정자: 사용자 / 결정 일시: 2026-08-08
- 근거: 대화형 승인 응답(상세는 [요구사항 승인 기록](./requirements.md#승인-기록))
- 효력: 기준선 v1 발행, 구현 시작 기준 성립

## 변경 이력

| 날짜 | 변경 | 근거 | 상태 또는 기준선 | 작성자·승인자 |
|---|---|---|---|---|
| 2026-08-08 | 최초 초안 작성 | 요구사항 초안, map_search 조사, P-01 결과 | draft | Claude(wf-design) |
| 2026-08-08 | 자체 검토 후 승인 요청 상태로 전환 | 일관성 검토(§4.5) 통과 | draft → awaiting-approval | Claude(wf-design) |
| 2026-08-08 | 기준선 v1 발행 | 사용자 승인 응답 | awaiting-approval → approved, v1 | 사용자 승인 / Claude 기록 |
| 2026-08-09 | DES-04 순회 전략(펼침 판정·안전 클릭 지대), DES-05 측면 라벨 판정 — 기준선 v2 | [DCR-001](./changes/DCR-001-list-traversal.md) 승인 | approved, v2 | 사용자 승인 / Claude 기록 |

## 인계

- 다음 단계 또는 워크플로우: [wf-implement](file:///C:/Users/hippo/.claude/skills/wf-implement/SKILL.md) (사용자 승인 후)
- 시작 조건: 충족 — 본 설계와 [요구사항](./requirements.md) 기준선 v1 승인 완료, [ADR-001](./decisions/ADR-001-storage-format.md)·[ADR-002](./decisions/ADR-002-recognition-strategy.md) `approved` (2026-08-08)
- 입력 문서와 기준선: 요구사항·설계 v1, ADR 2건
- 완료된 항목: 요구사항·설계·ADR, P-01 프로토타입, 사용자 승인(Q-01~Q-03 결정 포함)
- 미완료 항목: P-02·P-03(구현 초기 TASK), 구현 전체
- 차단 요인: 없음
- 다음 행동: [구현 계획](./plan.md) 수립 완료 — TASK-01부터 구현 실행
