# PLAN-20260809-battle-stats: 교전 통계 구현 계획

> 문서 유형: `plan`
> 작업 ID: `20260809-battle-stats`
> 상태: `completed` (2026-08-09 — TASK-S1~S5 전체, [완료 보고](./work-log.md#완료-보고-completion))
> 기준선: `v1` (2026-08-09 승인)
> 작성일: 2026-08-09
> 최종 갱신: 2026-08-09
> 관련 문서: [REQ v1](./requirements.md), [DESIGN v1](./design.md), [work-log](./work-log.md)

## 요약

- 목적: 기준선 v1(통계 4종 → HTML+CSV, `deckscan stats`)을 작업 단위로 번역.
- 현재 결론 또는 상태: TASK-S1~S5 정의, 착수.
- 다음 행동: TASK-S1부터 TDD 순차 수행.

## 문서 연결

| 방향 | 관계 | 대상 문서 | 대상 항목 | 비고 |
|---|---|---|---|---|
| input | baseline | [REQ-20260809-battle-stats](./requirements.md) | FR-01~06, AC-01~06 | 승인 기준선 v1 |
| input | baseline | [DESIGN-20260809-battle-stats](./design.md) | DES-S1~S4 | 승인 기준선 v1 |
| input | related | [PF-sgz-statiz](../PF-sgz-statiz/portfolio.md) | 작업 목록 | 포트폴리오 작업 2 |

## 기준선

- [요구사항 v1](./requirements.md)·[설계 v1](./design.md) (2026-08-09 승인). 수집 DB 스키마는 deckscan 기준선 v5(읽기 전용 소비).

## 계획 트리

```text
[작업] 20260809-battle-stats — 교전 통계 (기준선 v1) .... completed (2026-08-09)
├─ [✓★] 승인: 기준선 v1 (2026-08-09)
├─ [✓] 구현: TASK-S1 픽스처 DB 헬퍼 + aggregate 판별 계층 [TDD]
├─ [✓] 구현: TASK-S2 aggregate 통계 4종 [TDD]        depends: S1
├─ [✓] 구현: TASK-S3 CSV 4종 [TDD]                   depends: S2
├─ [✓] 구현: TASK-S4 HTML 리포트 [TDD]               depends: S2
├─ [✓] 구현: TASK-S5 CLI `stats`·실 DB 스모크·README depends: S3, S4
└─ [✓] 완료: 자체 리뷰·검증 기록·완료 보고           depends: S5
```

## 작업 목록

### TASK-S1: 픽스처 DB 헬퍼 + 판별 계층 (DES-S1 부분)

- 상태: completed (2026-08-09 — S1~S5 일괄, [work-log](./work-log.md#수행-기록))
- 상위: 없음
- 목표: 테스트용 소형 픽스처 DB 구성 헬퍼(유저 3·장수 6·전투 6 — 승/무/패, 아군=공격/수비, 라벨 확정/미확정), `friendly_alliance`(최빈 동맹+재정의, A-01), `side_result`(관점 정규화, 판별 불능 제외)
- 검증 방법(TDD 선행): 최빈 동맹 추정·재정의, 아군=공격 승→(공격 win, 수비 lose), 아군=수비 승 반전, 무승부, 판별 불능 제외 — AC-03 부분
- 완료 조건: 테스트 성공

### TASK-S2: aggregate 통계 4종 (DES-S1)

- 상태: pending / 의존성: S1
- 목표: `latest_decks`(최신 덱+변경 이력), `pick_rates`, `combo_stats`(조합 frozenset·n 병기), `user_records`
- 검증 방법(TDD): 픽스처 기대값 — AC-01(수치부)·02·03·04
- 완료 조건: 테스트 성공

### TASK-S3: CSV 4종 (DES-S3)

- 상태: pending / 의존성: S2
- 목표: `stats_latest_decks_`·`stats_pick_rates_`·`stats_combos_`·`stats_records_<날짜>.csv` (UTF-8 BOM)
- 검증 방법(TDD): 계약(파일·헤더)·수치가 집계 자료구조와 일치 — AC-05
- 완료 조건: 테스트 성공

### TASK-S4: HTML 리포트 (DES-S2)

- 상태: pending / 의존성: S2
- 목표: 단일 HTML(개요·최신 덱·전적·조합 승률·픽률, 정렬 JS·CSS 막대, 외부 리소스 0), 라벨 표기 규칙(`#ID(제안)`)
- 검증 방법(TDD): 생성물에 절·기대 수치·라벨 표기 존재, 외부 URL 부재 — AC-01·06
- 완료 조건: 테스트 성공

### TASK-S5: CLI 연결 + 스모크 + 문서 (DES-S4)

- 상태: pending / 의존성: S3, S4
- 목표: `deckscan stats [--db] [--out] [--alliance]`(ro 연결, 종료 코드 0/1), 실제 수집 DB 스모크, README 사용법 갱신
- 검증 방법: CLI 계약 테스트(빈 DB 종료 1) + 실 DB 생성 스모크(AC 정본은 단위)
- 완료 조건: 테스트 성공·스모크 산출물 확인

## 검증 계획

- unittest `tests/test_stats*.py`, TDD Red→Green. AC-01~06 전부 오프라인. 실기 스모크는 수치 검증이 아니라 생성 확인.

## 마이그레이션과 롤백

- 없음(신규 모듈, DB 읽기 전용). 롤백 = 파일 삭제.

## 인계

- 다음 단계: 구현 실행(TASK-S1부터), 완료 시 work-log에 verification·completion 병합 기록.
