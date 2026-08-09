# WORK-20260809-battle-stats: 교전 통계 구현 작업 기록

> 문서 유형: `work-log, verification, completion`
> 작업 ID: `20260809-battle-stats`
> 상태: `completed` (2026-08-09)
> 기준선: `v1`
> 작성일: 2026-08-09
> 최종 갱신: 2026-08-09
> 관련 문서: [PLAN](./plan.md), [REQ v1](./requirements.md), [DESIGN v1](./design.md)

## 요약

- 목적: 기준선 v1(통계 4종 → HTML+CSV) 구현 기록.
- 현재 결론 또는 상태: **완료** — TASK-S1~S5 전체, 테스트 13건(전체 스위트 74건) 성공, 실 DB 스모크 성공.
- 다음 행동: 없음(완료 보고 아래).

## 문서 연결

| 방향 | 관계 | 대상 문서 | 대상 항목 | 비고 |
|---|---|---|---|---|
| input | baseline | [PLAN-20260809-battle-stats](./plan.md) | TASK-S1~S5 | 수행 대상 계획 |
| input | baseline | [DESIGN v1](./design.md) | DES-S1~S4 | 구현 기준선 |

## 수행 기록

### 2026-08-09 — TASK-S1~S5 일괄 (TDD)

- TASK-S1·S2: 픽스처 DB 헬퍼(전투 7건 — 승/무/패·아군 공격/수비·일시 없음·아군 불명·라벨 미확정 포함) + `stats/aggregate.py` — 아군 최빈 추정·`--alliance` 재정의(A-01), 관점 정규화(`_side_of`+결과 반전), 최신 덱·변경 이력, 픽률(전체·측면), 조합(frozenset 아닌 정렬 튜플, A-02) 승/무/패·n, 상대별 전적, 미확정 `#ID(제안)` 표기(FR-06), 제외 집계(NFR-03). 선행 테스트 8건 Red(모듈 부재)→Green.
- TASK-S3·S4: `stats/csv_out.py`(4종, UTF-8 BOM — 집계 재계산 없이 직렬화, AC-05) + `stats/report.py`(단일 HTML — 개요·최신 덱·전적·조합·픽률 절, 인라인 CSS·정렬 JS ~15줄·CSS 막대, 외부 리소스 0). 선행 테스트 3건(계약·수치 일치·라벨 확정 반영 AC-06) Red→Green.
- TASK-S5: CLI `stats [--db] [--out] [--alliance]` — 읽기 전용 연결(NFR-01), DB 없음·0건 종료 1. 선행 테스트 2건 + **실 수집 DB 스모크 성공**(report_20260809.html + CSV 4종, pending 라벨 `#ID(제안)` 표기 확인).
- 변경 파일: src/deckscan/stats/(aggregate·csv_out·report·__init__, 신규), src/deckscan/cli.py(stats), tests/test_stats.py·test_stats_output.py(신규 13건), README.md

## 검증 결과 (verification)

전체 스위트 **74건 성공**(2026-08-09). AC는 전부 픽스처 DB 오프라인 검증(설계 검증 전략 그대로).

| ID | 인수 조건 | 방법 | 결과 | 증거 |
|---|---|---|---|---|
| VER-S1 | AC-01 최신 덱 표시 | 단위(latest_decks·HTML 절) | 성공 | tests/test_stats.py·test_stats_output.py |
| VER-S2 | AC-02 픽률 수치 | 단위(전체·측면별 기대값) | 성공 | test_pick_rates |
| VER-S3 | AC-03 관점 정규화 승률 | 단위(아군 공격/수비·무승부·반전) | 성공 | test_combo_stats_perspective_normalized |
| VER-S4 | AC-04 전적 | 단위(승무패·최근 일시) | 성공 | test_user_records |
| VER-S5 | AC-05 CSV=집계 동일 | 단위(combos 행 수치 대조) | 성공 | StatsCsvTest |
| VER-S6 | AC-06 라벨 확정 반영 | 단위(확정 전 `#ID(제안)` → 확정 후 이름) | 성공 | StatsHtmlTest |

실기: 실 수집 DB(5전보)로 생성 스모크 성공(수치 정본은 단위 테스트). 미수행: `--alliance` 오지정 오류 경로의 전용 테스트(코드 경로 단순 — 잔여로 기록).

## 설계와 달라진 점

- 없음(기준선 v1 준수). 구현 세부: 조합 키는 frozenset 대신 정렬 튜플(직렬화 편의 — 의미 동일).

## 완료 보고 (completion)

- **완료 상태: 완료** (2026-08-09, 기준선 v1). TASK-S1~S5 전체.
- 검증: 위 표(AC-01~06 성공, 74건 스위트). 통합: 로컬 커밋(push 대기).
- 남은 위험·후속: ① 소량 데이터 단계의 승률 유의성(n 병기로 표기 — 데이터 축적으로 해소) ② 아군 추정은 리포트에 근거 표기, 오판 시 `--alliance` ③ 라벨 확정(`label`) 운영이 리포트 가독성의 전제 ④ --alliance 오류 경로 전용 테스트 미작성.

## 재개 지점

- 작업 완료 — 재개 없음. 운영: `deckscan stats` 실행 → `output/stats/report_<날짜>.html` 열람.
