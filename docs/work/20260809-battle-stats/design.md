# DESIGN-20260809-battle-stats: 교전 통계 분석·시각화 SW 설계

> 문서 유형: `design`
> 작업 ID: `20260809-battle-stats`
> 상태: `approved`
> 기준선: `v1` (승인일 2026-08-09)
> 작성일: 2026-08-09
> 최종 갱신: 2026-08-09
> 관련 문서: [REQ: 요구사항](./requirements.md), [deckscan DESIGN v5](../20260808-telegram-deck-extract/design.md)

## 요약

- 목적: [요구사항](./requirements.md)의 통계 4종을 deckscan CLI의 `stats` 서브커맨드로 구현하는 구조·계약을 정의한다.
- 현재 결론 또는 상태: 초안 — 집계 계층(순수 함수) + 렌더 계층(HTML/CSV) 분리, 표준 라이브러리만 사용. 승인 대기.
- 다음 행동: 사용자 승인 → wf-implement 계획 수립.

## 문서 연결

| 방향 | 관계 | 대상 문서 | 대상 항목 | 비고 |
|---|---|---|---|---|
| input | baseline | [REQ-20260809-battle-stats](./requirements.md) | FR-01~06, AC-01~06 | 이 설계가 구체화하는 요구사항 |
| input | related | [deckscan DESIGN v5](../20260808-telegram-deck-extract/design.md) | §데이터와 인터페이스 | 읽기 전용으로 소비하는 스키마 |
| output | handoff | (미생성 — plan.md) | — | 승인 후 wf-implement가 작성 |

## 설계 목표와 제약

- 수집 DB를 **읽기 전용**으로 소비(NFR-01) — `mode=ro` URI로 연다.
- 외부 의존성 추가 없음: HTML은 문자열 템플릿, 표 정렬은 인라인 최소 JS, 막대는 CSS로 표현.
- 집계는 순수 함수로 분리해 픽스처 DB 단위 테스트가 가능해야 한다(AC 전부 오프라인 검증).

## 시스템 경계와 구조

```text
deckscan stats (DES-S4 CLI)
└─ stats/aggregate.py (DES-S1)   DB(ro) → 집계 자료구조 (통계 4종 + 메타)
   ├─ stats/report.py  (DES-S2)  집계 → 단일 HTML (output/stats/report_<날짜>.html)
   └─ stats/csv_out.py (DES-S3)  집계 → CSV 4종  (output/stats/stats_*_<날짜>.csv)
```

## 컴포넌트와 책임

- DES-S1 **aggregate**: 통계 계산의 유일한 원천.
  - `friendly_alliance(conn, override)` — 아군 동맹 판별(A-01): `--alliance` 지정 시 그 값(라벨 또는 ID), 미지정 시 battles의 공격·수비 동맹 중 최빈 동맹. 판별 결과·근거(등장 횟수)를 메타로 반환.
  - `side_result(battle, friendly)` — 관점 정규화(FR-03): 아군 동맹이 속한 측을 판별해 `result`(아군 관점)를 공격 측 결과·수비 측 결과로 변환. 아군 동맹이 어느 측에도 없거나 양측 모두면 해당 전보는 조합 승률·전적에서 제외(제외 건수 집계, NFR-03).
  - `latest_decks()` — 유저별 최신 덱(FR-01): 유저가 등장한 전투를 일시 내림차순으로 보고 최신 전투의 해당 측 3장수 + `general_latest_levels` 레벨. 구성(장수 집합)이 직전과 달라진 시점 목록 = 덱 변경 이력.
  - `pick_rates()` — 장수별 등장 횟수·비율, 전체/공격/수비(FR-02).
  - `combo_stats()` — 조합(장수 3인 frozenset, A-02)별 승/무/패·승률·표본 수 n(FR-03).
  - `user_records()` — 상대 유저별 승·무·패·최근 교전 일시(FR-04). "상대" = 아군 측의 반대편 유저.
