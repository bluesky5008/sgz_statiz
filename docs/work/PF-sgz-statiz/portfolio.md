# PF-sgz-statiz: 동맹전보 교전 통계 정리 포트폴리오

> 문서 유형: `portfolio`
> 문서 ID: `PF-sgz-statiz`
> 상태: `completed` (2026-08-09 — 등재 작업 2건 전체 완료)
> 작성일: 2026-08-09
> 최종 갱신: 2026-08-09
> 관련 문서: [WORK-20260808: deckscan 계획](../20260808-telegram-deck-extract/plan.md)

## 요약

- 목적: sgz_statiz 프로젝트의 작업들을 하나의 목표(동맹전보 교전 통계 정리) 아래 묶어 계획·추적한다.
- 현재 결론 또는 상태: **작업 2건 전체 완료**(2026-08-09) — 작업 1 deckscan(기준선 v5, [완료 보고](../20260808-telegram-deck-extract/work-log.md#완료-보고-completion)), 작업 2 통계 분석·시각화(기준선 v1, [완료 보고](../20260809-battle-stats/work-log.md#완료-보고-completion)).
- 다음 행동: 없음 — 운영(scan·label·stats 주기 실행)으로 전환.

## 문서 연결

| 방향 | 관계 | 대상 문서 | 대상 항목 | 비고 |
|---|---|---|---|---|
| input | baseline | [REQ-20260808-telegram-deck-extract](../20260808-telegram-deck-extract/requirements.md) | 문제와 목적, §범위 제외 | 목표 문구와 후보 작업의 근거 |
| output | refinement | [PLAN-20260808-telegram-deck-extract](../20260808-telegram-deck-extract/plan.md) | document | 작업 1의 상세 계획 |

## 목표와 범위

- **목표**: 삼국지 전략판 동맹전보(교전)의 덱 정보를 자동 수집하고, 수집 데이터로 교전 통계(예: 상대 유저별 덱 구성 파악)를 정리할 수 있게 한다.
- **포함**: ① 수집 도구 deckscan(진행 중), ② 수집 데이터 기반 통계 분석·시각화(후보 — 작업 1의 [요구사항 §범위 제외](../20260808-telegram-deck-extract/requirements.md#범위)에서 "추후 별도 작업"으로 명시된 항목).
- **제외**: 게임 상태를 바꾸는 자동화(전보 열람 외), 클라이언트 자동 실행·로그인, 주기 실행.

## 작업 목록

| 작업 ID | 제목 | 상태 | 의존 |
|---|---|---|---|
| [20260808-telegram-deck-extract](../20260808-telegram-deck-extract/plan.md) | deckscan — 동맹전보 교전 덱 추출 도구 | completed (2026-08-09) | — |
| [20260809-battle-stats](../20260809-battle-stats/requirements.md) | 교전 통계 분석·시각화 | completed (2026-08-09) | depends: 20260808-telegram-deck-extract |

- 후보 작업은 포트폴리오 등재일 뿐 승인된 작업이 아니다. 착수 시 wf-design부터 정식 경로를 따르며 그때 작업 ID를 발행한다.

## 계획 트리

<!-- generated — wf-tree 렌더링 생성물. 수정은 위 작업 목록에서 하고 재생성한다. -->

```text
[포트폴리오] PF-sgz-statiz — 동맹전보 교전 통계 정리 .... completed (2/2 완료, 2026-08-09)
├─ [✓★] 승인: 포트폴리오 범위 ........................... approved 2026-08-09
├─ [✓] 작업: 20260808-telegram-deck-extract deckscan .... completed 2026-08-09 (TASK-01~14, 기준선 v5)
│      └─ 상세: plan.md 계획 트리 참조 (TASK-01~14)
└─ [✓] 작업: 20260809-battle-stats 통계 분석·시각화 ..... completed 2026-08-09 (TASK-S1~S5, 기준선 v1)   depends: deck-extract
```

## 승인 기록

- 승인 대상: 본 포트폴리오의 목표·범위·작업 분해(작업 1 확정 + 작업 2 후보 등재)
- 결과: **승인** — wf-tree 최초 생성 승인 관문 통과
- 결정자: 사용자 / 결정 일시: 2026-08-09
- 근거: 대화형 승인 응답("승인" — 분해안 그대로 확정)

## 인계

- 다음 단계 또는 워크플로우: 작업 1 완료([완료 보고](../20260808-telegram-deck-extract/work-log.md#완료-보고-completion)). 작업 2는 착수 결정 시 wf-design부터
- 차단 요인: 없음

## 변경 이력

| 날짜 | 변경 | 근거 | 상태 또는 기준선 | 작성자·승인자 |
|---|---|---|---|---|
| 2026-08-09 | 최초 생성 (작업 1 등재, 작업 2 후보) | 사용자 생성 요청 | draft → awaiting-approval | Claude(wf-tree) |
| 2026-08-09 | 범위 승인 반영 | 사용자 승인 응답 | awaiting-approval → in-progress | 사용자 승인 / Claude 기록 |
| 2026-08-09 | 작업 1 완료 반영(TASK-01~14, 기준선 v5) | [완료 보고](../20260808-telegram-deck-extract/work-log.md#완료-보고-completion) | in-progress (1/2 완료) | Claude(wf-implement 완료 기록) |