- DES-S2 **report**: 집계 자료구조 → 단일 HTML. 절 구성: 개요(데이터 범위·제외 건수·아군 동맹 추정 근거) → 상대 유저별 최신 덱 → 유저별 전적 → 조합 승률 → 장수 픽률. 라벨 표기 규칙(FR-06): 확정 라벨 그대로, 미확정은 `#<ID>(<제안값>)`. 표 헤더 클릭 정렬(인라인 JS ~20줄), 비율은 CSS 막대 병기. 외부 리소스 0.
- DES-S3 **csv_out**: 집계 → `stats_latest_decks_`·`stats_pick_rates_`·`stats_combos_`·`stats_records_<날짜>.csv` (UTF-8 BOM). 수치는 DES-S1 자료구조를 그대로 직렬화(AC-05 — HTML과 동일 원천).
- DES-S4 **CLI**: `deckscan stats [--db PATH] [--out DIR] [--alliance NAME]`. 창·게임 무관(오프라인 명령) — 창 확정 경로를 타지 않는다. 종료 코드 0 정상 / 1 실행 불가(DB 없음·비어 있음).

## 데이터와 인터페이스

- 입력: deckscan DB v5 스키마(읽기 전용). failed 레코드·일시 없는 레코드는 시계열·승률 통계 제외 + 제외 건수 보고(NFR-03).
- 출력 계약: `output/stats/report_<YYYYMMDD>.html`, `stats_*_<YYYYMMDD>.csv` 4종. 같은 날짜 재실행은 덮어쓴다(NFR-02 재현성).
- 조합 키: 장수 ID 3개의 정렬 튜플(A-02). 승률 = 승 / (승+무+패), n 병기(RISK-02).

## 동작 (정상·실패 흐름)

| 상황 | 감지 | 대응 |
|---|---|---|
| DB 없음·battles 0건 | 초기화 검사 | 안내 후 종료 코드 1 |
| 아군 동맹 판별 불능(동맹 데이터 없음) | friendly_alliance | 조합 승률·전적 절을 "판별 불가" 표기로 생략, 나머지 통계는 생성 |
| 특정 전보의 측면 판별 불능 | side_result | 해당 전보만 승률·전적에서 제외, 제외 건수 보고 |

## 검증 전략

| 대상 | 방법 |
|---|---|
| AC-01~06 전부 | 픽스처 DB(코드로 구성한 소형 표본 — 유저 3·장수 6·전투 6, 승/무/패·라벨 확정/미확정 포함) 단위 테스트, TDD 선행 |
| HTML 계약 | 생성물에 절 앵커·기대 수치 문자열 존재 검사(렌더링 픽셀 검증은 하지 않음 — 사유: 브라우저 의존) |
| 실기 | 실제 수집 DB로 1회 생성 스모크(수치는 단위 테스트가 정본) |

## 위험

- [REQ RISK-01·02](./requirements.md#위험) — 설계 대응: 추정 근거 표기(개요 절)·`--alliance` 재정의, n 병기.

## 추적성

| 요구사항 | 설계 | 인수 조건 |
|---|---|---|
| FR-01 | DES-S1 latest_decks | AC-01 |
| FR-02 | DES-S1 pick_rates | AC-02 |
| FR-03 | DES-S1 side_result·combo_stats, A-01·02 | AC-03 |
| FR-04 | DES-S1 user_records | AC-04 |
| FR-05 | DES-S2·S3·S4 | AC-01, AC-05 |
| FR-06 | DES-S2 라벨 표기 규칙 | AC-06 |
| NFR-01~03 | ro 연결·재현 계약·제외 보고 | (검증 전략) |

## 승인 기록

- 승인 대상: 본 설계 v1, [요구사항 v1](./requirements.md)
- 결과: **승인** / 결정자: 사용자 / 결정 일시: 2026-08-09
- 근거: 대화형 승인 응답("승인")
- 효력: 기준선 v1 발행, 구현 시작 기준 성립

## 변경 이력

| 날짜 | 변경 | 근거 | 상태 또는 기준선 | 작성자·승인자 |
|---|---|---|---|---|
| 2026-08-09 | 최초 초안 | 요구사항 초안, deckscan v5 스키마 조사 | draft → awaiting-approval | Claude(wf-design) |
| 2026-08-09 | 기준선 v1 발행 | 사용자 승인 응답 | awaiting-approval → approved, v1 | 사용자 승인 / Claude 기록 |

## 인계

- 다음 단계 또는 워크플로우: 사용자 승인 → [wf-implement](file:///C:/Users/hippo/.claude/skills/wf-implement/SKILL.md) 계획 수립
- 시작 조건: 본 설계·요구사항 v1 승인
- 차단 요인: 없음
